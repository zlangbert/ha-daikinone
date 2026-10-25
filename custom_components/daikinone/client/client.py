"""DaikinOne orchestration: holds transport + thermostat cache, exposes the public API."""

import asyncio
import copy
import logging
from typing import Any

from custom_components.daikinone.client.mapping import map_thermostat
from custom_components.daikinone.client.models import (
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
        self._p1p2_reset_tasks: dict[str, asyncio.Task[None]] = {}

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
        thermostat = self.__thermostats.get(thermostat_id)
        if thermostat is None or not thermostat.p1p2_field_setting_supported:
            await self._transport.request(
                url=f"{DAIKIN_API_URL_DEVICE_DATA}/{thermostat_id}",
                method="PUT",
                body={"fanCirculate": fan_mode.value},
            )
            return

        existing_task = self._p1p2_reset_tasks.pop(thermostat_id, None)
        if existing_task is not None and not existing_task.done():
            existing_task.cancel()

        sw_val = 1 if fan_mode == DaikinThermostatFanMode.ALWAYS_ON else 2
        await self._transport.request(
            url=f"{DAIKIN_API_URL_DEVICE_DATA}/{thermostat_id}",
            method="PUT",
            body={
                "fanCirculate": fan_mode.value,
                "P1P2FieldSettingModeNumber": 12,
                "P1P2FieldSettingUnitNumChangeRequest": True,
                "P1P2SentFieldSettingSW3": sw_val,
                "P1P2SentFieldSettingSW6": sw_val,
            },
        )

        self._p1p2_reset_tasks[thermostat_id] = asyncio.create_task(self._reset_p1p2_field_setting(thermostat_id))

    async def _reset_p1p2_field_setting(self, thermostat_id: str, delay: float = 15.0) -> None:
        try:
            await asyncio.sleep(delay)
            await self._transport.request(
                url=f"{DAIKIN_API_URL_DEVICE_DATA}/{thermostat_id}",
                method="PUT",
                body={
                    "P1P2FieldSettingModeNumber": 0,
                    "P1P2FieldSettingUnitNumChangeRequest": False,
                    "P1P2SentFieldSettingSW3": 15,
                    "P1P2SentFieldSettingSW6": 15,
                },
            )
        except asyncio.CancelledError:
            log.debug("Cancelled pending P1/P2 field setting reset for %s", thermostat_id)
            raise
        except Exception:
            log.exception("Failed to reset P1/P2 field setting for %s", thermostat_id)
        finally:
            if self._p1p2_reset_tasks.get(thermostat_id) is asyncio.current_task():
                self._p1p2_reset_tasks.pop(thermostat_id, None)

    async def set_thermostat_fan_speed(self, thermostat_id: str, fan_speed: DaikinThermostatFanSpeed) -> None:
        """Set thermostat fan speed"""
        await self._transport.request(
            url=f"{DAIKIN_API_URL_DEVICE_DATA}/{thermostat_id}",
            method="PUT",
            body={"fanCirculateSpeed": fan_speed.value},
        )
