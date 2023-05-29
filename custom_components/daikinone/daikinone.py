import copy
import logging
from enum import Enum, auto
from typing import Any

import aiohttp
from aiohttp import ClientError
from pydantic import BaseModel
from pydantic.dataclasses import dataclass

from .const import (
    DAIKIN_API_URL_LOGIN,
    DAIKIN_API_URL_REFRESH_TOKEN,
    DAIKIN_API_URL_LOCATIONS,
    DAIKIN_API_URL_DEVICE_DATA,
    DaikinThermostatMode,
    DaikinThermostatStatus,
)
from .exceptions import DaikinServiceException
from custom_components.daikinone.utils import Temperature

log = logging.getLogger(__name__)


@dataclass
class DaikinUserCredentials:
    email: str
    password: str


@dataclass
class DaikinLocation:
    id: str
    name: str
    address: str


@dataclass
class DaikinDevice:
    id: str
    name: str
    model: str
    firmware_version: str


@dataclass
class DaikinEquipment(DaikinDevice):
    thermostat_id: str
    serial: str


@dataclass
class DaikinAirHandler(DaikinEquipment):
    mode: str
    current_airflow: int
    fan_demand_requested_percent: int
    fan_demand_current_percent: int
    heat_demand_requested_percent: int
    heat_demand_current_percent: int
    humidification_demand_requested_percent: int
    power_usage: float


@dataclass
class DaikinOutdoorUnit(DaikinEquipment):
    inverter_software_version: str | None
    fan_rpm: int
    heat_demand_percent: int
    cool_demand_percent: int
    fan_demand_percent: int
    dehumidify_demand_percent: int
    air_temperature: Temperature
    coil_temperature: Temperature
    discharge_temperature: Temperature
    liquid_temperature: Temperature
    defrost_sensor_temperature: Temperature
    power_usage: float


class DaikinThermostatCapability(Enum):
    HEAT = auto()
    COOL = auto()


@dataclass
class DaikinThermostatSchedule:
    enabled: bool


@dataclass
class DaikinThermostat(DaikinDevice):
    location_id: str
    online: bool
    capabilities: set[DaikinThermostatCapability]
    mode: DaikinThermostatMode
    status: DaikinThermostatStatus
    schedule: DaikinThermostatSchedule
    indoor_temperature: Temperature
    indoor_humidity: int
    set_point_heat: Temperature
    set_point_heat_min: Temperature
    set_point_heat_max: Temperature
    set_point_cool: Temperature
    set_point_cool_min: Temperature
    set_point_cool_max: Temperature
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

    __locations: dict[str, DaikinLocation] = dict()
    __thermostats: dict[str, DaikinThermostat] = dict()

    def __init__(self, creds: DaikinUserCredentials):
        self.creds = creds

    async def update(self) -> None:
        await self.__refresh_locations()
        await self.__refresh_thermostats()

    def get_locations(self) -> dict[str, DaikinLocation]:
        return copy.deepcopy(self.__locations)

    def get_location(self, location_id: str) -> DaikinLocation:
        return copy.deepcopy(self.__locations[location_id])

    def get_thermostat(self, thermostat_id: str) -> DaikinThermostat:
        return copy.deepcopy(self.__thermostats[thermostat_id])

    def get_thermostats(self) -> dict[str, DaikinThermostat]:
        return copy.deepcopy(self.__thermostats)

    async def __refresh_locations(self):
        locations = await self.__req(DAIKIN_API_URL_LOCATIONS)
        self.__locations = {
            location["id"]: DaikinLocation(
                id=location["id"],
                name=location["name"],
                address=location["address"],
            )
            for location in locations
        }
        log.info(f"Cached {len(self.__locations)} locations")

    async def __refresh_thermostats(self):
        devices = await self.__req(DAIKIN_API_URL_DEVICE_DATA)
        devices = [DaikinDeviceDataResponse(**device) for device in devices]

        self.__thermostats = {device.id: self.__map_thermostat(device) for device in devices}

        log.info(f"Cached {len(self.__thermostats)} thermostats")

    def __map_thermostat(self, payload: DaikinDeviceDataResponse) -> DaikinThermostat:
        capabilities = set(DaikinThermostatCapability)
        if payload.data["ctSystemCapHeat"]:
            capabilities.add(DaikinThermostatCapability.HEAT)
        if payload.data["ctSystemCapCool"]:
            capabilities.add(DaikinThermostatCapability.COOL)

        schedule = DaikinThermostatSchedule(enabled=payload.data["schedEnabled"])

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
            schedule=schedule,
            indoor_temperature=Temperature.from_celsius(payload.data["tempIndoor"]),
            indoor_humidity=payload.data["humIndoor"],
            set_point_heat=Temperature.from_celsius(payload.data["hspActive"]),
            set_point_heat_min=Temperature.from_celsius(payload.data["EquipProtocolMinHeatSetpoint"]),
            set_point_heat_max=Temperature.from_celsius(payload.data["EquipProtocolMaxHeatSetpoint"]),
            set_point_cool=Temperature.from_celsius(payload.data["cspActive"]),
            set_point_cool_min=Temperature.from_celsius(payload.data["EquipProtocolMinCoolSetpoint"]),
            set_point_cool_max=Temperature.from_celsius(payload.data["EquipProtocolMaxCoolSetpoint"]),
            equipment=self.__map_equipment(payload),
        )

        return thermostat

    def __map_equipment(self, payload: DaikinDeviceDataResponse) -> dict[str, DaikinEquipment]:
        equipment: dict[str, DaikinEquipment] = {}

        # air handler
        if payload.data["ctAHUnitType"] < 255:
            model = payload.data["ctAHModelNoCharacter1_15"].strip()
            serial = payload.data["ctAHSerialNoCharacter1_15"].strip()
            eid = f"{model}-{serial}"

            equipment[eid] = DaikinAirHandler(
                id=eid,
                thermostat_id=payload.id,
                name="Air Handler",
                model=model,
                firmware_version=payload.data["ctAHControlSoftwareVersion"].strip(),
                serial=serial,
                mode=payload.data["ctAHMode"].strip(),
                current_airflow=payload.data["ctAHCurrentIndoorAirflow"],
                fan_demand_requested_percent=payload.data["ctAHFanRequestedDemand"] / 2,
                fan_demand_current_percent=payload.data["ctAHFanCurrentDemandStatus"] / 2,
                heat_demand_requested_percent=payload.data["ctAHHeatRequestedDemand"] / 2,
                heat_demand_current_percent=payload.data["ctAHHeatCurrentDemandStatus"] / 2,
                humidification_demand_requested_percent=payload.data["ctAHHumidificationRequestedDemand"] / 2,
                power_usage=payload.data["ctIndoorPower"] / 10,
            )

        if payload.data["ctOutdoorUnitType"] < 255:
            model = payload.data["ctOutdoorModelNoCharacter1_15"].strip()
            serial = payload.data["ctOutdoorSerialNoCharacter1_15"].strip()
            eid = f"{model}-{serial}"

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
                firmware_version=payload.data["ctOutdoorControlSoftwareVersion"].strip(),
                inverter_software_version=payload.data["ctOutdoorInverterSoftwareVersion"].strip(),
                fan_rpm=payload.data["ctOutdoorFanRPM"],
                heat_demand_percent=round(payload.data["ctOutdoorHeatRequestedDemand"] / 2, 1),
                cool_demand_percent=round(payload.data["ctOutdoorCoolRequestedDemand"] / 2, 1),
                fan_demand_percent=round(payload.data["ctOutdoorFanRequestedDemandPercentage"] / 2, 1),
                dehumidify_demand_percent=round(payload.data["ctOutdoorDeHumidificationRequestedDemand"] / 2, 1),
                air_temperature=Temperature.from_fahrenheit(payload.data["ctOutdoorAirTemperature"] / 10),
                coil_temperature=Temperature.from_fahrenheit(payload.data["ctOutdoorCoilTemperature"] / 10),
                discharge_temperature=Temperature.from_fahrenheit(payload.data["ctOutdoorDischargeTemperature"] / 10),
                liquid_temperature=Temperature.from_fahrenheit(payload.data["ctOutdoorLiquidTemperature"] / 10),
                defrost_sensor_temperature=Temperature.from_fahrenheit(
                    payload.data["ctOutdoorDefrostSensorTemperature"] / 10
                ),
                power_usage=payload.data["ctOutdoorPower"] * 10,
            )

        return equipment

    async def login(self) -> bool:
        """Log in to the Daikin API with the given credentials to auth tokens"""
        log.info("Logging in to Daikin API")
        try:
            async with aiohttp.ClientSession(
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            ) as session:
                async with session.post(
                    url=DAIKIN_API_URL_LOGIN, json={"email": self.creds.email, "password": self.creds.password}
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
                json={"email": self.creds.email, "refreshToken": self.__auth.refresh_token},
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

    async def __req(self, url: str, retry: bool = True) -> Any:
        if self.__auth.authenticated is not True:
            await self.login()

        log.debug(f"Sending request to Daikin API: GET {url}")
        async with aiohttp.ClientSession(
            headers={"Accept": "application/json", "Authorization": f"Bearer {self.__auth.access_token}"}
        ) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    payload = await response.json()
                    return payload

                if response.status == 401:
                    if retry:
                        await self.__refresh_token()
                        return await self.__req(url, retry=False)

        raise DaikinServiceException(f"Failed to send request to Daikin API: GET {url}")
