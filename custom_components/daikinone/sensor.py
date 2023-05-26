import random

from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass, SensorStateClass

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.const import MANUFACTURER


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Daikin One sensors"""
    data: DaikinOneData = hass.data[DOMAIN]

    # entities = [
    #     DaikinOneSensor(daikin, sensor["name"], index, description)
    #     for index in range(len(data.ecobee.thermostats))
    #     for sensor in data.ecobee.get_remote_sensors(index)
    #     for item in sensor["capability"]
    #     for description in SENSOR_TYPES
    #     if description.key == item["type"]
    # ]

    entities = [
        DaikinOneSensor(data, "test", SensorEntityDescription(
            key="temperature",
            name="Temperature",
            native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT
        ))
    ]

    async_add_entities(entities, True)


class DaikinOneSensor(SensorEntity):

    def __init__(
            self,
            data: DaikinOneData,
            sensor_name,
            description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self.data = data
        self.sensor_name = sensor_name
        self._state = None
        #self._attr_name = f"{sensor_name} {description.name}"

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return "test"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for this sensor."""

        (device_id, device) = next(iter(self.data.daikin.get_devices().items()))

        return DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=MANUFACTURER,
            model=device.model,
            name=self.sensor_name,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return random.randint(1, 100)

    async def async_update(self) -> None:
        """Get the latest state of the sensor."""
        await self.data.update()
        self._state = 50
