from enum import Enum
import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
)
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_HIGH,
    FAN_ON,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_OFF,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.daikinone import DaikinOneData, DOMAIN
from custom_components.daikinone.entity import DaikinOneEntity
from custom_components.daikinone.daikinone import (
    DaikinThermostat,
    DaikinThermostatCapability,
    DaikinThermostatMode,
    DaikinThermostatStatus,
    DaikinThermostatFanMode,
    DaikinThermostatFanSpeed,
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


class DaikinOneThermostatFanMode(Enum):
    OFF = FAN_OFF
    ALWAYS_ON = "always_on"
    SCHEDULED = "schedule"
    LOW = FAN_LOW
    MEDIUM = FAN_MEDIUM
    HIGH = FAN_HIGH

class DaikinOneThermostatFanSpeed(Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2


class DaikinOneThermostat(DaikinOneEntity[DaikinThermostat], ClimateEntity):
    """Thermostat entity for Daikin One"""

    # to be removed in a future version of HA
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        description: ClimateEntityDescription,
        data: DaikinOneData,
        thermostat: DaikinThermostat,
    ):
        super().__init__(data, thermostat)

        self.entity_description = description

        self._attr_translation_key = "daikinone_thermostat"
        self._attr_unique_id = f"{self._device.id}-climate"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_supported_features = (
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.FAN_MODE
        )
        self._attr_hvac_modes = self.get_hvac_modes()
        self._attr_fan_modes = [m.value for m in DaikinOneThermostatFanMode]

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

        if DaikinThermostatCapability.EMERGENCY_HEAT in self._device.capabilities:
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes += [DaikinOneThermostatPresetMode.EMERGENCY_HEAT.value]

    def get_hvac_modes(self) -> list[HVACMode]:
        modes: list[HVACMode] = []

        if (
            DaikinThermostatCapability.HEAT in self._device.capabilities
            and DaikinThermostatCapability.COOL in self._device.capabilities
        ):
            modes.append(HVACMode.HEAT_COOL)

        if DaikinThermostatCapability.HEAT in self._device.capabilities:
            modes.append(HVACMode.HEAT)
        if DaikinThermostatCapability.COOL in self._device.capabilities:
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
        await self._data.daikin.set_thermostat_mode(self._device.id, target_mode)

        # update thermostat mode optimistically
        def update(t: DaikinThermostat):
            t.mode = target_mode

        await self.update_state_optimistically(
            operation=lambda: self._data.daikin.set_thermostat_mode(self._device.id, target_mode),
            optimistic_update=update,
            check=lambda t: t.mode == target_mode,
        )

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new target preset mode."""
        match preset_mode:

            case DaikinOneThermostatPresetMode.EMERGENCY_HEAT.value:
                await self.set_thermostat_mode(DaikinThermostatMode.AUX_HEAT)

            case DaikinOneThermostatPresetMode.NONE.value:
                match self._device.mode:

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

            # update set points optimistically
            def update(t: DaikinThermostat):
                if heat is not None:
                    t.set_point_heat = heat
                if cool is not None:
                    t.set_point_cool = cool

            await self.update_state_optimistically(
                operation=lambda: self._data.daikin.set_thermostat_home_set_points(
                    self._device.id,
                    heat=heat,
                    cool=cool,
                    override_schedule=self._device.schedule.enabled,
                ),
                optimistic_update=update,
                check=lambda t: t.set_point_heat == heat and t.set_point_cool == cool,
            )

        elif temperature:
            # setting a single temperature is only valid if the thermostat is in a mode that allows us to infer whether
            # it is a heat or cool set point
            temperature = Temperature.from_celsius(temperature)

            match self._device.mode:
                case DaikinThermostatMode.HEAT | DaikinThermostatMode.AUX_HEAT:
                    log.debug("Setting thermostat set point: heat=%s ", temperature)

                    # update set points optimistically
                    def update(t: DaikinThermostat):
                        t.set_point_heat = temperature

                    await self.update_state_optimistically(
                        operation=lambda: self._data.daikin.set_thermostat_home_set_points(
                            self._device.id,
                            heat=temperature,
                        ),
                        optimistic_update=update,
                        check=lambda t: t.set_point_heat == temperature,
                    )

                case DaikinThermostatMode.COOL:
                    log.debug("Setting thermostat set point: cool=%s ", temperature)

                    # update set points optimistically
                    def update(t: DaikinThermostat):
                        t.set_point_cool = temperature

                    await self.update_state_optimistically(
                        operation=lambda: self._data.daikin.set_thermostat_home_set_points(
                            self._device.id,
                            cool=temperature,
                        ),
                        optimistic_update=update,
                        check=lambda t: t.set_point_cool == temperature,
                    )

                case _:
                    raise ValueError("Invalid thermostat mode and set temperature combination")
        else:
            raise ValueError("Set temperature called with no temperature values")

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        target_fan_mode: DaikinThermostatFanMode

        match fan_mode:
            case DaikinOneThermostatFanMode.OFF.value:
                target_fan_mode = DaikinThermostatFanMode.OFF
            case DaikinOneThermostatFanMode.ALWAYS_ON.value:
                target_fan_mode = DaikinThermostatFanMode.ALWAYS_ON
            case DaikinOneThermostatFanMode.SCHEDULED.value:
                target_fan_mode = DaikinThermostatFanMode.SCHEDULED
            case DaikinOneThermostatFanMode.LOW.value:
                target_fan_mode = DaikinOneThermostatFanMode.LOW
            case DaikinOneThermostatFanMode.MEDIUM.value:
                target_fan_mode = DaikinOneThermostatFanMode.MEDIUM
            case DaikinOneThermostatFanMode.HIGH.value:
                target_fan_mode = DaikinOneThermostatFanMode.HIGH
            case _:
                raise ValueError(f"Attempted to set unsupported fan mode: {fan_mode}")

        if fan_mode in { DaikinOneThermostatFanMode.OFF.value, DaikinOneThermostatFanMode.ALWAYS_ON.value, DaikinOneThermostatFanMode.SCHEDULED.value } :
            # update fan mode optimistically
            def update(t: DaikinThermostat):
                t.fan_mode = target_fan_mode

            await self.update_state_optimistically(
                operation=lambda: self._data.daikin.set_thermostat_fan_mode(self._device.id, target_fan_mode),
                optimistic_update=update,
                check=lambda t: t.fan_mode == target_fan_mode,
            )
        else:
            # update fan mode to always_on before changing speed
            
            def update(t: DaikinThermostat):
                t.fan_mode = DaikinThermostatFanMode.ALWAYS_ON

            await self.update_state_optimistically(
                operation=lambda: self._data.daikin.set_thermostat_fan_mode(self._device.id, DaikinThermostatFanMode.ALWAYS_ON),
                optimistic_update=update,
                check=lambda t: t.fan_mode == DaikinThermostatFanMode.ALWAYS_ON,
            )
            
            target_fan_speed: DaikinThermostatFanSpeed
            
            match target_fan_mode:
                case DaikinOneThermostatFanMode.LOW:
                    target_fan_speed = DaikinThermostatFanSpeed.LOW
                case DaikinOneThermostatFanMode.MEDIUM:
                    target_fan_speed = DaikinThermostatFanSpeed.MEDIUM
                case DaikinOneThermostatFanMode.HIGH:
                    target_fan_speed = DaikinThermostatFanSpeed.HIGH
                case _:
                    raise ValueError(f"Attempted to set unsupported fan speed: {target_fan_mode}")     
                           
            # update fan speed optimistically
            def update(t: DaikinThermostat):
                t.fan_speed = target_fan_speed

            await self.update_state_optimistically(
                operation=lambda: self._data.daikin.set_thermostat_fan_speed(self._device.id, target_fan_speed),
                optimistic_update=update,
                check=lambda t: t.fan_speed == target_fan_speed,
            )
        
    async def async_get_device(self) -> DaikinThermostat:
        return self._data.daikin.get_thermostat(self._device.id)

    def update_entity_attributes(self) -> None:
        self._attr_available = self._device.online
        self._attr_current_temperature = self._device.indoor_temperature.celsius
        self._attr_current_humidity = self._device.indoor_humidity

        # hvac current mode and preset
        self._attr_preset_mode = DaikinOneThermostatPresetMode.NONE.value
        match self._device.mode:
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
        match self._device.status:
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

        match self._device.mode:
            case DaikinThermostatMode.HEAT | DaikinThermostatMode.AUX_HEAT:
                self._attr_target_temperature = self._device.set_point_heat.celsius
            case DaikinThermostatMode.COOL:
                self._attr_target_temperature = self._device.set_point_cool.celsius
            case DaikinThermostatMode.AUTO:
                self._attr_target_temperature_low = self._device.set_point_heat.celsius
                self._attr_target_temperature_high = self._device.set_point_cool.celsius
            case _:
                pass

        # temperature bounds
        # these should be the same but just in case, take the larger of the two for the min
        self._attr_min_temp = max(
            self._device.set_point_heat_min.celsius,
            self._device.set_point_cool_min.celsius,
        )
        # these should be the same but just in case, take the smaller of the two for the max
        self._attr_max_temp = min(
            self._device.set_point_heat_max.celsius,
            self._device.set_point_cool_max.celsius,
        )

        # fan settings
        match self._device.fan_mode:
            case DaikinThermostatFanMode.OFF:
                self._attr_fan_mode = DaikinOneThermostatFanMode.OFF.value
            case DaikinThermostatFanMode.ALWAYS_ON:
                self._attr_fan_mode = DaikinOneThermostatFanMode.ALWAYS_ON.value
            case DaikinThermostatFanMode.SCHEDULED:
                self._attr_fan_mode = DaikinOneThermostatFanMode.SCHEDULED.value
