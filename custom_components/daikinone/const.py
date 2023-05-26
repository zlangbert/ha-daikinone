"""Constants for the Daikin Skyport integration."""
from datetime import timedelta
from typing import Final
from urllib.parse import urljoin

from homeassistant.const import Platform

DOMAIN = "daikinone"
MANUFACTURER = "Daikin"

CONF_REFRESH_TOKEN: Final = "refresh_token"

PLATFORMS = [
    Platform.SENSOR,
]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

DAIKIN_API_URL_BASE = "https://api.daikinskyport.com"
DAIKIN_API_URL_LOGIN = urljoin(DAIKIN_API_URL_BASE, "/users/auth/login")
DAIKIN_API_URL_REFRESH_TOKEN = urljoin(DAIKIN_API_URL_BASE, "/users/auth/token")
DAIKIN_API_URL_LOCATIONS = urljoin(DAIKIN_API_URL_BASE, "/locations")
DAIKIN_API_URL_DEVICES = urljoin(DAIKIN_API_URL_BASE, "/devices")
DAIKIN_API_URL_DEVICE_DATA = urljoin(DAIKIN_API_URL_BASE, "/deviceData")
