import logging
from typing import Callable, TypeVar, Generic

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.const import MANUFACTURER
from custom_components.daikinone.daikinone import (
    DaikinDevice,
    DaikinThermostat,
    DaikinAirHandler,
    DaikinEquipment,
    DaikinOutdoorUnit,
)

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
                    entity_category=EntityCategory.DIAGNOSTIC,
                    icon="mdi:connection",
                ),
                data=data,
                device=thermostat,
                attribute=lambda d: "Online" if d.online else "Offline",
            ),
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
                                icon="mdi:fan",
                            ),
                            data=data,
                            device=equipment,
                            attribute=lambda e: e.current_airflow,
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="fan_demand_requested",
                                name="Fan Demand Requested",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement=PERCENTAGE,
                                icon="mdi:fan",
                            ),
                            data=data,
                            device=equipment,
                            attribute=lambda e: e.fan_demand_requested_percent,
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="fan_demand_current",
                                name="Fan Demand Current",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement=PERCENTAGE,
                                icon="mdi:fan",
                            ),
                            data=data,
                            device=equipment,
                            attribute=lambda e: e.fan_demand_current_percent,
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="heat_demand_requested",
                                name="Heat Demand Requested",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement=PERCENTAGE,
                                icon="mdi:heat-wave",
                            ),
                            data=data,
                            device=equipment,
                            attribute=lambda e: e.heat_demand_requested_percent,
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="heat_demand_current",
                                name="Heat Demand Current",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement=PERCENTAGE,
                                icon="mdi:heat-wave",
                            ),
                            data=data,
                            device=equipment,
                            attribute=lambda e: e.heat_demand_current_percent,
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="humidification_demand_requested",
                                name="Humidification Demand Requested",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement=PERCENTAGE,
                                icon="mdi:water-percent",
                            ),
                            data=data,
                            device=equipment,
                            attribute=lambda e: e.humidification_demand_requested_percent,
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
                                icon="mdi:fan",
                            ),
                            data=data,
                            device=equipment,
                            attribute=lambda e: e.fan_rpm,
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="heat_demand",
                                name="Heat Demand",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement=PERCENTAGE,
                                icon="mdi:sun-thermometer",
                            ),
                            data=data,
                            device=equipment,
                            attribute=lambda e: e.heat_demand_percent,
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="cool_demand",
                                name="Cool Demand",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement=PERCENTAGE,
                                icon="mdi:snowflake-thermometer",
                            ),
                            data=data,
                            device=equipment,
                            attribute=lambda e: e.cool_demand_percent,
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="fan_demand",
                                name="Fan Demand",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement=PERCENTAGE,
                                icon="mdi:air-filter",
                            ),
                            data=data,
                            device=equipment,
                            attribute=lambda e: e.fan_demand_percent,
                        ),
                        DaikinOneEquipmentSensor(
                            description=SensorEntityDescription(
                                key="dehumidify_demand",
                                name="Dehumidify Demand",
                                has_entity_name=True,
                                state_class=SensorStateClass.MEASUREMENT,
                                native_unit_of_measurement=PERCENTAGE,
                                icon="mdi:air-humidifier",
                            ),
                            data=data,
                            device=equipment,
                            attribute=lambda e: e.dehumidify_demand_percent,
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
                            device=equipment,
                            attribute=lambda e: e.air_temperature.celsius,
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
                            device=equipment,
                            attribute=lambda e: e.coil_temperature.celsius,
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
                            device=equipment,
                            attribute=lambda e: e.discharge_temperature.celsius,
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
                            device=equipment,
                            attribute=lambda e: e.liquid_temperature.celsius,
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
                            device=equipment,
                            attribute=lambda e: e.defrost_sensor_temperature.celsius,
                        ),
                    ]

                case _:
                    log.warning(f"unexpected equipment: {equipment}")

    async_add_entities(entities, True)


D = TypeVar("D", covariant=True, bound=DaikinDevice)


class DaikinOneSensor(SensorEntity, Generic[D]):
    _state: StateType = None

    def __init__(
        self, description: SensorEntityDescription, data: DaikinOneData, device: D, attribute: Callable[[D], StateType]
    ) -> None:
        """Initialize the sensor."""

        self.entity_description = description
        self._data = data
        self._device: D = device
        self._attribute = attribute

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return f"{self._device.id}-{self.name}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for this sensor."""

        info = DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            name=self.device_name,
            manufacturer=MANUFACTURER,
            model=self._device.model,
            sw_version=self._device.firmware_version,
        )

        if self.device_parent is not None:
            info["via_device"] = (DOMAIN, self.device_parent)

        return info

    @property
    def device_name(self) -> str:
        """Return the name of the device."""
        raise NotImplementedError("Sensor subclass did not implement device_name")

    @property
    def device_parent(self) -> str | None:
        """Return the name of the device."""
        return None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state


class DaikinOneThermostatSensor(DaikinOneSensor[DaikinThermostat]):
    def __init__(
        self,
        description: SensorEntityDescription,
        data: DaikinOneData,
        device: DaikinThermostat,
        attribute: Callable[[DaikinThermostat], StateType],
    ) -> None:
        super().__init__(description, data, device, attribute)

    @property
    def device_name(self) -> str:
        return f"{self._device.name} Thermostat"

    async def async_update(self) -> None:
        """Get the latest state of the sensor."""
        await self._data.update()
        self._device = self._data.daikin.get_thermostat(self._device.id)
        self._state = self._attribute(self._device)


E = TypeVar("E", bound=DaikinEquipment)


class DaikinOneEquipmentSensor(DaikinOneSensor[E]):
    def __init__(
        self, description: SensorEntityDescription, data: DaikinOneData, device: E, attribute: Callable[[E], StateType]
    ) -> None:
        super().__init__(description, data, device, attribute)

    @property
    def device_name(self) -> str:
        thermostat = self._data.daikin.get_thermostat(self._device.thermostat_id)
        return f"{thermostat.name} {self._device.name}"

    async def async_update(self) -> None:
        """Get the latest state of the sensor."""
        await self._data.update()
        thermostat = self._data.daikin.get_thermostat(self._device.thermostat_id)
        self._device = thermostat.equipment[self._device.id]
        self._state = self._attribute(self._device)
