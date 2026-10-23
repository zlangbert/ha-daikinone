"""Switch platform for Daikin One configuration controls."""

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.client.models import DaikinThermostat
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.entity import DaikinOneEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Daikin One night mode switches."""
    data: DaikinOneData = hass.data[DOMAIN]
    entities = [
        DaikinOneNightModeSwitch(
            data,
            thermostat,
            SwitchEntityDescription(
                key="night_mode",
                name="Night mode",
                icon="mdi:weather-night",
                has_entity_name=True,
                translation_key="night_mode",
                entity_category=EntityCategory.CONFIG,
            ),
        )
        for thermostat in data.daikin.get_thermostats().values()
        if thermostat.night_mode_enabled is not None
    ]
    async_add_entities(entities, True)


class DaikinOneNightModeSwitch(DaikinOneEntity[DaikinThermostat], SwitchEntity):
    """Enable or disable thermostat night mode."""

    def __init__(
        self,
        data: DaikinOneData,
        thermostat: DaikinThermostat,
        description: SwitchEntityDescription,
    ) -> None:
        super().__init__(data, thermostat)
        self.entity_description = description
        match data.entry.data[CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY]:
            case 0 | 1:
                self._attr_unique_id = f"{self._device.id}-{description.key}"
            case _:
                raise ValueError("unexpected entity uid schema version")
        self.update_entity_attributes()

    @property
    def device_name(self) -> str:
        return f"{self._device.name} Thermostat"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_night_mode(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_night_mode(False)

    async def _set_night_mode(self, enabled: bool) -> None:
        def update(thermostat: DaikinThermostat) -> None:
            thermostat.night_mode_enabled = enabled
            self.update_entity_attributes()

        await self.update_state_optimistically(
            operation=lambda: self._data.daikin.set_thermostat_night_mode(self._device.id, enabled),
            optimistic_update=update,
            check=lambda thermostat: thermostat.night_mode_enabled == enabled,
        )

    async def async_get_device(self) -> DaikinThermostat:
        return self._data.daikin.get_thermostat(self._device.id)

    def update_entity_attributes(self) -> None:
        self._attr_is_on = bool(self._device.night_mode_enabled)
        attributes: dict[str, Any] = {}
        if self._device.night_mode_active is not None:
            attributes["night_mode_active"] = self._device.night_mode_active
        if self._device.night_mode_light_bar_allowed is not None:
            attributes["light_bar_allowed"] = self._device.night_mode_light_bar_allowed
        self._attr_extra_state_attributes = attributes
