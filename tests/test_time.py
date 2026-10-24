"""Tests for fan circulation and night mode schedule time entities."""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.mapping import map_thermostat
from custom_components.daikinone.client.models import DaikinThermostat
from custom_components.daikinone.client.wire import DaikinDeviceDataResponse
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.time import (
    DaikinOneFanCirculationStartTime,
    DaikinOneFanCirculationStopTime,
    DaikinOneNightModeStartTime,
    DaikinOneNightModeStopTime,
    DaikinOneQuietModeStartTime,
    DaikinOneQuietModeStopTime,
    _slot_to_time,
    _time_to_slot,
    async_setup_entry,
)
from tests.test_mapping import _make_device


def _thermostat(**fields: object) -> DaikinThermostat:
    payload = _make_device()
    payload["data"].update(fields)
    return map_thermostat(DaikinDeviceDataResponse(**payload))


def _data(thermostat: DaikinThermostat, schema: int = 1) -> DaikinOneData:
    entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: schema})
    daikin = MagicMock(spec=DaikinOne)
    daikin.get_thermostat.return_value = thermostat
    daikin.get_thermostats.return_value = {thermostat.id: thermostat}
    for method in (
        "set_thermostat_fan_circulate_start",
        "set_thermostat_fan_circulate_stop",
        "set_thermostat_night_mode_start",
        "set_thermostat_night_mode_stop",
        "set_thermostat_quiet_mode_start_time",
        "set_thermostat_quiet_mode_stop_time",
    ):
        getattr(daikin, method).return_value = None
    return DaikinOneData(_hass=None, entry=entry, daikin=daikin)  # type: ignore[arg-type]


def test_slot_conversions_and_invalid_slots() -> None:
    assert _slot_to_time(0) == datetime.time(0, 0)
    assert _slot_to_time(95) == datetime.time(23, 45)
    assert _slot_to_time(None) is None
    assert _slot_to_time(255) is None
    assert _slot_to_time(-1) is None
    assert _time_to_slot(datetime.time(1, 7)) == 4
    assert _time_to_slot(datetime.time(1, 8)) == 5
    assert _time_to_slot(datetime.time(23, 59)) == 0


@pytest.mark.parametrize(
    ("field", "entity_type", "slot", "schema"),
    [
        ("fan_circulate_start", DaikinOneFanCirculationStartTime, 4, 0),
        ("fan_circulate_stop", DaikinOneFanCirculationStopTime, 92, 1),
        ("night_mode_start", DaikinOneNightModeStartTime, 88, 0),
        ("night_mode_stop", DaikinOneNightModeStopTime, 28, 1),
        ("quiet_mode_start_time", DaikinOneQuietModeStartTime, 88, 0),
        ("quiet_mode_stop_time", DaikinOneQuietModeStopTime, 28, 1),
    ],
)
def test_time_entity_value_and_metadata(field: str, entity_type: type[TimeEntity], slot: int, schema: int) -> None:
    key = {
        "fan_circulate_start": "fan_circulation_start",
        "fan_circulate_stop": "fan_circulation_stop",
        "night_mode_start": "night_mode_start",
        "night_mode_stop": "night_mode_stop",
        "quiet_mode_start_time": "quiet_mode_start_time",
        "quiet_mode_stop_time": "quiet_mode_stop_time",
    }[field]
    thermostat = _thermostat(
        fanCirculateStart=4,
        fanCirculateStop=92,
        nightModeStart=88,
        nightModeStop=28,
        ctQuietModeHODisplayEnable=True,
        quietModeStartTime=88,
        quietModeStopTime=28,
    )
    entity = entity_type(
        description=SimpleNamespace(key=key, name=key, icon=None, has_entity_name=True, entity_category=None),
        data=_data(thermostat, schema),
        thermostat=thermostat,
    )

    assert entity.unique_id == f"device123-{key}"
    assert entity.native_value == _slot_to_time(slot)


@pytest.mark.asyncio
async def test_setup_creates_entities_only_for_complete_valid_pairs() -> None:
    complete = _thermostat(
        fanCirculateStart=4,
        fanCirculateStop=92,
        nightModeStart=88,
        nightModeStop=28,
    )
    incomplete = _thermostat(fanCirculateStart=4, fanCirculateStop=255, nightModeStart=88)
    data = _data(complete)
    data.daikin.get_thermostats.return_value = {
        complete.id: complete,
        "incomplete": incomplete,
    }
    entities: list[TimeEntity] = []

    await async_setup_entry(
        SimpleNamespace(data={DOMAIN: data}),  # type: ignore[arg-type]
        data.entry,
        lambda added, update_before_add=False: entities.extend(added),
    )

    assert len(entities) == 4
    assert all(entity.entity_category is EntityCategory.CONFIG for entity in entities)


@pytest.mark.asyncio
async def test_time_write_converts_to_slot_and_updates_optimistically() -> None:
    thermostat = _thermostat(fanCirculateStart=4, fanCirculateStop=92)
    data = _data(thermostat)
    entity = DaikinOneFanCirculationStartTime(
        description=SimpleNamespace(
            key="fan_circulation_start",
            name="Fan circulation start time",
            icon="mdi:clock-start",
            has_entity_name=True,
            entity_category=EntityCategory.CONFIG,
        ),
        data=data,
        thermostat=thermostat,
    )
    entity.update_state_optimistically = AsyncMock()  # type: ignore[method-assign]

    await entity.async_set_value(datetime.time(3, 8))
    operation = entity.update_state_optimistically.await_args.kwargs["operation"]
    await operation()

    data.daikin.set_thermostat_fan_circulate_start.assert_awaited_once_with("device123", 13)
    update = entity.update_state_optimistically.await_args.kwargs["optimistic_update"]
    update(thermostat)
    assert thermostat.fan_circulate_start == 13


@pytest.mark.asyncio
async def test_optimistic_update_resumes_after_api_failure() -> None:
    thermostat = _thermostat(fanCirculateStart=4, fanCirculateStop=92)
    entity = DaikinOneFanCirculationStartTime(
        description=SimpleNamespace(key="fan_circulation_start", name="Start time"),
        data=_data(thermostat),
        thermostat=thermostat,
    )

    async def fail() -> None:
        raise RuntimeError("write failed")

    with pytest.raises(RuntimeError, match="write failed"):
        await entity.update_state_optimistically(
            operation=fail,
            optimistic_update=lambda _: None,
            check=lambda _: True,
        )

    assert entity._updates_paused is False


@pytest.mark.asyncio
async def test_setup_quiet_mode_time_gating() -> None:
    valid = _thermostat(
        ctQuietModeHODisplayEnable=True,
        quietModeStartTime=88,
        quietModeStopTime=28,
    )
    ho_disabled = _thermostat(
        ctQuietModeHODisplayEnable=False,
        quietModeStartTime=88,
        quietModeStopTime=28,
    )
    incomplete = _thermostat(
        ctQuietModeHODisplayEnable=True,
        quietModeStartTime=88,
        quietModeStopTime=255,
    )
    data = _data(valid)
    data.daikin.get_thermostats.return_value = {
        "valid": valid,
        "ho_disabled": ho_disabled,
        "incomplete": incomplete,
    }
    entities: list[TimeEntity] = []

    await async_setup_entry(
        SimpleNamespace(data={DOMAIN: data}),  # type: ignore[arg-type]
        data.entry,
        lambda added, update_before_add=False: entities.extend(added),
    )

    quiet_entities = [e for e in entities if isinstance(e, (DaikinOneQuietModeStartTime, DaikinOneQuietModeStopTime))]
    assert len(quiet_entities) == 2
    assert {e.entity_description.key for e in quiet_entities} == {
        "quiet_mode_start_time",
        "quiet_mode_stop_time",
    }
    assert all(e.entity_category is EntityCategory.CONFIG for e in quiet_entities)


@pytest.mark.asyncio
async def test_quiet_mode_time_writes_optimistic_update() -> None:
    thermostat = _thermostat(
        ctQuietModeHODisplayEnable=True,
        quietModeStartTime=88,
        quietModeStopTime=28,
    )
    data = _data(thermostat)
    start_entity = DaikinOneQuietModeStartTime(
        description=SimpleNamespace(
            key="quiet_mode_start_time",
            name="Quiet mode start time",
            icon="mdi:clock-start",
            has_entity_name=True,
            entity_category=EntityCategory.CONFIG,
        ),
        data=data,
        thermostat=thermostat,
    )
    start_entity.update_state_optimistically = AsyncMock()  # type: ignore[method-assign]

    await start_entity.async_set_value(datetime.time(22, 0))
    operation = start_entity.update_state_optimistically.await_args.kwargs["operation"]
    await operation()
    data.daikin.set_thermostat_quiet_mode_start_time.assert_awaited_once_with("device123", 88)
    start_entity.update_state_optimistically.await_args.kwargs["optimistic_update"](thermostat)
    assert thermostat.quiet_mode_start_time == 88

    stop_entity = DaikinOneQuietModeStopTime(
        description=SimpleNamespace(
            key="quiet_mode_stop_time",
            name="Quiet mode stop time",
            icon="mdi:clock-end",
            has_entity_name=True,
            entity_category=EntityCategory.CONFIG,
        ),
        data=data,
        thermostat=thermostat,
    )
    stop_entity.update_state_optimistically = AsyncMock()  # type: ignore[method-assign]

    await stop_entity.async_set_value(datetime.time(7, 0))
    operation = stop_entity.update_state_optimistically.await_args.kwargs["operation"]
    await operation()
    data.daikin.set_thermostat_quiet_mode_stop_time.assert_awaited_once_with("device123", 28)
    stop_entity.update_state_optimistically.await_args.kwargs["optimistic_update"](thermostat)
    assert thermostat.quiet_mode_stop_time == 28
