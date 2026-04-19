"""Wire-format primitives for the Daikin API."""

from typing import Any
from urllib.parse import urljoin

from pydantic import BaseModel


DAIKIN_API_URL_BASE = "https://api.daikinskyport.com"
DAIKIN_API_URL_LOGIN = urljoin(DAIKIN_API_URL_BASE, "/users/auth/login")
DAIKIN_API_URL_REFRESH_TOKEN = urljoin(DAIKIN_API_URL_BASE, "/users/auth/token")
DAIKIN_API_URL_LOCATIONS = urljoin(DAIKIN_API_URL_BASE, "/locations")
DAIKIN_API_URL_DEVICES = urljoin(DAIKIN_API_URL_BASE, "/devices")
DAIKIN_API_URL_DEVICE_DATA = urljoin(DAIKIN_API_URL_BASE, "/deviceData")


class DaikinDeviceDataResponse(BaseModel):
    id: str
    locationId: str
    name: str
    model: str
    firmware: str
    online: bool
    data: dict[str, Any]
