import copy
import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, NamedTuple

import aiohttp
from aiohttp import ClientError
from pydantic import BaseModel

from .const import DAIKIN_API_URL_LOGIN, DAIKIN_API_URL_REFRESH_TOKEN, \
    DAIKIN_API_URL_LOCATIONS, DAIKIN_API_URL_DEVICE_DATA, DaikinThermostatMode, DaikinThermostatStatus
from .exceptions import DaikinServiceException

log = logging.getLogger(__name__)


class DaikinUserCredentials(NamedTuple):
    email: str
    password: str


class DaikinLocation(NamedTuple):
    id: str
    name: str
    address: str


@dataclass
class DaikinEquipment:
    id: str
    name: str
    model: str
    serial: str
    control_software_version: str


@dataclass
class DaikinAirHandler(DaikinEquipment):
    current_airflow: int


@dataclass
class DaikinOutdoorUnit(DaikinEquipment):
    inverter_software_version: str | None
    fan_rpm: int


class DaikinThermostatCapability(Enum):
    HEAT = auto()
    COOL = auto()


class DaikinThermostatSchedule(NamedTuple):
    enabled: bool


class DaikinThermostat(NamedTuple):
    id: str
    location_id: str
    name: str
    model: str
    firmware: str
    online: bool
    capabilities: set[DaikinThermostatCapability]
    mode: DaikinThermostatMode
    status: DaikinThermostatStatus
    schedule: DaikinThermostatSchedule
    indoor_temperature: float
    indoor_humidity: float
    set_point_heat: float
    set_point_heat_min: float
    set_point_heat_max: float
    set_point_cool: float
    set_point_cool_min: float
    set_point_cool_max: float
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
        devices = [
            DaikinDeviceDataResponse(**device)
            for device in devices
        ]

        self.__thermostats = {
            device.id: self.__map_thermostat(device)
            for device in devices
        }

        log.info(f"Cached {len(self.__thermostats)} thermostats")

    def __map_thermostat(self, payload: DaikinDeviceDataResponse) -> DaikinThermostat:
        capabilities = set(DaikinThermostatCapability)
        if payload.data["ctSystemCapHeat"]:
            capabilities.add(DaikinThermostatCapability.HEAT)
        if payload.data["ctSystemCapCool"]:
            capabilities.add(DaikinThermostatCapability.COOL)

        schedule = DaikinThermostatSchedule(
            enabled=payload.data["schedEnabled"]
        )

        thermostat = DaikinThermostat(
            id=payload.id,
            location_id=payload.locationId,
            name=payload.name,
            model=payload.model,
            firmware=payload.firmware,
            online=payload.online,
            capabilities=capabilities,
            mode=DaikinThermostatMode(payload.data["mode"]),
            status=DaikinThermostatStatus(payload.data["equipmentStatus"]),
            schedule=schedule,
            indoor_temperature=payload.data["tempIndoor"],
            indoor_humidity=payload.data["humIndoor"],
            set_point_heat=payload.data["hspActive"],
            set_point_heat_min=payload.data["EquipProtocolMinHeatSetpoint"],
            set_point_heat_max=payload.data["EquipProtocolMaxHeatSetpoint"],
            set_point_cool=payload.data["cspActive"],
            set_point_cool_min=payload.data["EquipProtocolMinCoolSetpoint"],
            set_point_cool_max=payload.data["EquipProtocolMaxCoolSetpoint"],
            equipment=self.__map_equipment(payload)
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
                name="Air Handler",
                model=model,
                serial=serial,
                control_software_version=payload.data["ctAHControlSoftwareVersion"].strip(),
                current_airflow=payload.data["ctAHCurrentIndoorAirflow"]
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
                name=name,
                model=model,
                serial=serial,
                control_software_version=payload.data["ctOutdoorControlSoftwareVersion"].strip(),
                inverter_software_version=payload.data["ctOutdoorInverterSoftwareVersion"].strip(),
                fan_rpm=payload.data["ctOutdoorFanRPM"]
            )

        return equipment

    async def login(self) -> bool:
        """Log in to the Daikin API with the given credentials to auth tokens"""
        log.info("Logging in to Daikin API")
        try:
            async with aiohttp.ClientSession(
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    }
            ) as session:
                async with session.post(
                        url=DAIKIN_API_URL_LOGIN,
                        json={
                            "email": self.creds.email,
                            "password": self.creds.password
                        }
                ) as response:

                    if response.status != 200:
                        log.error(f"Request to login failed: {response}")
                        return False

                    payload = await response.json()
                    refresh_token = payload['refreshToken']
                    access_token = payload['accessToken']

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
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
        ) as session:
            async with session.post(
                    url=DAIKIN_API_URL_REFRESH_TOKEN,
                    json={
                        "email": self.creds.email,
                        "refreshToken": self.__auth.refresh_token
                    }
            ) as response:

                if response.status != 200:
                    log.error(f"Request to refresh access token: {response}")
                    self.__auth.authenticated = False
                    return False

                payload = await response.json()
                access_token = payload['accessToken']

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
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.__auth.access_token}"
                }
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
