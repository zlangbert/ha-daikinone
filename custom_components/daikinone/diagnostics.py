import logging
from typing import Any, Mapping

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntry

from custom_components.daikinone import DOMAIN, DaikinOneData

log = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    data: DaikinOneData = hass.data[DOMAIN]
    raw = await data.daikin.get_all_raw_device_data()

    return {"raw": raw}


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> Mapping[str, Any]:
    data: DaikinOneData = hass.data[DOMAIN]
    device_id = next(i for i in device.identifiers if i[0] == DOMAIN)[1]
    raw = await data.daikin.get_raw_device_data(device_id)

    return {"raw": raw}
