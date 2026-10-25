from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.models import (
    DaikinEEVCoil,
    DaikinIndoorUnit,
    DaikinOutdoorUnit,
    DaikinOutdoorUnitHeaterStatus,
    DaikinOutdoorUnitReversingValveStatus,
    DaikinP1P2IndoorUnit,
    DaikinP1P2OutdoorUnit,
    DaikinThermostatFanMode,
    DaikinThermostatFanSpeed,
    DaikinThermostatMode,
    DaikinThermostatStatus,
    DaikinUserCredentials,
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

P1P2_SINGLE_INDOOR_DATA: dict[str, Any] = {
    "P1P2IndoorUnitDataValid": True,
    "P1P2IndoorUnitModelNameManual": "FDMQ24RVJU\x00\x00\x00\x00\x00\x00",
    "P1P2IndoorUnitModelName": "FDMQ24RVJU\x00\x00\x00\x00\x00\x00",
    "P1P2IndoorUnitModelNameValid": True,
    "P1P2IndoorUnitSerialNumber": "E001234\x00\x00\x00",
    "P1P2IndoorSuctionAirThermistor": 21.5,
    "P1P2IndoorSuctionAirThermistorValid": True,
    "P1P2IndoorUnitDischargeAirThermistor": 0.0,
    "P1P2IndoorUnitDischargeAirThermistorValid": False,
    "P1P2IndoorUnitHeatExchangerThermistor": 12.3,
    "P1P2IndoorUnitHeatExchangerThermistorValid": True,
    "P1P2IndoorUnitHeatExchangerGasPipeThermistor": 15.4,
    "P1P2IndoorUnitHeatExchangerGasPipeThermistorValid": True,
    "P1P2IndoorUnitEEVOpenPulses": 250,
    "P1P2IndoorUnitEEVOpenPulsesValid": True,
    "P1P2IndoorUnitEnergizedTime": 1200,
    "P1P2IndoorUnitEnergizedTimeValid": True,
    "P1P2IndoorUnitOperatingTime": 800,
    "P1P2IndoorUnitOperatingTimeValid": True,
    "P1P2IndoorUnitFanOperationTime": 950,
    "P1P2IndoorUnitFanOperationTimeValid": True,
}

P1P2_OUTDOOR_DATA_VALID: dict[str, Any] = {
    "P1P2OutdoorUnitDataValid": True,
    "P1P2OutdoorUnitModelNameManual": "4MXL36TVJU\x00\x00\x00",
    "P1P2OutdoorUnitModelName": "4MXL36TVJU",
    "P1P2OutdoorUnitModelNameValid": True,
    "P1P2OutdoorUnitSerialNumber": "OD123456\x00\x00",
    "P1P2OutdoorAirThermistor": 25.0,
    "P1P2OutdoorAirThermistorValid": True,
    "P1P2OutdoorUnitHeatExchangerThermistor": 35.2,
    "P1P2OutdoorUnitHeatExchangerThermistorValid": True,
    "P1P2OutdoorUnitHeatExchangerGasPipeThermistor": 40.1,
    "P1P2OutdoorUnitHeatExchangerGasPipeThermistorValid": True,
    "P1P2OutdoorUnitHeatExchangerDeicerThermistor": 30.0,
    "P1P2OutdoorUnitHeatExchangerDeicerThermistorValid": True,
    "P1P2OutdoorUnitDischargePipeThermistor": 65.5,
    "P1P2OutdoorUnitDischargePipeThermistorValid": True,
    "P1P2OutdoorUnitLiquidPipeThermistor": 33.1,
    "P1P2OutdoorUnitLiquidPipeThermistorValid": True,
    "P1P2OutdoorUnitEEVOpenPulses": 180,
    "P1P2OutdoorUnitEEVOpenPulsesValid": True,
    "P1P2OutdoorUnitOperatingTime": 1500,
    "P1P2OutdoorUnitOperatingTimeValid": True,
    "P1P2OutdoorUnitCompressor1OperationTime": 1400,
    "P1P2OutdoorUnitCompressor1OperationTimeValid": True,
    "P1P2OutdoorUnitCompressor2OperationTime": 0,
    "P1P2OutdoorUnitCompressor2OperationTimeValid": True,
    "P1P2OutdoorUnitFan1OperationTime": 1450,
    "P1P2OutdoorUnitFan1OperationTimeValid": True,
    "P1P2OutdoorUnitFan2OperationTime": 0,
    "P1P2OutdoorUnitFan2OperationTimeValid": False,
}

P1P2_OUTDOOR_DATA_INVALID_RX24: dict[str, Any] = {
    "P1P2OutdoorUnitDataValid": False,
    "P1P2OutdoorUnitModelNameManual": "RX24RMVJU\x00\x00\x00",
    "P1P2OutdoorUnitModelName": "7J-/071\x00\x00\x00\x00\x00\x00",
    "P1P2OutdoorUnitModelNameValid": True,
    "P1P2OutdoorUnitSerialNumber": "g003661h\x00\x00\x00",
    "P1P2OutdoorAirThermistor": 0,
    "P1P2OutdoorAirThermistorValid": False,
    "P1P2OutdoorUnitHeatExchangerThermistor": 0,
    "P1P2OutdoorUnitHeatExchangerThermistorValid": False,
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


# --- End-to-end: granular sanitization through DaikinOne.update ---


class TestMappingPreservesValidFields:
    async def test_air_handler_garbage_demand_becomes_none(self, daikin_client: DaikinOne) -> None:
        ah = {**AIR_HANDLER_DATA, "ctAHFanRequestedDemand": 255, "ctAHHeatRequestedDemand": 255}
        device_data = _make_device(ah)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
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

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinIndoorUnit))
        assert unit.power_usage is None
        assert unit.fan_demand_requested_percent == 25

    async def test_outdoor_garbage_temperature_becomes_none(self, daikin_client: DaikinOne) -> None:
        od = {**OUTDOOR_UNIT_DATA, "ctOutdoorAirTemperature": 32767, "ctInverterFinTemp": 255}
        device_data = _make_device(od)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
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

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinOutdoorUnit))
        assert unit.total_runtime is None

    async def test_eev_coil_garbage_pressure_becomes_none(self, daikin_client: DaikinOne) -> None:
        eev = {**EEV_COIL_DATA, "ctEEVCoilPressureSensor": 32767}
        device_data = _make_device(eev)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinEEVCoil))
        assert unit.pressure_psi is None
        assert unit.indoor_superheat_temperature is not None

    async def test_humidity_out_of_range_becomes_none(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device()
        device_data["data"]["humIndoor"] = 255

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        assert thermostat.indoor_humidity is None

    async def test_thermostat_still_mapped_when_equipment_fields_garbage(self, daikin_client: DaikinOne) -> None:
        ah = {**AIR_HANDLER_DATA, "ctAHFanRequestedDemand": 255, "ctIndoorPower": 65535}
        device_data = _make_device(ah)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostats = daikin_client.get_thermostats()
        assert "device123" in thermostats
        assert thermostats["device123"].indoor_humidity == 45


class TestEquipmentSkippedOnInvalidIdentity:
    """When a wire identity string (model, serial) sanitizes to None, the equipment is
    omitted from the thermostat's equipment dict rather than registered under a synthetic
    id. Skipping preserves HA entity unique_id stability: the original `{model}-{serial}`
    eid is never polluted with fallback values, so entities go temporarily unavailable
    during garbage refreshes rather than being orphaned and re-registered under a new id."""

    async def test_air_handler_skipped_when_serial_invalid(self, daikin_client: DaikinOne) -> None:
        ah = {**AIR_HANDLER_DATA, "ctAHSerialNoCharacter1_15": "he\ufffdlo"}
        device_data = _make_device(ah)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        assert not any(isinstance(e, DaikinIndoorUnit) for e in thermostat.equipment.values())

    async def test_outdoor_skipped_when_model_invalid(self, daikin_client: DaikinOne) -> None:
        od = {**OUTDOOR_UNIT_DATA, "ctOutdoorModelNoCharacter1_15": "bad\ufffddata"}
        device_data = _make_device(od)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        assert not any(isinstance(e, DaikinOutdoorUnit) for e in thermostat.equipment.values())

    async def test_eev_skipped_when_serial_invalid(self, daikin_client: DaikinOne) -> None:
        eev = {**EEV_COIL_DATA, "ctCoilSerialNoCharacter1_15": "cor\ufffdupt"}
        device_data = _make_device(eev)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        assert not any(isinstance(e, DaikinEEVCoil) for e in thermostat.equipment.values())

    async def test_other_equipment_unaffected_by_one_skip(self, daikin_client: DaikinOne) -> None:
        """Skipping one equipment kind does not affect unrelated equipment on the same thermostat."""
        ah = {**AIR_HANDLER_DATA, "ctAHSerialNoCharacter1_15": "he\ufffdlo"}
        device_data = _make_device(ah, OUTDOOR_UNIT_DATA)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        assert not any(isinstance(e, DaikinIndoorUnit) for e in thermostat.equipment.values())
        assert any(isinstance(e, DaikinOutdoorUnit) for e in thermostat.equipment.values())

    async def test_identity_preserved_when_fields_valid(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device(AIR_HANDLER_DATA)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        unit = next(e for e in thermostat.equipment.values() if isinstance(e, DaikinIndoorUnit))
        assert unit.id == "AH-MODEL-AH-SERIAL"


class TestEquipmentUnitTypeAbsent:
    """P1/P2 mini-split payloads omit the ``ct*UnitType`` keys entirely; the mapping
    must treat that as 'equipment not present' rather than KeyError-ing on setup."""

    async def test_no_equipment_mapped_when_unit_type_keys_missing(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device()
        for key in ("ctAHUnitType", "ctIFCUnitType", "ctOutdoorUnitType", "ctCoilUnitType"):
            del device_data["data"][key]

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        assert thermostat.equipment == {}

    async def test_partial_unit_type_keys_gate_only_their_own_equipment(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device(OUTDOOR_UNIT_DATA)
        del device_data["data"]["ctAHUnitType"]
        del device_data["data"]["ctIFCUnitType"]
        del device_data["data"]["ctCoilUnitType"]

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        assert any(isinstance(e, DaikinOutdoorUnit) for e in thermostat.equipment.values())
        assert not any(isinstance(e, DaikinIndoorUnit) for e in thermostat.equipment.values())
        assert not any(isinstance(e, DaikinEEVCoil) for e in thermostat.equipment.values())


class TestThermostatCapabilitiesAbsent:
    """Some thermostat payloads omit the ``ctSystemCap*`` flags entirely; mapping
    must treat missing keys as 'capability not advertised' rather than KeyError-ing
    on setup."""

    async def test_no_capabilities_when_cap_keys_missing(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device()
        for key in ("ctSystemCapHeat", "ctSystemCapCool", "ctSystemCapEmergencyHeat"):
            del device_data["data"][key]

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        thermostat = daikin_client.get_thermostats()["device123"]
        assert thermostat.capabilities == set()


class TestOutdoorUnitName:
    async def test_heat_pump_when_max_rps_positive(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device({**OUTDOOR_UNIT_DATA, "ctOutdoorHeatMaxRPS": 100})

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        unit = next(
            e
            for e in daikin_client.get_thermostats()["device123"].equipment.values()
            if isinstance(e, DaikinOutdoorUnit)
        )
        assert unit.name == "Heat Pump"

    async def test_condensing_unit_when_max_rps_zero(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device({**OUTDOOR_UNIT_DATA, "ctOutdoorHeatMaxRPS": 0})

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        unit = next(
            e
            for e in daikin_client.get_thermostats()["device123"].equipment.values()
            if isinstance(e, DaikinOutdoorUnit)
        )
        assert unit.name == "Condensing Unit"

    async def test_condensing_unit_when_max_rps_sentinel(self, daikin_client: DaikinOne) -> None:
        # 65535 is the U16 sentinel returned during a thermostat reboot; previously this
        # was checked inline in mapping, now it flows through read()
        device_data = _make_device({**OUTDOOR_UNIT_DATA, "ctOutdoorHeatMaxRPS": 65535})

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        unit = next(
            e
            for e in daikin_client.get_thermostats()["device123"].equipment.values()
            if isinstance(e, DaikinOutdoorUnit)
        )
        assert unit.name == "Condensing Unit"


class TestEnumSanitization:
    """Enum-wrapped raw values would previously raise ValueError during reboot, crashing
    the refresh. _missing_ now coerces unknown values to UNKNOWN so the mapping completes."""

    async def test_thermostat_mode_sentinel_becomes_unknown(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device()
        device_data["data"]["mode"] = 255

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        assert daikin_client.get_thermostats()["device123"].mode is DaikinThermostatMode.UNKNOWN

    async def test_thermostat_status_sentinel_becomes_unknown(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device()
        device_data["data"]["equipmentStatus"] = 255

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        assert daikin_client.get_thermostats()["device123"].status is DaikinThermostatStatus.UNKNOWN

    async def test_thermostat_fan_mode_sentinel_becomes_unknown(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device()
        device_data["data"]["fanCirculate"] = 255

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        assert daikin_client.get_thermostats()["device123"].fan_mode is DaikinThermostatFanMode.UNKNOWN

    async def test_thermostat_fan_speed_sentinel_becomes_unknown(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device()
        device_data["data"]["fanCirculateSpeed"] = 255

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        assert daikin_client.get_thermostats()["device123"].fan_speed is DaikinThermostatFanSpeed.UNKNOWN

    async def test_thermostat_enum_unexpected_value_becomes_unknown(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device()
        device_data["data"]["mode"] = 99

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        assert daikin_client.get_thermostats()["device123"].mode is DaikinThermostatMode.UNKNOWN

    async def test_outdoor_reversing_valve_unexpected_value_becomes_unknown(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device({**OUTDOOR_UNIT_DATA, "ctReversingValve": 42})

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        unit = next(
            e
            for e in daikin_client.get_thermostats()["device123"].equipment.values()
            if isinstance(e, DaikinOutdoorUnit)
        )
        assert unit.reversing_valve is DaikinOutdoorUnitReversingValveStatus.UNKNOWN

    async def test_outdoor_heater_unexpected_value_becomes_unknown(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device({**OUTDOOR_UNIT_DATA, "ctCrankCaseHeaterOnOff": 42})

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        unit = next(
            e
            for e in daikin_client.get_thermostats()["device123"].equipment.values()
            if isinstance(e, DaikinOutdoorUnit)
        )
        assert unit.crank_case_heater is DaikinOutdoorUnitHeaterStatus.UNKNOWN


class TestP1P2Mapping:
    async def test_p1p2_single_indoor_and_outdoor_mapping(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device(P1P2_SINGLE_INDOOR_DATA, P1P2_OUTDOOR_DATA_VALID)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        equipment = daikin_client.get_thermostats()["device123"].equipment
        indoor_unit = next(e for e in equipment.values() if isinstance(e, DaikinP1P2IndoorUnit))
        outdoor_unit = next(e for e in equipment.values() if isinstance(e, DaikinP1P2OutdoorUnit))

        # Identity & null-stripping
        assert indoor_unit.name == "Indoor Unit"
        assert indoor_unit.model == "FDMQ24RVJU"
        assert indoor_unit.serial == "E001234"
        assert indoor_unit.id == "FDMQ24RVJU-E001234"

        # Indoor telemetry validity gating
        assert indoor_unit.suction_air_temperature == Temperature(21.5)
        assert indoor_unit.discharge_air_temperature is None  # Valid: False
        assert indoor_unit.liquid_pipe_temperature == Temperature(12.3)
        assert indoor_unit.gas_pipe_temperature == Temperature(15.4)
        assert indoor_unit.eev_open_pulses == 250
        assert indoor_unit.energized_hours == 1200
        assert indoor_unit.operating_hours == 800
        assert indoor_unit.fan_operating_hours == 950

        # Outdoor identity
        assert outdoor_unit.name == "Outdoor Unit"
        assert outdoor_unit.model == "4MXL36TVJU"
        assert outdoor_unit.serial == "OD123456"
        assert outdoor_unit.id == "4MXL36TVJU-OD123456"

        # Outdoor telemetry validity gating
        assert outdoor_unit.air_temperature == Temperature(25.0)
        assert outdoor_unit.heat_exchanger_temperature == Temperature(35.2)
        assert outdoor_unit.gas_pipe_temperature == Temperature(40.1)
        assert outdoor_unit.deicer_temperature == Temperature(30.0)
        assert outdoor_unit.discharge_pipe_temperature == Temperature(65.5)
        assert outdoor_unit.liquid_pipe_temperature == Temperature(33.1)
        assert outdoor_unit.eev_open_pulses == 180
        assert outdoor_unit.operating_hours == 1500
        assert outdoor_unit.compressor_1_operating_hours == 1400
        assert outdoor_unit.compressor_2_operating_hours is None  # 0 operating hours (uninstalled 2nd stage)
        assert outdoor_unit.fan_1_operating_hours == 1450
        assert outdoor_unit.fan_2_operating_hours is None  # Valid: False

    async def test_p1p2_multi_split_indexed_units(self, daikin_client: DaikinOne) -> None:
        multi_split_data: dict[str, Any] = {
            "P1P2IndoorUnitDataValidUnit1": True,
            "P1P2IndoorUnitModelNameManualUnit1": "FDMQ18RVJU\x00\x00",
            "P1P2IndoorUnitSerialNumberUnit1": "SN-UNIT-1",
            "P1P2IndoorSuctionAirThermistorUnit1": 22.0,
            "P1P2IndoorSuctionAirThermistorUnit1Valid": True,
            "P1P2IndoorUnitDataValidUnit2": True,
            "P1P2IndoorUnitModelNameManualUnit2": "FTX12NMVJU\x00\x00",
            "P1P2IndoorUnitSerialNumberUnit2": "SN-UNIT-2",
            "P1P2IndoorSuctionAirThermistorUnit2": 23.5,
            "P1P2IndoorSuctionAirThermistorUnit2Valid": True,
        }
        device_data = _make_device(multi_split_data)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        equipment = daikin_client.get_thermostats()["device123"].equipment
        indoor_units = [e for e in equipment.values() if isinstance(e, DaikinP1P2IndoorUnit)]
        assert len(indoor_units) == 2

        unit1 = next(u for u in indoor_units if u.name == "Indoor Unit 1")
        unit2 = next(u for u in indoor_units if u.name == "Indoor Unit 2")

        assert unit1.model == "FDMQ18RVJU"
        assert unit1.serial == "SN-UNIT-1"
        assert unit1.id == "FDMQ18RVJU-SN-UNIT-1"
        assert unit1.suction_air_temperature == Temperature(22.0)

        assert unit2.model == "FTX12NMVJU"
        assert unit2.serial == "SN-UNIT-2"
        assert unit2.id == "FTX12NMVJU-SN-UNIT-2"
        assert unit2.suction_air_temperature == Temperature(23.5)

    async def test_p1p2_single_indexed_unit1_named_indoor_unit(self, daikin_client: DaikinOne) -> None:
        single_unit1_data: dict[str, Any] = {
            "P1P2IndoorUnitDataValidUnit1": True,
            "P1P2IndoorUnitModelNameManualUnit1": "FTWR09TVJU",
            "P1P2IndoorUnitSerialNumberUnit1": "SN-SOLO-1",
            "P1P2IndoorSuctionAirThermistorUnit1": 20.0,
            "P1P2IndoorSuctionAirThermistorUnit1Valid": True,
        }
        device_data = _make_device(single_unit1_data)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        equipment = daikin_client.get_thermostats()["device123"].equipment
        indoor_units = [e for e in equipment.values() if isinstance(e, DaikinP1P2IndoorUnit)]
        assert len(indoor_units) == 1
        assert indoor_units[0].name == "Indoor Unit"
        assert indoor_units[0].model == "FTWR09TVJU"

    async def test_p1p2_outdoor_data_valid_false_rx24(self, daikin_client: DaikinOne) -> None:
        device_data = _make_device(P1P2_OUTDOOR_DATA_INVALID_RX24)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        equipment = daikin_client.get_thermostats()["device123"].equipment
        outdoor = next(e for e in equipment.values() if isinstance(e, DaikinP1P2OutdoorUnit))

        # Manual model takes priority over board string '7J-/071'
        assert outdoor.model == "RX24RMVJU"
        assert outdoor.serial == "g003661h"
        assert outdoor.id == "RX24RMVJU-g003661h"

        # DataValid is False: all telemetry attributes remain None
        assert outdoor.air_temperature is None
        assert outdoor.heat_exchanger_temperature is None
        assert outdoor.gas_pipe_temperature is None
        assert outdoor.deicer_temperature is None
        assert outdoor.discharge_pipe_temperature is None
        assert outdoor.liquid_pipe_temperature is None
        assert outdoor.eev_open_pulses is None
        assert outdoor.operating_hours is None
        assert outdoor.compressor_1_operating_hours is None
        assert outdoor.compressor_2_operating_hours is None
        assert outdoor.fan_1_operating_hours is None
        assert outdoor.fan_2_operating_hours is None

    async def test_p1p2_synthetic_id_fallback_when_serial_blank(self, daikin_client: DaikinOne) -> None:
        data: dict[str, Any] = {
            "P1P2IndoorUnitDataValid": True,
            "P1P2IndoorUnitModelNameManual": "FDMQ24RVJU",
            "P1P2IndoorUnitSerialNumber": "00000000",
            "P1P2OutdoorUnitDataValid": False,
            "P1P2OutdoorUnitModelNameManual": "RX24RMVJU",
            "P1P2OutdoorUnitSerialNumber": "",
        }
        device_data = _make_device(data)

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [device_data]
            await daikin_client.update()

        equipment = daikin_client.get_thermostats()["device123"].equipment
        indoor = next(e for e in equipment.values() if isinstance(e, DaikinP1P2IndoorUnit))
        outdoor = next(e for e in equipment.values() if isinstance(e, DaikinP1P2OutdoorUnit))

        assert indoor.serial is None
        assert indoor.id == "device123-p1p2-indoor"

        assert outdoor.serial is None
        assert outdoor.id == "device123-p1p2-outdoor"
