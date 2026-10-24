"""DaikinOne orchestration: holds transport + thermostat cache, exposes the public API."""

import copy
import logging
from typing import Any

from custom_components.daikinone.client.mapping import map_thermostat
from custom_components.daikinone.client.models import (
    DAIKIN_DAY_PREFIXES,
    SCHEDULE_PARTS,
    DaikinDaySchedule,
    DaikinSchedulePeriod,
    DaikinThermostat,
    DaikinThermostatFanMode,
    DaikinThermostatFanSpeed,
    DaikinThermostatMode,
    DaikinUserCredentials,
)
from custom_components.daikinone.client.transport import DaikinTransport
from custom_components.daikinone.client.wire import (
    DAIKIN_API_URL_DEVICE_DATA,
    DaikinDeviceDataResponse,
)
from custom_components.daikinone.utils import Temperature

log = logging.getLogger(__name__)


class DaikinOne:
    """Manages connection to Daikin API and fetching device data."""

    __thermostats: dict[str, DaikinThermostat] = dict()

    def __init__(self, creds: DaikinUserCredentials) -> None:
        self._transport = DaikinTransport(creds)

    async def login(self) -> bool:
        return await self._transport.login()

    async def get_all_raw_device_data(self) -> list[dict[str, Any]]:
        """Get raw device data"""
        return await self._transport.request(DAIKIN_API_URL_DEVICE_DATA)

    async def get_raw_device_data(self, device_id: str) -> dict[str, Any]:
        """Get raw device data"""
        return await self._transport.request(f"{DAIKIN_API_URL_DEVICE_DATA}/{device_id}")

    async def update(self) -> None:
        raw = await self._transport.request(DAIKIN_API_URL_DEVICE_DATA)
        responses = [DaikinDeviceDataResponse(**d) for d in raw]

        for r in responses:
            if not r.online and len(r.data) == 0:
                log.warning(f"Skipping offline device with no data: {r.name} ({r.id})")
                continue
            self.__thermostats[r.id] = map_thermostat(r)

        log.info(f"Cached {len(self.__thermostats)} thermostats")

    def get_thermostat(self, thermostat_id: str) -> DaikinThermostat:
        return copy.deepcopy(self.__thermostats[thermostat_id])

    def get_thermostats(self) -> dict[str, DaikinThermostat]:
        return copy.deepcopy(self.__thermostats)

    async def set_thermostat_mode(self, thermostat_id: str, mode: DaikinThermostatMode) -> None:
        """Set thermostat mode"""
        await self._transport.request(
            url=f"{DAIKIN_API_URL_DEVICE_DATA}/{thermostat_id}",
            method="PUT",
            body={"mode": mode.value},
        )

    async def set_thermostat_home_set_points(
        self,
        thermostat_id: str,
        heat: Temperature | None = None,
        cool: Temperature | None = None,
        override_schedule: bool = False,
    ) -> None:
        """Set thermostat home set points"""
        if not heat and not cool:
            raise ValueError("At least one of heat or cool set points must be set")

        payload: dict[str, Any] = {}
        if heat:
            payload["hspHome"] = heat.celsius
        if cool:
            payload["cspHome"] = cool.celsius
        if override_schedule:
            payload["schedOverride"] = 1

        await self._transport.request(
            url=f"{DAIKIN_API_URL_DEVICE_DATA}/{thermostat_id}",
            method="PUT",
            body=payload,
        )

    async def set_thermostat_fan_mode(self, thermostat_id: str, fan_mode: DaikinThermostatFanMode) -> None:
        """Set thermostat fan mode"""
        await self._transport.request(
            url=f"{DAIKIN_API_URL_DEVICE_DATA}/{thermostat_id}",
            method="PUT",
            body={"fanCirculate": fan_mode.value},
        )

    async def set_thermostat_fan_speed(self, thermostat_id: str, fan_speed: DaikinThermostatFanSpeed) -> None:
        """Set thermostat fan speed"""
        await self._transport.request(
            url=f"{DAIKIN_API_URL_DEVICE_DATA}/{thermostat_id}",
            method="PUT",
            body={"fanCirculateSpeed": fan_speed.value},
        )

    async def set_thermostat_schedule(self, thermostat_id: str, payload: dict[str, Any]) -> None:
        """Send an atomic batch PUT request to update thermostat schedule keys and update cache."""
        if not payload:
            raise ValueError("Schedule payload must not be empty")

        await self._transport.request(
            url=f"{DAIKIN_API_URL_DEVICE_DATA}/{thermostat_id}",
            method="PUT",
            body=payload,
        )

        # Optimistically apply the modified wire keys to the in-memory cached thermostat
        self._apply_optimistic_schedule_payload(thermostat_id, payload)

    def _apply_optimistic_schedule_payload(self, thermostat_id: str, payload: dict[str, Any]) -> None:
        """Update the cached DaikinThermostat.schedule in place from a wire key payload."""
        thermostat = self.__thermostats.get(thermostat_id)
        if thermostat is None:
            return

        if "schedEnabled" in payload:
            thermostat.schedule.enabled = bool(payload["schedEnabled"])
        if "schedOverride" in payload:
            thermostat.schedule.override = bool(payload["schedOverride"])

        if thermostat.schedule.days is None:
            thermostat.schedule.days = {}

        for day_key, day_prefix in DAIKIN_DAY_PREFIXES.items():
            for part in SCHEDULE_PARTS:
                prefix = f"sched{day_prefix}Part{part}"
                time_key = f"{prefix}Time"
                enabled_key = f"{prefix}Enabled"
                hsp_key = f"{prefix}hsp"
                csp_key = f"{prefix}csp"
                label_key = f"{prefix}Label"
                action_key = f"{prefix}Action"

                if not any(k in payload for k in (time_key, enabled_key, hsp_key, csp_key, label_key, action_key)):
                    continue

                day_sched = thermostat.schedule.days.get(day_key)
                if day_sched is None:
                    day_sched = DaikinDaySchedule(day=day_key, periods={})
                    thermostat.schedule.days[day_key] = day_sched

                existing = day_sched.periods.get(part)
                new_slot = int(payload[time_key]) if time_key in payload else (existing.start_slot if existing else 0)
                new_enabled = (
                    bool(payload[enabled_key]) if enabled_key in payload else (existing.enabled if existing else False)
                )
                new_hsp = (
                    Temperature.from_celsius(float(payload[hsp_key]))
                    if hsp_key in payload
                    else (existing.heat_setpoint if existing else Temperature.from_celsius(20.0))
                )
                new_csp = (
                    Temperature.from_celsius(float(payload[csp_key]))
                    if csp_key in payload
                    else (existing.cool_setpoint if existing else Temperature.from_celsius(24.0))
                )
                new_label = (
                    str(payload[label_key]).strip() if label_key in payload else (existing.label if existing else "")
                )
                new_action = int(payload[action_key]) if action_key in payload else (existing.action if existing else 0)

                day_sched.periods[part] = DaikinSchedulePeriod(
                    part=part,
                    enabled=new_enabled,
                    start_slot=new_slot,
                    heat_setpoint=new_hsp,
                    cool_setpoint=new_csp,
                    label=new_label,
                    action=new_action,
                )
