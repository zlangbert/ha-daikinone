from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.sensor import SensorEntityDescription

from custom_components.daikinone import DaikinOneData
from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.models import DaikinIndoorUnit, DaikinThermostat, DaikinUserCredentials
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.entity import DaikinOneEntity
from custom_components.daikinone.sensor import DaikinOneEquipmentSensor, DaikinOneThermostatSensor
from tests.test_mapping import AIR_HANDLER_DATA, _make_device


@pytest.fixture
def daikin_client() -> DaikinOne:
    creds = DaikinUserCredentials(email="test@example.com", password="password")
    client = DaikinOne(creds)
    client._DaikinOne__thermostats.clear()  # type: ignore[attr-defined]
    return client


@pytest.fixture
def data(daikin_client: DaikinOne) -> DaikinOneData:
    entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 1})
    return DaikinOneData(_hass=None, entry=entry, daikin=daikin_client)  # type: ignore[arg-type]


def _power_description() -> SensorEntityDescription:
    return SensorEntityDescription(key="power", name="Power", has_entity_name=True)


def _humidity_description() -> SensorEntityDescription:
    return SensorEntityDescription(key="humidity", name="Humidity", has_entity_name=True)


async def _refresh(daikin_client: DaikinOne, mock_req: AsyncMock, payload: dict[str, Any]) -> None:
    mock_req.return_value = [payload]
    await daikin_client.update()


class TestEntityAvailability:
    async def test_equipment_sensor_unavailable_when_equipment_skipped(
        self, daikin_client: DaikinOne, data: DaikinOneData
    ) -> None:
        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            await _refresh(daikin_client, mock_req, _make_device(AIR_HANDLER_DATA))

            thermostat = daikin_client.get_thermostats()["device123"]
            unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinIndoorUnit))
            sensor = DaikinOneEquipmentSensor(
                description=_power_description(), data=data, device=unit, attribute=lambda e: e.power_usage
            )

            bad_ah = {**AIR_HANDLER_DATA, "ctAHSerialNoCharacter1_15": "he\ufffdlo"}
            await _refresh(daikin_client, mock_req, _make_device(bad_ah))
            await sensor.async_update(no_throttle=True)

        assert sensor.available is False
        # last-known _device is retained so attributes can recover cleanly
        assert sensor._device.id == unit.id

    async def test_equipment_sensor_recovers_when_equipment_returns(
        self, daikin_client: DaikinOne, data: DaikinOneData
    ) -> None:
        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            await _refresh(daikin_client, mock_req, _make_device(AIR_HANDLER_DATA))

            thermostat = daikin_client.get_thermostats()["device123"]
            unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinIndoorUnit))
            sensor = DaikinOneEquipmentSensor(
                description=_power_description(), data=data, device=unit, attribute=lambda e: e.power_usage
            )

            bad_ah = {**AIR_HANDLER_DATA, "ctAHSerialNoCharacter1_15": "he\ufffdlo"}
            await _refresh(daikin_client, mock_req, _make_device(bad_ah))
            await sensor.async_update(no_throttle=True)
            assert sensor.available is False

            recovered = {**AIR_HANDLER_DATA, "ctIndoorPower": 1230}
            await _refresh(daikin_client, mock_req, _make_device(recovered))
            await sensor.async_update(no_throttle=True)

        assert sensor.available is True
        assert sensor._device.power_usage == 123.0

    async def test_thermostat_sensor_unaffected_by_equipment_availability(
        self, daikin_client: DaikinOne, data: DaikinOneData
    ) -> None:
        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            await _refresh(daikin_client, mock_req, _make_device(AIR_HANDLER_DATA))

            thermostat = daikin_client.get_thermostats()["device123"]
            sensor = DaikinOneThermostatSensor(
                description=_humidity_description(),
                data=data,
                device=thermostat,
                attribute=lambda t: t.indoor_humidity,
            )

            await sensor.async_update(no_throttle=True)

        assert sensor.available is True
        assert sensor.native_value == 45


class _StubEntity(DaikinOneEntity[DaikinThermostat]):
    async def async_get_device(self) -> DaikinThermostat:
        return self._device

    def update_entity_attributes(self) -> None:
        pass


class TestUpdateStateOptimistically:
    async def test_updates_paused_reset_after_operation_error(
        self, daikin_client: DaikinOne, data: DaikinOneData
    ) -> None:
        """Regression test: a failed operation must not permanently freeze the entity."""
        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            await _refresh(daikin_client, mock_req, _make_device(AIR_HANDLER_DATA))
        thermostat = daikin_client.get_thermostats()["device123"]

        entity = _StubEntity(data=data, device=thermostat)

        async def failing_operation() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await entity.update_state_optimistically(
                operation=failing_operation,
                optimistic_update=lambda d: None,
                check=lambda d: True,
            )

        assert entity._updates_paused is False

    async def test_updates_resume_after_wait_for_updated_value_error(
        self, daikin_client: DaikinOne, data: DaikinOneData
    ) -> None:
        """Regression test: a failed post-operation poll must not permanently freeze the entity."""
        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            await _refresh(daikin_client, mock_req, _make_device(AIR_HANDLER_DATA))
        thermostat = daikin_client.get_thermostats()["device123"]

        entity = _StubEntity(data=data, device=thermostat)
        entity.hass = None  # type: ignore[assignment]
        entity.entity_id = "climate.test"
        entity.async_write_ha_state = lambda: None  # type: ignore[method-assign]

        def check(_: DaikinThermostat) -> bool:
            raise RuntimeError("device disappeared mid-poll")

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [_make_device(AIR_HANDLER_DATA)]

            with pytest.raises(RuntimeError):
                await entity.update_state_optimistically(
                    operation=AsyncMock(),
                    optimistic_update=lambda d: None,
                    check=check,
                )

        assert entity._updates_paused is False
