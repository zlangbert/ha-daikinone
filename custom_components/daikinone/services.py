"""Service layer for reading and updating the Daikin 7-day cloud thermostat schedule."""

from __future__ import annotations

import logging
import re
from typing import Any, cast

import voluptuous as vol
from homeassistant.const import ATTR_ENTITY_ID, UnitOfTemperature
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from custom_components.daikinone.client.models import (
    DAIKIN_DAY_PREFIXES,
    SCHEDULE_DAYS,
    SCHEDULE_PARTS,
    DaikinSchedulePeriod,
    DaikinThermostat,
)
from custom_components.daikinone.const import DOMAIN
from custom_components.daikinone.exceptions import DaikinServiceException
from custom_components.daikinone.utils import Temperature

log = logging.getLogger(__name__)

SERVICE_GET_SCHEDULE = "get_schedule"
SERVICE_SET_SCHEDULE = "set_schedule"

ATTR_DAYS = "days"
ATTR_SCHEDULE_ENABLED = "schedule_enabled"
ATTR_TEMPERATURE_UNIT = "temperature_unit"
ATTR_PART = "part"
ATTR_ENABLED = "enabled"
ATTR_START_TIME = "start_time"
ATTR_START_SLOT = "start_slot"
ATTR_HEAT_TARGET = "heat_target"
ATTR_COOL_TARGET = "cool_target"
ATTR_LABEL = "label"

DAY_ALIASES: dict[str, str] = {
    "mon": "mon",
    "monday": "mon",
    "tue": "tue",
    "tuesday": "tue",
    "wed": "wed",
    "wednesday": "wed",
    "thu": "thu",
    "thursday": "thu",
    "fri": "fri",
    "friday": "fri",
    "sat": "sat",
    "saturday": "sat",
    "sun": "sun",
    "sunday": "sun",
}

_TIME_STR_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::00)?$")


def _normalize_entity_id(raw_entity_id: str | list[str]) -> str:
    """Extract a single entity_id string from service data."""
    if isinstance(raw_entity_id, list):
        if len(raw_entity_id) != 1 or not isinstance(raw_entity_id[0], str):
            raise ServiceValidationError("Exactly one target climate entity_id must be provided.")
        return raw_entity_id[0]
    if isinstance(raw_entity_id, str) and raw_entity_id.strip():
        return raw_entity_id.strip()
    raise ServiceValidationError("A valid climate entity_id must be provided.")


def _parse_time_to_slot(value: str | int) -> int:
    """Convert an 'HH:MM' string or integer slot (0-95) into a validated 15-minute slot index."""
    if isinstance(value, bool):
        raise ServiceValidationError(f"Invalid start_time '{value}': must be an 'HH:MM' string or integer slot (0-95).")
    if isinstance(value, int):
        if not (0 <= value <= 95):
            raise ServiceValidationError(
                f"Invalid start_time slot {value}: integer slot must be between 0 (00:00) and 95 (23:45)."
            )
        return value

    if isinstance(value, str):
        match = _TIME_STR_RE.match(value.strip())
        if not match:
            raise ServiceValidationError(
                f"Invalid start_time '{value}': expected 'HH:MM' 24-hour format (e.g. '06:30')."
            )
        hour = int(match.group(1))
        minute = int(match.group(2))
        if not (0 <= hour <= 23) or not (0 <= minute <= 59):
            raise ServiceValidationError(f"Invalid start_time '{value}': hour must be 0-23 and minute must be 0-59.")
        if minute % 15 != 0:
            raise ServiceValidationError(
                f"Invalid start_time '{value}': minutes must be in 15-minute increments (:00, :15, :30, :45)."
            )
        return (hour * 60 + minute) // 15

    raise ServiceValidationError(f"Invalid start_time '{value}': must be an 'HH:MM' string or integer slot (0-95).")


def _format_temp(temp: Temperature, unit: str) -> float:
    """Format a Temperature object into the requested unit (°C or °F)."""
    if unit == UnitOfTemperature.FAHRENHEIT:
        return temp.fahrenheit
    return temp.celsius


def _convert_temperature_value(value: float, source_unit: str, target_unit: str) -> float:
    """Convert temperature units without quantizing, for deadband validation."""
    if source_unit == target_unit:
        return value
    if source_unit == UnitOfTemperature.FAHRENHEIT:
        return (value - 32) * 5 / 9
    if source_unit == UnitOfTemperature.CELSIUS:
        return value * 9 / 5 + 32
    raise ServiceValidationError(f"Unsupported temperature unit '{source_unit}'.")


def _parse_temp_to_celsius(value: float, unit: str) -> float:
    """Convert a user-supplied temperature in the active unit (°C or °F) to rounded Celsius."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ServiceValidationError(f"Invalid temperature value '{value}'.")
    if unit == UnitOfTemperature.FAHRENHEIT:
        return Temperature.from_fahrenheit(float(value)).celsius
    return Temperature.from_celsius(float(value)).celsius


def _resolve_thermostat(hass: HomeAssistant, entity_id: str) -> tuple[Any, DaikinThermostat]:
    """Resolve an entity_id (or thermostat_id) to (DaikinOneData, DaikinThermostat) from RAM."""
    if DOMAIN not in hass.data:
        raise ServiceValidationError("The Daikin One integration is not loaded.")

    data = hass.data[DOMAIN]
    thermostats: dict[str, DaikinThermostat] = data.daikin.get_thermostats()
    if not thermostats:
        raise ServiceValidationError("No Daikin One thermostats are available in cache.")

    # 1. Direct match by thermostat ID
    if entity_id in thermostats:
        return data, thermostats[entity_id]

    # 2. Entity registry lookup
    try:
        ent_reg = er.async_get(hass)
        reg_entry = ent_reg.async_get(entity_id)
        if reg_entry is not None and reg_entry.unique_id:
            uid = reg_entry.unique_id
            if uid.endswith("-climate"):
                t_id = uid[: -len("-climate")]
                if t_id in thermostats:
                    return data, thermostats[t_id]
            for t_id, t_obj in thermostats.items():
                if uid.startswith(t_id):
                    return data, t_obj
    except Exception:  # noqa: BLE001, S110
        pass

    # 3. Fallback slug match (e.g. climate.mainfloor_thermostat or climate.mainfloor)
    target_slug = entity_id.removeprefix("climate.").lower()
    for t_obj in thermostats.values():
        name_slug = slugify(t_obj.name)
        if target_slug in (name_slug, f"{name_slug}_thermostat", t_obj.id.lower()):
            return data, t_obj

    raise ServiceValidationError(f"Could not find a Daikin One thermostat matching '{entity_id}'.")


GET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): vol.Any(cv.entity_id, vol.All(cv.ensure_list, [cv.entity_id])),
    }
)

PERIOD_INPUT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_PART): vol.All(vol.Coerce(int), vol.Range(min=1, max=6)),
        vol.Optional(ATTR_ENABLED): cv.boolean,
        vol.Optional(ATTR_START_TIME): vol.Any(str, int),
        vol.Optional(ATTR_START_SLOT): vol.All(vol.Coerce(int), vol.Range(min=0, max=95)),
        vol.Optional(ATTR_HEAT_TARGET): vol.Coerce(float),
        vol.Optional(ATTR_COOL_TARGET): vol.Coerce(float),
        vol.Optional(ATTR_LABEL): cv.string,
    },
    extra=vol.REMOVE_EXTRA,
)

SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): vol.Any(cv.entity_id, vol.All(cv.ensure_list, [cv.entity_id])),
        vol.Optional(ATTR_SCHEDULE_ENABLED): cv.boolean,
        vol.Optional(ATTR_TEMPERATURE_UNIT): vol.In(
            [UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT, "C", "F"]
        ),
        vol.Optional(ATTR_DAYS): dict,
    },
    extra=vol.REMOVE_EXTRA,
)


async def _async_handle_get_schedule(call: ServiceCall) -> ServiceResponse:
    """Handle daikinone.get_schedule service call from local process RAM (<5ms, 0 HTTP calls)."""
    hass = call.hass
    entity_id = _normalize_entity_id(call.data[ATTR_ENTITY_ID])
    _, thermostat = _resolve_thermostat(hass, entity_id)

    unit = hass.config.units.temperature_unit
    schedule = thermostat.schedule

    if schedule.days is None:
        raise ServiceValidationError(f"Thermostat '{thermostat.name}' does not have schedule data available in memory.")

    min_heat_c = thermostat.set_point_heat_min.celsius if thermostat.set_point_heat_min else 10.0
    min_cool_c = thermostat.set_point_cool_min.celsius if thermostat.set_point_cool_min else 10.0
    max_heat_c = thermostat.set_point_heat_max.celsius if thermostat.set_point_heat_max else 32.2
    max_cool_c = thermostat.set_point_cool_max.celsius if thermostat.set_point_cool_max else 32.2

    min_bound = _format_temp(Temperature.from_celsius(min(min_heat_c, min_cool_c)), unit)
    max_bound = _format_temp(Temperature.from_celsius(max(max_heat_c, max_cool_c)), unit)
    min_delta = 3.0 if unit == UnitOfTemperature.FAHRENHEIT else round(schedule.min_temp_delta, 1)

    days_response: dict[str, list[dict[str, Any]]] = {}
    for day_key in SCHEDULE_DAYS:
        day_sched = schedule.days.get(day_key)
        period_list: list[dict[str, Any]] = []
        if day_sched is not None:
            for part in SCHEDULE_PARTS:
                period = day_sched.periods.get(part)
                if period is not None:
                    period_list.append(
                        {
                            "part": period.part,
                            "enabled": period.enabled,
                            "start_time": period.start_time_str,
                            "start_slot": period.start_slot,
                            "heat_target": _format_temp(period.heat_setpoint, unit),
                            "cool_target": _format_temp(period.cool_setpoint, unit),
                            "label": period.label,
                        }
                    )
        days_response[day_key] = period_list

    response: dict[str, Any] = {
        "entity_id": entity_id,
        "thermostat_id": thermostat.id,
        "name": thermostat.name,
        "schedule_enabled": schedule.enabled,
        "schedule_override": schedule.override,
        "temperature_unit": unit,
        "min_temp": min_bound,
        "max_temp": max_bound,
        "min_temp_delta": min_delta,
        "days": days_response,
    }
    return cast(ServiceResponse, response)


async def _async_handle_set_schedule(call: ServiceCall) -> None:
    """Handle daikinone.set_schedule service call with atomic batch PUT and optimistic RAM update."""
    hass = call.hass
    entity_id = _normalize_entity_id(call.data[ATTR_ENTITY_ID])
    data, thermostat = _resolve_thermostat(hass, entity_id)

    ha_unit = hass.config.units.temperature_unit
    raw_unit = call.data.get(ATTR_TEMPERATURE_UNIT, ha_unit)
    if raw_unit == "F":
        unit = UnitOfTemperature.FAHRENHEIT
    elif raw_unit == "C":
        unit = UnitOfTemperature.CELSIUS
    else:
        unit = raw_unit

    days_input: dict[str, Any] | None = call.data.get(ATTR_DAYS)
    sched_enabled_input: bool | None = call.data.get(ATTR_SCHEDULE_ENABLED)

    if not days_input and sched_enabled_input is None:
        raise ServiceValidationError("At least one of 'days' or 'schedule_enabled' must be provided.")

    min_heat_c = thermostat.set_point_heat_min.celsius if thermostat.set_point_heat_min else 10.0
    max_heat_c = thermostat.set_point_heat_max.celsius if thermostat.set_point_heat_max else 32.2
    min_cool_c = thermostat.set_point_cool_min.celsius if thermostat.set_point_cool_min else 10.0
    max_cool_c = thermostat.set_point_cool_max.celsius if thermostat.set_point_cool_max else 32.2
    wire_payload: dict[str, Any] = {}

    if sched_enabled_input is not None:
        wire_payload["schedEnabled"] = bool(sched_enabled_input)
        wire_payload["schedOverride"] = 0

    if days_input:
        for raw_day_key, raw_periods in days_input.items():
            norm_day = DAY_ALIASES.get(str(raw_day_key).strip().lower())
            if norm_day is None:
                raise ServiceValidationError(f"Invalid day key '{raw_day_key}': must be one of {list(SCHEDULE_DAYS)}.")

            day_prefix = DAIKIN_DAY_PREFIXES[norm_day]
            existing_day = (
                thermostat.schedule.days.get(norm_day) if thermostat.schedule and thermostat.schedule.days else None
            )

            # Normalize raw_periods into a list of (part_int, period_dict)
            normalized_periods: list[tuple[int, dict[str, Any]]] = []
            if isinstance(raw_periods, list):
                for idx, raw_item in enumerate(raw_periods, start=1):
                    if not isinstance(raw_item, dict):
                        raise ServiceValidationError(f"Invalid period entry in '{raw_day_key}': expected dictionary.")
                    item: dict[str, Any] = cast(dict[str, Any], raw_item)
                    raw_part = item.get(ATTR_PART)
                    if raw_part is not None:
                        try:
                            p_val = int(str(raw_part))
                            if p_val not in SCHEDULE_PARTS:
                                raise ServiceValidationError(
                                    f"Invalid part number {p_val} in '{raw_day_key}': must be 1 to 6."
                                )
                        except ValueError as err:
                            raise ServiceValidationError(
                                f"Invalid part number in '{raw_day_key}': must be 1 to 6."
                            ) from err
                    try:
                        validated_item = PERIOD_INPUT_SCHEMA(item)
                    except vol.Invalid as err:
                        raise ServiceValidationError(f"Invalid period entry in '{raw_day_key}': {err}") from err
                    part_num = validated_item.get(ATTR_PART, idx)
                    if part_num not in SCHEDULE_PARTS:
                        raise ServiceValidationError(
                            f"Invalid part number {part_num} in '{raw_day_key}': must be 1 to 6."
                        )
                    normalized_periods.append((part_num, validated_item))
            elif isinstance(raw_periods, dict):
                for part_key, item in raw_periods.items():
                    try:
                        part_num = int(str(part_key).lower().removeprefix("part"))
                    except ValueError as err:
                        raise ServiceValidationError(
                            f"Invalid part key '{part_key}' in '{raw_day_key}': must be 1 to 6."
                        ) from err
                    if part_num not in SCHEDULE_PARTS:
                        raise ServiceValidationError(
                            f"Invalid part number {part_num} in '{raw_day_key}': must be 1 to 6."
                        )
                    if not isinstance(item, dict):
                        raise ServiceValidationError(f"Invalid period entry for part {part_num} in '{raw_day_key}'.")
                    try:
                        validated_item = PERIOD_INPUT_SCHEMA(item)
                    except vol.Invalid as err:
                        raise ServiceValidationError(
                            f"Invalid period entry for part {part_num} in '{raw_day_key}': {err}"
                        ) from err
                    normalized_periods.append((part_num, validated_item))
            else:
                raise ServiceValidationError(
                    f"Invalid periods structure for '{raw_day_key}': must be a list or dictionary of periods."
                )

            if not normalized_periods:
                raise ServiceValidationError(f"Day '{raw_day_key}' must contain at least one period update.")

            for part_num, p_data in normalized_periods:
                existing_period: DaikinSchedulePeriod | None = (
                    existing_day.periods.get(part_num) if existing_day else None
                )

                # 1. Start slot
                if ATTR_START_TIME in p_data:
                    slot = _parse_time_to_slot(p_data[ATTR_START_TIME])
                elif ATTR_START_SLOT in p_data:
                    slot = _parse_time_to_slot(p_data[ATTR_START_SLOT])
                elif existing_period is not None:
                    slot = existing_period.start_slot
                else:
                    slot = 0

                # 2. Enabled flag
                if ATTR_ENABLED in p_data:
                    enabled = bool(p_data[ATTR_ENABLED])
                elif existing_period is not None:
                    enabled = existing_period.enabled
                else:
                    enabled = True

                # 3. Heating setpoint (°C)
                if ATTR_HEAT_TARGET in p_data:
                    heat_target = _convert_temperature_value(float(p_data[ATTR_HEAT_TARGET]), unit, ha_unit)
                    hsp_c = _parse_temp_to_celsius(p_data[ATTR_HEAT_TARGET], unit)
                elif existing_period is not None:
                    hsp_c = existing_period.heat_setpoint.celsius
                    heat_target = _format_temp(existing_period.heat_setpoint, ha_unit)
                else:
                    hsp_c = 20.0
                    heat_target = _format_temp(Temperature.from_celsius(hsp_c), ha_unit)

                # 4. Cooling setpoint (°C)
                if ATTR_COOL_TARGET in p_data:
                    cool_target = _convert_temperature_value(float(p_data[ATTR_COOL_TARGET]), unit, ha_unit)
                    csp_c = _parse_temp_to_celsius(p_data[ATTR_COOL_TARGET], unit)
                elif existing_period is not None:
                    csp_c = existing_period.cool_setpoint.celsius
                    cool_target = _format_temp(existing_period.cool_setpoint, ha_unit)
                else:
                    csp_c = 24.0
                    cool_target = _format_temp(Temperature.from_celsius(csp_c), ha_unit)

                # 5. Label
                if ATTR_LABEL in p_data:
                    label = str(p_data[ATTR_LABEL]).strip()
                elif existing_period is not None:
                    label = existing_period.label
                else:
                    label = ""

                # Validate temperature bounds
                if not (min_heat_c - 0.1 <= hsp_c <= max_heat_c + 0.1):
                    raise ServiceValidationError(
                        f"Heating target ({hsp_c}°C) for {norm_day.upper()} Part {part_num} is outside "
                        f"hardware bounds ({min_heat_c}°C to {max_heat_c}°C)."
                    )
                if not (min_cool_c - 0.1 <= csp_c <= max_cool_c + 0.1):
                    raise ServiceValidationError(
                        f"Cooling target ({csp_c}°C) for {norm_day.upper()} Part {part_num} is outside "
                        f"hardware bounds ({min_cool_c}°C to {max_cool_c}°C)."
                    )

                # Validate in HA's configured unit before using the Celsius
                # values for the cloud wire payload.
                min_deadband = 3.0 if ha_unit == UnitOfTemperature.FAHRENHEIT else 2.0
                if heat_target > cool_target:
                    raise ServiceValidationError(
                        f"Invalid setpoints for {norm_day.upper()} Part {part_num}: "
                        f"heating target ({heat_target}°{ha_unit[-1]}) cannot exceed "
                        f"cooling target ({cool_target}°{ha_unit[-1]})."
                    )
                if (cool_target - heat_target) < min_deadband:
                    raise ServiceValidationError(
                        f"Deadband violation for {norm_day.upper()} Part {part_num}: "
                        f"cooling target must be at least {min_deadband}°{ha_unit[-1]} above "
                        f"heating target."
                    )

                prefix = f"sched{day_prefix}Part{part_num}"
                wire_payload[f"{prefix}Time"] = slot
                wire_payload[f"{prefix}Enabled"] = enabled
                wire_payload[f"{prefix}hsp"] = hsp_c
                wire_payload[f"{prefix}csp"] = csp_c
                wire_payload[f"{prefix}Label"] = label

    try:
        await data.daikin.set_thermostat_schedule(thermostat.id, wire_payload)
    except DaikinServiceException as err:
        raise HomeAssistantError(f"Failed to update schedule on thermostat '{thermostat.name}': {err}") from err


def async_register_services(hass: HomeAssistant) -> None:
    """Register Daikin One schedule services if not already registered."""
    if not hass.services.has_service(DOMAIN, SERVICE_GET_SCHEDULE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_SCHEDULE,
            _async_handle_get_schedule,
            schema=GET_SCHEDULE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_SCHEDULE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_SCHEDULE,
            _async_handle_set_schedule,
            schema=SET_SCHEDULE_SCHEMA,
        )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister Daikin One schedule services when the last config entry is unloaded."""
    if hass.services.has_service(DOMAIN, SERVICE_GET_SCHEDULE):
        hass.services.async_remove(DOMAIN, SERVICE_GET_SCHEDULE)
    if hass.services.has_service(DOMAIN, SERVICE_SET_SCHEDULE):
        hass.services.async_remove(DOMAIN, SERVICE_SET_SCHEDULE)
