"""Wire-format primitives for the Daikin API.

Covers the raw shape of device-data payloads (``DaikinDeviceDataResponse``),
URL constants, and the machinery for decoding individual fields out of a
payload's ``data`` dict. Field specs declare each value's sentinel + scale
+ output type; the ``read`` function applies a spec and returns ``None``
when the wire value is a sentinel (unavailable data), so Home Assistant
renders that specific sensor as unavailable while unaffected fields on
the same device continue to update.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import IntEnum
from typing import Any, Literal, overload
from urllib.parse import urljoin

from pydantic import BaseModel

from custom_components.daikinone.utils import Temperature


# --- URLs ---

DAIKIN_API_URL_BASE = "https://api.daikinskyport.com"
DAIKIN_API_URL_LOGIN = urljoin(DAIKIN_API_URL_BASE, "/users/auth/login")
DAIKIN_API_URL_REFRESH_TOKEN = urljoin(DAIKIN_API_URL_BASE, "/users/auth/token")
DAIKIN_API_URL_LOCATIONS = urljoin(DAIKIN_API_URL_BASE, "/locations")
DAIKIN_API_URL_DEVICES = urljoin(DAIKIN_API_URL_BASE, "/devices")
DAIKIN_API_URL_DEVICE_DATA = urljoin(DAIKIN_API_URL_BASE, "/deviceData")


# --- Payload shape ---


class DaikinDeviceDataResponse(BaseModel):
    id: str
    locationId: str
    name: str
    model: str
    firmware: str
    online: bool
    data: dict[str, Any]


# --- Sentinels ---


class Sentinel(IntEnum):
    U8 = 255
    U16 = 65535
    I16 = 32767
    U32 = 4294967295


# --- Field specs ---


@dataclass(frozen=True, slots=True)
class IntField:
    """uint/int wire value, optionally scaled; None when value matches sentinel."""

    key: str
    sentinel: Sentinel
    scale: float = 1.0


@dataclass(frozen=True, slots=True)
class FloatField:
    """uint/int wire value, scaled to float; None when value matches sentinel."""

    key: str
    sentinel: Sentinel
    scale: float = 1.0


@dataclass(frozen=True, slots=True)
class TempField:
    """int wire value, scaled to a Temperature; None when value matches sentinel."""

    key: str
    sentinel: Sentinel = Sentinel.I16
    scale: float = 0.1
    unit: Literal["F", "C"] = "F"


@dataclass(frozen=True, slots=True)
class RuntimeField:
    """uint hours; None when value matches sentinel."""

    key: str
    sentinel: Sentinel = Sentinel.U32


@dataclass(frozen=True, slots=True)
class StringField:
    """Wire string; None when the stripped value contains the replacement char."""

    key: str


@dataclass(frozen=True, slots=True)
class PercentField:
    """Integer 0..100 (humidity, etc.); None if out of range."""

    key: str


@dataclass(frozen=True, slots=True)
class CelsiusField:
    """Celsius value already in decimal form; None if outside a plausible range."""

    key: str
    min_c: float = -60
    max_c: float = 80


@dataclass(frozen=True, slots=True)
class UnitTypeField:
    """Equipment unit-type presence flag.

    Reads as True when the ``ct*UnitType`` key is present and not the U8 sentinel.
    P1/P2 mini-split payloads omit these keys entirely, so a missing key also reads
    as False (equipment not present).
    """

    key: str


# --- Reader ---


@overload
def read(data: dict[str, Any], f: IntField) -> int | None: ...
@overload
def read(data: dict[str, Any], f: FloatField) -> float | None: ...
@overload
def read(data: dict[str, Any], f: TempField) -> Temperature | None: ...
@overload
def read(data: dict[str, Any], f: RuntimeField) -> timedelta | None: ...
@overload
def read(data: dict[str, Any], f: StringField) -> str | None: ...
@overload
def read(data: dict[str, Any], f: PercentField) -> int | None: ...
@overload
def read(data: dict[str, Any], f: CelsiusField) -> Temperature | None: ...
@overload
def read(data: dict[str, Any], f: UnitTypeField) -> bool: ...


def read(data: dict[str, Any], f: Any) -> Any:
    if isinstance(f, UnitTypeField):
        return data.get(f.key, Sentinel.U8) < Sentinel.U8
    value = data[f.key]
    if isinstance(f, IntField):
        return None if value == f.sentinel else round(value * f.scale)
    if isinstance(f, FloatField):
        return None if value == f.sentinel else value * f.scale
    if isinstance(f, TempField):
        if value == f.sentinel:
            return None
        t = value * f.scale
        return Temperature.from_fahrenheit(t) if f.unit == "F" else Temperature.from_celsius(t)
    if isinstance(f, RuntimeField):
        return None if value == f.sentinel else timedelta(hours=value)
    if isinstance(f, StringField):
        s = value.strip()
        return None if "\ufffd" in s else s
    if isinstance(f, PercentField):
        return value if 0 <= value <= 100 else None
    if isinstance(f, CelsiusField):
        return Temperature.from_celsius(value) if f.min_c <= value <= f.max_c else None
    raise TypeError(f"unknown field spec: {type(f).__name__}")


# --- Helpers ---


def capitalize(s: str | None) -> str | None:
    return s.capitalize() if s else None
