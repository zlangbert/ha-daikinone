from enum import Enum
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
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_ON,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)
from custom_components.daikinone.const import (FAN_SCHEDULE)

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
    DaikinFan,
    DaikinFanMode,
    DaikinFanSpeed,
)
from custom_components.daikinone.utils import Temperature

DaikinFanModeMap: dict[str, int] = {
    FAN_AUTO: 0,
    FAN_ON: 1,
    FAN_SCHEDULE: 2,
    FAN_LOW: 0,
    FAN_MEDIUM: 1,
    FAN_HIGH: 2,
}

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
            ClimateEntityDescription(key=device.id, has_entity_name=True, name=None),
            data,
            device,
        )
        for device in data.daikin.get_thermostats().values()
    ]

    async_add_entities(entities, True)


class DaikinOneThermostatPresetMode(Enum):
    NONE = "none"
    EMERGENCY_HEAT = "emergency_heat"


class DaikinOneThermostat(ClimateEntity):
    """Thermostat entity for Daikin One"""

    _data: DaikinOneData
    _thermostat: DaikinThermostat

    _updates_paused: bool = False

    # to be removed in a future version of HA
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        description: ClimateEntityDescription,
        data: DaikinOneData,
        thermostat: DaikinThermostat,
    ):
        self.entity_description = description
        self._data = data
        self._thermostat = thermostat

        self._attr_translation_key = "daikinone_thermostat"
        self._attr_unique_id = f"{self._thermostat.id}-climate"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_supported_features = (
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.FAN_MODE
        )
        self._attr_hvac_modes = self.get_hvac_modes()

        # Adding fan support
        self._attr_fan_modes = [FAN_AUTO, FAN_ON, FAN_SCHEDULE, FAN_LOW, FAN_MEDIUM, FAN_HIGH]    
        self._attr_fan_mode = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._thermostat.id)},
            name=f"{self._thermostat.name} Thermostat",
            manufacturer=MANUFACTURER,
            model=self._thermostat.model,
            sw_version=self._thermostat.firmware_version,
        )

        # These attributes must be initialized otherwise HA `CachedProperties` doesn't create a
        # backing prop. If they are not initialized, climate will error during setup because we support
        # TARGET_TEMPERATURE_RANGE and it tries to read them. These attributes are not initialized in
        # `ClimateEntity` like most others, and in a case where the thermostat is not set to auto,
        # they do not get set in async_update either.
        self._attr_target_temperature_low = None
        self._attr_target_temperature_high = None

        # Set up preset modes based on thermostat capabilities. The preset climate feature will only be
        # enabled if at least one preset is detected as supported.
        self._attr_preset_modes = [DaikinOneThermostatPresetMode.NONE.value]
        self._attr_preset_mode = None
        
        if DaikinThermostatCapability.EMERGENCY_HEAT in self._thermostat.capabilities:
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes += [DaikinOneThermostatPresetMode.EMERGENCY_HEAT.value]

    def get_hvac_modes(self) -> list[HVACMode]:
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

        await self.set_thermostat_mode(target_mode)

    async def set_thermostat_mode(self, target_mode: DaikinThermostatMode) -> None:
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

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        log.debug("Setting thermostat fan mode to %s", fan_mode)
        if fan_mode in {FAN_ON, FAN_AUTO, FAN_SCHEDULE}:
            # update fan mode
            await self._data.daikin.set_fan_mode(self._thermostat.id, DaikinFanModeMap.get(fan_mode))        
        elif fan_mode in {FAN_LOW, FAN_MEDIUM, FAN_HIGH}:
            # update fan speed
            if self._attr_fan_mode == FAN_AUTO:
                await self._data.daikin.set_fan_mode(self._thermostat.id, DaikinFanModeMap.get(FAN_ON))        
            await self._data.daikin.set_fan_speed(self._thermostat.id, DaikinFanModeMap.get(fan_mode)) 
        else:
            raise ValueError("At least one of heat or cool set points must be set")

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new target preset mode."""
        match preset_mode:

            case DaikinOneThermostatPresetMode.EMERGENCY_HEAT.value:
                await self.set_thermostat_mode(DaikinThermostatMode.AUX_HEAT)

            case DaikinOneThermostatPresetMode.NONE.value:
                match self._thermostat.mode:

                    # turning off emergency heat should set the thermostat mode to heat
                    case DaikinThermostatMode.AUX_HEAT:
                        await self.set_thermostat_mode(DaikinThermostatMode.HEAT)

                    # any other thermostat mode should already be "none", and if its not,
                    # we don't need to do anything
                    case _:
                        pass

            case _:
                raise ValueError(f"Attempted to set unsupported preset mode: {preset_mode}")

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

        self.update_entity_attributes()

    def update_entity_attributes(self) -> None:
        self._attr_available = self._thermostat.online
        self._attr_current_temperature = self._thermostat.indoor_temperature.celsius
        self._attr_current_humidity = self._thermostat.indoor_humidity

        # hvac current mode and preset
        self._attr_preset_mode = DaikinOneThermostatPresetMode.NONE.value
        match self._thermostat.mode:
            case DaikinThermostatMode.AUTO:
                self._attr_hvac_mode = HVACMode.HEAT_COOL
            case DaikinThermostatMode.HEAT:
                self._attr_hvac_mode = HVACMode.HEAT
            case DaikinThermostatMode.COOL:
                self._attr_hvac_mode = HVACMode.COOL
            case DaikinThermostatMode.AUX_HEAT:
                self._attr_hvac_mode = HVACMode.HEAT
                self._attr_preset_mode = DaikinOneThermostatPresetMode.EMERGENCY_HEAT.value
            case DaikinThermostatMode.OFF:
                self._attr_hvac_mode = HVACMode.OFF

        # hvac current action
        match self._thermostat.status:
            case DaikinThermostatStatus.HEATING:
                self._attr_hvac_action = HVACAction.HEATING
            case DaikinThermostatStatus.COOLING:
                self._attr_hvac_action = HVACAction.COOLING
            case DaikinThermostatStatus.CIRCULATING_AIR:
                self._attr_hvac_action = HVACAction.FAN
            case DaikinThermostatStatus.DRYING:
                self._attr_hvac_action = HVACAction.DRYING
            case DaikinThermostatStatus.IDLE:
                self._attr_hvac_action = HVACAction.IDLE

        # target temperature

        # reset target temperature attributes first, single target temp takes precedence and can conflict with range
        self._attr_target_temperature = None
        self._attr_target_temperature_low = None
        self._attr_target_temperature_high = None

        match self._thermostat.mode:
            case DaikinThermostatMode.HEAT | DaikinThermostatMode.AUX_HEAT:
                self._attr_target_temperature = self._thermostat.set_point_heat.celsius
            case DaikinThermostatMode.COOL:
                self._attr_target_temperature = self._thermostat.set_point_cool.celsius
            case DaikinThermostatMode.AUTO:
                self._attr_target_temperature_low = self._thermostat.set_point_heat.celsius
                self._attr_target_temperature_high = self._thermostat.set_point_cool.celsius
            case _:
                pass

        # temperature bounds
        # these should be the same but just in case, take the larger of the two for the min
        self._attr_min_temp = max(
            self._thermostat.set_point_heat_min.celsius,
            self._thermostat.set_point_cool_min.celsius,
        )
        # these should be the same but just in case, take the smaller of the two for the max
        self._attr_max_temp = min(
            self._thermostat.set_point_heat_max.celsius,
            self._thermostat.set_point_cool_max.celsius,
        )

        # Fan mode.
        self._attr_fan_mode = FAN_AUTO
        if self._thermostat.fan == DaikinFan.AUTO and self._thermostat.fan_mode == DaikinFanMode.OFF:
            self._attr_fan_mode = FAN_AUTO
        elif self._thermostat.fan_mode == DaikinFanMode.SCHEDULE:
            self._attr_fan_mode = FAN_SCHEDULE
        elif self._thermostat.fan_mode == DaikinFanMode.OFF:
            self._attr_fan_mode = FAN_OFF
        elif self._thermostat.fan_speed == DaikinFanSpeed.LOW:
            self._attr_fan_mode = FAN_LOW
        elif self._thermostat.fan_speed == DaikinFanSpeed.MEDIUM:
            self._attr_fan_mode = FAN_MEDIUM
        elif self._thermostat.fan_speed == DaikinFanSpeed.HIGH:
            self._attr_fan_mode = FAN_HIGH

        log.debug("fan: %s", self._thermostat.fan )
        log.debug("fan_mode: %s", self._thermostat.fan_mode )
        log.debug("fan_speed: %s", self._thermostat.fan_speed )


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
        self.update_entity_attributes()
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
