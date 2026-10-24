"""Tests for fan circulation select entities."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import EntityCategory

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.mapping import map_thermostat
from custom_components.daikinone.client.models import (
    DaikinThermostat,
    DaikinThermostatFanCirculateDuration,
)
from custom_components.daikinone.client.wire import DaikinDeviceDataResponse
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.select import (
    DaikinOneFanCirculationDutyCycleSelect,
    DaikinOneFanSpeedSelect,
    FAN_CIRCULATE_DUTY_CYCLE_OPTIONS,
    async_setup_entry,
)
from tests.test_mapping import _make_device


def _thermostat(duration: int | None = 2) -> DaikinThermostat:
    payload = _make_device()
    if duration is not None:
        payload["data"]["fanCirculateDuration"] = duration
    return map_thermostat(DaikinDeviceDataResponse(**payload))


def _data(thermostat: DaikinThermostat) -> DaikinOneData:
    entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 1})
    daikin = MagicMock(spec=DaikinOne)
    daikin.get_thermostat.return_value = thermostat
    daikin.get_thermostats.return_value = {thermostat.id: thermostat}
    daikin.set_thermostat_fan_circulate_duration = AsyncMock()
    return DaikinOneData(_hass=None, entry=entry, daikin=daikin)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_setup_creates_duty_cycle_only_when_register_is_available() -> None:
    thermostat = _thermostat()
    absent = _thermostat(None)
    unknown = _thermostat(255)
    data = _data(thermostat)
    data.daikin.get_thermostats.return_value = {
        thermostat.id: thermostat,
        "absent": absent,
        "unknown": unknown,
    }
    entities: list[object] = []

    await async_setup_entry(
        SimpleNamespace(data={DOMAIN: data}),  # type: ignore[arg-type]
        data.entry,
        lambda added, update_before_add=False: entities.extend(added),
    )

    speed_entities = [entity for entity in entities if isinstance(entity, DaikinOneFanSpeedSelect)]
    duty_entities = [entity for entity in entities if isinstance(entity, DaikinOneFanCirculationDutyCycleSelect)]
    assert len(speed_entities) == 3
    assert len(duty_entities) == 1
    assert duty_entities[0].unique_id == "device123-fan_circulation_duty_cycle"
    assert duty_entities[0].entity_category is EntityCategory.CONFIG
    assert duty_entities[0].options == list(FAN_CIRCULATE_DUTY_CYCLE_OPTIONS)
    assert speed_entities[0].entity_description.name == "Fan circulation speed"
    assert speed_entities[0].entity_category is EntityCategory.CONFIG


@pytest.mark.asyncio
async def test_duty_cycle_selection_uses_api_and_optimistic_value() -> None:
    thermostat = _thermostat()
    data = _data(thermostat)
    entity = DaikinOneFanCirculationDutyCycleSelect(
        description=SimpleNamespace(
            key="fan_circulation_duty_cycle",
            name="Fan circulation duty cycle",
            icon="mdi:fan-clock",
            has_entity_name=True,
            entity_category=EntityCategory.CONFIG,
            options=list(FAN_CIRCULATE_DUTY_CYCLE_OPTIONS),
        ),
        data=data,
        thermostat=thermostat,
    )
    entity.update_state_optimistically = AsyncMock()  # type: ignore[method-assign]

    await entity.async_select_option("30 min/hr")
    kwargs = entity.update_state_optimistically.await_args.kwargs
    await kwargs["operation"]()
    kwargs["optimistic_update"](thermostat)
    entity.update_entity_attributes()

    data.daikin.set_thermostat_fan_circulate_duration.assert_awaited_once_with(
        "device123", DaikinThermostatFanCirculateDuration.MIN_30
    )
    assert thermostat.fan_circulate_duration is DaikinThermostatFanCirculateDuration.MIN_30
    assert entity.current_option == "30 min/hr"


@pytest.mark.asyncio
async def test_unsupported_duty_cycle_raises() -> None:
    thermostat = _thermostat()
    entity = DaikinOneFanCirculationDutyCycleSelect(
        description=SimpleNamespace(
            key="fan_circulation_duty_cycle",
            name="Fan circulation duty cycle",
            icon="mdi:fan-clock",
            has_entity_name=True,
            entity_category=EntityCategory.CONFIG,
            options=list(FAN_CIRCULATE_DUTY_CYCLE_OPTIONS),
        ),
        data=_data(thermostat),
        thermostat=thermostat,
    )
    with pytest.raises(ValueError, match="unsupported fan circulation duty cycle"):
        await entity.async_select_option("not a duration")
