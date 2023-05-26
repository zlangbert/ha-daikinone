import asyncio
import copy
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp
from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import IntegrationError

from custom_components.daikinone.const import DAIKIN_API_URL_LOGIN, DAIKIN_API_URL_REFRESH_TOKEN, \
    DAIKIN_API_URL_DEVICES, DAIKIN_API_URL_LOCATIONS, DAIKIN_API_URL_DEVICE_DATA

log = logging.getLogger(__name__)


@dataclass
class DaikinUserCredentials:
    email: str
    password: str


@dataclass
class DaikinAuthTokens:
    refresh: str
    access: str


@dataclass
class DaikinLocation:
    id: str
    name: str
    address: str


@dataclass
class DaikinDevice:
    id: str
    location_id: str
    name: str
    model: str
    data: dict[str, Any]


class DaikinOne:
    """Manages connection to Daikin API and fetching device data"""

    __tokens: DaikinAuthTokens | None = None
    __authenticated: bool = False

    __locations: dict[str, DaikinLocation] = dict()
    __devices: dict[str, DaikinDevice] = dict()

    def __init__(self, hass: HomeAssistant, creds: DaikinUserCredentials):
        self._hass = hass
        self.creds = creds

    async def update(self) -> None:
        await self.__refresh_locations()
        await self.__refresh_devices()

    def get_locations(self) -> dict[str, DaikinLocation]:
        return copy.deepcopy(self.__locations)

    def get_location(self, location_id: str) -> DaikinLocation | None:
        return self.__locations[location_id]

    def get_device(self, device_id: str) -> DaikinDevice | None:
        return self.__devices[device_id]

    def get_devices(self) -> dict[str, DaikinDevice]:
        return copy.deepcopy(self.__devices)

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

    async def __refresh_devices(self):
        devices = await self.__req(DAIKIN_API_URL_DEVICES)

        devices = await asyncio.gather(
            *(
                asyncio.create_task(
                    self.__refresh_device(device),
                    name=f"daikin device refresh {device['id']}",
                )
                for device in devices
            )
        )

        self.__devices = {
            device.id: device
            for device in devices
        }
        log.info(f"Cached {len(self.__devices)} devices")

    async def __refresh_device(self, device) -> DaikinDevice:
        data = await self.__req(DAIKIN_API_URL_DEVICE_DATA + f"/{device['id']}")
        return DaikinDevice(
            id=device["id"],
            location_id=device["locationId"],
            name=device["name"],
            model=device["model"],
            data=data,
        )

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
                    self.__tokens = DaikinAuthTokens(refresh=refresh_token, access=access_token)
                    self.__authenticated = True

                    return True

        except ClientError as e:
            log.error(f"Request to login failed: {e}")
            return False

    async def __refresh_token(self) -> bool:
        log.debug("Refreshing access token")
        if self.__authenticated is not True:
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
                        "refreshToken": self.creds.password
                    }
            ) as response:

                if response.status != 200:
                    log.error(f"Request to refresh access token: {response}")
                    return False

                payload = await response.json()
                access_token = payload['accessToken']

                if access_token is None:
                    log.error("No access token found in refresh response")
                    return False

                # save token
                self.__tokens.access = access_token
                self.__authenticated = True

                return True

    async def __req(self, url: str, retry: bool = True) -> Any:

        if self.__authenticated is not True:
            await self.login()

        log.debug(f"Sending request to Daikin API: GET {url}")
        async with aiohttp.ClientSession(
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.__tokens.access}"
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

        raise IntegrationError(f"Failed to send request to Daikin API: GET {url}")
