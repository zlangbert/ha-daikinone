"""Domain models exposed by the Daikin client to the rest of the integration."""

from datetime import timedelta
from enum import Enum, auto

from pydantic.dataclasses import dataclass

from custom_components.daikinone.utils import Temperature


@dataclass
class DaikinUserCredentials:
    email: str
    password: str


@dataclass
class DaikinDevice:
    id: str
    name: str
    model: str | None
    firmware_version: str | None


@dataclass
class DaikinEquipment(DaikinDevice):
    thermostat_id: str
    serial: str | None


@dataclass
class DaikinIndoorUnit(DaikinEquipment):
    mode: str | None
    current_airflow: int | None
    fan_demand_requested_percent: int | None
    fan_demand_current_percent: int | None
    heat_demand_requested_percent: int | None
    heat_demand_current_percent: int | None
    cool_demand_requested_percent: int | None
    cool_demand_current_percent: int | None
    humidification_demand_requested_percent: int | None
    dehumidification_demand_requested_percent: int | None
    power_usage: float | None


class DaikinOutdoorUnitReversingValveStatus(Enum):
    OFF = 0
    ON = 1
    UNKNOWN = 255

    @classmethod
    def _missing_(cls, value: object) -> "DaikinOutdoorUnitReversingValveStatus":
        return cls.UNKNOWN


class DaikinOutdoorUnitHeaterStatus(Enum):
    OFF = 0
    ON = 1
    UNKNOWN = 255

    @classmethod
    def _missing_(cls, value: object) -> "DaikinOutdoorUnitHeaterStatus":
        return cls.UNKNOWN


@dataclass
class DaikinOutdoorUnit(DaikinEquipment):
    inverter_software_version: str | None
    total_runtime: timedelta | None
    mode: str | None
    compressor_speed_target: int | None
    compressor_speed_current: int | None
    outdoor_fan_target_rpm: int | None
    outdoor_fan_rpm: int | None
    suction_pressure_psi: int | None
    eev_opening_percent: int | None
    reversing_valve: DaikinOutdoorUnitReversingValveStatus
    heat_demand_percent: int | None
    cool_demand_percent: int | None
    fan_demand_percent: int | None
    fan_demand_airflow: int | None
    dehumidify_demand_percent: int | None
    air_temperature: Temperature | None
    coil_temperature: Temperature | None
    discharge_temperature: Temperature | None
    liquid_temperature: Temperature | None
    defrost_sensor_temperature: Temperature | None
    inverter_fin_temperature: Temperature | None
    power_usage: float | None
    compressor_amps: float | None
    inverter_amps: float | None
    fan_motor_amps: float | None
    crank_case_heater: DaikinOutdoorUnitHeaterStatus
    drain_pan_heater: DaikinOutdoorUnitHeaterStatus
    preheat_heater: DaikinOutdoorUnitHeaterStatus

    # needs confirmation on unit in raw data
    # preheat_output_watts: int | None

    # compressor reduction mode - ctOutdoorCompressorReductionMode - 1=off, ?


class DaikinOneAirQualitySensorSummaryLevel(Enum):
    GOOD = 0
    MODERATE = 1
    UNHEALTHY = 2
    # The app shows 3 as "Unhealthy" but with a red color instead of orange, so we will call it "Hazardous"
    HAZARDOUS = 3


@dataclass
class DaikinOneAirQualitySensorOutdoor:
    aqi: int
    aqi_summary_level: DaikinOneAirQualitySensorSummaryLevel
    particles_microgram_m3: int
    # even though the app displays ppb, the levels seem to be µg/m³ based on my local weather data
    ozone_microgram_m3: int


@dataclass
class DaikinOneAirQualitySensorIndoor:
    aqi: int
    aqi_summary_level: DaikinOneAirQualitySensorSummaryLevel
    # TODO: see if there is unit data available from somewhere
    particles: int
    particles_summary_level: DaikinOneAirQualitySensorSummaryLevel
    voc: int
    voc_summary_level: DaikinOneAirQualitySensorSummaryLevel


@dataclass
class DaikinEEVCoil(DaikinEquipment):
    indoor_superheat_temperature: Temperature | None
    liquid_temperature: Temperature | None
    suction_temperature: Temperature | None
    pressure_psi: int | None


class DaikinThermostatCapability(Enum):
    HEAT = auto()
    COOL = auto()
    EMERGENCY_HEAT = auto()


class DaikinThermostatMode(Enum):
    OFF = 0
    HEAT = 1
    COOL = 2
    AUTO = 3
    AUX_HEAT = 4
    UNKNOWN = 255

    @classmethod
    def _missing_(cls, value: object) -> "DaikinThermostatMode":
        return cls.UNKNOWN


class DaikinThermostatStatus(Enum):
    COOLING = 1
    DRYING = 2
    HEATING = 3
    CIRCULATING_AIR = 4
    IDLE = 5
    UNKNOWN = 255

    @classmethod
    def _missing_(cls, value: object) -> "DaikinThermostatStatus":
        return cls.UNKNOWN


SCHEDULE_DAYS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAIKIN_DAY_PREFIXES: dict[str, str] = {
    "mon": "Mon",
    "tue": "Tue",
    "wed": "Wed",
    "thu": "Thu",
    "fri": "Fri",
    "sat": "Sat",
    "sun": "Sun",
}
SCHEDULE_PARTS: tuple[int, ...] = (1, 2, 3, 4, 5, 6)


@dataclass
class DaikinSchedulePeriod:
    """Represents one of the 6 daily schedule periods on a Daikin thermostat."""

    part: int
    enabled: bool
    start_slot: int
    heat_setpoint: Temperature
    cool_setpoint: Temperature
    label: str = ""
    action: int = 0

    @property
    def start_time_str(self) -> str:
        """Return the start time formatted as HH:MM (00:00 to 23:45)."""
        clamped = max(0, min(95, self.start_slot))
        total_minutes = clamped * 15
        return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


@dataclass
class DaikinDaySchedule:
    """Represents the 6 schedule periods for a single day of the week."""

    day: str
    periods: dict[int, DaikinSchedulePeriod]


@dataclass
class DaikinThermostatSchedule:
    """Represents the thermostat schedule state and 7-day x 6-period matrix."""

    enabled: bool
    override: bool = False
    days: dict[str, DaikinDaySchedule] | None = None
    min_temp_delta: float = 2.0
    scheduled_heat_setpoint: Temperature | None = None
    scheduled_cool_setpoint: Temperature | None = None


class DaikinThermostatFanMode(Enum):
    OFF = 0
    ALWAYS_ON = 1
    SCHEDULED = 2
    UNKNOWN = 255

    @classmethod
    def _missing_(cls, value: object) -> "DaikinThermostatFanMode":
        return cls.UNKNOWN


class DaikinThermostatFanSpeed(Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    UNKNOWN = 255

    @classmethod
    def _missing_(cls, value: object) -> "DaikinThermostatFanSpeed":
        return cls.UNKNOWN


@dataclass
class DaikinThermostat(DaikinDevice):
    location_id: str
    online: bool
    capabilities: set[DaikinThermostatCapability]
    mode: DaikinThermostatMode
    status: DaikinThermostatStatus
    fan_mode: DaikinThermostatFanMode
    fan_speed: DaikinThermostatFanSpeed
    schedule: DaikinThermostatSchedule
    indoor_temperature: Temperature | None
    indoor_humidity: int | None
    set_point_heat: Temperature | None
    set_point_heat_min: Temperature | None
    set_point_heat_max: Temperature | None
    set_point_cool: Temperature | None
    set_point_cool_min: Temperature | None
    set_point_cool_max: Temperature | None
    outdoor_temperature: Temperature | None
    outdoor_humidity: int | None
    air_quality_outdoor: DaikinOneAirQualitySensorOutdoor | None
    air_quality_indoor: DaikinOneAirQualitySensorIndoor | None
    equipment: dict[str, DaikinEquipment]
