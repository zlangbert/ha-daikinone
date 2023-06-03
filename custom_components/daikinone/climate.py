import logging
from typing import Callable

import backoff
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    HVACMode,
    ClimateEntityFeature,
    HVACAction,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_HIGH,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.daikinone import DaikinOneData, DOMAIN
from custom_components.daikinone.const import MANUFACTURER
from custom_components.daikinone.daikinone import (
    DaikinThermostat,
    DaikinThermostatCapability,
    DaikinThermostatMode,
    DaikinThermostatStatus,
)
from custom_components.daikinone.utils import Temperature

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Daikin One thermostats"""
    data: DaikinOneData = hass.data[DOMAIN]

    entities = [
        DaikinOneThermostat(
            ClimateEntityDescription(key=device.id, has_entity_name=True),
            data,
            device,
        )
        for device in data.daikin.get_thermostats().values()
    ]

    async_add_entities(entities, True)


class DaikinOneThermostat(ClimateEntity):
    """Thermostat entity for Daikin One"""

    _data: DaikinOneData
    _thermostat: DaikinThermostat

    _updates_paused: bool = False

    def __init__(
        self,
        description: ClimateEntityDescription,
        data: DaikinOneData,
        thermostat: DaikinThermostat,
    ):
        self.entity_description = description
        self._data = data
        self._thermostat = thermostat

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return f"{self._thermostat.id}-climate"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for this sensor."""

        return DeviceInfo(
            identifiers={(DOMAIN, self._thermostat.id)},
            name=f"{self._thermostat.name} Thermostat",
            manufacturer=MANUFACTURER,
            model=self._thermostat.model,
            sw_version=self._thermostat.firmware_version,
        )

    @property
    def available(self):
        """Return if device is available."""
        return self._thermostat.online

    @property
    def supported_features(self):
        return ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

    @property
    def temperature_unit(self):
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        return self._thermostat.indoor_temperature.celsius

    @property
    def target_temperature(self) -> float | None:
        match self._thermostat.mode:
            case DaikinThermostatMode.HEAT | DaikinThermostatMode.AUX_HEAT:
                return self._thermostat.set_point_heat.celsius
            case DaikinThermostatMode.COOL:
                return self._thermostat.set_point_cool.celsius
            case _:
                pass

        return None

    @property
    def target_temperature_low(self) -> float | None:
        match self._thermostat.mode:
            case DaikinThermostatMode.AUTO:
                return self._thermostat.set_point_heat.celsius
            case _:
                pass

        return None

    @property
    def target_temperature_high(self) -> float | None:
        match self._thermostat.mode:
            case DaikinThermostatMode.AUTO:
                return self._thermostat.set_point_cool.celsius
            case _:
                pass

        return None

    @property
    def min_temp(self) -> float:
        # these should be the same but just in case, take the larger of the two for the min
        return max(
            self._thermostat.set_point_heat_min.celsius,
            self._thermostat.set_point_cool_min.celsius,
        )

    @property
    def max_temp(self) -> float:
        # these should be the same but just in case, take the smaller of the two for the max
        return min(
            self._thermostat.set_point_heat_max.celsius,
            self._thermostat.set_point_cool_max.celsius,
        )

    @property
    def current_humidity(self) -> int:
        return self._thermostat.indoor_humidity

    @property
    def hvac_modes(self) -> list[HVACMode]:
        modes: list[HVACMode] = []

        if (
            DaikinThermostatCapability.HEAT in self._thermostat.capabilities
            and DaikinThermostatCapability.COOL in self._thermostat.capabilities
        ):
            modes.append(HVACMode.HEAT_COOL)

        if DaikinThermostatCapability.HEAT in self._thermostat.capabilities:
            modes.append(HVACMode.HEAT)
        if DaikinThermostatCapability.COOL in self._thermostat.capabilities:
            modes.append(HVACMode.COOL)

        modes.append(HVACMode.OFF)

        return modes

    @property
    def hvac_mode(self):
        match self._thermostat.mode:
            case DaikinThermostatMode.AUTO:
                return HVACMode.HEAT_COOL
            case DaikinThermostatMode.HEAT:
                return HVACMode.HEAT
            case DaikinThermostatMode.COOL:
                return HVACMode.COOL
            case DaikinThermostatMode.AUX_HEAT:
                return HVACMode.HEAT
            case DaikinThermostatMode.OFF:
                return HVACMode.OFF

    @property
    def hvac_action(self):
        match self._thermostat.status:
            case DaikinThermostatStatus.HEATING:
                return HVACAction.HEATING
            case DaikinThermostatStatus.COOLING:
                return HVACAction.COOLING
            case DaikinThermostatStatus.CIRCULATING_AIR:
                return HVACAction.FAN
            case DaikinThermostatStatus.DRYING:
                return HVACAction.DRYING
            case DaikinThermostatStatus.IDLE:
                return HVACAction.IDLE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        target_mode: DaikinThermostatMode
        match hvac_mode:
            case HVACMode.HEAT_COOL:
                target_mode = DaikinThermostatMode.AUTO
            case HVACMode.HEAT:
                target_mode = DaikinThermostatMode.HEAT
            case HVACMode.COOL:
                target_mode = DaikinThermostatMode.COOL
            case HVACMode.OFF:
                target_mode = DaikinThermostatMode.OFF
            case _:
                raise ValueError(f"Attempted to set unsupported HVAC mode: {hvac_mode}")

        log.debug("Setting thermostat mode to %s", target_mode)

        # update thermostat mode
        await self._data.daikin.set_thermostat_mode(self._thermostat.id, target_mode)

        # update entity state optimistically
        def update(t: DaikinThermostat):
            t.mode = target_mode

        await self.update_state_optimistically(
            update=update,
            check=lambda t: t.mode == target_mode,
        )

    async def async_set_temperature(self, **kwargs: float) -> None:
        """Set new target temperature(s)."""

        temperature = kwargs.get(ATTR_TEMPERATURE)
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        if target_temp_low or target_temp_high:
            heat = Temperature.from_celsius(target_temp_low) if target_temp_low is not None else None
            cool = Temperature.from_celsius(target_temp_high) if target_temp_high is not None else None

            # TODO: take min temp delta into account

            log.debug("Setting thermostat set points: heat=%s and cool=%s", heat, cool)

            await self._data.daikin.set_thermostat_home_set_points(
                self._thermostat.id,
                heat=heat,
                cool=cool,
                override_schedule=self._thermostat.schedule.enabled,
            )

            # update entity state optimistically
            def update(t: DaikinThermostat):
                if heat is not None:
                    t.set_point_heat = heat
                if cool is not None:
                    t.set_point_cool = cool

            await self.update_state_optimistically(
                update=update,
                check=lambda t: t.set_point_heat == heat and t.set_point_cool == cool,
            )

        elif temperature:
            # setting a single temperature is only valid if the thermostat is in a mode that allows us to infer whether
            # it is a heat or cool set point
            temperature = Temperature.from_celsius(temperature)

            match self._thermostat.mode:
                case DaikinThermostatMode.HEAT | DaikinThermostatMode.AUX_HEAT:
                    log.debug("Setting thermostat set point: heat=%s ", temperature)

                    await self._data.daikin.set_thermostat_home_set_points(self._thermostat.id, heat=temperature)

                    # update entity state optimistically
                    def update(t: DaikinThermostat):
                        t.set_point_heat = temperature

                    await self.update_state_optimistically(
                        update=update,
                        check=lambda t: t.set_point_heat == temperature,
                    )

                case DaikinThermostatMode.COOL:
                    log.debug("Setting thermostat set point: cool=%s ", temperature)

                    await self._data.daikin.set_thermostat_home_set_points(self._thermostat.id, cool=temperature)

                    # update entity state optimistically
                    def update(t: DaikinThermostat):
                        t.set_point_cool = temperature

                    await self.update_state_optimistically(
                        update=update,
                        check=lambda t: t.set_point_cool == temperature,
                    )

                case _:
                    raise ValueError("Invalid thermostat mode and set temperature combination")
        else:
            raise ValueError("Set temperature called with no temperature values")

    async def async_update(self, no_throttle: bool = False) -> None:
        """Get the latest state of the sensor."""
        if self._updates_paused:
            return

        log.debug("Updating climate entity for thermostat %s", self._thermostat.id)
        await self._data.update(no_throttle=no_throttle)
        self._thermostat = self._data.daikin.get_thermostat(self._thermostat.id)

    async def update_state_optimistically(
        self, update: Callable[[DaikinThermostat], None], check: Callable[[DaikinThermostat], bool]
    ) -> None:
        """
        Executes the given state update optimistically, then waits for the API to update the state as well. Regularly
        scheduled updates are paused while waiting to avoid overwriting the optimistic update with stale data. A full
        entity update is scheduled at the end regardless of whether updated remote state was found or not.
        """
        # pause entity updates
        _updates_paused = True

        # execute state update optimistically
        update(self._thermostat)
        self.async_write_ha_state()

        # wait for remote state to be updated
        await self._wait_for_updated_value(check)

        # resume entity updates
        _updates_paused = False

        # full entity update to make sure everything is in sync
        await self.async_update(no_throttle=True)
        self.async_write_ha_state()

    @backoff.on_predicate(
        backoff.constant,
        max_time=10,
        on_success=lambda _: log.debug("Finished waiting for updated value"),
        on_giveup=lambda _: log.debug("Gave up waiting for updated value"),
        logger=log.getChild("backoff"),
        backoff_log_level=logging.DEBUG,
        giveup_log_level=logging.DEBUG,
    )
    async def _wait_for_updated_value(self, check: Callable[[DaikinThermostat], bool]) -> bool:
        """
        Waits for an updated value from the API. Continually retries until the check passes or max_time has been
        reached.
        """

        await self._data.update(no_throttle=True)
        return check(self._data.daikin.get_thermostat(self._thermostat.id))
