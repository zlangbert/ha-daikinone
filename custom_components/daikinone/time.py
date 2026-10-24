"""Time platform for Daikin One configuration schedules."""

import datetime

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.daikinone import DOMAIN, DaikinOneData
from custom_components.daikinone.client.models import DaikinThermostat
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.entity import DaikinOneEntity


def _slot_to_time(value: int | None) -> datetime.time | None:
    """Convert a valid 15-minute slot index (0-95) to local time."""
    if value is None or not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 95:
        return None
    return datetime.time(hour=value * 15 // 60, minute=(value * 15) % 60)


def _time_to_slot(value: datetime.time) -> int:
    """Convert local time to the nearest 15-minute slot index."""
    return (value.hour * 60 + value.minute + 7) // 15 % 96


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Daikin One schedule time entities."""
    data: DaikinOneData = hass.data[DOMAIN]
    entities: list[TimeEntity] = []

    for thermostat in data.daikin.get_thermostats().values():
        if (
            _slot_to_time(thermostat.fan_circulate_start) is not None
            and _slot_to_time(thermostat.fan_circulate_stop) is not None
        ):
            entities.extend(
                [
                    DaikinOneFanCirculationStartTime(
                        _description(
                            "fan_circulation_start",
                            "Fan circulation start time",
                            "mdi:clock-start",
                        ),
                        data,
                        thermostat,
                    ),
                    DaikinOneFanCirculationStopTime(
                        _description(
                            "fan_circulation_stop",
                            "Fan circulation stop time",
                            "mdi:clock-end",
                        ),
                        data,
                        thermostat,
                    ),
                ]
            )

        if (
            _slot_to_time(thermostat.night_mode_start) is not None
            and _slot_to_time(thermostat.night_mode_stop) is not None
        ):
            entities.extend(
                [
                    DaikinOneNightModeStartTime(
                        _description("night_mode_start", "Night mode start time", "mdi:clock-start"),
                        data,
                        thermostat,
                    ),
                    DaikinOneNightModeStopTime(
                        _description("night_mode_stop", "Night mode stop time", "mdi:clock-end"),
                        data,
                        thermostat,
                    ),
                ]
            )

        if (
            thermostat.quiet_mode_ho_display_enable is True
            and thermostat.quiet_mode_start_time is not None
            and thermostat.quiet_mode_stop_time is not None
        ):
            entities.extend(
                [
                    DaikinOneQuietModeStartTime(
                        _description(
                            "quiet_mode_start_time",
                            "Quiet mode start time",
                            "mdi:clock-start",
                        ),
                        data,
                        thermostat,
                    ),
                    DaikinOneQuietModeStopTime(
                        _description(
                            "quiet_mode_stop_time",
                            "Quiet mode stop time",
                            "mdi:clock-end",
                        ),
                        data,
                        thermostat,
                    ),
                ]
            )

    async_add_entities(entities, True)


def _description(key: str, name: str, icon: str) -> TimeEntityDescription:
    return TimeEntityDescription(
        key=key,
        name=name,
        icon=icon,
        has_entity_name=True,
        entity_category=EntityCategory.CONFIG,
        translation_key=key,
    )


class _DaikinOneScheduleTime(DaikinOneEntity[DaikinThermostat], TimeEntity):
    """Shared unique ID and device behavior for schedule time entities."""

    def __init__(
        self,
        description: TimeEntityDescription,
        data: DaikinOneData,
        thermostat: DaikinThermostat,
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

    async def async_get_device(self) -> DaikinThermostat:
        return self._data.daikin.get_thermostat(self._device.id)


class DaikinOneFanCirculationStartTime(_DaikinOneScheduleTime):
    """Configure the fan circulation start time."""

    def update_entity_attributes(self) -> None:
        self._attr_native_value = _slot_to_time(self._device.fan_circulate_start)

    async def async_set_value(self, value: datetime.time) -> None:
        slot = _time_to_slot(value)

        def update(thermostat: DaikinThermostat) -> None:
            thermostat.fan_circulate_start = slot

        await self.update_state_optimistically(
            operation=lambda: self._data.daikin.set_thermostat_fan_circulate_start(self._device.id, slot),
            optimistic_update=update,
            check=lambda thermostat: thermostat.fan_circulate_start == slot,
        )


class DaikinOneFanCirculationStopTime(_DaikinOneScheduleTime):
    """Configure the fan circulation stop time."""

    def update_entity_attributes(self) -> None:
        self._attr_native_value = _slot_to_time(self._device.fan_circulate_stop)

    async def async_set_value(self, value: datetime.time) -> None:
        slot = _time_to_slot(value)

        def update(thermostat: DaikinThermostat) -> None:
            thermostat.fan_circulate_stop = slot

        await self.update_state_optimistically(
            operation=lambda: self._data.daikin.set_thermostat_fan_circulate_stop(self._device.id, slot),
            optimistic_update=update,
            check=lambda thermostat: thermostat.fan_circulate_stop == slot,
        )


class DaikinOneNightModeStartTime(_DaikinOneScheduleTime):
    """Configure the thermostat night mode start time."""

    def update_entity_attributes(self) -> None:
        self._attr_native_value = _slot_to_time(self._device.night_mode_start)

    async def async_set_value(self, value: datetime.time) -> None:
        slot = _time_to_slot(value)

        def update(thermostat: DaikinThermostat) -> None:
            thermostat.night_mode_start = slot

        await self.update_state_optimistically(
            operation=lambda: self._data.daikin.set_thermostat_night_mode_start(self._device.id, slot),
            optimistic_update=update,
            check=lambda thermostat: thermostat.night_mode_start == slot,
        )


class DaikinOneNightModeStopTime(_DaikinOneScheduleTime):
    """Configure the thermostat night mode stop time."""

    def update_entity_attributes(self) -> None:
        self._attr_native_value = _slot_to_time(self._device.night_mode_stop)

    async def async_set_value(self, value: datetime.time) -> None:
        slot = _time_to_slot(value)

        def update(thermostat: DaikinThermostat) -> None:
            thermostat.night_mode_stop = slot

        await self.update_state_optimistically(
            operation=lambda: self._data.daikin.set_thermostat_night_mode_stop(self._device.id, slot),
            optimistic_update=update,
            check=lambda thermostat: thermostat.night_mode_stop == slot,
        )


class DaikinOneQuietModeStartTime(_DaikinOneScheduleTime):
    """Configure outdoor unit inverter quiet mode start time."""

    def update_entity_attributes(self) -> None:
        self._attr_native_value = _slot_to_time(self._device.quiet_mode_start_time)

    async def async_set_value(self, value: datetime.time) -> None:
        slot = _time_to_slot(value)

        def update(thermostat: DaikinThermostat) -> None:
            thermostat.quiet_mode_start_time = slot

        await self.update_state_optimistically(
            operation=lambda: self._data.daikin.set_thermostat_quiet_mode_start_time(self._device.id, slot),
            optimistic_update=update,
            check=lambda thermostat: thermostat.quiet_mode_start_time == slot,
        )


class DaikinOneQuietModeStopTime(_DaikinOneScheduleTime):
    """Configure outdoor unit inverter quiet mode stop time."""

    def update_entity_attributes(self) -> None:
        self._attr_native_value = _slot_to_time(self._device.quiet_mode_stop_time)

    async def async_set_value(self, value: datetime.time) -> None:
        slot = _time_to_slot(value)

        def update(thermostat: DaikinThermostat) -> None:
            thermostat.quiet_mode_stop_time = slot

        await self.update_state_optimistically(
            operation=lambda: self._data.daikin.set_thermostat_quiet_mode_stop_time(self._device.id, slot),
            optimistic_update=update,
            check=lambda thermostat: thermostat.quiet_mode_stop_time == slot,
        )
