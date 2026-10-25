"""Unit tests for DaikinOne client orchestration and P1/P2 fan mode write pipelines."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.models import (
    DaikinThermostatFanMode,
    DaikinUserCredentials,
)
from custom_components.daikinone.client.wire import DAIKIN_API_URL_DEVICE_DATA


@pytest.fixture
def daikin_client() -> DaikinOne:
    creds = DaikinUserCredentials(email="test@example.com", password="password")
    client = DaikinOne(creds)
    client._DaikinOne__thermostats.clear()  # type: ignore[attr-defined]
    return client


BASE_THERMOSTAT_DATA: dict[str, Any] = {
    "ctSystemCapHeat": True,
    "ctSystemCapCool": True,
    "ctSystemCapEmergencyHeat": False,
    "mode": 1,
    "equipmentStatus": 5,
    "fanCirculate": 0,
    "fanCirculateSpeed": 1,
    "schedEnabled": True,
    "tempIndoor": 20.0,
    "humIndoor": 45,
    "hspActive": 19.0,
    "EquipProtocolMinHeatSetpoint": 10.0,
    "EquipProtocolMaxHeatSetpoint": 30.0,
    "cspActive": 24.0,
    "EquipProtocolMinCoolSetpoint": 18.0,
    "EquipProtocolMaxCoolSetpoint": 32.0,
    "tempOutdoor": 15.0,
    "humOutdoor": 60,
    "aqOutdoorAvailable": False,
    "aqIndoorAvailable": False,
    "ctAHUnitType": 255,
    "ctIFCUnitType": 255,
    "ctOutdoorUnitType": 255,
    "ctCoilUnitType": 255,
}


def _make_unitary_device(device_id: str = "unitary123") -> dict[str, Any]:
    return {
        "id": device_id,
        "locationId": "loc1",
        "name": "Unitary Thermostat",
        "model": "ONEPLUS",
        "firmware": "1.0.0",
        "online": True,
        "data": dict(BASE_THERMOSTAT_DATA),
    }


def _make_p1p2_device(
    device_id: str = "p1p2_123",
    populated_units: int = 1,
    unit_type: int = 1,
    indoor_valid: bool = True,
    include_mode_num: bool = True,
) -> dict[str, Any]:
    data = dict(BASE_THERMOSTAT_DATA)
    data.update(
        {
            "P1P2PopulatedUnits": populated_units,
            "P1P2UnitType": unit_type,
            "P1P2IndoorUnitDataValid": indoor_valid,
        }
    )
    if include_mode_num:
        data["P1P2FieldSettingModeNumber"] = 0

    return {
        "id": device_id,
        "locationId": "loc1",
        "name": "P1P2 Thermostat",
        "model": "ONEPLUS",
        "firmware": "1.0.0",
        "online": True,
        "data": data,
    }


class TestUnitaryFanCirculateWrites:
    async def test_unitary_fan_mode_only_sends_fan_circulate(self, daikin_client: DaikinOne) -> None:
        device_data = _make_unitary_device("unitary123")
        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

            mock_req.reset_mock()
            await daikin_client.set_thermostat_fan_mode("unitary123", DaikinThermostatFanMode.ALWAYS_ON)

            mock_req.assert_awaited_once_with(
                url=f"{DAIKIN_API_URL_DEVICE_DATA}/unitary123",
                method="PUT",
                body={"fanCirculate": 1},
            )
            assert "unitary123" not in daikin_client._p1p2_reset_tasks

    async def test_uncached_thermostat_falls_back_to_standard_put(self, daikin_client: DaikinOne) -> None:
        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            await daikin_client.set_thermostat_fan_mode("uncached123", DaikinThermostatFanMode.ALWAYS_ON)

            mock_req.assert_awaited_once_with(
                url=f"{DAIKIN_API_URL_DEVICE_DATA}/uncached123",
                method="PUT",
                body={"fanCirculate": 1},
            )
            assert "uncached123" not in daikin_client._p1p2_reset_tasks


class TestP1P2FanCirculateWrites:
    async def test_p1p2_fan_mode_always_on_dispatches_mode_12_sw_1(self, daikin_client: DaikinOne) -> None:
        device_data = _make_p1p2_device("p1p2_123")
        with (
            patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_req.return_value = [device_data]
            await daikin_client.update()

            mock_req.reset_mock()
            await daikin_client.set_thermostat_fan_mode("p1p2_123", DaikinThermostatFanMode.ALWAYS_ON)

            # First PUT must be immediate Mode 12 write with SW3=1, SW6=1
            mock_req.assert_any_await(
                url=f"{DAIKIN_API_URL_DEVICE_DATA}/p1p2_123",
                method="PUT",
                body={
                    "fanCirculate": 1,
                    "P1P2FieldSettingModeNumber": 12,
                    "P1P2FieldSettingUnitNumChangeRequest": True,
                    "P1P2SentFieldSettingSW3": 1,
                    "P1P2SentFieldSettingSW6": 1,
                },
            )

            # Wait for background reset task to complete
            task = daikin_client._p1p2_reset_tasks.get("p1p2_123")
            if task:
                await task

    @pytest.mark.parametrize(
        ("fan_mode", "expected_fan_circulate"),
        [
            (DaikinThermostatFanMode.OFF, 0),
            (DaikinThermostatFanMode.SCHEDULED, 2),
        ],
    )
    async def test_p1p2_fan_mode_off_and_scheduled_dispatch_mode_12_sw_2(
        self, daikin_client: DaikinOne, fan_mode: DaikinThermostatFanMode, expected_fan_circulate: int
    ) -> None:
        device_data = _make_p1p2_device("p1p2_123")
        with (
            patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_req.return_value = [device_data]
            await daikin_client.update()

            mock_req.reset_mock()
            await daikin_client.set_thermostat_fan_mode("p1p2_123", fan_mode)

            mock_req.assert_any_await(
                url=f"{DAIKIN_API_URL_DEVICE_DATA}/p1p2_123",
                method="PUT",
                body={
                    "fanCirculate": expected_fan_circulate,
                    "P1P2FieldSettingModeNumber": 12,
                    "P1P2FieldSettingUnitNumChangeRequest": True,
                    "P1P2SentFieldSettingSW3": 2,
                    "P1P2SentFieldSettingSW6": 2,
                },
            )

            task = daikin_client._p1p2_reset_tasks.get("p1p2_123")
            if task:
                await task

    async def test_p1p2_reset_task_executes_after_delay(self, daikin_client: DaikinOne) -> None:
        device_data = _make_p1p2_device("p1p2_123")
        with (
            patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_req.return_value = [device_data]
            await daikin_client.update()

            mock_req.reset_mock()
            await daikin_client.set_thermostat_fan_mode("p1p2_123", DaikinThermostatFanMode.ALWAYS_ON)

            task = daikin_client._p1p2_reset_tasks["p1p2_123"]
            await task

            # Verify sleep delay
            mock_sleep.assert_awaited_once_with(15.0)

            # Verify reset PUT was dispatched
            mock_req.assert_awaited_with(
                url=f"{DAIKIN_API_URL_DEVICE_DATA}/p1p2_123",
                method="PUT",
                body={
                    "P1P2FieldSettingModeNumber": 0,
                    "P1P2FieldSettingUnitNumChangeRequest": False,
                    "P1P2SentFieldSettingSW3": 15,
                    "P1P2SentFieldSettingSW6": 15,
                },
            )

            # Task removed after clean completion
            assert "p1p2_123" not in daikin_client._p1p2_reset_tasks

    async def test_rapid_back_to_back_fan_mode_changes_cancel_previous_reset(self, daikin_client: DaikinOne) -> None:
        device_data = _make_p1p2_device("p1p2_123")
        sleep_gate = asyncio.Event()

        async def controlled_sleep(seconds: float) -> None:
            await sleep_gate.wait()

        with (
            patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req,
            patch("asyncio.sleep", side_effect=controlled_sleep),
        ):
            mock_req.return_value = [device_data]
            await daikin_client.update()

            # First write: ALWAYS_ON
            await daikin_client.set_thermostat_fan_mode("p1p2_123", DaikinThermostatFanMode.ALWAYS_ON)
            first_task = daikin_client._p1p2_reset_tasks["p1p2_123"]
            assert not first_task.done()

            # Second write: OFF immediately while first reset is still sleeping
            await daikin_client.set_thermostat_fan_mode("p1p2_123", DaikinThermostatFanMode.OFF)
            second_task = daikin_client._p1p2_reset_tasks["p1p2_123"]

            # First task was requested to cancel and raises CancelledError when awaited
            with pytest.raises(asyncio.CancelledError):
                await first_task
            assert first_task.cancelled()
            assert second_task is not first_task
            assert not second_task.done()

            # Let sleep proceed for second task
            sleep_gate.set()
            await second_task

            # Reset task completes cleanly and clears dictionary entry
            assert "p1p2_123" not in daikin_client._p1p2_reset_tasks

    async def test_reset_task_catches_transport_exception(self, daikin_client: DaikinOne) -> None:
        device_data = _make_p1p2_device("p1p2_123")
        call_count = 0

        async def mock_transport_request(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Initial update
                return [device_data]
            if call_count == 2:
                # Immediate Mode 12 PUT
                return {}
            # Reset PUT raises exception
            raise RuntimeError("API connection failure")

        with (
            patch.object(daikin_client._transport, "request", side_effect=mock_transport_request),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await daikin_client.update()
            await daikin_client.set_thermostat_fan_mode("p1p2_123", DaikinThermostatFanMode.ALWAYS_ON)

            task = daikin_client._p1p2_reset_tasks["p1p2_123"]
            # Await task: exception should be caught inside _reset_p1p2_field_setting and not raised
            await task

            assert "p1p2_123" not in daikin_client._p1p2_reset_tasks


class TestP1P2FieldSettingSupportMapping:
    @pytest.mark.parametrize(
        ("data", "expected_supported"),
        [
            # PopulatedUnits > 0
            (
                {
                    "P1P2FieldSettingModeNumber": 0,
                    "P1P2PopulatedUnits": 1,
                    "P1P2UnitType": 255,
                    "P1P2IndoorUnitDataValid": False,
                },
                True,
            ),
            # UnitType not in (0, 255)
            (
                {
                    "P1P2FieldSettingModeNumber": 0,
                    "P1P2PopulatedUnits": 0,
                    "P1P2UnitType": 1,
                    "P1P2IndoorUnitDataValid": False,
                },
                True,
            ),
            # IndoorUnitDataValid is True
            (
                {
                    "P1P2FieldSettingModeNumber": 0,
                    "P1P2PopulatedUnits": 0,
                    "P1P2UnitType": 255,
                    "P1P2IndoorUnitDataValid": True,
                },
                True,
            ),
            # Missing P1P2FieldSettingModeNumber entirely
            (
                {
                    "P1P2PopulatedUnits": 1,
                    "P1P2UnitType": 1,
                    "P1P2IndoorUnitDataValid": True,
                },
                False,
            ),
            # Mode number present but all three criteria false/sentinel
            (
                {
                    "P1P2FieldSettingModeNumber": 0,
                    "P1P2PopulatedUnits": 0,
                    "P1P2UnitType": 255,
                    "P1P2IndoorUnitDataValid": False,
                },
                False,
            ),
            # UnitType is 0 (sentinel) and other criteria false
            (
                {
                    "P1P2FieldSettingModeNumber": 0,
                    "P1P2PopulatedUnits": 0,
                    "P1P2UnitType": 0,
                    "P1P2IndoorUnitDataValid": False,
                },
                False,
            ),
        ],
    )
    async def test_p1p2_field_setting_support_detection(
        self, daikin_client: DaikinOne, data: dict[str, Any], expected_supported: bool
    ) -> None:
        base_device = _make_unitary_device("dev1")
        base_device["data"].update(data)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [base_device]
            await daikin_client.update()

        tstat = daikin_client.get_thermostat("dev1")
        assert tstat.p1p2_field_setting_supported is expected_supported
