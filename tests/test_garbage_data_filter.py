# pyright: reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from typing import Any
import pytest
from unittest.mock import AsyncMock, patch

from custom_components.daikinone.daikinone import (
    DaikinOne,
    DaikinUserCredentials,
    DaikinIndoorUnit,
    DaikinOutdoorUnit,
)


@pytest.fixture
def daikin_client() -> DaikinOne:
    """Create a DaikinOne client for testing"""
    creds = DaikinUserCredentials(email="test@example.com", password="password")
    client = DaikinOne(creds)
    client._DaikinOne__thermostats.clear()  # type: ignore[attr-defined]
    return client


COMMON_THERMOSTAT_DATA: dict[str, Any] = {
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
}

AIR_HANDLER_DATA: dict[str, Any] = {
    "ctAHUnitType": 1,
    "ctAHModelNoCharacter1_15": "AH-MODEL        ",
    "ctAHSerialNoCharacter1_15": "AH-SERIAL        ",
    "ctAHControlSoftwareVersion": "1.0.0           ",
    "ctAHMode": "heat            ",
    "ctAHCurrentIndoorAirflow": 400,
    "ctAHFanRequestedDemand": 50,
    "ctAHFanCurrentDemandStatus": 48,
    "ctAHHeatRequestedDemand": 100,
    "ctAHHeatCurrentDemandStatus": 98,
    "ctAHHumidificationRequestedDemand": 0,
    "ctIndoorPower": 100,
}

OUTDOOR_UNIT_DATA: dict[str, Any] = {
    "ctOutdoorUnitType": 1,
    "ctOutdoorModelNoCharacter1_15": "OD-MODEL         ",
    "ctOutdoorSerialNoCharacter1_15": "OD-SERIAL        ",
    "ctOutdoorControlSoftwareVersion": "2.0.0           ",
    "ctOutdoorInverterSoftwareVersion": "1.5.0           ",
    "ctOutdoorCompressorRunTime": 1000,
    "ctOutdoorMode": "cool            ",
    "ctTargetCompressorspeed": 50,
    "ctCurrentCompressorRPS": 48,
    "ctTargetODFanRPM": 80,
    "ctOutdoorFanRPM": 780,
    "ctOutdoorSuctionPressure": 120,
    "ctOutdoorEEVOpening": 50,
    "ctReversingValve": 1,
    "ctOutdoorHeatRequestedDemand": 80,
    "ctOutdoorCoolRequestedDemand": 100,
    "ctOutdoorFanRequestedDemandPercentage": 60,
    "ctOutdoorRequestedIndoorAirflow": 400,
    "ctOutdoorDeHumidificationRequestedDemand": 0,
    "ctOutdoorAirTemperature": 750,
    "ctOutdoorCoilTemperature": 600,
    "ctOutdoorDischargeTemperature": 900,
    "ctOutdoorLiquidTemperature": 500,
    "ctOutdoorDefrostSensorTemperature": 320,
    "ctInverterFinTemp": 40,
    "ctOutdoorPower": 500,
    "ctCompressorCurrent": 50,
    "ctInverterCurrent": 30,
    "ctODFanMotorCurrent": 10,
    "ctCrankCaseHeaterOnOff": 0,
    "ctDrainPanHeaterOnOff": 0,
    "ctPreHeatOnOff": 0,
    "ctOutdoorHeatMaxRPS": 100,
}

NO_EQUIPMENT: dict[str, Any] = {
    "ctAHUnitType": 255,
    "ctIFCUnitType": 255,
    "ctOutdoorUnitType": 255,
    "ctCoilUnitType": 255,
}


def _make_device(extra_data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = {**COMMON_THERMOSTAT_DATA, **NO_EQUIPMENT}
    if extra_data:
        data.update(extra_data)
    return {
        "id": "device123",
        "locationId": "loc456",
        "name": "Test Thermostat",
        "model": "ONEPLUS",
        "firmware": "1.0.0",
        "online": True,
        "data": data,
    }


class TestSanitize:
    def test_int_sentinel_returns_none(self, daikin_client: DaikinOne) -> None:
        sanitize = daikin_client._DaikinOne__sanitize_int  # type: ignore[attr-defined]
        assert sanitize(255, 255) is None
        assert sanitize(65535, 65535) is None
        assert sanitize(32767, 32767) is None

    def test_float_sentinel_returns_none(self, daikin_client: DaikinOne) -> None:
        sanitize = daikin_client._DaikinOne__sanitize_float  # type: ignore[attr-defined]
        assert sanitize(255, 255) is None
        assert sanitize(65535, 65535) is None

    def test_int_returns_rounded(self, daikin_client: DaikinOne) -> None:
        sanitize = daikin_client._DaikinOne__sanitize_int  # type: ignore[attr-defined]
        assert sanitize(100, 255, 0.5) == 50
        assert isinstance(sanitize(100, 255, 0.5), int)
        assert sanitize(500, 65535, 10) == 5000

    def test_float_returns_float(self, daikin_client: DaikinOne) -> None:
        sanitize = daikin_client._DaikinOne__sanitize_float  # type: ignore[attr-defined]
        assert sanitize(100, 65535, 0.1) == 10.0
        assert isinstance(sanitize(100, 65535, 0.1), float)

    def test_zero_returns_zero(self, daikin_client: DaikinOne) -> None:
        sanitize_int = daikin_client._DaikinOne__sanitize_int  # type: ignore[attr-defined]
        sanitize_float = daikin_client._DaikinOne__sanitize_float  # type: ignore[attr-defined]
        assert sanitize_int(0, 255) == 0
        assert sanitize_float(0, 65535, 10) == 0

    def test_default_scale_is_identity(self, daikin_client: DaikinOne) -> None:
        sanitize = daikin_client._DaikinOne__sanitize_int  # type: ignore[attr-defined]
        assert sanitize(42, 255) == 42


class TestGranularSentinelFiltering:
    """Tests that sentinel values in individual fields become None while other fields remain valid"""

    async def test_air_handler_garbage_demand_becomes_none(self, daikin_client: DaikinOne) -> None:
        ah_data = {**AIR_HANDLER_DATA, "ctAHFanRequestedDemand": 255, "ctAHHeatRequestedDemand": 255}
        device_data = _make_device({**ah_data})

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        ah = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinIndoorUnit))
        assert ah.fan_demand_requested_percent is None
        assert ah.heat_demand_requested_percent is None
        # Non-sentinel fields should still have values
        assert ah.current_airflow == 400

    async def test_air_handler_garbage_power_becomes_none(self, daikin_client: DaikinOne) -> None:
        ah_data = {**AIR_HANDLER_DATA, "ctIndoorPower": 65535}
        device_data = _make_device({**ah_data})

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        ah = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinIndoorUnit))
        assert ah.power_usage is None
        assert ah.fan_demand_requested_percent == 25  # 50 / 2

    async def test_outdoor_unit_garbage_demand_becomes_none(self, daikin_client: DaikinOne) -> None:
        od_data = {**OUTDOOR_UNIT_DATA, "ctOutdoorHeatRequestedDemand": 255, "ctOutdoorCoolRequestedDemand": 255}
        device_data = _make_device({**od_data})

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        od = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinOutdoorUnit))
        assert od.heat_demand_percent is None
        assert od.cool_demand_percent is None
        assert od.compressor_speed_current == 48  # Non-sentinel field unaffected

    async def test_outdoor_unit_garbage_power_becomes_none(self, daikin_client: DaikinOne) -> None:
        od_data = {**OUTDOOR_UNIT_DATA, "ctOutdoorPower": 65535}
        device_data = _make_device({**od_data})

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        od = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinOutdoorUnit))
        assert od.power_usage is None

    async def test_clean_data_has_all_values(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device({**AIR_HANDLER_DATA})

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        ah = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinIndoorUnit))
        assert ah.fan_demand_requested_percent == 25  # 50 / 2
        assert ah.heat_demand_requested_percent == 50  # 100 / 2
        assert ah.power_usage == 10.0  # 100 / 10

    async def test_thermostat_always_updated_even_with_sentinel_equipment(
        self, daikin_client: DaikinOne
    ) -> None:
        """Sentinel values in equipment don't block the thermostat update"""
        ah_data = {**AIR_HANDLER_DATA, "ctAHFanRequestedDemand": 255, "ctIndoorPower": 65535}
        device_data = _make_device({**ah_data})

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostats = daikin_client.get_thermostats()
        assert "device123" in thermostats
        assert thermostats["device123"].indoor_humidity == 45
