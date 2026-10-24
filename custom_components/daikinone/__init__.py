import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import Throttle

from custom_components.daikinone.const import (
    CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY,
    PLATFORMS,
    DOMAIN,
    MANUFACTURER,
    MIN_TIME_BETWEEN_UPDATES,
)
from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.models import DaikinUserCredentials

log = logging.getLogger(__name__)


@dataclass
class DaikinOneData:
    _hass: HomeAssistant
    entry: ConfigEntry
    daikin: DaikinOne

    async def update(self, no_throttle: bool = False) -> None:
        """Get the latest data from Daikin cloud"""
        await self._update(no_throttle=no_throttle)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def _update(self) -> None:
        """
        @Throttle throws off the type checker so use internal implementation that can be type ignored in one place
        instead of everywhere that calls update
        """
        log.debug("Updating Daikin One data from cloud")
        await self.daikin.update()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the given config entry"""

    log.info(f"Setting up Daikin One integration for {entry.data[CONF_EMAIL]}")

    # create daikin one connector
    data = DaikinOneData(
        hass, entry, DaikinOne(DaikinUserCredentials(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]))
    )
    await data.update()
    locations = await data.daikin.get_locations()

    # Dynamic Entry Title Migration
    if getattr(entry, "title", None) == "Daikin One" and locations:
        target_location = None
        for loc in locations.values():
            if any(t.location_id == loc.id for t in data.daikin.thermostats.values()):
                target_location = loc
                break
        if target_location is None and locations:
            target_location = next(iter(locations.values()))

        if target_location and target_location.name and hasattr(hass, "config_entries"):
            hass.config_entries.async_update_entry(entry, title=target_location.name)

    # Register Location Hub Device(s) in Device Registry
    device_registry = dr.async_get(hass)
    for location_id, location in locations.items():
        if any(t.location_id == location_id for t in data.daikin.thermostats.values()):
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, location.id)},
                name=location.name,
                manufacturer=MANUFACTURER,
                model="Skyport Location",
                entry_type=dr.DeviceEntryType.SERVICE,
                configuration_url=f"https://api.daikinskyport.com/locations/{location.id}",
            )

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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    log.debug("Migrating from version %s.%s", entry.version, entry.minor_version)

    if entry.version > 1:
        log.error(
            "Incompatible downgrade detected, please restore from a earlier backup or remove and re-add the integration",
            entry.version,
            entry.minor_version,
        )
        return False

    if entry.version == 1:
        new = {**entry.data}

        # migrate to 1.2
        if entry.minor_version < 2:
            entry.minor_version = 2

            # retain legacy id schema if this is an upgrade of an existing entry
            new[CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY] = 0

        hass.config_entries.async_update_entry(entry, data=new)

    log.info("Migration to version %s.%s successful", entry.version, entry.minor_version)

    return True
