import copy
import json
import logging
from datetime import timedelta
from enum import Enum, auto
from urllib.parse import urljoin
from typing import Any

import aiohttp
from aiohttp import ClientError
from pydantic import BaseModel
from pydantic.dataclasses import dataclass

from .exceptions import DaikinServiceException
from custom_components.daikinone import fields as f
from custom_components.daikinone.fields import capitalize, equipment_id, read
from custom_components.daikinone.utils import Temperature

log = logging.getLogger(__name__)

DAIKIN_API_URL_BASE = "https://api.daikinskyport.com"
DAIKIN_API_URL_LOGIN = urljoin(DAIKIN_API_URL_BASE, "/users/auth/login")
DAIKIN_API_URL_REFRESH_TOKEN = urljoin(DAIKIN_API_URL_BASE, "/users/auth/token")
DAIKIN_API_URL_LOCATIONS = urljoin(DAIKIN_API_URL_BASE, "/locations")
DAIKIN_API_URL_DEVICES = urljoin(DAIKIN_API_URL_BASE, "/devices")
DAIKIN_API_URL_DEVICE_DATA = urljoin(DAIKIN_API_URL_BASE, "/deviceData")


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


class DaikinOutdoorUnitHeaterStatus(Enum):
    OFF = 0
    ON = 1
    UNKNOWN = 255


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


class DaikinThermostatStatus(Enum):
    COOLING = 1
    DRYING = 2
    HEATING = 3
    CIRCULATING_AIR = 4
    IDLE = 5


@dataclass
class DaikinThermostatSchedule:
    enabled: bool


class DaikinThermostatFanMode(Enum):
    OFF = 0
    ALWAYS_ON = 1
    SCHEDULED = 2


class DaikinThermostatFanSpeed(Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2


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


class DaikinDeviceDataResponse(BaseModel):
    id: str
    locationId: str
    name: str
    model: str
    firmware: str
    online: bool
    data: dict[str, Any]


class DaikinOne:
    """Manages connection to Daikin API and fetching device data"""

    @dataclass
    class _AuthState:
        authenticated: bool = False
        refresh_token: str | None = None
        access_token: str | None = None

    __auth = _AuthState()

    __thermostats: dict[str, DaikinThermostat] = dict()

    def __init__(self, creds: DaikinUserCredentials):
        self.creds = creds

    async def get_all_raw_device_data(self) -> list[dict[str, Any]]:
        """Get raw device data"""
        return await self.__req(DAIKIN_API_URL_DEVICE_DATA)

    async def get_raw_device_data(self, device_id: str) -> dict[str, Any]:
        """Get raw device data"""
        return await self.__req(f"{DAIKIN_API_URL_DEVICE_DATA}/{device_id}")

    async def update(self) -> None:
        await self.__refresh_thermostats()

    def get_thermostat(self, thermostat_id: str) -> DaikinThermostat:
        return copy.deepcopy(self.__thermostats[thermostat_id])

    def get_thermostats(self) -> dict[str, DaikinThermostat]:
        return copy.deepcopy(self.__thermostats)

    async def set_thermostat_mode(self, thermostat_id: str, mode: DaikinThermostatMode) -> None:
        """Set thermostat mode"""
        await self.__req(
            url=f"{DAIKIN_API_URL_DEVICE_DATA}/{thermostat_id}",
            method="PUT",
            body={"mode": mode.value},
        )

    async def set_thermostat_home_set_points(
        self,
        thermostat_id: str,
        heat: Temperature | None = None,
        cool: Temperature | None = None,
        override_schedule: bool = False,
    ) -> None:
        """Set thermostat home set points"""
        if not heat and not cool:
            raise ValueError("At least one of heat or cool set points must be set")

        payload: dict[str, Any] = {}
        if heat:
            payload["hspHome"] = heat.celsius
        if cool:
            payload["cspHome"] = cool.celsius
        if override_schedule:
            payload["schedOverride"] = 1

        await self.__req(
            url=f"{DAIKIN_API_URL_DEVICE_DATA}/{thermostat_id}",
            method="PUT",
            body=payload,
        )

    async def set_thermostat_fan_mode(self, thermostat_id: str, fan_mode: DaikinThermostatFanMode) -> None:
        """Set thermostat fan mode"""
        await self.__req(
            url=f"{DAIKIN_API_URL_DEVICE_DATA}/{thermostat_id}",
            method="PUT",
            body={"fanCirculate": fan_mode.value},
        )

    async def set_thermostat_fan_speed(self, thermostat_id: str, fan_speed: DaikinThermostatFanSpeed) -> None:
        """Set thermostat fan speed"""
        await self.__req(
            url=f"{DAIKIN_API_URL_DEVICE_DATA}/{thermostat_id}",
            method="PUT",
            body={"fanCirculateSpeed": fan_speed.value},
        )

    async def __refresh_thermostats(self) -> None:
        devices = await self.__req(DAIKIN_API_URL_DEVICE_DATA)
        devices = [DaikinDeviceDataResponse(**device) for device in devices]

        valid_devices: list[DaikinDeviceDataResponse] = []
        for device in devices:
            if not device.online and len(device.data) == 0:
                log.warning(f"Skipping offline device with no data: {device.name} ({device.id})")
            else:
                valid_devices.append(device)

        for device in valid_devices:
            self.__thermostats[device.id] = self.__map_thermostat(device)

        log.info(f"Cached {len(self.__thermostats)} thermostats ({len(devices) - len(valid_devices)} skipped offline)")

    def __map_thermostat(self, payload: DaikinDeviceDataResponse) -> DaikinThermostat:
        capabilities = set(DaikinThermostatCapability)
        if payload.data["ctSystemCapHeat"]:
            capabilities.add(DaikinThermostatCapability.HEAT)
        if payload.data["ctSystemCapCool"]:
            capabilities.add(DaikinThermostatCapability.COOL)
        if payload.data["ctSystemCapEmergencyHeat"]:
            capabilities.add(DaikinThermostatCapability.EMERGENCY_HEAT)

        thermostat = DaikinThermostat(
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
            air_quality_outdoor=self.__map_air_quality_outdoor(payload),
            air_quality_indoor=self.__map_air_quality_indoor(payload),
            equipment=self.__map_equipment(payload),
        )

        return thermostat

    def __map_air_quality_outdoor(self, payload: DaikinDeviceDataResponse) -> DaikinOneAirQualitySensorOutdoor | None:
        if not payload.data["aqOutdoorAvailable"]:
            return None

        return DaikinOneAirQualitySensorOutdoor(
            aqi=payload.data["aqOutdoorValue"],
            aqi_summary_level=payload.data["aqOutdoorLevel"],
            particles_microgram_m3=payload.data["aqOutdoorParticles"],
            ozone_microgram_m3=payload.data["aqOutdoorOzone"],
        )

    def __map_air_quality_indoor(self, payload: DaikinDeviceDataResponse) -> DaikinOneAirQualitySensorIndoor | None:
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

    def __map_equipment(self, payload: DaikinDeviceDataResponse) -> dict[str, DaikinEquipment]:
        equipment: dict[str, DaikinEquipment] = {}

        # air handler
        if payload.data["ctAHUnitType"] < 255:
            model = read(payload.data, f.F_AH_MODEL)
            serial = read(payload.data, f.F_AH_SERIAL)
            eid = equipment_id(payload.id, "airhandler", f"{model}-{serial}" if model and serial else None)

            equipment[eid] = DaikinIndoorUnit(
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

        # furnace
        if payload.data["ctIFCUnitType"] < 255:
            model = read(payload.data, f.F_IFC_MODEL)
            serial = read(payload.data, f.F_IFC_SERIAL)
            eid = equipment_id(payload.id, "furnace", f"{model}-{serial}" if model and serial else None)

            equipment[eid] = DaikinIndoorUnit(
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

        # outdoor unit
        if payload.data["ctOutdoorUnitType"] < 255:
            model = read(payload.data, f.F_OD_MODEL)
            serial = read(payload.data, f.F_OD_SERIAL)
            eid = equipment_id(payload.id, "outdoor", f"{model}-{serial}" if model and serial else None)

            # assume it can cool, and if it can also heat it should be a heat pump
            name = "Condensing Unit"
            if payload.data["ctOutdoorHeatMaxRPS"] != 0 and payload.data["ctOutdoorHeatMaxRPS"] != 65535:
                name = "Heat Pump"

            equipment[eid] = DaikinOutdoorUnit(
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

        # eev coil
        if payload.data["ctCoilUnitType"] < 255:
            serial = read(payload.data, f.F_EEV_SERIAL)
            eid = equipment_id(payload.id, "eevcoil", f"eevcoil-{serial}" if serial else None)

            equipment[eid] = DaikinEEVCoil(
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

        return equipment

    async def login(self) -> bool:
        """Log in to the Daikin API with the given credentials to auth tokens"""
        log.info("Logging in to Daikin API")
        try:
            async with aiohttp.ClientSession(
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
            ) as session:
                async with session.post(
                    url=DAIKIN_API_URL_LOGIN,
                    json={"email": self.creds.email, "password": self.creds.password},
                ) as response:
                    if response.status != 200:
                        log.error(f"Request to login failed: {response}")
                        return False

                    payload = await response.json()
                    refresh_token = payload["refreshToken"]
                    access_token = payload["accessToken"]

                    if refresh_token is None:
                        log.error("No refresh token found in login response")
                        return False
                    if access_token is None:
                        log.error("No access token found in login response")
                        return False

                    # save token
                    self.__auth.refresh_token = refresh_token
                    self.__auth.access_token = access_token
                    self.__auth.authenticated = True

                    return True

        except ClientError as e:
            log.error(f"Request to login failed: {e}")
            return False

    async def __refresh_token(self) -> bool:
        log.debug("Refreshing access token")
        if self.__auth.authenticated is not True:
            await self.login()

        async with aiohttp.ClientSession(
            headers={"Accept": "application/json", "Content-Type": "application/json"}
        ) as session:
            async with session.post(
                url=DAIKIN_API_URL_REFRESH_TOKEN,
                json={
                    "email": self.creds.email,
                    "refreshToken": self.__auth.refresh_token,
                },
            ) as response:
                if response.status != 200:
                    log.error(f"Request to refresh access token: {response}")
                    self.__auth.authenticated = False
                    return False

                payload = await response.json()
                access_token = payload["accessToken"]

                if access_token is None:
                    log.error("No access token found in refresh response")
                    self.__auth.authenticated = False
                    return False

                # save token
                log.info("Refreshed access token")
                self.__auth.access_token = access_token
                self.__auth.authenticated = True

                return True

    async def __req(
        self,
        url: str,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        retry: bool = True,
    ) -> Any:
        if self.__auth.authenticated is not True:
            await self.login()

        log.debug(f"Sending request to Daikin API: {method} {url}")
        async with aiohttp.ClientSession(
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.__auth.access_token}",
            }
        ) as session:
            async with session.request(method, url, json=body) as response:
                log.debug(f"Got response: {response.status}")

                if response.status == 200:
                    payload = await response.json()
                    return payload

                if response.status == 401:
                    if retry:
                        await self.__refresh_token()
                        return await self.__req(url, method, body, retry=False)

                raise DaikinServiceException(
                    f"Failed to send request to Daikin API: method={method} url={url} body={json.dumps(body)}, response_code={response.status} response_body={await response.text()}",
                    status=response.status,
                )
