"""Tests for Daikin One climate platform and native HVAC actions."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from homeassistant.components.climate import ClimateEntityDescription
from homeassistant.components.climate.const import (
    HVACAction,
)

from custom_components.daikinone import DaikinOneData
from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.models import (
    DaikinIndoorUnit,
    DaikinOutdoorUnit,
    DaikinOutdoorUnitHeaterStatus,
    DaikinOutdoorUnitReversingValveStatus,
    DaikinThermostat,
    DaikinThermostatCapability,
    DaikinThermostatFanMode,
    DaikinThermostatFanSpeed,
    DaikinThermostatMode,
    DaikinThermostatSchedule,
    DaikinThermostatStatus,
)
from custom_components.daikinone.climate import DaikinOneThermostat
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.utils import Temperature


def _create_outdoor_unit(
    mode: str | None = None,
    compressor_speed: int = 0,
    heat_demand: int = 0,
) -> DaikinOutdoorUnit:
    return DaikinOutdoorUnit(
        id="OD-123",
        thermostat_id="device123",
        name="Heat Pump",
        model="OD-MODEL",
        serial="OD-SERIAL",
        firmware_version="1.0.0",
        inverter_software_version="1.0.0",
        total_runtime=None,
        mode=mode,
        compressor_speed_target=compressor_speed,
        compressor_speed_current=compressor_speed,
        outdoor_fan_target_rpm=None,
        outdoor_fan_rpm=None,
        suction_pressure_psi=None,
        eev_opening_percent=None,
        reversing_valve=DaikinOutdoorUnitReversingValveStatus.UNKNOWN,
        heat_demand_percent=heat_demand,
        cool_demand_percent=None,
        fan_demand_percent=None,
        fan_demand_airflow=None,
        dehumidify_demand_percent=None,
        air_temperature=None,
        coil_temperature=None,
        discharge_temperature=None,
        liquid_temperature=None,
        defrost_sensor_temperature=None,
        inverter_fin_temperature=None,
        power_usage=None,
        compressor_amps=None,
        inverter_amps=None,
        fan_motor_amps=None,
        crank_case_heater=DaikinOutdoorUnitHeaterStatus.UNKNOWN,
        drain_pan_heater=DaikinOutdoorUnitHeaterStatus.UNKNOWN,
        preheat_heater=DaikinOutdoorUnitHeaterStatus.UNKNOWN,
    )


def _create_indoor_unit(
    airflow: int = 0,
    heat_demand: int = 0,
) -> DaikinIndoorUnit:
    return DaikinIndoorUnit(
        id="AH-123",
        thermostat_id="device123",
        name="Air Handler",
        model="AH-MODEL",
        firmware_version="1.0.0",
        serial="AH-SERIAL",
        mode=None,
        current_airflow=airflow,
        fan_demand_requested_percent=None,
        fan_demand_current_percent=None,
        heat_demand_requested_percent=heat_demand,
        heat_demand_current_percent=heat_demand,
        cool_demand_requested_percent=None,
        cool_demand_current_percent=None,
        humidification_demand_requested_percent=None,
        dehumidification_demand_requested_percent=None,
        power_usage=None,
    )


def _create_mock_thermostat(
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
        capabilities={DaikinThermostatCapability.HEAT, DaikinThermostatCapability.COOL},
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


@pytest.fixture
def mock_data() -> DaikinOneData:
    entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 1})
    client = MagicMock(spec=DaikinOne)
    data = DaikinOneData(_hass=None, entry=entry, daikin=client)  # type: ignore[arg-type]
    return data


def _climate_desc() -> ClimateEntityDescription:
    return ClimateEntityDescription(key="device123", has_entity_name=True, name=None)


class TestClimateHVACAction:
    """Test native HVAC actions on DaikinOneThermostat."""

    async def test_hvac_action_idle(self, mock_data: DaikinOneData) -> None:
        t = _create_mock_thermostat(status=DaikinThermostatStatus.IDLE)
        climate = DaikinOneThermostat(_climate_desc(), mock_data, t)
        climate.update_entity_attributes()
        assert climate.hvac_action == HVACAction.IDLE

    async def test_hvac_action_cooling(self, mock_data: DaikinOneData) -> None:
        t = _create_mock_thermostat(status=DaikinThermostatStatus.COOLING)
        climate = DaikinOneThermostat(_climate_desc(), mock_data, t)
        climate.update_entity_attributes()
        assert climate.hvac_action == HVACAction.COOLING

    async def test_hvac_action_drying(self, mock_data: DaikinOneData) -> None:
        t = _create_mock_thermostat(status=DaikinThermostatStatus.DRYING)
        climate = DaikinOneThermostat(_climate_desc(), mock_data, t)
        climate.update_entity_attributes()
        assert climate.hvac_action == HVACAction.DRYING

    async def test_hvac_action_fan(self, mock_data: DaikinOneData) -> None:
        t = _create_mock_thermostat(status=DaikinThermostatStatus.CIRCULATING_AIR)
        climate = DaikinOneThermostat(_climate_desc(), mock_data, t)
        climate.update_entity_attributes()
        assert climate.hvac_action == HVACAction.FAN

    async def test_hvac_action_heating(self, mock_data: DaikinOneData) -> None:
        od = _create_outdoor_unit(mode="Heating", compressor_speed=50, heat_demand=80)
        ah = _create_indoor_unit(airflow=450, heat_demand=80)
        t = _create_mock_thermostat(
            status=DaikinThermostatStatus.HEATING,
            equipment={"od": od, "ah": ah},
        )
        climate = DaikinOneThermostat(_climate_desc(), mock_data, t)
        climate.update_entity_attributes()
        assert climate.hvac_action == HVACAction.HEATING

    async def test_hvac_action_defrosting(self, mock_data: DaikinOneData) -> None:
        od = _create_outdoor_unit(mode="Defrost", compressor_speed=60, heat_demand=100)
        ah = _create_indoor_unit(airflow=400, heat_demand=50)
        t = _create_mock_thermostat(
            status=DaikinThermostatStatus.HEATING,
            equipment={"od": od, "ah": ah},
        )
        climate = DaikinOneThermostat(_climate_desc(), mock_data, t)
        climate.update_entity_attributes()
        assert climate.hvac_action == HVACAction.DEFROSTING

    async def test_hvac_action_preheating_startup_mode(self, mock_data: DaikinOneData) -> None:
        od = _create_outdoor_unit(mode="Heating startup", compressor_speed=30, heat_demand=50)
        ah = _create_indoor_unit(airflow=0, heat_demand=50)
        t = _create_mock_thermostat(
            status=DaikinThermostatStatus.HEATING,
            equipment={"od": od, "ah": ah},
        )
        climate = DaikinOneThermostat(_climate_desc(), mock_data, t)
        climate.update_entity_attributes()
        assert climate.hvac_action == HVACAction.PREHEATING

    async def test_hvac_action_preheating_zero_airflow(self, mock_data: DaikinOneData) -> None:
        od = _create_outdoor_unit(mode="Heating", compressor_speed=30, heat_demand=50)
        ah = _create_indoor_unit(airflow=0, heat_demand=50)
        t = _create_mock_thermostat(
            status=DaikinThermostatStatus.HEATING,
            equipment={"od": od, "ah": ah},
        )
        climate = DaikinOneThermostat(_climate_desc(), mock_data, t)
        climate.update_entity_attributes()
        assert climate.hvac_action == HVACAction.PREHEATING
