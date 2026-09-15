"""Pure functions that turn a Daikin device-data payload into domain models."""

import logging
from datetime import UTC, datetime

from custom_components.daikinone.client import fields as f
from custom_components.daikinone.client.models import (
    DaikinEEVCoil,
    DaikinFault,
    DaikinEquipment,
    DaikinIndoorUnit,
    DaikinOneAirQualitySensorIndoor,
    DaikinOneAirQualitySensorOutdoor,
    DaikinOutdoorUnit,
    DaikinOutdoorUnitHeaterStatus,
    DaikinOutdoorUnitReversingValveStatus,
    DaikinSplitUnit,
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
        _map_p1p2_split_unit(payload),
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


def _map_p1p2_split_unit(payload: DaikinDeviceDataResponse) -> DaikinSplitUnit | None:
    if not read(payload.data, f.F_P1P2_UNIT_TYPE):
        return None

    model = read(payload.data, f.F_P1P2_MODEL)
    serial = read(payload.data, f.F_P1P2_SERIAL)
    if not model or not serial:
        log.warning("Skipping P1/P2 indoor unit for thermostat %s: model or serial unavailable", payload.id)
        return None

    def optional_bool(field: object) -> bool | None:
        value = read(payload.data, field)
        return None if value is None else bool(value)

    def read_when_valid(field: object, valid_key: str) -> object | None:
        """P1/P2 publishes a separate validity bit for its live telemetry."""
        return read(payload.data, field) if payload.data.get(valid_key) is True else None

    def bool_when_valid(field: object, valid_key: str) -> bool | None:
        value = read_when_valid(field, valid_key)
        return None if value is None else bool(value)

    return DaikinSplitUnit(
        id=f"{model}-{serial}",
        thermostat_id=payload.id,
        name="Split/Multi-Split Indoor Unit",
        model=model,
        serial=serial,
        firmware_version=payload.firmware.strip(),
        mode=DaikinThermostatMode(read(payload.data, f.F_P1P2_MODE)),
        # The P1/P2-specific status is stale at 1 (cooling) on idle units in
        # real device responses. The top-level status follows the actual HVAC
        # state and is the status documented by Daikin's public API.
        equipment_status=DaikinThermostatStatus(payload.data["equipmentStatus"]),
        indoor_temperature=read(payload.data, f.F_P1P2_INDOOR_TEMP),
        indoor_humidity=read(payload.data, f.F_P1P2_INDOOR_HUMIDITY),
        set_point_heat=read(payload.data, f.F_P1P2_HEAT_SETPOINT) or read(payload.data, f.F_SETPOINT_HEAT),
        set_point_cool=read(payload.data, f.F_P1P2_COOL_SETPOINT) or read(payload.data, f.F_SETPOINT_COOL),
        fan_speed_code=read_when_valid(f.F_P1P2_FAN_SPEED, "P1P2IndoorUnitFanSpeedValid"),
        flap_swing_code=read_when_valid(f.F_P1P2_FLAP_SWING, "P1P2IndoorUnitFlapSwingValid"),
        suction_temperature=read_when_valid(f.F_P1P2_SUCTION_TEMP, "P1P2IndoorSuctionAirThermistorValid"),
        discharge_temperature=read_when_valid(
            f.F_P1P2_DISCHARGE_TEMP, "P1P2IndoorUnitDischargeAirThermistorValid"
        ),
        operating_time=read_when_valid(f.F_P1P2_OPERATING_TIME, "P1P2IndoorUnitOperatingTimeValid"),
        energized_time=read_when_valid(f.F_P1P2_ENERGIZED_TIME, "P1P2IndoorUnitEnergizedTimeValid"),
        fan_operation_time=read_when_valid(f.F_P1P2_FAN_OPERATION_TIME, "P1P2IndoorUnitFanOperationTimeValid"),
        eev_open_pulses=read_when_valid(f.F_P1P2_EEV_OPEN_PULSES, "P1P2IndoorUnitEEVOpenPulsesValid"),
        gas_pipe_temp=read_when_valid(
            f.F_P1P2_GAS_PIPE_TEMP, "P1P2IndoorUnitHeatExchangerGasPipeThermistorValid"
        ),
        heat_exchanger_temp=read_when_valid(
            f.F_P1P2_HEAT_EXCHANGER_TEMP, "P1P2IndoorUnitHeatExchangerThermistorValid"
        ),
        fan_tap_active=(
            optional_bool(f.F_P1P2_FAN_TAP) if payload.data.get("P1P2IndoorUnitFanTapValid") is True else None
        ),
        humidifier_on=optional_bool(f.F_P1P2_HUMIDIFIER),
        dehumidifier_on=optional_bool(f.F_P1P2_DEHUMIDIFIER),
        drain_pump_on=bool_when_valid(f.F_P1P2_DRAIN_PUMP, "P1P2DrainPumpOnOffValid"),
        float_switch_on=bool_when_valid(f.F_P1P2_FLOAT_SWITCH, "P1P2FloatOnOffValid"),
        anti_freeze_on=bool_when_valid(f.F_P1P2_ANTI_FREEZE, "P1P2AntiFreezeControlOnOffValid"),
        electric_heater_on=bool_when_valid(f.F_P1P2_ELECTRIC_HEATER, "P1P2ElectricHeaterOnOffValid"),
        humidifier_control_on=bool_when_valid(f.F_P1P2_HUMIDIFIER_CONTROL, "P1P2HumidifierOnOffValid"),
        recent_fault=_most_recent_fault(payload.data),
    )


def _most_recent_fault(data: dict[str, object]) -> DaikinFault | None:
    """Return the newest valid record from the thermostat fault-history slots."""
    faults: list[DaikinFault] = []
    for index in range(1, 26):
        code = data.get(f"fault{index}Code")
        timestamp = data.get(f"fault{index}Date")
        level = data.get(f"fault{index}Level")
        if not isinstance(code, int) or code in {0, 255, 65535}:
            continue
        if not isinstance(timestamp, int) or timestamp < 946684800:
            continue
        faults.append(
            DaikinFault(
                code=code,
                occurred_at=datetime.fromtimestamp(timestamp, UTC),
                level=level if isinstance(level, int) and level != 255 else None,
            )
        )
    return max(faults, key=lambda fault: fault.occurred_at) if faults else None
