"""The Halox Smart integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HaloxApi
from .const import CONF_REFRESH_TOKEN
from .coordinator import HaloxCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH]

type HaloxConfigEntry = ConfigEntry[HaloxCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HaloxConfigEntry) -> bool:
    """Set up Halox Smart from a config entry."""
    session = async_get_clientsession(hass)
    api = HaloxApi(session, refresh_token=entry.data[CONF_REFRESH_TOKEN])

    coordinator = HaloxCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HaloxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
