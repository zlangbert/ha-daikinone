from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.client.models import DaikinThermostat
from custom_components.daikinone.entity import DaikinOneEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Daikin One switch entities"""
    data: DaikinOneData = hass.data[DOMAIN]
    thermostats = data.daikin.get_thermostats().values()

    entities: list[SwitchEntity] = []
    for thermostat in thermostats:
        if thermostat.one_clean_fan_active is not None:
            entities.append(
                DaikinOneOneCleanFanSwitch(
                    description=SwitchEntityDescription(
                        key="one_clean_fan",
                        name="One Clean Fan",
                        has_entity_name=True,
                        icon="mdi:fan-auto",
                    ),
                    data=data,
                    thermostat=thermostat,
                )
            )

    async_add_entities(entities, True)


class DaikinOneOneCleanFanSwitch(DaikinOneEntity[DaikinThermostat], SwitchEntity):
    """Runs the One Clean cycle: the indoor fan at full speed for three hours."""

    def __init__(self, description: SwitchEntityDescription, data: DaikinOneData, thermostat: DaikinThermostat):
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_active(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_active(False)

    async def _set_active(self, active: bool) -> None:
        def update(t: DaikinThermostat) -> None:
            t.one_clean_fan_active = active

        await self.update_state_optimistically(
            operation=lambda: self._data.daikin.set_one_clean_fan_active(self._device.id, active),
            optimistic_update=update,
            check=lambda t: t.one_clean_fan_active == active,
        )

    async def async_get_device(self) -> DaikinThermostat:
        return self._data.daikin.get_thermostat(self._device.id)

    def update_entity_attributes(self) -> None:
        self._attr_is_on = self._device.one_clean_fan_active
