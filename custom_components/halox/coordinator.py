"""Data update coordinator for Halox Smart."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HaloxApi, HaloxApiError, HaloxAuthError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

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
