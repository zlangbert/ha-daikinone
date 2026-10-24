from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.binary_sensor import (
    CONSUMABLE_ALERT_CONFIGS,
    DaikinOneConsumableAlertBinarySensor,
    async_setup_entry as async_setup_binary_sensors,
)
from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.models import DaikinThermostat, DaikinUserCredentials
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.sensor import (
    CONSUMABLE_SENSOR_CONFIGS,
    DaikinOneConsumableLifeSensor,
    async_setup_entry as async_setup_sensors,
)
from tests.test_mapping import _make_device


@pytest.fixture
def daikin_client() -> DaikinOne:
    client = DaikinOne(DaikinUserCredentials(email="test@example.com", password="test"))
    client._DaikinOne__thermostats.clear()  # type: ignore[attr-defined]
    return client


@pytest.fixture
def data(daikin_client: DaikinOne) -> DaikinOneData:
    entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 1})
    return DaikinOneData(_hass=None, entry=entry, daikin=daikin_client)  # type: ignore[arg-type]


async def _refresh(daikin_client: DaikinOne, payload: dict[str, Any]) -> DaikinThermostat:
    with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = [payload]
        await daikin_client.update()
    return daikin_client.get_thermostats()["device123"]


def _consumable_payload(**updates: Any) -> dict[str, Any]:
    data = {
        "NumMediafilters": 1,
        "alertMediaAirFilterDays": 30,
        "alertMediaAirFilterDaysLimit": 90,
        "alertMediaAirFilterRuntime": 100,
        "alertMediaAirFilterRuntimeLimit": 400,
        "alertMediaAirFilterActive": "false",
        "alertMediaAirFilterDate": 0,
    }
    data.update(updates)
    return _make_device(data)


class TestConsumableMapping:
    async def test_alert_fields_are_normalized(self, daikin_client: DaikinOne) -> None:
        thermostat = await _refresh(
            daikin_client,
            _consumable_payload(
                AuxDehumidifierStatus="false",
                alertMediaAirFilterActive="true",
                alertMediaAirFilterDate=0,
            ),
        )

        assert thermostat.num_media_filters == 1
        assert thermostat.aux_dehumidifier_status is False
        assert thermostat.media_air_filter_active is True
        assert thermostat.media_air_filter_date is None
        assert thermostat.media_air_filter_days == 30
        assert thermostat.media_air_filter_days_limit == 90
        assert thermostat.media_air_filter_runtime == 100
        assert thermostat.media_air_filter_runtime_limit == 400

    async def test_sentinel_inventory_and_alert_values_are_unavailable(self, daikin_client: DaikinOne) -> None:
        thermostat = await _refresh(
            daikin_client,
            _consumable_payload(
                NumMediafilters=255,
                alertMediaAirFilterDays=65535,
                alertMediaAirFilterRuntime=-32768,
                alertMediaAirFilterActive=255,
                alertMediaAirFilterDate="0",
            ),
        )

        assert thermostat.num_media_filters is None
        assert thermostat.media_air_filter_days is None
        assert thermostat.media_air_filter_runtime is None
        assert thermostat.media_air_filter_active is None
        assert thermostat.media_air_filter_date is None


class TestConsumableEntities:
    async def test_life_percentage_and_binary_due_threshold(
        self, daikin_client: DaikinOne, data: DaikinOneData
    ) -> None:
        thermostat = await _refresh(daikin_client, _consumable_payload())
        life_config = CONSUMABLE_SENSOR_CONFIGS[0]
        alert_config = CONSUMABLE_ALERT_CONFIGS[0]

        life = DaikinOneConsumableLifeSensor(
            description=life_config.description,
            data=data,
            thermostat=thermostat,
            days_key=life_config.days_key,
            limit_key=life_config.limit_key,
            runtime_key=life_config.runtime_key,
            runtime_limit_key=life_config.runtime_limit_key,
        )
        alert = DaikinOneConsumableAlertBinarySensor(
            description=alert_config.description,
            data=data,
            thermostat=thermostat,
            active_key=alert_config.active_key,
            days_key=alert_config.days_key,
            limit_key=alert_config.limit_key,
            runtime_key=alert_config.runtime_key,
            runtime_limit_key=alert_config.runtime_limit_key,
        )

        assert life.native_value == 66.7
        assert life.extra_state_attributes == {
            "days_used": 30,
            "days_limit": 90,
            "days_remaining": 60,
            "runtime_hours_used": 100,
            "runtime_hours_limit": 400,
        }
        assert alert.is_on is False

        due = await _refresh(
            daikin_client,
            _consumable_payload(alertMediaAirFilterDays=90),
        )
        alert._device = due
        alert.update_entity_attributes()
        assert alert.is_on is True

    async def test_sentinel_inventory_blocks_consumable_entity_creation(
        self, daikin_client: DaikinOne, data: DaikinOneData
    ) -> None:
        await _refresh(daikin_client, _consumable_payload(NumMediafilters=255))
        hass = SimpleNamespace(data={DOMAIN: data})
        sensors: list[object] = []
        binary_sensors: list[object] = []

        await async_setup_sensors(
            hass,
            data.entry,
            lambda entities, _: sensors.extend(entities),  # type: ignore[arg-type]
        )
        await async_setup_binary_sensors(
            hass,
            data.entry,
            lambda entities, _: binary_sensors.extend(entities),  # type: ignore[arg-type]
        )

        assert not any(isinstance(entity, DaikinOneConsumableLifeSensor) for entity in sensors)
        assert not any(isinstance(entity, DaikinOneConsumableAlertBinarySensor) for entity in binary_sensors)
