"""Switch platform for Halox Smart."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HaloxConfigEntry
from .const import DOMAIN
from .coordinator import HaloxCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaloxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Halox switches from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        HaloxSwitch(coordinator, device_id) for device_id in coordinator.data
    )


class HaloxSwitch(CoordinatorEntity[HaloxCoordinator], SwitchEntity):
    """A Halox smart switch/plug."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: HaloxCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = device_id

    @property
    def _device(self) -> dict:
        return self.coordinator.data[self._device_id]

    @property
    def device_info(self) -> DeviceInfo:
        dev = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, dev["board_id"])},
            name=dev.get("board_name") or dev["name"],
            manufacturer="Halox",
            model=dev.get("type", "switch"),
            sw_version=dev.get("firmware"),
        )

    @property
    def available(self) -> bool:
        return super().available and self._device_id in self.coordinator.data

    @property
    def is_on(self) -> bool:
        return self._device["is_on"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)

    async def _set(self, on: bool) -> None:
        dev = self._device
        await self.coordinator.api.set_state(self._device_id, dev["board_id"], on)
        # Optimistic update until the next poll confirms.
        dev["is_on"] = on
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._device_id in self.coordinator.data:
            self.async_write_ha_state()
