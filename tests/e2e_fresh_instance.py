"""Fresh-instance smoke test: drive a brand-new Home Assistant exactly like a
user — onboarding, the Halox config flow, then check that switches appear.

Usage (against an empty HA instance, e.g. in a container):

    docker run -d --name ha-e2e \
        -v /path/to/empty-config:/config -p 127.0.0.1:8123:8123 \
        homeassistant/home-assistant:2026.10.1
    # copy the integration into the config dir first:
    #   /config/custom_components/halox  (from this repo)

    HALOX_EMAIL=you@example.com HALOX_PASSWORD=secret \
    HA_URL=http://127.0.0.1:8123 python3 tests/e2e_fresh_instance.py

The HA onboarding user it creates is tester@example.com / test-pass-123.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("HA_URL", "http://127.0.0.1:8123")
EMAIL = os.environ.get("HALOX_EMAIL")
PASSWORD = os.environ.get("HALOX_PASSWORD")
CLIENT_ID = "http://localhost/"


def req(method, path, token=None, payload=None):
    r = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"}, method=method)
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read())


def form(path, payload):
    body = urllib.parse.urlencode(payload).encode()
    r = urllib.request.Request(BASE + path, data=body, method="POST",
                               headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read())


def wait_ha():
    for _ in range(120):
        try:
            req("GET", "/api/")
            return True
        except urllib.error.HTTPError as e:
            if e.code in (401, 404):
                return True  # up; auth required
            raise
        except Exception:
            time.sleep(3)
    return False


def main():
    if not EMAIL or not PASSWORD:
        sys.exit("HALOX_EMAIL / HALOX_PASSWORD must be set")
    assert wait_ha(), "HA did not come up"

    steps = {s["step"]: s["done"] for s in req("GET", "/api/onboarding")}
    if not steps.get("user"):
        req("POST", "/api/onboarding/users", payload={
            "client_id": CLIENT_ID, "language": "en", "name": "Tester",
            "username": "tester@example.com", "password": "test-pass-123"})

    flow = req("POST", "/auth/login_flow", payload={
        "client_id": CLIENT_ID, "handler": ["homeassistant", None],
        "redirect_uri": CLIENT_ID})
    step = req("POST", f"/auth/login_flow/{flow['flow_id']}", payload={
        "username": "tester@example.com", "password": "test-pass-123",
        "client_id": CLIENT_ID})
    token = form("/auth/token", {
        "grant_type": "authorization_code",
        "code": step.get("result") or step["code"], "client_id": CLIENT_ID,
    })["access_token"]

    init = req("POST", "/api/config/config_entries/flow", token=token,
               payload={"handler": "halox"})
    flow = req("POST", f"/api/config/config_entries/flow/{init['flow_id']}",
               token=token, payload={"email": EMAIL, "password": PASSWORD})
    if flow.get("type") != "create_entry":
        print(json.dumps(flow, indent=2)[:2000])
        sys.exit(1)
    print("entry created:", flow["result"]["title"],
          "state:", flow["result"]["state"])

    for _ in range(60):
        states = req("GET", "/api/states", token)
        switches = [s for s in states if s["entity_id"].startswith("switch.")]
        if switches:
            for s in switches:
                print("SWITCH:", s["entity_id"], "=", s["state"])
            print("E2E-OK")
            return
        time.sleep(3)
    sys.exit("no switch entities appeared")


main()
