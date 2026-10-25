"""Pure functions that turn a Daikin device-data payload into domain models."""

import logging
from typing import Any

from custom_components.daikinone.client import fields as f
from custom_components.daikinone.client.models import (
    DaikinEEVCoil,
    DaikinEquipment,
    DaikinIndoorUnit,
    DaikinOneAirQualitySensorIndoor,
    DaikinOneAirQualitySensorOutdoor,
    DaikinOutdoorUnit,
    DaikinOutdoorUnitHeaterStatus,
    DaikinOutdoorUnitReversingValveStatus,
    DaikinP1P2IndoorUnit,
    DaikinP1P2OutdoorUnit,
    DaikinThermostat,
    DaikinThermostatCapability,
    DaikinThermostatFanMode,
    DaikinThermostatFanSpeed,
    DaikinThermostatMode,
    DaikinThermostatSchedule,
    DaikinThermostatStatus,
)
from custom_components.daikinone.client.wire import (
    DaikinDeviceDataResponse,
    capitalize,
    read,
)
from custom_components.daikinone.utils import Temperature

log = logging.getLogger(__name__)


def map_thermostat(payload: DaikinDeviceDataResponse) -> DaikinThermostat:
    capabilities: set[DaikinThermostatCapability] = set()
    if payload.data.get("ctSystemCapHeat"):
        capabilities.add(DaikinThermostatCapability.HEAT)
    if payload.data.get("ctSystemCapCool"):
        capabilities.add(DaikinThermostatCapability.COOL)
    if payload.data.get("ctSystemCapEmergencyHeat"):
        capabilities.add(DaikinThermostatCapability.EMERGENCY_HEAT)

    return DaikinThermostat(
        id=payload.id,
        location_id=payload.locationId,
        name=payload.name,
        model=payload.model,
        firmware_version=payload.firmware,
        online=payload.online,
        capabilities=capabilities,
        mode=DaikinThermostatMode(payload.data["mode"]),
        status=DaikinThermostatStatus(payload.data["equipmentStatus"]),
        fan_mode=DaikinThermostatFanMode(payload.data["fanCirculate"]),
        fan_speed=DaikinThermostatFanSpeed(payload.data["fanCirculateSpeed"]),
        schedule=DaikinThermostatSchedule(enabled=payload.data["schedEnabled"]),
        indoor_temperature=read(payload.data, f.F_TEMP_INDOOR),
        indoor_humidity=read(payload.data, f.F_HUM_INDOOR),
        set_point_heat=read(payload.data, f.F_SETPOINT_HEAT),
        set_point_heat_min=read(payload.data, f.F_SETPOINT_HEAT_MIN),
        set_point_heat_max=read(payload.data, f.F_SETPOINT_HEAT_MAX),
        set_point_cool=read(payload.data, f.F_SETPOINT_COOL),
        set_point_cool_min=read(payload.data, f.F_SETPOINT_COOL_MIN),
        set_point_cool_max=read(payload.data, f.F_SETPOINT_COOL_MAX),
        outdoor_temperature=read(payload.data, f.F_TEMP_OUTDOOR),
        outdoor_humidity=read(payload.data, f.F_HUM_OUTDOOR),
        air_quality_outdoor=map_air_quality_outdoor(payload),
        air_quality_indoor=map_air_quality_indoor(payload),
        equipment=map_equipment(payload),
    )


def map_air_quality_outdoor(
    payload: DaikinDeviceDataResponse,
) -> DaikinOneAirQualitySensorOutdoor | None:
    if not payload.data["aqOutdoorAvailable"]:
        return None

    return DaikinOneAirQualitySensorOutdoor(
        aqi=payload.data["aqOutdoorValue"],
        aqi_summary_level=payload.data["aqOutdoorLevel"],
        particles_microgram_m3=payload.data["aqOutdoorParticles"],
        ozone_microgram_m3=payload.data["aqOutdoorOzone"],
    )


def map_air_quality_indoor(
    payload: DaikinDeviceDataResponse,
) -> DaikinOneAirQualitySensorIndoor | None:
    if not payload.data["aqIndoorAvailable"]:
        return None

    return DaikinOneAirQualitySensorIndoor(
        aqi=payload.data["aqIndoorValue"],
        aqi_summary_level=payload.data["aqIndoorLevel"],
        particles=payload.data["aqIndoorParticlesValue"],
        particles_summary_level=payload.data["aqIndoorParticlesLevel"],
        voc=payload.data["aqIndoorVOCValue"],
        voc_summary_level=payload.data["aqIndoorVOCLevel"],
    )


def map_equipment(payload: DaikinDeviceDataResponse) -> dict[str, DaikinEquipment]:
    units: list[DaikinEquipment | None] = [
        _map_air_handler(payload),
        _map_furnace(payload),
        _map_outdoor_unit(payload),
        _map_eev_coil(payload),
        *_map_p1p2_indoor_units(payload),
        _map_p1p2_outdoor_unit(payload),
    ]
    return {u.id: u for u in units if u is not None}


def _map_air_handler(payload: DaikinDeviceDataResponse) -> DaikinIndoorUnit | None:
    if not read(payload.data, f.F_AH_UNIT_TYPE):
        return None

    model = read(payload.data, f.F_AH_MODEL)
    serial = read(payload.data, f.F_AH_SERIAL)
    if not model or not serial:
        log.warning(
            "Skipping air handler for thermostat %s: model or serial unavailable in this response",
            payload.id,
        )
        return None
    eid = f"{model}-{serial}"

    return DaikinIndoorUnit(
        id=eid,
        thermostat_id=payload.id,
        name="Air Handler",
        model=model,
        firmware_version=read(payload.data, f.F_AH_FIRMWARE),
        serial=serial,
        mode=capitalize(read(payload.data, f.F_AH_MODE)),
        current_airflow=read(payload.data, f.F_AH_AIRFLOW),
        fan_demand_requested_percent=read(payload.data, f.F_AH_FAN_REQ_DEMAND),
        fan_demand_current_percent=read(payload.data, f.F_AH_FAN_CUR_DEMAND),
        heat_demand_requested_percent=read(payload.data, f.F_AH_HEAT_REQ_DEMAND),
        heat_demand_current_percent=read(payload.data, f.F_AH_HEAT_CUR_DEMAND),
        cool_demand_requested_percent=None,
        cool_demand_current_percent=None,
        humidification_demand_requested_percent=read(payload.data, f.F_AH_HUM_REQ_DEMAND),
        dehumidification_demand_requested_percent=None,
        power_usage=read(payload.data, f.F_INDOOR_POWER),
    )


def _map_furnace(payload: DaikinDeviceDataResponse) -> DaikinIndoorUnit | None:
    if not read(payload.data, f.F_IFC_UNIT_TYPE):
        return None

    model = read(payload.data, f.F_IFC_MODEL)
    serial = read(payload.data, f.F_IFC_SERIAL)
    if not model or not serial:
        log.warning(
            "Skipping furnace for thermostat %s: model or serial unavailable in this response",
            payload.id,
        )
        return None
    eid = f"{model}-{serial}"

    return DaikinIndoorUnit(
        id=eid,
        thermostat_id=payload.id,
        name="Furnace",
        model=model,
        firmware_version=read(payload.data, f.F_IFC_FIRMWARE),
        serial=serial,
        mode=capitalize(read(payload.data, f.F_IFC_MODE)),
        current_airflow=read(payload.data, f.F_IFC_AIRFLOW),
        fan_demand_requested_percent=read(payload.data, f.F_IFC_FAN_REQ_DEMAND),
        fan_demand_current_percent=read(payload.data, f.F_IFC_FAN_CUR_DEMAND),
        heat_demand_requested_percent=read(payload.data, f.F_IFC_HEAT_REQ_DEMAND),
        heat_demand_current_percent=read(payload.data, f.F_IFC_HEAT_CUR_DEMAND),
        cool_demand_requested_percent=read(payload.data, f.F_IFC_COOL_REQ_DEMAND),
        cool_demand_current_percent=read(payload.data, f.F_IFC_COOL_CUR_DEMAND),
        humidification_demand_requested_percent=read(payload.data, f.F_IFC_HUM_REQ_DEMAND),
        dehumidification_demand_requested_percent=read(payload.data, f.F_IFC_DEHUM_REQ_DEMAND),
        power_usage=read(payload.data, f.F_INDOOR_POWER),
    )


def _map_outdoor_unit(payload: DaikinDeviceDataResponse) -> DaikinOutdoorUnit | None:
    if not read(payload.data, f.F_OD_UNIT_TYPE):
        return None

    model = read(payload.data, f.F_OD_MODEL)
    serial = read(payload.data, f.F_OD_SERIAL)
    if not model or not serial:
        log.warning(
            "Skipping outdoor unit for thermostat %s: model or serial unavailable in this response",
            payload.id,
        )
        return None
    eid = f"{model}-{serial}"

    # assume it can cool, and if it can also heat it should be a heat pump
    heat_max_rps = read(payload.data, f.F_OD_HEAT_MAX_RPS)
    name = "Heat Pump" if heat_max_rps else "Condensing Unit"

    return DaikinOutdoorUnit(
        id=eid,
        thermostat_id=payload.id,
        name=name,
        model=model,
        serial=serial,
        firmware_version=read(payload.data, f.F_OD_FIRMWARE),
        inverter_software_version=read(payload.data, f.F_OD_INVERTER_FIRMWARE),
        total_runtime=read(payload.data, f.F_OD_COMPRESSOR_RUNTIME),
        mode=capitalize(read(payload.data, f.F_OD_MODE)),
        compressor_speed_target=read(payload.data, f.F_OD_COMPRESSOR_SPEED_TARGET),
        compressor_speed_current=read(payload.data, f.F_OD_COMPRESSOR_SPEED_CURRENT),
        outdoor_fan_target_rpm=read(payload.data, f.F_OD_FAN_TARGET_RPM),
        outdoor_fan_rpm=read(payload.data, f.F_OD_FAN_RPM),
        suction_pressure_psi=read(payload.data, f.F_OD_SUCTION_PRESSURE),
        eev_opening_percent=read(payload.data, f.F_OD_EEV_OPENING),
        reversing_valve=DaikinOutdoorUnitReversingValveStatus(payload.data["ctReversingValve"]),
        heat_demand_percent=read(payload.data, f.F_OD_HEAT_REQ_DEMAND),
        cool_demand_percent=read(payload.data, f.F_OD_COOL_REQ_DEMAND),
        fan_demand_percent=read(payload.data, f.F_OD_FAN_REQ_DEMAND),
        fan_demand_airflow=read(payload.data, f.F_OD_FAN_REQ_AIRFLOW),
        dehumidify_demand_percent=read(payload.data, f.F_OD_DEHUM_REQ_DEMAND),
        air_temperature=read(payload.data, f.F_OD_AIR_TEMP),
        coil_temperature=read(payload.data, f.F_OD_COIL_TEMP),
        discharge_temperature=read(payload.data, f.F_OD_DISCHARGE_TEMP),
        liquid_temperature=read(payload.data, f.F_OD_LIQUID_TEMP),
        defrost_sensor_temperature=read(payload.data, f.F_OD_DEFROST_TEMP),
        inverter_fin_temperature=read(payload.data, f.F_OD_INVERTER_FIN_TEMP),
        power_usage=read(payload.data, f.F_OD_POWER),
        compressor_amps=read(payload.data, f.F_OD_COMPRESSOR_AMPS),
        inverter_amps=read(payload.data, f.F_OD_INVERTER_AMPS),
        fan_motor_amps=read(payload.data, f.F_OD_FAN_MOTOR_AMPS),
        crank_case_heater=DaikinOutdoorUnitHeaterStatus(payload.data["ctCrankCaseHeaterOnOff"]),
        drain_pan_heater=DaikinOutdoorUnitHeaterStatus(payload.data["ctDrainPanHeaterOnOff"]),
        preheat_heater=DaikinOutdoorUnitHeaterStatus(payload.data["ctPreHeatOnOff"]),
    )


def _map_eev_coil(payload: DaikinDeviceDataResponse) -> DaikinEEVCoil | None:
    if not read(payload.data, f.F_COIL_UNIT_TYPE):
        return None

    serial = read(payload.data, f.F_EEV_SERIAL)
    if not serial:
        log.warning(
            "Skipping EEV coil for thermostat %s: serial unavailable in this response",
            payload.id,
        )
        return None
    eid = f"eevcoil-{serial}"

    return DaikinEEVCoil(
        id=eid,
        thermostat_id=payload.id,
        name="EEV Coil",
        model="EEV Coil",
        serial=serial,
        firmware_version=read(payload.data, f.F_EEV_FIRMWARE),
        pressure_psi=read(payload.data, f.F_EEV_PRESSURE),
        indoor_superheat_temperature=read(payload.data, f.F_EEV_SUPERHEAT_TEMP),
        liquid_temperature=read(payload.data, f.F_EEV_SUBCOOL_TEMP),
        suction_temperature=read(payload.data, f.F_EEV_SUCTION_TEMP),
    )


def _clean_string(value: object | None) -> str | None:
    if value is None:
        return None
    s = str(value).replace("\x00", "").strip()
    if not s or set(s) == {"0"}:
        return None
    return s


def _get_p1p2_temp(data: dict[str, Any], key: str, *valid_keys: str) -> Temperature | None:
    if not any(bool(data.get(k)) for k in valid_keys):
        return None
    val = data.get(key)
    if val is None:
        return None
    try:
        return Temperature(float(val))
    except ValueError, TypeError:
        return None


def _get_p1p2_int(data: dict[str, Any], key: str, *valid_keys: str, min_value: int | None = None) -> int | None:
    if not any(bool(data.get(k)) for k in valid_keys):
        return None
    val = data.get(key)
    if val is None:
        return None
    try:
        ival = int(val)
        if min_value is not None and ival < min_value:
            return None
        return ival
    except ValueError, TypeError:
        return None


def _read_indoor_telemetry(d: dict[str, Any], suffix: str) -> dict[str, Any]:
    return {
        "suction_air_temperature": _get_p1p2_temp(
            d,
            f"P1P2IndoorSuctionAirThermistor{suffix}",
            f"P1P2IndoorSuctionAirThermistor{suffix}Valid",
            f"P1P2IndoorSuctionAirThermistorValid{suffix}",
        ),
        "discharge_air_temperature": _get_p1p2_temp(
            d,
            f"P1P2IndoorUnitDischargeAirThermistor{suffix}",
            f"P1P2IndoorUnitDischargeAirThermistor{suffix}Valid",
            f"P1P2IndoorUnitDischargeAirThermistorValid{suffix}",
        ),
        "liquid_pipe_temperature": _get_p1p2_temp(
            d,
            f"P1P2IndoorUnitHeatExchangerThermistor{suffix}",
            f"P1P2IndoorUnitHeatExchangerThermistor{suffix}Valid",
            f"P1P2IndoorUnitHeatExchangerThermistorValid{suffix}",
        ),
        "gas_pipe_temperature": _get_p1p2_temp(
            d,
            f"P1P2IndoorUnitHeatExchangerGasPipeThermistor{suffix}",
            f"P1P2IndoorUnitHeatExchangerGasPipeThermistor{suffix}Valid",
            f"P1P2IndoorUnitHeatExchangerGasPipeThermistorValid{suffix}",
        ),
        "eev_open_pulses": _get_p1p2_int(
            d,
            f"P1P2IndoorUnitEEVOpenPulses{suffix}",
            f"P1P2IndoorUnitEEVOpenPulses{suffix}Valid",
            f"P1P2IndoorUnitEEVOpenPulsesValid{suffix}",
        ),
        "energized_hours": _get_p1p2_int(
            d,
            f"P1P2IndoorUnitEnergizedTime{suffix}",
            f"P1P2IndoorUnitEnergizedTime{suffix}Valid",
            f"P1P2IndoorUnitEnergizedTimeValid{suffix}",
        ),
        "operating_hours": _get_p1p2_int(
            d,
            f"P1P2IndoorUnitOperatingTime{suffix}",
            f"P1P2IndoorUnitOperatingTime{suffix}Valid",
            f"P1P2IndoorUnitOperatingTimeValid{suffix}",
        ),
        "fan_operating_hours": _get_p1p2_int(
            d,
            f"P1P2IndoorUnitFanOperationTime{suffix}",
            f"P1P2IndoorUnitFanOperationTime{suffix}Valid",
            f"P1P2IndoorUnitFanOperationTimeValid{suffix}",
        ),
    }


def _is_indoor_slot_populated(d: dict[str, Any], n: int) -> bool:
    if bool(d.get(f"P1P2IndoorUnitDataValidUnit{n}")):
        return True
    if _clean_string(d.get(f"P1P2IndoorUnitModelNameManualUnit{n}")):
        return True
    auto_valid = bool(d.get(f"P1P2IndoorUnitModelNameUnit{n}Valid")) or bool(
        d.get(f"P1P2IndoorUnitModelNameValidUnit{n}")
    )
    if auto_valid and _clean_string(d.get(f"P1P2IndoorUnitModelNameUnit{n}")):
        return True
    return False


def _map_p1p2_indoor_units(payload: DaikinDeviceDataResponse) -> list[DaikinP1P2IndoorUnit]:
    d = payload.data
    populated_slots = [n for n in range(1, 16) if _is_indoor_slot_populated(d, n)]

    if len(populated_slots) > 1:
        results: list[DaikinP1P2IndoorUnit] = []
        for n in populated_slots:
            manual_model = _clean_string(d.get(f"P1P2IndoorUnitModelNameManualUnit{n}"))
            auto_valid = bool(d.get(f"P1P2IndoorUnitModelNameUnit{n}Valid")) or bool(
                d.get(f"P1P2IndoorUnitModelNameValidUnit{n}")
            )
            auto_model = _clean_string(d.get(f"P1P2IndoorUnitModelNameUnit{n}")) if auto_valid else None
            model = manual_model or auto_model

            serial = _clean_string(d.get(f"P1P2IndoorUnitSerialNumberUnit{n}")) or _clean_string(
                d.get("P1P2IndoorUnitSerialNumberEquip")
            )
            eid = f"{model}-{serial}" if (model and serial) else (serial or f"{payload.id}-p1p2-indoor-{n}")
            telemetry = _read_indoor_telemetry(d, f"Unit{n}")

            results.append(
                DaikinP1P2IndoorUnit(
                    id=eid,
                    thermostat_id=payload.id,
                    name=f"Indoor Unit {n}",
                    model=model,
                    serial=serial,
                    firmware_version=None,
                    **telemetry,
                )
            )
        return results

    if len(populated_slots) == 1:
        n = populated_slots[0]
        manual_model = _clean_string(d.get(f"P1P2IndoorUnitModelNameManualUnit{n}")) or _clean_string(
            d.get("P1P2IndoorUnitModelNameManual")
        )
        auto_valid_slot = bool(d.get(f"P1P2IndoorUnitModelNameUnit{n}Valid")) or bool(
            d.get(f"P1P2IndoorUnitModelNameValidUnit{n}")
        )
        auto_valid_top = bool(d.get("P1P2IndoorUnitModelNameValid"))
        auto_model = (
            _clean_string(d.get(f"P1P2IndoorUnitModelNameUnit{n}"))
            if auto_valid_slot
            else (_clean_string(d.get("P1P2IndoorUnitModelName")) if auto_valid_top else None)
        )
        model = manual_model or auto_model

        serial = (
            _clean_string(d.get(f"P1P2IndoorUnitSerialNumberUnit{n}"))
            or _clean_string(d.get("P1P2IndoorUnitSerialNumber"))
            or _clean_string(d.get("P1P2IndoorUnitSerialNumberEquip"))
        )
        eid = f"{model}-{serial}" if (model and serial) else (serial or f"{payload.id}-p1p2-indoor")

        indexed_telemetry = _read_indoor_telemetry(d, f"Unit{n}")
        unsuffixed_telemetry = _read_indoor_telemetry(d, "")
        telemetry = {
            k: (indexed_telemetry[k] if indexed_telemetry[k] is not None else unsuffixed_telemetry[k])
            for k in indexed_telemetry
        }

        return [
            DaikinP1P2IndoorUnit(
                id=eid,
                thermostat_id=payload.id,
                name="Indoor Unit",
                model=model,
                serial=serial,
                firmware_version=None,
                **telemetry,
            )
        ]

    # 0 populated indexed slots: check top-level unsuffixed registers
    unsuffixed_valid = bool(d.get("P1P2IndoorUnitDataValid"))
    unsuffixed_manual = _clean_string(d.get("P1P2IndoorUnitModelNameManual"))
    unsuffixed_auto_valid = bool(d.get("P1P2IndoorUnitModelNameValid"))
    unsuffixed_auto = _clean_string(d.get("P1P2IndoorUnitModelName")) if unsuffixed_auto_valid else None
    if not (unsuffixed_valid or unsuffixed_manual or unsuffixed_auto):
        return []

    model = unsuffixed_manual or unsuffixed_auto
    serial = _clean_string(d.get("P1P2IndoorUnitSerialNumber")) or _clean_string(
        d.get("P1P2IndoorUnitSerialNumberEquip")
    )
    eid = f"{model}-{serial}" if (model and serial) else (serial or f"{payload.id}-p1p2-indoor")
    telemetry = _read_indoor_telemetry(d, "")

    return [
        DaikinP1P2IndoorUnit(
            id=eid,
            thermostat_id=payload.id,
            name="Indoor Unit",
            model=model,
            serial=serial,
            firmware_version=None,
            **telemetry,
        )
    ]


def _map_p1p2_outdoor_unit(payload: DaikinDeviceDataResponse) -> DaikinP1P2OutdoorUnit | None:
    d = payload.data
    od_data_valid = bool(d.get("P1P2OutdoorUnitDataValid"))

    manual_model = _clean_string(d.get("P1P2OutdoorUnitModelNameManual"))
    auto_model_valid = bool(d.get("P1P2OutdoorUnitModelNameValid"))
    auto_model = _clean_string(d.get("P1P2OutdoorUnitModelName")) if auto_model_valid else None
    model = manual_model or auto_model

    if not od_data_valid and not model:
        return None

    serial = _clean_string(d.get("P1P2OutdoorUnitSerialNumber"))
    eid = f"{model}-{serial}" if (model and serial) else (serial or f"{payload.id}-p1p2-outdoor")

    if not od_data_valid:
        return DaikinP1P2OutdoorUnit(
            id=eid,
            thermostat_id=payload.id,
            name="Outdoor Unit",
            model=model,
            serial=serial,
            firmware_version=None,
        )

    return DaikinP1P2OutdoorUnit(
        id=eid,
        thermostat_id=payload.id,
        name="Outdoor Unit",
        model=model,
        serial=serial,
        firmware_version=None,
        air_temperature=_get_p1p2_temp(d, "P1P2OutdoorAirThermistor", "P1P2OutdoorAirThermistorValid"),
        heat_exchanger_temperature=_get_p1p2_temp(
            d, "P1P2OutdoorUnitHeatExchangerThermistor", "P1P2OutdoorUnitHeatExchangerThermistorValid"
        ),
        gas_pipe_temperature=_get_p1p2_temp(
            d,
            "P1P2OutdoorUnitHeatExchangerGasPipeThermistor",
            "P1P2OutdoorUnitHeatExchangerGasPipeThermistorValid",
        ),
        deicer_temperature=_get_p1p2_temp(
            d,
            "P1P2OutdoorUnitHeatExchangerDeicerThermistor",
            "P1P2OutdoorUnitHeatExchangerDeicerThermistorValid",
        ),
        discharge_pipe_temperature=_get_p1p2_temp(
            d,
            "P1P2OutdoorUnitDischargePipeThermistor",
            "P1P2OutdoorUnitDischargePipeThermistorValid",
        ),
        liquid_pipe_temperature=_get_p1p2_temp(
            d,
            "P1P2OutdoorUnitLiquidPipeThermistor",
            "P1P2OutdoorUnitLiquidPipeThermistorValid",
        ),
        eev_open_pulses=_get_p1p2_int(d, "P1P2OutdoorUnitEEVOpenPulses", "P1P2OutdoorUnitEEVOpenPulsesValid"),
        operating_hours=_get_p1p2_int(d, "P1P2OutdoorUnitOperatingTime", "P1P2OutdoorUnitOperatingTimeValid"),
        compressor_1_operating_hours=_get_p1p2_int(
            d,
            "P1P2OutdoorUnitCompressor1OperationTime",
            "P1P2OutdoorUnitCompressor1OperationTimeValid",
        ),
        compressor_2_operating_hours=_get_p1p2_int(
            d,
            "P1P2OutdoorUnitCompressor2OperationTime",
            "P1P2OutdoorUnitCompressor2OperationTimeValid",
            min_value=1,
        ),
        fan_1_operating_hours=_get_p1p2_int(
            d,
            "P1P2OutdoorUnitFan1OperationTime",
            "P1P2OutdoorUnitFan1OperationTimeValid",
        ),
        fan_2_operating_hours=_get_p1p2_int(
            d,
            "P1P2OutdoorUnitFan2OperationTime",
            "P1P2OutdoorUnitFan2OperationTimeValid",
            min_value=1,
        ),
    )
