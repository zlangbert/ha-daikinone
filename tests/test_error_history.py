from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.sensor import SensorEntityDescription

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.mapping import (
    MAX_VALID_EPOCH_TIMESTAMP,
    MIN_VALID_EPOCH_TIMESTAMP,
    map_equipment_errors,
    map_system_errors,
)
from custom_components.daikinone.client.models import DaikinThermostat, DaikinUserCredentials, format_error_code
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.sensor import (
    ACTION_PROMPT_MESSAGE,
    DaikinOneEquipmentErrorHistorySensor,
    DaikinOneSystemErrorHistorySensor,
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


def _fault_payload(**updates: Any) -> dict[str, Any]:
    return _make_device(updates)


async def _refresh(daikin_client: DaikinOne, payload: dict[str, Any]) -> DaikinThermostat:
    with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = [payload]
        await daikin_client.update()
    return daikin_client.get_thermostats()["device123"]


def _epoch(year: int, month: int, day: int, hour: int, minute: int, second: int) -> int:
    return int(datetime(year, month, day, hour, minute, second, tzinfo=UTC).timestamp())


class TestErrorHistoryMapping:
    def test_equipment_errors_reject_invalid_codes_dates_and_metadata(self) -> None:
        errors = map_equipment_errors(
            {
                "fault1Code": 20,
                "fault1Date": _epoch(2026, 10, 16, 5, 25, 43),
                "fault1Level": 3,
                "fault1Equipment": 256,
                "fault2Code": True,
                "fault2Date": _epoch(2026, 10, 16, 5, 25, 43),
                "fault3Code": 256,
                "fault3Date": _epoch(2026, 10, 16, 5, 25, 43),
                "fault4Code": 20,
                "fault4Date": 4_294_967_295,
                "fault5Code": 20,
                "fault5Date": MAX_VALID_EPOCH_TIMESTAMP + 1,
                "fault6Code": 20,
                "fault6Date": True,
            }
        )

        assert len(errors) == 1
        assert errors[0].level is None
        assert errors[0].equipment_id is None
        assert errors[0].severity == "minor"

    def test_system_errors_reject_invalid_codes_and_dates(self) -> None:
        errors = map_system_errors(
            {
                "sysFault1Code": 16,
                "sysFault1Date": 4_294_967_295,
                "sysFault2Code": True,
                "sysFault2Date": _epoch(2026, 10, 16, 5, 25, 43),
                "sysFault3Code": -1,
                "sysFault3Date": _epoch(2026, 10, 16, 5, 25, 43),
                "sysFault4Code": 16,
                "sysFault4Date": MAX_VALID_EPOCH_TIMESTAMP + 1,
                "sysFault5Code": 16,
                "sysFault5Date": True,
            }
        )

        assert errors == []

    def test_error_mapping_clamps_negative_entry_limit(self) -> None:
        assert map_equipment_errors({}, max_entries=-1) == []
        assert map_system_errors({}, max_entries=-1) == []

    async def test_equipment_errors_are_valid_sorted_and_limited(self, daikin_client: DaikinOne) -> None:
        thermostat = await _refresh(
            daikin_client,
            _fault_payload(
                fault1Code=20,
                fault1Date=_epoch(2026, 10, 16, 5, 25, 43),
                fault1Level=1,
                fault1Equipment=6,
                fault2Code=180,
                fault2Date=_epoch(2026, 10, 16, 6, 25, 43),
                fault2Level=2,
                fault2Equipment=3,
                fault3Code=236,
                fault3Date=_epoch(2026, 10, 16, 7, 25, 43),
                fault3Level=2,
                fault3Equipment=3,
                fault4Code=10,
                fault4Date=22,
                fault5Code=255,
                fault5Date=_epoch(2026, 10, 16, 8, 25, 43),
                fault6Code=True,
                fault6Date=_epoch(2026, 10, 16, 9, 25, 43),
                fault7Code=20,
                fault7Date=4_294_967_295,
                fault7Level=1,
                fault7Equipment=1,
            ),
        )

        assert thermostat.equipment_errors is not None
        assert [error.code for error in thermostat.equipment_errors] == ["EC", "B4", "14"]
        assert [error.raw_code for error in thermostat.equipment_errors] == [236, 180, 20]
        assert [error.severity for error in thermostat.equipment_errors] == ["critical", "critical", "minor"]
        assert [error.level for error in thermostat.equipment_errors] == [2, 2, 1]
        assert [error.equipment_id for error in thermostat.equipment_errors] == [3, 3, 6]
        assert thermostat.equipment_errors[2].timestamp == datetime(2026, 10, 16, 5, 25, 43, tzinfo=UTC)

    async def test_system_errors_filter_pre_ntp_and_return_latest_three(self, daikin_client: DaikinOne) -> None:
        thermostat = await _refresh(
            daikin_client,
            _fault_payload(
                sysFault1Code=16,
                sysFault1Date=_epoch(2026, 7, 20, 20, 23, 40),
                sysFault2Code=5,
                sysFault2Date=_epoch(2026, 7, 19, 20, 23, 40),
                sysFault3Code=16,
                sysFault3Date=_epoch(2026, 7, 18, 20, 23, 40),
                sysFault4Code=5,
                sysFault4Date=_epoch(2026, 7, 17, 20, 23, 40),
                sysFault5Code=1,
                sysFault5Date=22,
            ),
        )

        assert thermostat.system_errors is not None
        assert [error.code for error in thermostat.system_errors] == ["10", "05", "10"]
        assert [error.raw_code for error in thermostat.system_errors] == [16, 5, 16]
        assert thermostat.system_errors[0].timestamp == datetime(2026, 7, 20, 20, 23, 40, tzinfo=UTC)

    async def test_empty_history_is_an_empty_list(self, daikin_client: DaikinOne) -> None:
        thermostat = await _refresh(daikin_client, _fault_payload())

        assert thermostat.equipment_errors == []
        assert thermostat.system_errors == []

    def test_fault_code_format_rejects_sentinels_and_out_of_range_values(self) -> None:
        assert format_error_code(10) == "0A"
        assert format_error_code(180) == "B4"
        assert format_error_code(0) is None
        assert format_error_code(255) is None
        assert format_error_code(-1) is None
        assert format_error_code(256) is None
        assert format_error_code(True) is None
        assert MIN_VALID_EPOCH_TIMESTAMP == 1_000_000_000
        assert MAX_VALID_EPOCH_TIMESTAMP == 253_402_300_799


class TestErrorHistorySensors:
    async def test_setup_registers_both_diagnostic_sensors(self, daikin_client: DaikinOne, data: DaikinOneData) -> None:
        await _refresh(daikin_client, _fault_payload())
        hass = SimpleNamespace(data={DOMAIN: data})
        entities: list[object] = []

        await async_setup_sensors(
            hass,
            data.entry,
            lambda new_entities, _: entities.extend(new_entities),  # type: ignore[arg-type]
        )

        assert sum(isinstance(entity, DaikinOneEquipmentErrorHistorySensor) for entity in entities) == 1
        assert sum(isinstance(entity, DaikinOneSystemErrorHistorySensor) for entity in entities) == 1

    async def test_sensor_states_attributes_and_schema_v1_unique_ids(
        self, daikin_client: DaikinOne, data: DaikinOneData
    ) -> None:
        thermostat = await _refresh(
            daikin_client,
            _fault_payload(
                fault1Code=180,
                fault1Date=_epoch(2026, 10, 16, 5, 25, 43),
                fault1Level=2,
                fault1Equipment=3,
                sysFault1Code=16,
                sysFault1Date=_epoch(2026, 7, 20, 20, 23, 40),
            ),
        )
        equipment_sensor = DaikinOneEquipmentErrorHistorySensor(
            description=SensorEntityDescription(
                key="last_equipment_error",
                name="Last equipment error",
                has_entity_name=True,
            ),
            data=data,
            device=thermostat,
        )
        system_sensor = DaikinOneSystemErrorHistorySensor(
            description=SensorEntityDescription(
                key="last_system_error",
                name="Last system error",
                has_entity_name=True,
            ),
            data=data,
            device=thermostat,
        )

        assert equipment_sensor.unique_id == "device123-last_equipment_error"
        assert equipment_sensor.native_value == datetime(2026, 10, 16, 5, 25, 43, tzinfo=UTC)
        assert equipment_sensor.extra_state_attributes == {
            "latest_code": "B4",
            "latest_raw_code": 180,
            "latest_severity": "critical",
            "latest_level": 2,
            "latest_equipment_id": 3,
            "recent_errors": [
                {
                    "timestamp": "2026-10-16T05:25:43+00:00",
                    "code": "B4",
                    "raw_code": 180,
                    "severity": "critical",
                    "level": 2,
                    "equipment_id": 3,
                }
            ],
            "action_prompt": ACTION_PROMPT_MESSAGE,
        }
        assert system_sensor.unique_id == "device123-last_system_error"
        assert system_sensor.native_value == datetime(2026, 7, 20, 20, 23, 40, tzinfo=UTC)
        assert system_sensor.extra_state_attributes["latest_code"] == "10"
        assert system_sensor.extra_state_attributes["recent_errors"] == [
            {
                "timestamp": "2026-07-20T20:23:40+00:00",
                "code": "10",
                "raw_code": 16,
            }
        ]
        assert system_sensor.extra_state_attributes["action_prompt"] == ACTION_PROMPT_MESSAGE

    async def test_empty_histories_have_unknown_state_and_schema_v0_unique_ids(
        self, daikin_client: DaikinOne, data: DaikinOneData
    ) -> None:
        thermostat = await _refresh(daikin_client, _fault_payload())
        data.entry.data[CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY] = 0

        equipment_sensor = DaikinOneEquipmentErrorHistorySensor(
            description=SensorEntityDescription(
                key="last_equipment_error",
                name="Last equipment error",
                has_entity_name=True,
            ),
            data=data,
            device=thermostat,
        )
        system_sensor = DaikinOneSystemErrorHistorySensor(
            description=SensorEntityDescription(
                key="last_system_error",
                name="Last system error",
                has_entity_name=True,
            ),
            data=data,
            device=thermostat,
        )

        assert equipment_sensor.native_value is None
        assert equipment_sensor.extra_state_attributes["recent_errors"] == []
        assert equipment_sensor.unique_id.endswith("-Last equipment error")
        assert system_sensor.native_value is None
        assert system_sensor.extra_state_attributes["recent_errors"] == []
        assert system_sensor.unique_id.endswith("-Last system error")
