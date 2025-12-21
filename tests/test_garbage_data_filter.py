# pyright: reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
import copy
from typing import Any
import pytest
from unittest.mock import AsyncMock, patch
from _pytest.logging import LogCaptureFixture

from custom_components.daikinone.daikinone import DaikinOne, DaikinUserCredentials, DaikinDeviceDataResponse


@pytest.fixture
def daikin_client() -> DaikinOne:
    """Create a DaikinOne client for testing"""
    creds = DaikinUserCredentials(email="test@example.com", password="password")
    client = DaikinOne(creds)
    # Clear the class-level thermostats cache to ensure test isolation
    client._DaikinOne__thermostats.clear()  # type: ignore[attr-defined]
    return client


@pytest.fixture
def clean_device_data() -> dict[str, Any]:
    """Create a clean device data response without garbage values"""
    return {
        "id": "device123",
        "locationId": "loc456",
        "name": "Test Thermostat",
        "model": "ONEPLUS",
        "firmware": "1.0.0",
        "online": True,
        "data": {
            "ctIndoorPower": 100,
            "ctOutdoorPower": 500,
            "ctAHFanRequestedDemand": 50,
            "ctAHHeatRequestedDemand": 100,
            "ctIFCFanRequestedDemandPercent": 75,
            "ctOutdoorHeatRequestedDemand": 80,
            "ctOutdoorCoolRequestedDemand": 0,
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
        },
    }


@pytest.fixture
def garbage_device_data_power() -> dict[str, Any]:
    """Create device data with garbage power value (65535)"""
    return {
        "id": "device123",
        "locationId": "loc456",
        "name": "Test Thermostat",
        "model": "ONEPLUS",
        "firmware": "1.0.0",
        "online": True,
        "data": {
            "ctIndoorPower": 100,
            "ctOutdoorPower": 65535,  # Garbage sentinel value
            "ctAHFanRequestedDemand": 50,
            "ctAHHeatRequestedDemand": 100,
            "ctIFCFanRequestedDemandPercent": 75,
            "ctOutdoorHeatRequestedDemand": 80,
            "ctOutdoorCoolRequestedDemand": 0,
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
        },
    }


@pytest.fixture
def garbage_device_data_demand() -> dict[str, Any]:
    """Create device data with garbage demand value (255)"""
    return {
        "id": "device123",
        "locationId": "loc456",
        "name": "Test Thermostat",
        "model": "ONEPLUS",
        "firmware": "1.0.0",
        "online": True,
        "data": {
            "ctIndoorPower": 100,
            "ctOutdoorPower": 500,
            "ctAHFanRequestedDemand": 255,  # Garbage sentinel value
            "ctAHHeatRequestedDemand": 100,
            "ctIFCFanRequestedDemandPercent": 75,
            "ctOutdoorHeatRequestedDemand": 80,
            "ctOutdoorCoolRequestedDemand": 0,
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
        },
    }


class TestGarbageDataDetection:
    """Tests for garbage data detection in Daikin API responses"""

    def test_clean_data_not_detected_as_garbage(
        self, daikin_client: DaikinOne, clean_device_data: dict[str, Any]
    ) -> None:
        """Test that clean data is not flagged as garbage"""
        device = DaikinDeviceDataResponse(**clean_device_data)
        result = daikin_client._DaikinOne__has_garbage_data(device)  # type: ignore[attr-defined]
        assert result is False, "Clean data should not be detected as garbage"

    def test_garbage_power_value_detected(
        self, daikin_client: DaikinOne, garbage_device_data_power: dict[str, Any]
    ) -> None:
        """Test that garbage power value (65535) is detected"""
        device = DaikinDeviceDataResponse(**garbage_device_data_power)
        result = daikin_client._DaikinOne__has_garbage_data(device)  # type: ignore[attr-defined]
        assert result is True, "Garbage power value (65535) should be detected"

    def test_garbage_demand_value_detected(
        self, daikin_client: DaikinOne, garbage_device_data_demand: dict[str, Any]
    ) -> None:
        """Test that garbage demand value (255) is detected"""
        device = DaikinDeviceDataResponse(**garbage_device_data_demand)
        result = daikin_client._DaikinOne__has_garbage_data(device)  # type: ignore[attr-defined]
        assert result is True, "Garbage demand value (255) should be detected"

    def test_garbage_indoor_power_detected(
        self, daikin_client: DaikinOne, clean_device_data: dict[str, Any]
    ) -> None:
        """Test that garbage ctIndoorPower value is detected"""
        clean_device_data["data"]["ctIndoorPower"] = 65535
        device = DaikinDeviceDataResponse(**clean_device_data)
        result = daikin_client._DaikinOne__has_garbage_data(device)  # type: ignore[attr-defined]
        assert result is True, "Garbage ctIndoorPower value should be detected"

    def test_multiple_demand_fields_checked(
        self, daikin_client: DaikinOne, clean_device_data: dict[str, Any]
    ) -> None:
        """Test that various demand fields are checked for garbage values"""
        demand_fields = [
            "ctAHFanRequestedDemand",
            "ctAHHeatRequestedDemand",
            "ctOutdoorHeatRequestedDemand",
            "ctOutdoorCoolRequestedDemand",
        ]

        for field in demand_fields:
            test_data = clean_device_data.copy()
            test_data["data"] = clean_device_data["data"].copy()
            test_data["data"][field] = 255
            device = DaikinDeviceDataResponse(**test_data)
            result = daikin_client._DaikinOne__has_garbage_data(device)  # type: ignore[attr-defined]
            assert result is True, f"Garbage value in {field} should be detected"


class TestRefreshThermostatsFiltering:
    """Tests for garbage data filtering during thermostat refresh"""

    async def test_clean_data_updates_thermostat(
        self, daikin_client: DaikinOne, clean_device_data: dict[str, Any]
    ) -> None:
        """Test that clean data updates the thermostat cache"""
        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [clean_device_data]

            await daikin_client.update()

            thermostats = daikin_client.get_thermostats()
            assert "device123" in thermostats, "Clean data should update thermostat cache"

    async def test_garbage_data_preserves_previous_state(
        self, daikin_client: DaikinOne, clean_device_data: dict[str, Any], garbage_device_data_power: dict[str, Any]
    ) -> None:
        """Test that garbage data preserves the previous good state"""
        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            # First update with clean data
            mock_req.return_value = [clean_device_data]
            await daikin_client.update()
            thermostats_before = daikin_client.get_thermostats()

            # Second update with garbage data
            mock_req.return_value = [garbage_device_data_power]
            await daikin_client.update()
            thermostats_after = daikin_client.get_thermostats()

            # Verify the state hasn't changed
            assert thermostats_before == thermostats_after, "Garbage data should preserve previous state"

    async def test_garbage_data_logs_warning(
        self, daikin_client: DaikinOne, garbage_device_data_power: dict[str, Any], caplog: LogCaptureFixture
    ) -> None:
        """Test that garbage data triggers a warning log"""
        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [garbage_device_data_power]

            await daikin_client.update()

            assert any(
                "garbage data" in record.message.lower() for record in caplog.records
            ), "Garbage data should trigger a warning log"
            assert any(
                "device123" in record.message for record in caplog.records
            ), "Warning log should include device ID"

    async def test_mixed_clean_and_garbage_data(
        self, daikin_client: DaikinOne, clean_device_data: dict[str, Any], garbage_device_data_power: dict[str, Any]
    ) -> None:
        """Test that only clean devices are updated when receiving mixed data"""
        clean_device_data_2 = copy.deepcopy(clean_device_data)
        clean_device_data_2["id"] = "device456"
        clean_device_data_2["name"] = "Good Thermostat"

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            # Send both clean and garbage data
            mock_req.return_value = [clean_device_data_2, garbage_device_data_power]

            await daikin_client.update()

            thermostats = daikin_client.get_thermostats()
            assert "device456" in thermostats, "Clean device should be in cache"
            assert "device123" not in thermostats, "Garbage device should not be added to cache"
