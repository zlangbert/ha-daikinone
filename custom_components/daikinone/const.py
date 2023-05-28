"""Constants for the Daikin Skyport integration."""
from datetime import timedelta
from enum import Enum, auto
from urllib.parse import urljoin

from homeassistant.const import Platform

DOMAIN = "daikinone"
MANUFACTURER = "Daikin"

PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

DAIKIN_API_URL_BASE = "https://api.daikinskyport.com"
DAIKIN_API_URL_LOGIN = urljoin(DAIKIN_API_URL_BASE, "/users/auth/login")
DAIKIN_API_URL_REFRESH_TOKEN = urljoin(DAIKIN_API_URL_BASE, "/users/auth/token")
DAIKIN_API_URL_LOCATIONS = urljoin(DAIKIN_API_URL_BASE, "/locations")
DAIKIN_API_URL_DEVICES = urljoin(DAIKIN_API_URL_BASE, "/devices")
DAIKIN_API_URL_DEVICE_DATA = urljoin(DAIKIN_API_URL_BASE, "/deviceData")


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
