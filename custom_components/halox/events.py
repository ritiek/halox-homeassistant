"""Live state feed for Halox Smart.

The vendor app holds a Socket.IO long-poll connection to the same AWS backend
that serves the REST API. Auth travels in plain headers: the Firebase ID token,
the user's Firebase UID, the home id and a client device id. The server pushes
`stateUpdate` (device on/off) and `onlineStatusUpdate` (board reachability)
events on that connection.

The app's own socket host is dead (it points at an EC2 box that now answers
404), which is why its UI only refreshes on a cold start. We connect to the
working Socket.IO endpoint on the API host instead and keep REST polling as a
slow fallback.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress

from aiohttp import ClientSession, ClientTimeout

from .const import SOCKET_URL

_LOGGER = logging.getLogger(__name__)

_RECONNECT_MIN = 5
_RECONNECT_MAX = 300
_POLL_TIMEOUT = ClientTimeout(total=45, connect=10, sock_read=40)


def parse_events(payload: str) -> list[tuple[str, dict]]:
    """Return (event, data) pairs from an Engine.IO polling payload."""
    events: list[tuple[str, dict]] = []
    for packet in payload.split("\x1e"):
        if not packet.startswith("42"):
            continue
        try:
            message = json.loads(packet[2:])
        except ValueError:
            continue
        if (
            isinstance(message, list)
            and len(message) == 2
            and isinstance(message[0], str)
            and isinstance(message[1], dict)
        ):
            events.append((message[0], message[1]))
    return events


def token_user_id(token: str) -> str:
    """Read the Firebase UID from an ID token without re-verifying it."""
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["user_id"]


class HaloxSocket:
    """One Socket.IO long-poll connection for one home."""

    def __init__(
        self,
        session: ClientSession,
        api,
        home_id: str,
        device_id: str,
        on_event: Callable[[str, dict], Awaitable[None]],
        on_connection: Callable[[bool], None],
    ) -> None:
        self._session = session
        self._api = api
        self._home_id = home_id
        self._device_id = device_id
        self._on_event = on_event
        self._on_connection = on_connection
        self._task: asyncio.Task | None = None

    async def async_start(self) -> None:
        """Start the background listener; connection happens asynchronously."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def async_stop(self) -> None:
        """Stop the listener and release the in-flight long poll."""
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        backoff = _RECONNECT_MIN
        while True:
            try:
                await self._listen()
                backoff = _RECONNECT_MIN
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - reconnect on any failure
                _LOGGER.debug("Halox event stream disconnected: %s", err)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _RECONNECT_MAX)

    async def _listen(self) -> None:
        token = await self._api.async_get_access_token()
        headers = {
            "token": f"Bearer {token}",
            "user-id": token_user_id(token),
            "home-id": self._home_id,
            "device-id": self._device_id,
        }
        sid = await self._handshake(headers)
        connected = False
        try:
            await self._post(sid, "40", headers)
            while True:
                for packet in (await self._get(sid, headers)).split("\x1e"):
                    if packet == "2":
                        await self._post(sid, "3", headers)
                    elif packet.startswith("40"):
                        if not connected:
                            connected = True
                            self._on_connection(True)
                            _LOGGER.debug("Halox event stream connected")
                    elif packet.startswith("42"):
                        for event, data in parse_events(packet):
                            await self._on_event(event, data)
                    elif packet.startswith("41") or packet == "1":
                        raise ConnectionError("server closed the event stream")
                    elif packet.startswith("44"):
                        raise ConnectionError(packet)
        finally:
            if connected:
                self._on_connection(False)

    async def _handshake(self, headers: dict[str, str]) -> str:
        async with self._session.get(
            SOCKET_URL,
            params={"EIO": "4", "transport": "polling"},
            headers=headers,
            timeout=_POLL_TIMEOUT,
        ) as resp:
            body = await resp.text()
            if resp.status != 200 or not body.startswith("0"):
                raise ConnectionError(f"handshake failed: {resp.status} {body[:100]}")
        return json.loads(body[1:])["sid"]

    async def _get(self, sid: str, headers: dict[str, str]) -> str:
        async with self._session.get(
            SOCKET_URL,
            params={"EIO": "4", "transport": "polling", "sid": sid},
            headers=headers,
            timeout=_POLL_TIMEOUT,
        ) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise ConnectionError(f"poll failed: {resp.status} {body[:100]}")
        return body

    async def _post(self, sid: str, payload: str, headers: dict[str, str]) -> None:
        async with self._session.post(
            SOCKET_URL,
            params={"EIO": "4", "transport": "polling", "sid": sid},
            data=payload,
            headers={**headers, "Content-Type": "text/plain;charset=UTF-8"},
            timeout=_POLL_TIMEOUT,
        ) as resp:
            if resp.status != 200:
                raise ConnectionError(f"send failed: {resp.status}")
