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

CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY = "entity_uid_schema_version"

FAN_SCHEDULE = "Schedule"