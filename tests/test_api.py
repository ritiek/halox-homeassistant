"""Regression self-checks for the Halox Smart cloud client.

Loads the integration's modules standalone (no Home Assistant needed) and runs
them against a throwaway local HTTP server that mimics the vendor API.

Run with:
    nix-shell -p 'python3.withPackages(p: [p.aiohttp p.pytest])' --run 'pytest tests -q'
"""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import aiohttp
from aiohttp import web

HALOX_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "halox"


def _load_module(name: str):
    """Import a halox module without triggering the package __init__ (which
    needs Home Assistant installed)."""
    if "halox_test" not in sys.modules:
        pkg = types.ModuleType("halox_test")
        pkg.__path__ = [str(HALOX_DIR)]
        sys.modules["halox_test"] = pkg
    spec = importlib.util.spec_from_file_location(
        f"halox_test.{name}", HALOX_DIR / f"{name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"halox_test.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


api = _load_module("api")
events = _load_module("events")


async def _serve(requests_seen, make_requests):
    """Point the client at a local fake vendor API and record its requests."""

    async def home_all(request):
        requests_seen.append(("GET", request.path, None, _auth(request)))
        return web.json_response({"data": [{"_id": "H1"}]})

    async def board_all(request):
        requests_seen.append(("POST", request.path, await request.json(), _auth(request)))
        return web.json_response({"data": [{
            "board_id": "B1", "name": "Plug Board", "firmware_version": "4.0.4",
            "devices": [{
                "device_id": "D1", "name": "Plug 1", "state": {"on": True},
                "online": True, "type": "switch",
            }],
        }]})

    async def update_state(request):
        requests_seen.append(("POST", request.path, await request.json(), _auth(request)))
        return web.json_response({"data": {}})

    def _auth(request):
        return request.headers.get("Authorization")

    app = web.Application()
    app.router.add_get("/api/v1/home/all", home_all)
    app.router.add_post("/api/v1/board/all", board_all)
    app.router.add_post("/api/v1/device/update_state", update_state)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    api.API_BASE = f"http://127.0.0.1:{runner.addresses[0][1]}/api/v1"
    async with aiohttp.ClientSession() as session:
        client = api.HaloxApi(session, refresh_token="r")
        client._access_token = "test-token"
        client._expiry = float("inf")
        return await make_requests(client)
    await runner.cleanup()


def test_set_state_posts_flat_payload():
    """Pin the exact control request the integration sends."""
    seen = []
    asyncio.run(_serve(seen, lambda c: c.set_state("D1", False)))
    assert seen == [
        ("POST", "/api/v1/device/update_state", {"device_id": "D1", "on": False},
         "Bearer test-token")
    ]


def test_get_devices_flattens_homes_boards_devices():
    seen = []

    async def run(client):
        return await client.get_devices()

    devices = asyncio.run(_serve(seen, run))
    assert devices == [{
        "device_id": "D1", "name": "Plug 1", "board_id": "B1",
        "board_name": "Plug Board", "is_on": True, "online": True,
        "type": "switch", "home_id": "H1", "firmware": "4.0.4",
    }]
    assert ("POST", "/api/v1/board/all", {"home_id": "H1"}, "Bearer test-token") in seen


def test_parse_events_reads_pushed_state_and_presence():
    """Full event payloads captured from the vendor's live socket."""
    payload = (
        '42["stateUpdate",{"device_id":"A024420B21E20","type":"switch",'
        '"state":{"on":false}}]'
        "\x1e"
        '42["onlineStatusUpdate",{"client_id":"A024420B21E2","online":true}]'
    )
    assert events.parse_events(payload) == [
        ("stateUpdate", {
            "device_id": "A024420B21E20", "type": "switch",
            "state": {"on": False},
        }),
        ("onlineStatusUpdate", {"client_id": "A024420B21E2", "online": True}),
    ]


def test_parse_events_ignores_heartbeat_and_malformed_packets():
    assert events.parse_events('2\x1e40{"sid":"x"}\x1e42[bad') == []


def test_token_user_id_reads_firebase_uid():
    """The socket header wants the Firebase UID from the ID token's payload."""
    import base64
    import json

    def b64(obj):
        raw = json.dumps(obj).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    token = f"{b64({'alg': 'none'})}.{b64({'user_id': 'uid-123', 'exp': 1234567890})}.sig"
    assert events.token_user_id(token) == "uid-123"
    assert events.token_expiry(token) == 1234567890
