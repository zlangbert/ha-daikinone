"""Tests for the dual-fuel balance point number entity."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.number import NumberDeviceClass, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.mapping import map_thermostat
from custom_components.daikinone.client.models import DaikinThermostat
from custom_components.daikinone.client.wire import DAIKIN_API_URL_DEVICE_DATA, DaikinDeviceDataResponse
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.number import (
    DEBOUNCE_DELAY,
    DaikinOneDualFuelBalancePointNumber,
    async_setup_entry,
)
from tests.test_mapping import _make_device


def _make_thermostat(value: float | None = 4.5) -> DaikinThermostat:
    payload = _make_device()
    payload["data"]["auxHeatLockoutTemp"] = value
    return map_thermostat(DaikinDeviceDataResponse(**payload))


def _data_for(thermostat: DaikinThermostat, schema: int = 1) -> DaikinOneData:
    entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: schema})
    daikin = MagicMock(spec=DaikinOne)
    daikin.get_thermostats.return_value = {thermostat.id: thermostat}
    daikin.get_thermostat.return_value = thermostat
    daikin.set_thermostat_aux_heat_lockout_temp = AsyncMock()
    data = DaikinOneData(_hass=None, entry=entry, daikin=daikin)  # type: ignore[arg-type]
    data.update = AsyncMock()  # type: ignore[method-assign]
    return data


def _entity(thermostat: DaikinThermostat, schema: int = 1) -> tuple[DaikinOneDualFuelBalancePointNumber, DaikinOneData]:
    data = _data_for(thermostat, schema)
    return DaikinOneDualFuelBalancePointNumber(data, thermostat), data


def _make_hass() -> MagicMock:
    loop = asyncio.get_running_loop()
    hass = MagicMock(spec=HomeAssistant)
    hass.loop = loop
    hass.async_create_task = MagicMock(side_effect=loop.create_task)
    return hass


async def test_setup_creates_entity_only_when_register_is_populated() -> None:
    thermostat = _make_thermostat()
    data = _data_for(thermostat)
    entities: list[object] = []
    hass = SimpleNamespace(data={DOMAIN: data})

    await async_setup_entry(hass, data.entry, lambda added, update_before_add=False: entities.extend(added))  # type: ignore[arg-type]

    assert len(entities) == 1
    entity = entities[0]
    assert isinstance(entity, DaikinOneDualFuelBalancePointNumber)
    assert entity.entity_description.key == "dual_fuel_balance_point"

    absent = _make_thermostat(None)
    absent_data = _data_for(absent)
    absent_entities: list[object] = []
    await async_setup_entry(
        SimpleNamespace(data={DOMAIN: absent_data}),
        absent_data.entry,
        lambda added, update_before_add=False: absent_entities.extend(added),
    )  # type: ignore[arg-type]
    assert absent_entities == []


def test_entity_description_and_unique_id_compatibility() -> None:
    thermostat = _make_thermostat()
    entity, _ = _entity(thermostat)

    assert entity.unique_id == "device123-dual_fuel_balance_point"
    assert entity.entity_description.name == "Dual fuel balance point"
    assert entity.entity_description.icon == "mdi:thermometer"
    assert entity.entity_description.device_class == NumberDeviceClass.TEMPERATURE
    assert entity.entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert entity.entity_description.native_step == 0.5
    assert entity.entity_description.mode == NumberMode.BOX
    assert entity.entity_description.entity_category == EntityCategory.CONFIG

    legacy, _ = _entity(thermostat, schema=0)
    assert legacy.unique_id == "device123-Dual fuel balance point"


def test_unknown_unique_id_schema_raises() -> None:
    with pytest.raises(ValueError, match="unexpected entity uid schema version"):
        _entity(_make_thermostat(), schema=99)


@pytest.mark.parametrize(
    ("value", "minimum", "maximum"),
    [
        (4.5, -23.0, 22.0),
        (-30.0, -30.0, 22.0),
        (25.5, -23.0, 25.5),
        (None, -23.0, 22.0),
    ],
)
def test_value_and_dynamic_bounds(value: float | None, minimum: float, maximum: float) -> None:
    entity, _ = _entity(_make_thermostat(value))
    assert entity.native_value == value
    assert entity.native_min_value == minimum
    assert entity.native_max_value == maximum


@pytest.mark.asyncio
async def test_debounce_coalesces_writes_and_updates_optimistically(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("custom_components.daikinone.number.DEBOUNCE_DELAY", 0.01)
    thermostat = _make_thermostat()
    entity, data = _entity(thermostat)
    entity.hass = _make_hass()
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_native_value(5.0)
    await entity.async_set_native_value(5.5)
    await entity.async_set_native_value(6.0)
    assert entity.native_value == 6.0
    assert entity.async_write_ha_state.call_count == 3
    data.daikin.set_thermostat_aux_heat_lockout_temp.assert_not_called()

    await asyncio.sleep(0.05)

    data.daikin.set_thermostat_aux_heat_lockout_temp.assert_awaited_once_with(thermostat.id, 6.0)
    assert entity._debounce_timer is None


@pytest.mark.asyncio
async def test_removal_cancels_pending_write() -> None:
    thermostat = _make_thermostat()
    entity, data = _entity(thermostat)
    entity.hass = _make_hass()
    entity.async_write_ha_state = MagicMock()
    await entity.async_set_native_value(5.0)
    timer = entity._debounce_timer

    await entity.async_will_remove_from_hass()
    await asyncio.sleep(DEBOUNCE_DELAY + 0.05)

    assert timer is not None and timer.cancelled()
    assert entity._debounce_timer is None
    data.daikin.set_thermostat_aux_heat_lockout_temp.assert_not_called()


@pytest.mark.asyncio
async def test_api_write_uses_aux_heat_lockout_key() -> None:
    client = object.__new__(DaikinOne)
    client._transport = SimpleNamespace(request=AsyncMock())
    await client.set_thermostat_aux_heat_lockout_temp("thermostat-id", 4.5)

    client._transport.request.assert_awaited_once_with(
        url=f"{DAIKIN_API_URL_DEVICE_DATA}/thermostat-id",
        method="PUT",
        body={"auxHeatLockoutTemp": 4.5},
    )


@pytest.mark.asyncio
async def test_optimistic_update_unpauses_after_write_failure() -> None:
    entity, _ = _entity(_make_thermostat())

    async def fail() -> None:
        raise RuntimeError("write failed")

    with pytest.raises(RuntimeError, match="write failed"):
        await entity.update_state_optimistically(
            operation=fail,
            optimistic_update=lambda thermostat: None,
            check=lambda thermostat: True,
        )

    assert entity._updates_paused is False
