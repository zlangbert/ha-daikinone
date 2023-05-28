import logging
from typing import Callable, TypeVar

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.const import MANUFACTURER
from custom_components.daikinone.daikinone import DaikinThermostat, DaikinAirHandler, DaikinEquipment, DaikinOutdoorUnit

log = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Daikin One sensors"""
    data: DaikinOneData = hass.data[DOMAIN]
    thermostats = data.daikin.get_thermostats().values()

    entities: list[SensorEntity] = []
    for thermostat in thermostats:
        # thermostat sensors

        entities += [
            DaikinOneThermostatSensor(
                description=SensorEntityDescription(
                    key="online",
                    name="Online Status",
                    has_entity_name=True,
                    device_class=SensorDeviceClass.ENUM,
                    entity_category=EntityCategory.DIAGNOSTIC
                ),
                data=data,
                thermostat=thermostat,
                attribute=lambda d: "Online" if d.online else "Offline"
            )
        ]

        # equipment sensors
        for equipment in thermostat.equipment.values():
            match equipment:

                # air handler sensors
                case DaikinAirHandler():
                    entities += [
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="airflow",
                                name="Airflow",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement="cfm",
                                icon="md:fan",
                            ),
                            data=data,
                            thermostat=thermostat,
                            equipment=equipment,
                            attribute=lambda e: e.current_airflow
                        ),
                    ]

                # outdoor unit sensors
                case DaikinOutdoorUnit():
                    entities += [
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="fan_speed",
                                name="Fan Speed",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement="rpm",
                                icon="md:fan",
                            ),
                            data=data,
                            thermostat=thermostat,
                            equipment=equipment,
                            attribute=lambda e: e.fan_rpm
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="heat_demand",
                                name="Heat Demand",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement=PERCENTAGE,
                            ),
                            data=data,
                            thermostat=thermostat,
                            equipment=equipment,
                            attribute=lambda e: e.heat_demand_percent
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="cool_demand",
                                name="Cool Demand",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement=PERCENTAGE,
                            ),
                            data=data,
                            thermostat=thermostat,
                            equipment=equipment,
                            attribute=lambda e: e.cool_demand_percent
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="fan_demand",
                                name="Fan Demand",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement=PERCENTAGE,
                            ),
                            data=data,
                            thermostat=thermostat,
                            equipment=equipment,
                            attribute=lambda e: e.fan_demand_percent
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="dehumidify_demand",
                                name="Dehumidify Demand",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement=PERCENTAGE,
                            ),
                            data=data,
                            thermostat=thermostat,
                            equipment=equipment,
                            attribute=lambda e: e.dehumidify_demand_percent
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="air_temperature",
                                name="Air Temperature",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                device_class=SensorDeviceClass.TEMPERATURE,
                                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                                icon="mdi:thermometer",
                            ),
                            data=data,
                            thermostat=thermostat,
                            equipment=equipment,
                            attribute=lambda e: e.air_temperature.celsius
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="coil_temperature",
                                name="Coil Temperature",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                device_class=SensorDeviceClass.TEMPERATURE,
                                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                                icon="mdi:thermometer",
                            ),
                            data=data,
                            thermostat=thermostat,
                            equipment=equipment,
                            attribute=lambda e: e.coil_temperature.celsius
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="discharge_temperature",
                                name="Discharge Temperature",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                device_class=SensorDeviceClass.TEMPERATURE,
                                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                                icon="mdi:thermometer",
                            ),
                            data=data,
                            thermostat=thermostat,
                            equipment=equipment,
                            attribute=lambda e: e.discharge_temperature.celsius
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="liquid_temperature",
                                name="Liquid Temperature",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                device_class=SensorDeviceClass.TEMPERATURE,
                                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                                icon="mdi:thermometer",
                            ),
                            data=data,
                            thermostat=thermostat,
                            equipment=equipment,
                            attribute=lambda e: e.liquid_temperature.celsius
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="defrost_sensor_temperature",
                                name="Defrost Sensor Temperature",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                device_class=SensorDeviceClass.TEMPERATURE,
                                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                                icon="mdi:thermometer",
                            ),
                            data=data,
                            thermostat=thermostat,
                            equipment=equipment,
                            attribute=lambda e: e.defrost_sensor_temperature.celsius
                        ),
                    ]

                case _:
                    log.warning(f"unexpected equipment: {equipment}")

    async_add_entities(entities, True)


class DaikinOneThermostatSensor(SensorEntity):

    def __init__(
            self,
            description: SensorEntityDescription,
            data: DaikinOneData,
            thermostat: DaikinThermostat,
            attribute: Callable[[DaikinThermostat], str]
    ) -> None:
        """Initialize the sensor."""

        self.entity_description = description
        self._data = data
        self._thermostat = thermostat
        self._attribute = attribute
        self._state = None

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return f"{self._thermostat.id}-{self.name}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for this sensor."""

        return DeviceInfo(
            identifiers={(DOMAIN, self._thermostat.id)},
            name=f"{self._thermostat.name} Thermostat",
            manufacturer=MANUFACTURER,
            model=self._thermostat.model,
            sw_version=self._thermostat.firmware,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self) -> None:
        """Get the latest state of the sensor."""
        await self._data.update()
        self._thermostat = self._data.daikin.get_thermostat(self._thermostat.id)
        self._state = self._attribute(self._thermostat)


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
        return f"{self._equipment.id}-{self.name}"

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
