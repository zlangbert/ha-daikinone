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
from custom_components.daikinone.switch import (
    DaikinOneNightModeSwitch,
    DaikinOneQuietModeSwitch,
    async_setup_entry,
)
from tests.test_mapping import _make_device


def _thermostat(enabled: bool | None = True) -> DaikinThermostat:
    payload = _make_device()
    payload["data"].update(
        {
            "nightModeEnabled": enabled,
            "nightModeActive": False,
            "nightModeLightBarAllowed": True,
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


def test_switch_state_and_optional_attributes() -> None:
    entity, _ = _entity(_thermostat())
    assert entity.is_on is True
    assert entity.extra_state_attributes == {
        "night_mode_active": False,
        "light_bar_allowed": True,
    }

    without_attributes, _ = _entity(_thermostat(enabled=False))
    without_attributes._device.night_mode_active = None
    without_attributes._device.night_mode_light_bar_allowed = None
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


def _quiet_thermostat(
    enabled: bool | None = True,
    ho_display: bool | None = True,
    active: bool | None = False,
) -> DaikinThermostat:
    payload = _make_device()
    payload["data"].update(
        {
            "ctOutdoorQuietModeEnabled": 1 if enabled is True else (0 if enabled is False else None),
            "quietModeActive": 1 if active is True else (0 if active is False else None),
            "ctQuietModeHODisplayEnable": ho_display,
        }
    )
    return map_thermostat(DaikinDeviceDataResponse(**payload))


def _quiet_data(thermostat: DaikinThermostat, schema: int = 1) -> DaikinOneData:
    entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: schema})
    daikin = MagicMock(spec=DaikinOne)
    daikin.get_thermostat.return_value = thermostat
    daikin.get_thermostats.return_value = {thermostat.id: thermostat}
    daikin.set_thermostat_quiet_mode_enabled = AsyncMock()
    return DaikinOneData(_hass=None, entry=entry, daikin=daikin)  # type: ignore[arg-type]


def _quiet_entity(
    thermostat: DaikinThermostat,
    schema: int = 1,
) -> tuple[DaikinOneQuietModeSwitch, DaikinOneData]:
    data = _quiet_data(thermostat, schema)
    entity = DaikinOneQuietModeSwitch(
        data,
        thermostat,
        SimpleNamespace(
            key="quiet_mode",
            name="Quiet mode",
            icon="mdi:volume-off",
            entity_category=EntityCategory.CONFIG,
            has_entity_name=True,
            translation_key="quiet_mode",
        ),
    )
    return entity, data


class TestQuietModeSwitch:
    @pytest.mark.asyncio
    async def test_setup_registers_switch_when_ho_display_true_and_enabled_not_none(self) -> None:
        thermostat = _quiet_thermostat(enabled=True, ho_display=True)
        data = _quiet_data(thermostat)
        entities: list = []

        await async_setup_entry(
            SimpleNamespace(data={DOMAIN: data}),  # type: ignore[arg-type]
            data.entry,
            lambda added, update_before_add=False: entities.extend(added),
        )

        quiet_switches = [e for e in entities if isinstance(e, DaikinOneQuietModeSwitch)]
        assert len(quiet_switches) == 1
        assert quiet_switches[0].unique_id == "device123-quiet_mode"
        assert quiet_switches[0].entity_description.entity_category is EntityCategory.CONFIG

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("enabled", "ho_display"),
        [
            (None, True),
            (True, False),
            (True, None),
            (None, None),
        ],
    )
    async def test_setup_suppresses_switch_when_gate_fails(self, enabled: bool | None, ho_display: bool | None) -> None:
        thermostat = _quiet_thermostat(enabled=enabled, ho_display=ho_display)
        data = _quiet_data(thermostat)
        entities: list = []

        await async_setup_entry(
            SimpleNamespace(data={DOMAIN: data}),  # type: ignore[arg-type]
            data.entry,
            lambda added, update_before_add=False: entities.extend(added),
        )

        quiet_switches = [e for e in entities if isinstance(e, DaikinOneQuietModeSwitch)]
        assert len(quiet_switches) == 0

    def test_switch_state_and_extra_state_attributes(self) -> None:
        entity, _ = _quiet_entity(_quiet_thermostat(enabled=True, active=True))
        assert entity.is_on is True
        assert entity.extra_state_attributes == {"quiet_mode_active": True}

        entity_off, _ = _quiet_entity(_quiet_thermostat(enabled=False, active=False))
        assert entity_off.is_on is False
        assert entity_off.extra_state_attributes == {"quiet_mode_active": False}

        without_active, _ = _quiet_entity(_quiet_thermostat(enabled=True, active=None))
        assert without_active.is_on is True
        assert without_active.extra_state_attributes == {}

    @pytest.mark.parametrize("schema", [0, 1])
    def test_unique_id_stability(self, schema: int) -> None:
        entity, _ = _quiet_entity(_quiet_thermostat(enabled=True), schema=schema)
        assert entity.unique_id == "device123-quiet_mode"

    @pytest.mark.asyncio
    async def test_turn_on_and_off_uses_optimistic_update(self) -> None:
        entity, data = _quiet_entity(_quiet_thermostat(enabled=False))
        entity.update_state_optimistically = AsyncMock()  # type: ignore[method-assign]

        await entity.async_turn_on()
        kwargs = entity.update_state_optimistically.await_args.kwargs
        await kwargs["operation"]()
        kwargs["optimistic_update"](entity._device)
        data.daikin.set_thermostat_quiet_mode_enabled.assert_awaited_once_with("device123", True)
        assert entity.is_on is True

        data.daikin.set_thermostat_quiet_mode_enabled.reset_mock()
        await entity.async_turn_off()
        kwargs = entity.update_state_optimistically.await_args.kwargs
        await kwargs["operation"]()
        kwargs["optimistic_update"](entity._device)
        data.daikin.set_thermostat_quiet_mode_enabled.assert_awaited_once_with("device123", False)
        assert entity.is_on is False

    async def test_async_get_device(self) -> None:
        entity, _ = _quiet_entity(_quiet_thermostat(enabled=True))
        dev = await entity.async_get_device()
        assert dev.id == "device123"
