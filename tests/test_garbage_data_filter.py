from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.daikinone.daikinone import (
    DaikinEEVCoil,
    DaikinIndoorUnit,
    DaikinOne,
    DaikinOutdoorUnit,
    DaikinUserCredentials,
)
from custom_components.daikinone.fields import (
    CelsiusField,
    FloatField,
    IntField,
    PercentField,
    RuntimeField,
    Sentinel,
    StringField,
    TempField,
    capitalize,
    equipment_id,
    read,
)
from custom_components.daikinone.utils import Temperature


@pytest.fixture
def daikin_client() -> DaikinOne:
    creds = DaikinUserCredentials(email="test@example.com", password="password")
    client = DaikinOne(creds)
    client._DaikinOne__thermostats.clear()  # type: ignore[attr-defined]
    return client


# --- Fixtures: minimal but complete device-data payloads ---

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
    "ctAHSerialNoCharacter1_15": "AH-SERIAL       ",
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
    "ctOutdoorModelNoCharacter1_15": "OD-MODEL        ",
    "ctOutdoorSerialNoCharacter1_15": "OD-SERIAL       ",
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

EEV_COIL_DATA: dict[str, Any] = {
    "ctCoilUnitType": 1,
    "ctCoilSerialNoCharacter1_15": "EEV-SERIAL      ",
    "ctCoilControlSoftwareVersion": "3.0.0           ",
    "ctEEVCoilPressureSensor": 150,
    "ctEEVCoilSuperHeatValue": 100,
    "ctEEVCoilSubCoolValue": 50,
    "ctEEVCoilSuctionTemperature": 400,
}

NO_EQUIPMENT: dict[str, Any] = {
    "ctAHUnitType": 255,
    "ctIFCUnitType": 255,
    "ctOutdoorUnitType": 255,
    "ctCoilUnitType": 255,
}


def _make_device(*equipment_blocks: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {**COMMON_THERMOSTAT_DATA, **NO_EQUIPMENT}
    for block in equipment_blocks:
        data.update(block)
    return {
        "id": "device123",
        "locationId": "loc456",
        "name": "Test Thermostat",
        "model": "ONEPLUS",
        "firmware": "1.0.0",
        "online": True,
        "data": data,
    }


# --- Direct tests for the field reader ---


class TestIntField:
    def test_sentinel_returns_none(self) -> None:
        assert read({"k": 255}, IntField("k", Sentinel.U8)) is None
        assert read({"k": 65535}, IntField("k", Sentinel.U16)) is None
        assert read({"k": 32767}, IntField("k", Sentinel.I16)) is None

    def test_scaled(self) -> None:
        assert read({"k": 100}, IntField("k", Sentinel.U8, 0.5)) == 50
        assert read({"k": 80}, IntField("k", Sentinel.U8, 10)) == 800

    def test_returns_int(self) -> None:
        v = read({"k": 3}, IntField("k", Sentinel.U8, 0.5))
        assert isinstance(v, int)

    def test_zero_preserved(self) -> None:
        assert read({"k": 0}, IntField("k", Sentinel.U8, 0.5)) == 0


class TestFloatField:
    def test_sentinel_returns_none(self) -> None:
        assert read({"k": 65535}, FloatField("k", Sentinel.U16, 0.1)) is None

    def test_scaled(self) -> None:
        assert read({"k": 100}, FloatField("k", Sentinel.U16, 0.1)) == 10.0

    def test_returns_float(self) -> None:
        v = read({"k": 100}, FloatField("k", Sentinel.U16, 0.1))
        assert isinstance(v, float)


class TestTempField:
    def test_deci_fahrenheit_default(self) -> None:
        t = read({"k": 750}, TempField("k"))
        assert t is not None
        assert abs(t.celsius - Temperature.from_fahrenheit(75.0).celsius) < 1e-6

    def test_sentinel_default_i16(self) -> None:
        assert read({"k": 32767}, TempField("k")) is None

    def test_celsius_unit(self) -> None:
        t = read({"k": 40}, TempField("k", Sentinel.U8, scale=1, unit="C"))
        assert t is not None
        assert t.celsius == 40

    def test_celsius_sentinel(self) -> None:
        assert read({"k": 255}, TempField("k", Sentinel.U8, scale=1, unit="C")) is None


class TestRuntimeField:
    def test_hours_to_timedelta(self) -> None:
        t = read({"k": 1000}, RuntimeField("k"))
        assert t is not None
        assert t.total_seconds() == 1000 * 3600

    def test_sentinel_returns_none(self) -> None:
        assert read({"k": 4294967295}, RuntimeField("k")) is None


class TestStringField:
    def test_strips(self) -> None:
        assert read({"k": "hello   "}, StringField("k")) == "hello"

    def test_replacement_char_returns_none(self) -> None:
        assert read({"k": "he\ufffdlo"}, StringField("k")) is None


class TestPercentField:
    def test_valid_range(self) -> None:
        assert read({"k": 0}, PercentField("k")) == 0
        assert read({"k": 50}, PercentField("k")) == 50
        assert read({"k": 100}, PercentField("k")) == 100

    def test_out_of_range_returns_none(self) -> None:
        assert read({"k": -1}, PercentField("k")) is None
        assert read({"k": 101}, PercentField("k")) is None
        assert read({"k": 255}, PercentField("k")) is None


class TestCelsiusField:
    def test_in_range(self) -> None:
        t = read({"k": 21.5}, CelsiusField("k"))
        assert t is not None and t.celsius == 21.5

    def test_out_of_range_returns_none(self) -> None:
        assert read({"k": -99}, CelsiusField("k")) is None
        assert read({"k": 200}, CelsiusField("k")) is None

    def test_custom_bounds(self) -> None:
        assert read({"k": 5}, CelsiusField("k", min_c=10, max_c=30)) is None
        assert read({"k": 15}, CelsiusField("k", min_c=10, max_c=30)) is not None


class TestHelpers:
    def test_capitalize_none_passthrough(self) -> None:
        assert capitalize(None) is None
        assert capitalize("") is None  # empty string is falsy

    def test_capitalize(self) -> None:
        assert capitalize("heat") == "Heat"

    def test_equipment_id_prefers_identity(self) -> None:
        assert equipment_id("tid1", "airhandler", "AH-MODEL-AH-SERIAL") == "AH-MODEL-AH-SERIAL"

    def test_equipment_id_falls_back_when_missing(self) -> None:
        assert equipment_id("tid1", "airhandler", None) == "airhandler-tid1"


# --- End-to-end: granular sanitization through DaikinOne.update ---


class TestMappingPreservesValidFields:
    async def test_air_handler_garbage_demand_becomes_none(self, daikin_client: DaikinOne) -> None:
        ah = {**AIR_HANDLER_DATA, "ctAHFanRequestedDemand": 255, "ctAHHeatRequestedDemand": 255}
        device_data = _make_device(ah)

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinIndoorUnit))
        assert unit.fan_demand_requested_percent is None
        assert unit.heat_demand_requested_percent is None
        assert unit.current_airflow == 400

    async def test_air_handler_garbage_power_becomes_none(self, daikin_client: DaikinOne) -> None:
        ah = {**AIR_HANDLER_DATA, "ctIndoorPower": 65535}
        device_data = _make_device(ah)

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinIndoorUnit))
        assert unit.power_usage is None
        assert unit.fan_demand_requested_percent == 25

    async def test_outdoor_garbage_temperature_becomes_none(self, daikin_client: DaikinOne) -> None:
        od = {**OUTDOOR_UNIT_DATA, "ctOutdoorAirTemperature": 32767, "ctInverterFinTemp": 255}
        device_data = _make_device(od)

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinOutdoorUnit))
        assert unit.air_temperature is None
        assert unit.inverter_fin_temperature is None
        assert unit.coil_temperature is not None

    async def test_outdoor_garbage_runtime_becomes_none(self, daikin_client: DaikinOne) -> None:
        od = {**OUTDOOR_UNIT_DATA, "ctOutdoorCompressorRunTime": 4294967295}
        device_data = _make_device(od)

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinOutdoorUnit))
        assert unit.total_runtime is None

    async def test_eev_coil_garbage_pressure_becomes_none(self, daikin_client: DaikinOne) -> None:
        eev = {**EEV_COIL_DATA, "ctEEVCoilPressureSensor": 32767}
        device_data = _make_device(eev)

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinEEVCoil))
        assert unit.pressure_psi is None
        assert unit.indoor_superheat_temperature is not None

    async def test_humidity_out_of_range_becomes_none(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device()
        device_data["data"]["humIndoor"] = 255

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        assert thermostat.indoor_humidity is None

    async def test_thermostat_still_mapped_when_equipment_fields_garbage(
        self, daikin_client: DaikinOne
    ) -> None:
        ah = {**AIR_HANDLER_DATA, "ctAHFanRequestedDemand": 255, "ctIndoorPower": 65535}
        device_data = _make_device(ah)

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostats = daikin_client.get_thermostats()
        assert "device123" in thermostats
        assert thermostats["device123"].indoor_humidity == 45


class TestEquipmentIdStability:
    """Equipment id (used for HA entity uniqueness) stays stable when identity strings
    sanitize to None on transient responses."""

    async def test_air_handler_falls_back_when_serial_invalid(
        self, daikin_client: DaikinOne
    ) -> None:
        ah = {**AIR_HANDLER_DATA, "ctAHSerialNoCharacter1_15": "he\ufffdlo"}
        device_data = _make_device(ah)

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinIndoorUnit))
        assert unit.id == "airhandler-device123"
        assert unit.serial is None

    async def test_outdoor_falls_back_when_model_invalid(self, daikin_client: DaikinOne) -> None:
        od = {**OUTDOOR_UNIT_DATA, "ctOutdoorModelNoCharacter1_15": "bad\ufffddata"}
        device_data = _make_device(od)

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinOutdoorUnit))
        assert unit.id == "outdoor-device123"
        assert unit.model is None
        assert unit.serial == "OD-SERIAL"

    async def test_eev_falls_back_when_serial_invalid(self, daikin_client: DaikinOne) -> None:
        eev = {**EEV_COIL_DATA, "ctCoilSerialNoCharacter1_15": "cor\ufffdupt"}
        device_data = _make_device(eev)

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinEEVCoil))
        assert unit.id == "eevcoil-device123"
        assert unit.serial is None

    async def test_identity_preserved_when_fields_valid(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device(AIR_HANDLER_DATA)

        with patch.object(daikin_client, "_DaikinOne__req", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinIndoorUnit))
        assert unit.id == "AH-MODEL-AH-SERIAL"
