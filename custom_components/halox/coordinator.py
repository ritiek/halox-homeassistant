"""Data update coordinator for Halox Smart."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HaloxApi, HaloxApiError, HaloxAuthError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, SOCKET_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class HaloxCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Polls the Halox cloud and exposes devices keyed by device_id."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: HaloxApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self.entry = entry
        self.sockets: list = []
        self._live_sockets = 0

    def set_socket_connected(self, connected: bool) -> None:
        """Slow the REST fallback while a live event stream is up."""
        self._live_sockets = max(0, self._live_sockets + (1 if connected else -1))
        self.update_interval = timedelta(
            seconds=SOCKET_SCAN_INTERVAL if self._live_sockets else DEFAULT_SCAN_INTERVAL
        )

    async def async_handle_event(self, event: str, data: dict) -> None:
        """Apply a pushed device or board state change."""
        if not self.data:
            return
        if event == "stateUpdate":
            device = self.data.get(data.get("device_id"))
            on = data.get("state", {}).get("on")
            if device is None or on is None or device.get("is_on") == bool(on):
                return
            device["is_on"] = bool(on)
            self.async_set_updated_data(self.data)
        elif event == "onlineStatusUpdate":
            board_id = data.get("client_id")
            online = data.get("online")
            if board_id is None or online is None:
                return
            changed = False
            for device in self.data.values():
                if device.get("board_id") == board_id and device.get(
                    "online"
                ) != bool(online):
                    device["online"] = bool(online)
                    changed = True
            if changed:
                self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> dict[str, dict]:
        try:
            devices = await self.api.get_devices()
        except HaloxAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except HaloxApiError as err:
            raise UpdateFailed(f"Error talking to Halox cloud: {err}") from err
        # Persist a rotated refresh token so restarts keep working.
        if self.api.refresh_token and self.api.refresh_token != self.entry.data.get(
            "refresh_token"
        ):
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={**self.entry.data, "refresh_token": self.api.refresh_token},
            )
        return {dev["device_id"]: dev for dev in devices}
