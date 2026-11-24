"""Regression self-check: a stale REST poll must not undo a fresh command.

Stubs the few Home Assistant classes the coordinator imports, so it runs
without Home Assistant installed (same command as test_api.py).
"""

import asyncio
import sys
import types

from test_api import _load_module


def _stub_homeassistant() -> None:
    class DataUpdateCoordinator:
        def __class_getitem__(cls, _item):
            return cls

        def __init__(self, hass, logger, name, update_interval):
            self.data = None
            self.update_interval = update_interval

        def async_set_updated_data(self, data):
            self.data = data

    class UpdateFailed(Exception):
        pass

    modules = {
        "homeassistant": {},
        "homeassistant.config_entries": {"ConfigEntry": object},
        "homeassistant.core": {"HomeAssistant": object},
        "homeassistant.helpers": {},
        "homeassistant.helpers.update_coordinator": {
            "DataUpdateCoordinator": DataUpdateCoordinator,
            "UpdateFailed": UpdateFailed,
        },
    }
    for name, attrs in modules.items():
        mod = sys.modules.setdefault(name, types.ModuleType(name))
        for key, value in attrs.items():
            setattr(mod, key, value)


_stub_homeassistant()
coordinator_mod = _load_module("coordinator")

DEV = "dev1"


class FakeApi:
    """REST that still reports the pre-command state, like the real cloud."""

    refresh_token = None

    def __init__(self):
        self.rest_on = True

    async def set_state(self, device_id, on):
        pass

    async def get_devices(self):
        return [{"device_id": DEV, "board_id": "b1", "is_on": self.rest_on}]


def _coordinator():
    entry = types.SimpleNamespace(data={})
    coord = coordinator_mod.HaloxCoordinator(None, entry, FakeApi())
    coord.data = {DEV: {"device_id": DEV, "board_id": "b1", "is_on": True}}
    return coord


def _push(coord, on):
    return coord.async_handle_event(
        "stateUpdate", {"device_id": DEV, "state": {"on": on}}
    )


async def _poll(coord):
    coord.async_set_updated_data(await coord._async_update_data())


def test_stale_poll_after_push_keeps_command():
    async def run():
        coord = _coordinator()
        await coord.async_set_state(DEV, False)
        await _push(coord, False)  # device ack arrives first
        await _poll(coord)  # stale REST lands last
        assert coord.data[DEV]["is_on"] is False

    asyncio.run(run())


def test_stale_poll_before_push_keeps_command():
    async def run():
        coord = _coordinator()
        await coord.async_set_state(DEV, False)
        await _poll(coord)
        assert coord.data[DEV]["is_on"] is False
        await _push(coord, False)
        assert coord.data[DEV]["is_on"] is False

    asyncio.run(run())


def test_push_inside_window_wins_and_rest_resumes_after():
    async def run():
        coord = _coordinator()
        await coord.async_set_state(DEV, False)
        await _push(coord, True)  # physical button pressed right after
        await _poll(coord)
        assert coord.data[DEV]["is_on"] is True

        coord.api.rest_on = False
        coord._commanded[DEV] = (True, 0)  # window expired
        await _poll(coord)
        assert coord.data[DEV]["is_on"] is False
        assert DEV not in coord._commanded

    asyncio.run(run())
