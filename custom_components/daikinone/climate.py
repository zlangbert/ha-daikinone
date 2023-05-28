import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    HVACMode,
    ClimateEntityFeature,
    HVACAction
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.daikinone import DaikinOneData, DOMAIN
from custom_components.daikinone.const import DaikinThermostatMode, MANUFACTURER, DaikinThermostatStatus
from custom_components.daikinone.daikinone import DaikinThermostat, DaikinThermostatCapability

log = logging.getLogger(__name__)

DAIKIN_THERMOSTAT_STATUS_TO_HASS = {
    DaikinThermostatStatus.HEATING: HVACAction.HEATING,
    DaikinThermostatStatus.COOLING: HVACAction.COOLING,
    DaikinThermostatStatus.CIRCULATING_AIR: HVACAction.FAN,
    DaikinThermostatStatus.DRYING: HVACAction.DRYING,
    DaikinThermostatStatus.IDLE: HVACAction.IDLE,
}


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Daikin One thermostats"""
    data: DaikinOneData = hass.data[DOMAIN]

    entities = [
        DaikinOneThermostat(
            ClimateEntityDescription(
                key=device.id,
                name="Thermostat",
                has_entity_name=True
            ),
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

    def __init__(
            self,
            description: ClimateEntityDescription,
            data: DaikinOneData,
            thermostat: DaikinThermostat
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
            name=self._thermostat.name,
            manufacturer=MANUFACTURER,
            model=self._thermostat.model,
            sw_version=self._thermostat.firmware,
        )

    @property
    def supported_features(self):
        return (
                ClimateEntityFeature.TARGET_TEMPERATURE |
                ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        )

    @property
    def temperature_unit(self):
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        return self._thermostat.indoor_temperature

    @property
    def target_temperature(self):
        match self._thermostat.mode:
            case DaikinThermostatMode.HEAT, DaikinThermostatMode.AUX_HEAT:
                return self._thermostat.set_point_heat
            case DaikinThermostatMode.COOL:
                return self._thermostat.set_point_cool

        return None

    @property
    def target_temperature_low(self):
        match self._thermostat.mode:
            case DaikinThermostatMode.AUTO:
                return self._thermostat.set_point_heat

        return None

    @property
    def target_temperature_high(self):
        match self._thermostat.mode:
            case DaikinThermostatMode.AUTO:
                return self._thermostat.set_point_cool

        return None

    @property
    def min_temp(self):
        # these should be the same but just in case, take the larger of the two for the min
        return max(self._thermostat.set_point_heat_min, self._thermostat.set_point_cool_min)

    @property
    def max_temp(self):
        # these should be the same but just in case, take the smaller of the two for the max
        return min(self._thermostat.set_point_heat_max, self._thermostat.set_point_cool_max)

    @property
    def current_humidity(self):
        return self._thermostat.indoor_humidity

    @property
    def hvac_modes(self) -> list[HVACMode]:
        modes = [HVACMode.AUTO]

        if (DaikinThermostatCapability.HEAT in self._thermostat.capabilities and
                DaikinThermostatCapability.COOL in self._thermostat.capabilities):
            modes.append(HVACMode.HEAT_COOL)

        if DaikinThermostatCapability.HEAT in self._thermostat.capabilities:
            modes.append(HVACMode.HEAT)
        if DaikinThermostatCapability.COOL in self._thermostat.capabilities:
            modes.append(HVACMode.COOL)

        return modes

    @property
    def hvac_mode(self):
        if self._thermostat.schedule.enabled:
            return HVACMode.AUTO

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
        return DAIKIN_THERMOSTAT_STATUS_TO_HASS[self._thermostat.status]

    async def async_update(self, no_throttle: bool = False) -> None:
        """Get the latest state of the sensor."""
        await self._data.update(no_throttle=no_throttle)
        self._thermostat = self._data.daikin.get_thermostat(self._thermostat.id)
