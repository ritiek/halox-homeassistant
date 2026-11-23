"""Thin async client for the Halox Smart (LivSmart) cloud API.

Auth model: Firebase (Google Identity Platform) email/password sign-in returns a
long-lived refresh token plus a 1-hour ID token (JWT). Every REST call to the
vendor backend is authorized with `Authorization: Bearer <ID token>`.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import (
    ANDROID_PACKAGE,
    API_BASE,
    FIREBASE_API_KEY,
    IDENTITY_URL,
    SECURETOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)


class HaloxAuthError(Exception):
    """Raised when authentication fails (bad credentials or revoked token)."""


class HaloxApiError(Exception):
    """Raised when a backend request fails."""


class HaloxApi:
    """Minimal client covering discovery, state polling and control."""

    def __init__(self, session: ClientSession, refresh_token: str | None = None) -> None:
        self._session = session
        self._refresh_token = refresh_token
        self._access_token: str | None = None
        self._expiry: float = 0.0

    @classmethod
    async def login(
        cls, session: ClientSession, email: str, password: str
    ) -> "HaloxApi":
        """Sign in with email + password and return a ready client."""
        api = cls(session)
        url = f"{IDENTITY_URL}/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
        try:
            async with session.post(
                url,
                json={"email": email, "password": password, "returnSecureToken": True},
            ) as resp:
                data = await resp.json(content_type=None)
        except ClientError as err:
            raise HaloxApiError(str(err)) from err
        if "error" in data:
            raise HaloxAuthError(data["error"].get("message", "login failed"))
        api._refresh_token = data["refreshToken"]
        api._access_token = data["idToken"]
        api._expiry = time.time() + int(data.get("expiresIn", 3600)) - 60
        return api

    @property
    def refresh_token(self) -> str | None:
        """Current refresh token (persisted in the config entry)."""
        return self._refresh_token

    async def _ensure_token(self) -> None:
        if self._access_token and time.time() < self._expiry:
            return
        if not self._refresh_token:
            raise HaloxAuthError("no refresh token available")
        try:
            async with self._session.post(
                f"{SECURETOKEN_URL}?key={FIREBASE_API_KEY}",
                headers={"X-Android-Package": ANDROID_PACKAGE},
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
            ) as resp:
                data = await resp.json(content_type=None)
        except ClientError as err:
            raise HaloxApiError(str(err)) from err
        if "access_token" not in data:
            raise HaloxAuthError(data.get("error", "token refresh failed"))
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._expiry = time.time() + int(data.get("expires_in", 3600)) - 60

    async def _request(
        self, method: str, path: str, json: dict | None = None
    ) -> Any:
        await self._ensure_token()
        try:
            async with self._session.request(
                method,
                f"{API_BASE}{path}",
                json=json,
                headers={"Authorization": f"Bearer {self._access_token}"},
            ) as resp:
                body = await resp.json(content_type=None)
        except ClientError as err:
            raise HaloxApiError(str(err)) from err
        if isinstance(body, dict) and "error" in body:
            raise HaloxApiError(body["error"])
        if isinstance(body, dict):
            return body.get("data")
        return body

    async def get_devices(self) -> list[dict]:
        """Flatten every controllable device across all homes."""
        devices: list[dict] = []
        homes = await self._request("GET", "/home/all") or []
        for home in homes:
            boards = await self._request(
                "POST", "/board/all", {"home_id": home["_id"]}
            ) or []
            for board in boards:
                for dev in board.get("devices", []):
                    devices.append(
                        {
                            "device_id": dev["device_id"],
                            "name": dev.get("name") or board.get("name"),
                            "board_id": board["board_id"],
                            "board_name": board.get("name"),
                            "is_on": bool(dev.get("state", {}).get("on")),
                            "online": bool(dev.get("online")),
                            "type": dev.get("type", "switch"),
                            "home_id": home["_id"],
                            "firmware": board.get("firmware_version"),
                        }
                    )
        return devices

    async def set_state(self, device_id: str, on: bool) -> None:
        """Turn a device on/off via the REST control endpoint."""
        await self._request(
            "POST", "/device/update_state", {"device_id": device_id, "on": on}
        )
