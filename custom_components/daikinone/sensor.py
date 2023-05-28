from typing import Callable

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.const import MANUFACTURER
from custom_components.daikinone.daikinone import DaikinThermostat


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Daikin One sensors"""
    data: DaikinOneData = hass.data[DOMAIN]

    entities = [
        DaikinOneThermostatSensor(
            SensorEntityDescription(
                key="online",
                name="Online Status",
                has_entity_name=True,
                device_class=SensorDeviceClass.ENUM,
                entity_category=EntityCategory.DIAGNOSTIC
            ),
            data,
            device,
            lambda d: "Online" if d.online else "Offline"
        )
        for device in data.daikin.get_thermostats().values()
    ]

    async_add_entities(entities, True)


class DaikinOneThermostatSensor(SensorEntity):

    def __init__(
            self,
            description: SensorEntityDescription,
            data: DaikinOneData,
            device: DaikinThermostat,
            attribute: Callable[[DaikinThermostat], str]
    ) -> None:
        """Initialize the sensor."""

        self.entity_description = description
        self.data = data
        self.device = device
        self.attribute = attribute
        self._state = None

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return f"{self.device.id}-{self.name}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for this sensor."""

        return DeviceInfo(
            identifiers={(DOMAIN, self.device.id)},
            name=self.device.name,
            manufacturer=MANUFACTURER,
            model=self.device.model,
            sw_version=self.device.firmware,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self) -> None:
        """Get the latest state of the sensor."""
        await self.data.update()
        self._state = self.attribute(self.device)
