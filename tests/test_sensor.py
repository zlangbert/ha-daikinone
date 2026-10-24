"""Tests for Daikin One heat source sensor."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.core import HomeAssistant

from custom_components.daikinone import DaikinOneData
from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.models import (
    DaikinHeatSource,
    DaikinIndoorUnit,
    DaikinThermostat,
    DaikinThermostatCapability,
    DaikinThermostatFanMode,
    DaikinThermostatFanSpeed,
    DaikinThermostatMode,
    DaikinThermostatSchedule,
    DaikinThermostatStatus,
)
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.sensor import DaikinOneHeatSourceSensor, async_setup_entry
from custom_components.daikinone.utils import Temperature


def _create_mock_thermostat(
    capabilities: set[DaikinThermostatCapability] | None = None,
    status: DaikinThermostatStatus = DaikinThermostatStatus.IDLE,
    mode: DaikinThermostatMode = DaikinThermostatMode.HEAT,
    equipment: dict | None = None,
) -> DaikinThermostat:
    return DaikinThermostat(
        id="device123",
        location_id="loc456",
        name="Living Room",
        model="ONEPLUS",
        firmware_version="1.0.0",
        online=True,
        capabilities=capabilities if capabilities is not None else {DaikinThermostatCapability.HEAT},
        mode=mode,
        status=status,
        fan_mode=DaikinThermostatFanMode.OFF,
        fan_speed=DaikinThermostatFanSpeed.LOW,
        schedule=DaikinThermostatSchedule(enabled=True),
        indoor_temperature=Temperature.from_celsius(21.0),
        indoor_humidity=45,
        set_point_heat=Temperature.from_celsius(20.0),
        set_point_heat_min=Temperature.from_celsius(10.0),
        set_point_heat_max=Temperature.from_celsius(30.0),
        set_point_cool=Temperature.from_celsius(24.0),
        set_point_cool_min=Temperature.from_celsius(18.0),
        set_point_cool_max=Temperature.from_celsius(32.0),
        outdoor_temperature=Temperature.from_celsius(10.0),
        outdoor_humidity=60,
        air_quality_outdoor=None,
        air_quality_indoor=None,
        equipment=equipment if equipment is not None else {},
    )


def _heat_source_description() -> SensorEntityDescription:
    return SensorEntityDescription(
        key="heat_source",
        name="Heat source",
        translation_key="heat_source",
        has_entity_name=True,
        device_class=SensorDeviceClass.ENUM,
        options=[s.value for s in DaikinHeatSource],
    )


class TestHeatSourceSensor:
    """Tests for DaikinOneHeatSourceSensor."""

    async def test_sensor_metadata_and_options(self) -> None:
        entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 1})
        client = MagicMock(spec=DaikinOne)
        data = DaikinOneData(_hass=None, entry=entry, daikin=client)  # type: ignore[arg-type]
        thermostat = _create_mock_thermostat()

        sensor = DaikinOneHeatSourceSensor(_heat_source_description(), data, thermostat)
        assert sensor.entity_description.key == "heat_source"
        assert sensor.entity_description.name == "Heat source"
        assert sensor.entity_description.device_class == SensorDeviceClass.ENUM
        assert sensor.entity_description.options == ["none", "heat_pump", "gas", "resistive"]

    async def test_schema_v0_unique_id(self) -> None:
        entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 0})
        client = MagicMock(spec=DaikinOne)
        data = DaikinOneData(_hass=None, entry=entry, daikin=client)  # type: ignore[arg-type]
        thermostat = _create_mock_thermostat()

        sensor = DaikinOneHeatSourceSensor(_heat_source_description(), data, thermostat)
        assert sensor.unique_id == "device123-Heat source"

    async def test_schema_v1_unique_id(self) -> None:
        entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 1})
        client = MagicMock(spec=DaikinOne)
        data = DaikinOneData(_hass=None, entry=entry, daikin=client)  # type: ignore[arg-type]
        thermostat = _create_mock_thermostat()

        sensor = DaikinOneHeatSourceSensor(_heat_source_description(), data, thermostat)
        assert sensor.unique_id == "device123-heat_source"

    async def test_native_value_updates(self) -> None:
        entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 1})
        client = MagicMock(spec=DaikinOne)
        data = DaikinOneData(_hass=None, entry=entry, daikin=client)  # type: ignore[arg-type]

        furnace = DaikinIndoorUnit(
            id="IFC-123",
            thermostat_id="device123",
            name="Furnace",
            model="IFC",
            firmware_version="1.0",
            serial="IFC-SER",
            mode="Heating",
            current_airflow=450,
            fan_demand_requested_percent=None,
            fan_demand_current_percent=None,
            heat_demand_requested_percent=100,
            heat_demand_current_percent=80,
            cool_demand_requested_percent=None,
            cool_demand_current_percent=None,
            humidification_demand_requested_percent=None,
            dehumidification_demand_requested_percent=None,
            power_usage=None,
        )
        thermostat = _create_mock_thermostat(
            status=DaikinThermostatStatus.HEATING,
            equipment={"furnace": furnace},
        )

        sensor = DaikinOneHeatSourceSensor(_heat_source_description(), data, thermostat)
        sensor.update_entity_attributes()
        assert sensor.native_value == "gas"

    async def test_async_setup_entry_heat_gating(self) -> None:
        """Verify heat source sensor is only added when heat capability is present."""
        entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 1})
        client = MagicMock(spec=DaikinOne)

        t_heat = _create_mock_thermostat(capabilities={DaikinThermostatCapability.HEAT})
        t_cool_only = _create_mock_thermostat(capabilities={DaikinThermostatCapability.COOL})
        t_cool_only.id = "cool_only"

        client.get_thermostats.return_value = {"device123": t_heat, "cool_only": t_cool_only}
        data = DaikinOneData(_hass=None, entry=entry, daikin=client)  # type: ignore[arg-type]

        hass = MagicMock(spec=HomeAssistant)
        hass.data = {"daikinone": data}

        added_entities = []

        def async_add_entities(entities: list, update_before_add: bool = False) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, entry, async_add_entities)  # type: ignore[arg-type]

        heat_source_entities = [e for e in added_entities if isinstance(e, DaikinOneHeatSourceSensor)]
        assert len(heat_source_entities) == 1
        assert heat_source_entities[0]._device.id == "device123"
