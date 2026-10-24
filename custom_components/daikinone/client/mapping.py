"""Pure functions that turn a Daikin device-data payload into domain models."""

import logging
from typing import Any

from custom_components.daikinone.client import fields as f
from custom_components.daikinone.client.models import (
    DAIKIN_DAY_PREFIXES,
    SCHEDULE_PARTS,
    DaikinDaySchedule,
    DaikinEEVCoil,
    DaikinEquipment,
    DaikinIndoorUnit,
    DaikinOneAirQualitySensorIndoor,
    DaikinOneAirQualitySensorOutdoor,
    DaikinOutdoorUnit,
    DaikinOutdoorUnitHeaterStatus,
    DaikinOutdoorUnitReversingValveStatus,
    DaikinSchedulePeriod,
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
        schedule=map_thermostat_schedule(payload.data),
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


def map_thermostat_schedule(data: dict[str, Any]) -> DaikinThermostatSchedule:
    """Parse thermostat schedule state and 7-day x 6-part schedule matrix from raw payload data."""
    enabled = bool(data["schedEnabled"])
    override = bool(data.get("schedOverride", 0))

    raw_delta = data.get("tempDeltaMin", 2.0)
    try:
        min_temp_delta = float(raw_delta) if raw_delta is not None else 2.0
    except ValueError, TypeError:
        min_temp_delta = 2.0

    sched_hsp_raw = data.get("hspSched")
    scheduled_heat = (
        Temperature.from_celsius(float(sched_hsp_raw))
        if isinstance(sched_hsp_raw, (int, float)) and -60 <= float(sched_hsp_raw) <= 80
        else None
    )

    sched_csp_raw = data.get("cspSched")
    scheduled_cool = (
        Temperature.from_celsius(float(sched_csp_raw))
        if isinstance(sched_csp_raw, (int, float)) and -60 <= float(sched_csp_raw) <= 80
        else None
    )

    days: dict[str, DaikinDaySchedule] = {}
    has_any_schedule_keys = False

    for day_key, day_prefix in DAIKIN_DAY_PREFIXES.items():
        periods: dict[int, DaikinSchedulePeriod] = {}
        for part in SCHEDULE_PARTS:
            prefix = f"sched{day_prefix}Part{part}"
            time_key = f"{prefix}Time"
            enabled_key = f"{prefix}Enabled"
            hsp_key = f"{prefix}hsp"
            csp_key = f"{prefix}csp"
            label_key = f"{prefix}Label"
            action_key = f"{prefix}Action"

            if time_key not in data and enabled_key not in data and hsp_key not in data and csp_key not in data:
                continue

            has_any_schedule_keys = True

            raw_slot = data.get(time_key, 0)
            try:
                slot = int(raw_slot)
            except ValueError, TypeError:
                slot = 0
            # Guard against U8 sentinel (255) or out-of-bounds slots
            if not (0 <= slot <= 95):
                slot = 0

            part_enabled = bool(data.get(enabled_key, False))

            raw_hsp = data.get(hsp_key, 20.0)
            try:
                hsp_c = float(raw_hsp)
            except ValueError, TypeError:
                hsp_c = 20.0

            raw_csp = data.get(csp_key, 24.0)
            try:
                csp_c = float(raw_csp)
            except ValueError, TypeError:
                csp_c = 24.0

            raw_label = data.get(label_key, "")
            label = str(raw_label).strip() if raw_label is not None else ""

            raw_action = data.get(action_key, 0)
            try:
                action = int(raw_action)
            except ValueError, TypeError:
                action = 0

            periods[part] = DaikinSchedulePeriod(
                part=part,
                enabled=part_enabled,
                start_slot=slot,
                heat_setpoint=Temperature.from_celsius(hsp_c),
                cool_setpoint=Temperature.from_celsius(csp_c),
                label=label,
                action=action,
            )

        if periods:
            days[day_key] = DaikinDaySchedule(day=day_key, periods=periods)

    return DaikinThermostatSchedule(
        enabled=enabled,
        override=override,
        days=days if has_any_schedule_keys else None,
        min_temp_delta=min_temp_delta,
        scheduled_heat_setpoint=scheduled_heat,
        scheduled_cool_setpoint=scheduled_cool,
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
