"""Constants for the Daikin Skyport integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "daikinone"
MANUFACTURER = "Daikin"

PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)
