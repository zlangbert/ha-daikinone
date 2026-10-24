"""Tests for fan circulation and night mode API writes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.models import DaikinThermostatFanCirculateDuration
from custom_components.daikinone.client.wire import DAIKIN_API_URL_DEVICE_DATA


@pytest.mark.parametrize(
    ("method", "value", "key"),
    [
        ("set_thermostat_fan_circulate_start", 12, "fanCirculateStart"),
        ("set_thermostat_fan_circulate_stop", 84, "fanCirculateStop"),
        ("set_thermostat_fan_circulate_duration", DaikinThermostatFanCirculateDuration.MIN_15, "fanCirculateDuration"),
        ("set_thermostat_night_mode", True, "nightModeEnabled"),
        ("set_thermostat_night_mode_start", 88, "nightModeStart"),
        ("set_thermostat_night_mode_stop", 28, "nightModeStop"),
    ],
)
async def test_schedule_api_writes(method: str, value: object, key: str) -> None:
    client = object.__new__(DaikinOne)
    client._transport = SimpleNamespace(request=AsyncMock())
    if method == "set_thermostat_fan_circulate_duration":
        expected_value = DaikinThermostatFanCirculateDuration.MIN_15.value
    else:
        expected_value = value

    await getattr(client, method)("thermostat-id", value)

    client._transport.request.assert_awaited_once_with(
        url=f"{DAIKIN_API_URL_DEVICE_DATA}/thermostat-id",
        method="PUT",
        body={key: expected_value},
    )


@pytest.mark.parametrize(
    ("method", "value", "key", "expected_value"),
    [
        ("set_thermostat_quiet_mode_enabled", True, "ctOutdoorQuietModeEnabled", 1),
        ("set_thermostat_quiet_mode_enabled", False, "ctOutdoorQuietModeEnabled", 0),
        ("set_thermostat_quiet_mode_start_time", 88, "quietModeStartTime", 88),
        ("set_thermostat_quiet_mode_stop_time", 28, "quietModeStopTime", 28),
    ],
)
async def test_quiet_mode_api_writes(method: str, value: object, key: str, expected_value: object) -> None:
    client = object.__new__(DaikinOne)
    client._transport = SimpleNamespace(request=AsyncMock())

    await getattr(client, method)("thermostat-id", value)

    client._transport.request.assert_awaited_once_with(
        url=f"{DAIKIN_API_URL_DEVICE_DATA}/thermostat-id",
        method="PUT",
        body={key: expected_value},
    )


async def test_quiet_mode_optimistic_cache_mutation() -> None:
    client = object.__new__(DaikinOne)
    client._transport = SimpleNamespace(request=AsyncMock())
    thermostat = SimpleNamespace(
        id="dev1",
        quiet_mode_enabled=False,
        quiet_mode_start_time=0,
        quiet_mode_stop_time=0,
    )
    client._DaikinOne__thermostats = {"dev1": thermostat}

    await client.set_thermostat_quiet_mode_enabled("dev1", True)
    assert thermostat.quiet_mode_enabled is True

    await client.set_thermostat_quiet_mode_start_time("dev1", 88)
    assert thermostat.quiet_mode_start_time == 88

    await client.set_thermostat_quiet_mode_stop_time("dev1", 28)
    assert thermostat.quiet_mode_stop_time == 28
