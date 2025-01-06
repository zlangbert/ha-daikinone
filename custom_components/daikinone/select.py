from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.daikinone import DaikinThermostat, DaikinThermostatFanSpeed
from custom_components.daikinone.entity import DaikinOneEntity
from custom_components.daikinone.climate import DaikinOneThermostatFanSpeed


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Daikin One select entities"""
    data: DaikinOneData = hass.data[DOMAIN]
    thermostats = data.daikin.get_thermostats().values()

    entities: list[SelectEntity] = []
    for thermostat in thermostats:
        entities += [
            DaikinOneFanSpeedSelect(
                description=SelectEntityDescription(
                    key="fan_speed",
                    name="Fan Speed",
                    has_entity_name=True,
                    icon="mdi:fan",
                    options=[speed.name.capitalize() for speed in DaikinOneThermostatFanSpeed],
                ),
                data=data,
                thermostat=thermostat,
            )
        ]

    async_add_entities(entities, True)


class DaikinOneFanSpeedSelect(DaikinOneEntity[DaikinThermostat], SelectEntity):

    def __init__(self, description: SelectEntityDescription, data: DaikinOneData, thermostat: DaikinThermostat):
        super().__init__(data, thermostat)

        self.entity_description = description

        match data.entry.data[CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY]:
            case 0 | 1:
                self._attr_unique_id = f"{self._device.id}-{self.entity_description.key}"
            case _:
                raise ValueError("unexpected entity uid schema version")

    @property
    def device_name(self) -> str:
        return f"{self._device.name} Thermostat"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        target_fan_speed: DaikinThermostatFanSpeed
        match option.upper():
            case DaikinOneThermostatFanSpeed.LOW.name:
                target_fan_speed = DaikinThermostatFanSpeed.LOW
            case DaikinOneThermostatFanSpeed.MEDIUM.name:
                target_fan_speed = DaikinThermostatFanSpeed.MEDIUM
            case DaikinOneThermostatFanSpeed.HIGH.name:
                target_fan_speed = DaikinThermostatFanSpeed.HIGH
            case _:
                raise ValueError(f"Attempted to set unsupported fan speed: {option}")

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
        self._attr_current_option = self._device.fan_speed.name.capitalize()
