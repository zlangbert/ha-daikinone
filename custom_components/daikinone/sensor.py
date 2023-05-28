import logging
from typing import Callable, TypeVar

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.const import MANUFACTURER
from custom_components.daikinone.daikinone import DaikinThermostat, DaikinAirHandler, DaikinEquipment

log = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Daikin One sensors"""
    data: DaikinOneData = hass.data[DOMAIN]
    thermostats = data.daikin.get_thermostats().values()

    entities = [
        DaikinOneThermostatSensor(
            description=SensorEntityDescription(
                key="online",
                name="Online Status",
                has_entity_name=True,
                device_class=SensorDeviceClass.ENUM,
                entity_category=EntityCategory.DIAGNOSTIC
            ),
            data=data,
            device=thermostat,
            attribute=lambda d: "Online" if d.online else "Offline"
        )
        for thermostat in thermostats
    ]

    for thermostat in thermostats:
        for equipment in thermostat.equipment.values():
            match equipment:
                case DaikinAirHandler():
                    entities += [
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="airflow",
                                name="Airflow",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement="cfm",
                            ),
                            data=data,
                            thermostat=thermostat,
                            equipment=equipment,
                            attribute=lambda e: e.current_airflow
                        )
                    ]
                case _:
                    log.warning(f"unexpected equipment: {equipment}")

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
            name=f"{self.device.name} Thermostat",
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


E = TypeVar("E", bound=DaikinEquipment)


class DaikinOneEquipmentSensor(SensorEntity):

    def __init__(
            self,
            description: SensorEntityDescription,
            data: DaikinOneData,
            thermostat: DaikinThermostat,
            equipment: E,
            attribute: Callable[[E], StateType]
    ) -> None:
        """Initialize the sensor."""

        self.entity_description = description
        self._data = data
        self._thermostat = thermostat
        self._equipment: E = equipment
        self._attribute = attribute

        self._state: StateType = None

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return self._equipment.id

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for this sensor."""

        return DeviceInfo(
            identifiers={(DOMAIN, self._equipment.id)},
            name=f"{self._thermostat.name} {self._equipment.name}",
            manufacturer=MANUFACTURER,
            model=self._equipment.model,
            sw_version=self._equipment.control_software_version,
            via_device=(DOMAIN, self._thermostat.id)
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self) -> None:
        """Get the latest state of the sensor."""
        await self._data.update()
        self._thermostat = self._data.daikin.get_thermostat(self._thermostat.id)
        self._equipment = self._thermostat.equipment[self._equipment.id]
        self._state = self._attribute(self._equipment)
