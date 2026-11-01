"""Tests for the thermostat night mode switch."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import EntityCategory

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.mapping import map_thermostat
from custom_components.daikinone.client.models import DaikinThermostat
from custom_components.daikinone.client.wire import DaikinDeviceDataResponse
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.switch import DaikinOneNightModeSwitch, async_setup_entry
from tests.test_mapping import _make_device


def _thermostat(
    enabled: bool | None = True,
    active: bool | None = False,
    light_bar: bool | None = True,
) -> DaikinThermostat:
    payload = _make_device()
    payload["data"].update(
        {
            "nightModeEnabled": enabled,
            "nightModeActive": active,
            "nightModeLightBarAllowed": light_bar,
        }
    )
    return map_thermostat(DaikinDeviceDataResponse(**payload))


def _data(thermostat: DaikinThermostat) -> DaikinOneData:
    entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 1})
    daikin = MagicMock(spec=DaikinOne)
    daikin.get_thermostat.return_value = thermostat
    daikin.get_thermostats.return_value = {thermostat.id: thermostat}
    daikin.set_thermostat_night_mode = AsyncMock()
    return DaikinOneData(_hass=None, entry=entry, daikin=daikin)  # type: ignore[arg-type]


def _entity(thermostat: DaikinThermostat) -> tuple[DaikinOneNightModeSwitch, DaikinOneData]:
    data = _data(thermostat)
    entity = DaikinOneNightModeSwitch(
        data,
        thermostat,
        SimpleNamespace(key="night_mode", name="Night mode", icon="mdi:weather-night"),
    )
    return entity, data


@pytest.mark.asyncio
async def test_setup_only_creates_switch_when_register_is_available() -> None:
    thermostat = _thermostat()
    data = _data(thermostat)
    entities: list[DaikinOneNightModeSwitch] = []

    await async_setup_entry(
        SimpleNamespace(data={DOMAIN: data}),  # type: ignore[arg-type]
        data.entry,
        lambda added, update_before_add=False: entities.extend(added),
    )

    assert len(entities) == 1
    assert entities[0].unique_id == "device123-night_mode"
    assert entities[0].entity_category is EntityCategory.CONFIG


def test_switch_state_and_optional_attributes() -> None:
    entity, _ = _entity(_thermostat())
    assert entity.is_on is True
    assert entity.extra_state_attributes == {
        "night_mode_active": False,
        "light_bar_allowed": True,
    }

    without_attributes, _ = _entity(_thermostat(enabled=False, active=None, light_bar=None))
    assert without_attributes.is_on is False
    assert without_attributes.extra_state_attributes == {}


@pytest.mark.asyncio
async def test_turn_on_uses_optimistic_update() -> None:
    entity, data = _entity(_thermostat(False))
    entity.update_state_optimistically = AsyncMock()  # type: ignore[method-assign]

    await entity.async_turn_on()

    kwargs = entity.update_state_optimistically.await_args.kwargs
    await kwargs["operation"]()
    kwargs["optimistic_update"](entity._device)
    data.daikin.set_thermostat_night_mode.assert_awaited_once_with("device123", True)
    assert entity.is_on is True
