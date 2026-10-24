"""Tests for Daikin One schedule hold status and override resume time sensors."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor.const import SensorDeviceClass

from custom_components.daikinone import DaikinOneData
from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.models import (
    DaikinThermostat,
    DaikinThermostatCapability,
    DaikinThermostatFanMode,
    DaikinThermostatFanSpeed,
    DaikinThermostatMode,
    DaikinThermostatSchedule,
    DaikinThermostatStatus,
    DaikinUserCredentials,
)
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.sensor import (
    DaikinOneScheduleResumeTimeSensor,
    DaikinOneScheduleStatusSensor,
    async_setup_entry,
)
from custom_components.daikinone.utils import Temperature


def _create_mock_thermostat(**kwargs) -> DaikinThermostat:
    defaults = {
        "id": "device123",
        "location_id": "loc456",
        "name": "Test Thermostat",
        "model": "ONEPLUS",
        "firmware_version": "1.0.0",
        "online": True,
        "capabilities": {
            DaikinThermostatCapability.HEAT,
            DaikinThermostatCapability.COOL,
        },
        "mode": DaikinThermostatMode.HEAT,
        "status": DaikinThermostatStatus.IDLE,
        "fan_mode": DaikinThermostatFanMode.OFF,
        "fan_speed": DaikinThermostatFanSpeed.LOW,
        "schedule": DaikinThermostatSchedule(enabled=True, override=False),
        "indoor_temperature": Temperature.from_celsius(20.0),
        "indoor_humidity": 45,
        "set_point_heat": Temperature.from_celsius(19.0),
        "set_point_heat_min": Temperature.from_celsius(10.0),
        "set_point_heat_max": Temperature.from_celsius(30.0),
        "set_point_cool": Temperature.from_celsius(24.0),
        "set_point_cool_min": Temperature.from_celsius(18.0),
        "set_point_cool_max": Temperature.from_celsius(32.0),
        "outdoor_temperature": Temperature.from_celsius(15.0),
        "outdoor_humidity": 60,
        "air_quality_outdoor": None,
        "air_quality_indoor": None,
        "equipment": {},
        "sched_resume_time": None,
        "sched_override_duration": None,
    }
    defaults.update(kwargs)
    return DaikinThermostat(**defaults)


@pytest.fixture
def daikin_client() -> DaikinOne:
    creds = DaikinUserCredentials(email="test@example.com", password="password")
    client = DaikinOne(creds)
    client._DaikinOne__thermostats.clear()  # type: ignore[attr-defined]
    return client


@pytest.fixture
def data_v1(daikin_client: DaikinOne) -> DaikinOneData:
    entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 1})
    return DaikinOneData(_hass=None, entry=entry, daikin=daikin_client)  # type: ignore[arg-type]


@pytest.fixture
def data_v0(daikin_client: DaikinOne) -> DaikinOneData:
    entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 0})
    return DaikinOneData(_hass=None, entry=entry, daikin=daikin_client)  # type: ignore[arg-type]


class TestScheduleStatusSensor:
    def test_metadata_and_schema_v1_uid(self, data_v1: DaikinOneData) -> None:
        thermostat = _create_mock_thermostat()
        sensor = DaikinOneScheduleStatusSensor(data=data_v1, device=thermostat)

        assert sensor.unique_id == "device123-schedule_status"
        assert sensor.entity_description.key == "schedule_status"
        assert sensor.entity_description.name == "Schedule status"
        assert sensor.entity_description.device_class == SensorDeviceClass.ENUM
        assert sensor.entity_description.entity_category is None
        assert sensor.entity_description.options == [
            "using_schedule",
            "temporary_hold",
            "permanent_hold",
        ]

    def test_schema_v0_uid(self, data_v0: DaikinOneData) -> None:
        thermostat = _create_mock_thermostat()
        sensor = DaikinOneScheduleStatusSensor(data=data_v0, device=thermostat)

        assert sensor.unique_id == "device123-Schedule Status"

    def test_using_schedule_state_and_icon(self, data_v1: DaikinOneData) -> None:
        thermostat = _create_mock_thermostat(schedule=DaikinThermostatSchedule(enabled=True, override=False))
        sensor = DaikinOneScheduleStatusSensor(data=data_v1, device=thermostat)

        assert sensor.native_value == "using_schedule"
        assert sensor.icon == "mdi:calendar-check"

    def test_temporary_hold_state_and_icon(self, data_v1: DaikinOneData) -> None:
        thermostat = _create_mock_thermostat(schedule=DaikinThermostatSchedule(enabled=True, override=True))
        sensor = DaikinOneScheduleStatusSensor(data=data_v1, device=thermostat)

        assert sensor.native_value == "temporary_hold"
        assert sensor.icon == "mdi:calendar-clock"

    def test_permanent_hold_when_schedule_disabled(self, data_v1: DaikinOneData) -> None:
        # Permanent hold whether override flag is True or False if enabled is False
        thermostat = _create_mock_thermostat(schedule=DaikinThermostatSchedule(enabled=False, override=False))
        sensor = DaikinOneScheduleStatusSensor(data=data_v1, device=thermostat)

        assert sensor.native_value == "permanent_hold"
        assert sensor.icon == "mdi:calendar-remove"

        thermostat_override_false = _create_mock_thermostat(
            schedule=DaikinThermostatSchedule(enabled=False, override=True)
        )
        sensor_override_false = DaikinOneScheduleStatusSensor(data=data_v1, device=thermostat_override_false)

        assert sensor_override_false.native_value == "permanent_hold"
        assert sensor_override_false.icon == "mdi:calendar-remove"

    async def test_async_get_device(self, data_v1: DaikinOneData, daikin_client: DaikinOne) -> None:
        thermostat = _create_mock_thermostat()
        daikin_client.get_thermostat = MagicMock(return_value=thermostat)  # type: ignore[method-assign]
        sensor = DaikinOneScheduleStatusSensor(data=data_v1, device=thermostat)

        dev = await sensor.async_get_device()
        assert dev.id == "device123"


class TestScheduleResumeTimeSensor:
    def test_metadata_and_schema_v1_uid(self, data_v1: DaikinOneData) -> None:
        thermostat = _create_mock_thermostat()
        sensor = DaikinOneScheduleResumeTimeSensor(data=data_v1, device=thermostat)

        assert sensor.unique_id == "device123-schedule_resume_time"
        assert sensor.entity_description.key == "schedule_resume_time"
        assert sensor.entity_description.name == "Schedule resume time"
        assert sensor.entity_description.device_class == SensorDeviceClass.TIMESTAMP
        assert sensor.entity_description.entity_category is None
        assert sensor.icon == "mdi:clock-end"

    def test_schema_v0_uid(self, data_v0: DaikinOneData) -> None:
        thermostat = _create_mock_thermostat()
        sensor = DaikinOneScheduleResumeTimeSensor(data=data_v0, device=thermostat)

        assert sensor.unique_id == "device123-Schedule Override Resume Time"

    def test_active_override_returns_timestamp(self, data_v1: DaikinOneData) -> None:
        resume_dt = datetime(2026, 10, 24, 18, 0, 0, tzinfo=timezone.utc)
        thermostat = _create_mock_thermostat(
            schedule=DaikinThermostatSchedule(enabled=True, override=True),
            sched_resume_time=resume_dt,
        )
        sensor = DaikinOneScheduleResumeTimeSensor(data=data_v1, device=thermostat)

        assert sensor.native_value == resume_dt

    def test_no_override_returns_none(self, data_v1: DaikinOneData) -> None:
        resume_dt = datetime(2026, 10, 24, 18, 0, 0, tzinfo=timezone.utc)
        thermostat = _create_mock_thermostat(
            schedule=DaikinThermostatSchedule(enabled=True, override=False),
            sched_resume_time=resume_dt,
        )
        sensor = DaikinOneScheduleResumeTimeSensor(data=data_v1, device=thermostat)

        assert sensor.native_value is None

    def test_schedule_disabled_returns_none(self, data_v1: DaikinOneData) -> None:
        resume_dt = datetime(2026, 10, 24, 18, 0, 0, tzinfo=timezone.utc)
        thermostat = _create_mock_thermostat(
            schedule=DaikinThermostatSchedule(enabled=False, override=True),
            sched_resume_time=resume_dt,
        )
        sensor = DaikinOneScheduleResumeTimeSensor(data=data_v1, device=thermostat)

        assert sensor.native_value is None

    def test_none_resume_time_returns_none(self, data_v1: DaikinOneData) -> None:
        thermostat = _create_mock_thermostat(
            schedule=DaikinThermostatSchedule(enabled=True, override=True),
            sched_resume_time=None,
        )
        sensor = DaikinOneScheduleResumeTimeSensor(data=data_v1, device=thermostat)

        assert sensor.native_value is None

    async def test_async_get_device(self, data_v1: DaikinOneData, daikin_client: DaikinOne) -> None:
        thermostat = _create_mock_thermostat()
        daikin_client.get_thermostat = MagicMock(return_value=thermostat)  # type: ignore[method-assign]
        sensor = DaikinOneScheduleResumeTimeSensor(data=data_v1, device=thermostat)

        dev = await sensor.async_get_device()
        assert dev.id == "device123"


class TestSensorAsyncSetupEntry:
    async def test_async_setup_entry_registers_schedule_sensors(
        self, data_v1: DaikinOneData, daikin_client: DaikinOne
    ) -> None:
        thermostat = _create_mock_thermostat()
        daikin_client.get_thermostats = MagicMock(return_value={"device123": thermostat})  # type: ignore[method-assign]

        hass = MagicMock()
        hass.data = {"daikinone": data_v1}
        entry = MagicMock()
        added_entities: list = []

        def add_entities_callback(entities: list, update_before_add: bool = False) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, entry, add_entities_callback)

        status_sensors = [e for e in added_entities if isinstance(e, DaikinOneScheduleStatusSensor)]
        resume_sensors = [e for e in added_entities if isinstance(e, DaikinOneScheduleResumeTimeSensor)]

        assert len(status_sensors) == 1
        assert len(resume_sensors) == 1
        assert status_sensors[0].unique_id == "device123-schedule_status"
        assert resume_sensors[0].unique_id == "device123-schedule_resume_time"
