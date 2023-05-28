import logging
from dataclasses import dataclass

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import Throttle

from custom_components.daikinone.const import PLATFORMS, DOMAIN, MIN_TIME_BETWEEN_UPDATES
from custom_components.daikinone.daikinone import DaikinOne, DaikinUserCredentials

log = logging.getLogger(__name__)


@dataclass
class DaikinOneData:
    _hass: HomeAssistant
    entry: ConfigEntry
    daikin: DaikinOne

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self):
        """Get the latest data from Daikin cloud"""
        log.debug("Updating Daikin One data from cloud")
        await self.entry.async_create_task(self._hass, self.daikin.update())


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the given config entry"""

    log.info(f"Setting up Daikin One integration for {entry.data[CONF_EMAIL]}")

    # create daikin one connector
    data = DaikinOneData(
        hass,
        entry,
        DaikinOne(DaikinUserCredentials(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]))
    )
    await data.update()
    hass.data[DOMAIN] = data

    # load platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry and platforms"""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data.pop(DOMAIN)
    return ok
