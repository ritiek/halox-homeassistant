"""The Halox Smart integration."""

from __future__ import annotations

import asyncio
import uuid

import voluptuous as vol
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import HaloxApi
from .const import CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import HaloxCoordinator
from .events import HaloxSocket

PLATFORMS: list[Platform] = [Platform.SWITCH]

type HaloxConfigEntry = ConfigEntry[HaloxCoordinator]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_EMAIL): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import a YAML-configured account (optional; UI setup also works)."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HaloxConfigEntry) -> bool:
    """Set up Halox Smart from a config entry."""
    session = async_get_clientsession(hass)
    api = HaloxApi(session, refresh_token=entry.data[CONF_REFRESH_TOKEN])

    coordinator = HaloxCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # One live event stream per home; REST polling stays as a slow fallback.
    device_id = str(uuid.uuid5(uuid.NAMESPACE_URL, entry.entry_id))
    home_ids = {dev["home_id"] for dev in coordinator.data.values()}
    coordinator.sockets = [
        HaloxSocket(
            session,
            api,
            home_id,
            device_id,
            coordinator.async_handle_event,
            coordinator.set_socket_connected,
        )
        for home_id in home_ids
    ]
    for sock in coordinator.sockets:
        await sock.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HaloxConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = entry.runtime_data
    await asyncio.gather(*(sock.async_stop() for sock in coordinator.sockets))
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
