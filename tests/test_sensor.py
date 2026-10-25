"""Unit tests for Daikin One sensor platform, focusing on P1/P2 equipment."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.models import (
    DaikinP1P2IndoorUnit,
    DaikinP1P2OutdoorUnit,
    DaikinUserCredentials,
)
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.sensor import (
    DaikinOneEquipmentSensor,
    async_setup_entry,
)
from tests.test_mapping import (
    P1P2_OUTDOOR_DATA_INVALID_RX24,
    P1P2_OUTDOOR_DATA_VALID,
    P1P2_SINGLE_INDOOR_DATA,
    _make_device,
)


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


async def _setup_sensors(daikin_client: DaikinOne, data: DaikinOneData, payload: dict[str, Any]) -> list[SensorEntity]:
    with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = [payload]
        await daikin_client.update()

    hass = SimpleNamespace(data={DOMAIN: data})
    created_entities: list[SensorEntity] = []

    def async_add_entities(entities: list[SensorEntity], update_before_add: bool = True) -> None:
        created_entities.extend(entities)

    await async_setup_entry(hass, data.entry, async_add_entities)  # type: ignore[arg-type]
    return created_entities


class TestP1P2Sensors:
    async def test_p1p2_indoor_sensors_created_only_for_non_none(
        self, daikin_client: DaikinOne, data: DaikinOneData
    ) -> None:
        device_data = _make_device(P1P2_SINGLE_INDOOR_DATA)
        entities = await _setup_sensors(daikin_client, data, device_data)

        # Filter entities belonging to the indoor unit
        indoor_sensors = [
            e
            for e in entities
            if isinstance(e, DaikinOneEquipmentSensor) and isinstance(e._device, DaikinP1P2IndoorUnit)
        ]

        sensor_keys = {s.entity_description.key: s for s in indoor_sensors}

        # 7 sensors should be created (discharge_air_temperature was None)
        assert len(indoor_sensors) == 7
        assert "discharge_air_temperature" not in sensor_keys

        # Check Suction air temperature
        suction = sensor_keys["suction_air_temperature"]
        assert suction.entity_description.name == "Suction air temperature"
        assert suction.entity_description.device_class == SensorDeviceClass.TEMPERATURE
        assert suction.entity_description.state_class == SensorStateClass.MEASUREMENT
        assert suction.entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS
        assert suction.entity_description.icon == "mdi:thermometer"
        suction.update_entity_attributes()
        assert suction.native_value == 21.5

        # Check Liquid pipe temperature
        liquid = sensor_keys["liquid_pipe_temperature"]
        assert liquid.entity_description.name == "Liquid pipe temperature"
        assert liquid.entity_description.device_class == SensorDeviceClass.TEMPERATURE
        assert liquid.entity_description.state_class == SensorStateClass.MEASUREMENT
        assert liquid.entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS
        liquid.update_entity_attributes()
        assert liquid.native_value == 12.3

        # Check Gas pipe temperature
        gas = sensor_keys["gas_pipe_temperature"]
        assert gas.entity_description.name == "Gas pipe temperature"
        assert gas.entity_description.device_class == SensorDeviceClass.TEMPERATURE
        gas.update_entity_attributes()
        assert gas.native_value == 15.4

        # Check EEV open pulses
        eev = sensor_keys["eev_open_pulses"]
        assert eev.entity_description.name == "EEV open pulses"
        assert eev.entity_description.device_class is None
        assert eev.entity_description.state_class == SensorStateClass.MEASUREMENT
        assert eev.entity_description.native_unit_of_measurement == "pulses"
        assert eev.entity_description.entity_category == EntityCategory.DIAGNOSTIC
        assert eev.entity_description.icon == "mdi:valve"
        eev.update_entity_attributes()
        assert eev.native_value == 250

        # Check Energized time
        energized = sensor_keys["energized_hours"]
        assert energized.entity_description.name == "Energized time"
        assert energized.entity_description.device_class == SensorDeviceClass.DURATION
        assert energized.entity_description.state_class == SensorStateClass.TOTAL_INCREASING
        assert energized.entity_description.native_unit_of_measurement == UnitOfTime.HOURS
        assert energized.entity_description.entity_category == EntityCategory.DIAGNOSTIC
        assert energized.entity_description.icon == "mdi:clock-outline"
        energized.update_entity_attributes()
        assert energized.native_value == 1200

        # Check Operating time
        operating = sensor_keys["operating_hours"]
        assert operating.entity_description.name == "Operating time"
        assert operating.entity_description.device_class == SensorDeviceClass.DURATION
        assert operating.entity_description.state_class == SensorStateClass.TOTAL_INCREASING
        assert operating.entity_description.native_unit_of_measurement == UnitOfTime.HOURS
        assert operating.entity_description.entity_category == EntityCategory.DIAGNOSTIC
        operating.update_entity_attributes()
        assert operating.native_value == 800

        # Check Fan operating time
        fan_op = sensor_keys["fan_operating_hours"]
        assert fan_op.entity_description.name == "Fan operating time"
        assert fan_op.entity_description.device_class == SensorDeviceClass.DURATION
        assert fan_op.entity_description.state_class == SensorStateClass.TOTAL_INCREASING
        assert fan_op.entity_description.native_unit_of_measurement == UnitOfTime.HOURS
        assert fan_op.entity_description.entity_category == EntityCategory.DIAGNOSTIC
        assert fan_op.entity_description.icon == "mdi:fan-clock"
        fan_op.update_entity_attributes()
        assert fan_op.native_value == 950

    async def test_p1p2_outdoor_sensors_created_when_data_valid(
        self, daikin_client: DaikinOne, data: DaikinOneData
    ) -> None:
        device_data = _make_device(P1P2_OUTDOOR_DATA_VALID)
        entities = await _setup_sensors(daikin_client, data, device_data)

        outdoor_sensors = [
            e
            for e in entities
            if isinstance(e, DaikinOneEquipmentSensor) and isinstance(e._device, DaikinP1P2OutdoorUnit)
        ]

        sensor_keys = {s.entity_description.key: s for s in outdoor_sensors}

        # compressor_2 and fan_2 were None, so 10 out of 12 sensors created
        assert len(outdoor_sensors) == 10
        assert "compressor_2_operating_hours" not in sensor_keys
        assert "fan_2_operating_hours" not in sensor_keys

        # Check names in Sentence case
        assert sensor_keys["air_temperature"].entity_description.name == "Air temperature"
        assert sensor_keys["heat_exchanger_temperature"].entity_description.name == "Heat exchanger temperature"
        assert sensor_keys["gas_pipe_temperature"].entity_description.name == "Gas pipe temperature"
        assert sensor_keys["deicer_temperature"].entity_description.name == "Deicer temperature"
        assert sensor_keys["discharge_pipe_temperature"].entity_description.name == "Discharge pipe temperature"
        assert sensor_keys["liquid_pipe_temperature"].entity_description.name == "Liquid pipe temperature"
        assert sensor_keys["eev_open_pulses"].entity_description.name == "EEV open pulses"
        assert sensor_keys["operating_hours"].entity_description.name == "Operating time"
        assert sensor_keys["compressor_1_operating_hours"].entity_description.name == "Compressor 1 operating time"
        assert sensor_keys["fan_1_operating_hours"].entity_description.name == "Fan 1 operating time"

        # Check attribute values
        sensor_keys["air_temperature"].update_entity_attributes()
        assert sensor_keys["air_temperature"].native_value == 25.0
        sensor_keys["compressor_1_operating_hours"].update_entity_attributes()
        assert sensor_keys["compressor_1_operating_hours"].native_value == 1400

    async def test_p1p2_outdoor_zero_sensors_when_data_invalid_rx24(
        self, daikin_client: DaikinOne, data: DaikinOneData
    ) -> None:
        device_data = _make_device(P1P2_OUTDOOR_DATA_INVALID_RX24)
        entities = await _setup_sensors(daikin_client, data, device_data)

        # Outdoor unit device exists in equipment
        thermostat = daikin_client.get_thermostats()["device123"]
        assert any(isinstance(e, DaikinP1P2OutdoorUnit) for e in thermostat.equipment.values())

        # But 0 sensors are spawned for this outdoor unit
        outdoor_sensors = [
            e
            for e in entities
            if isinstance(e, DaikinOneEquipmentSensor) and isinstance(e._device, DaikinP1P2OutdoorUnit)
        ]
        assert len(outdoor_sensors) == 0
