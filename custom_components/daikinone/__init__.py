import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import Throttle

from custom_components.daikinone.const import (
    CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY,
    PLATFORMS,
    DOMAIN,
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
            # retain legacy id schema if this is an upgrade of an existing entry
            new[CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY] = 0

        # The original P1/P2 sensors used percentage units for two fields that
        # are not percentages.  Keep their entity IDs while moving their
        # unique IDs to the corrected RPM/louvre entities.
        if entry.minor_version < 3:
            registry = er.async_get(hass)
            for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
                replacements = {
                    "-Fan Speed Percentage": "-Fan Speed",
                    "-Flap Swing": "-Louvre Setting",
                }
                for old_suffix, new_suffix in replacements.items():
                    if entity.unique_id.endswith(old_suffix):
                        registry.async_update_entity(
                            entity.entity_id,
                            new_unique_id=entity.unique_id.removesuffix(old_suffix) + new_suffix,
                        )
                        break

        hass.config_entries.async_update_entry(entry, data=new, minor_version=3)

    log.info("Migration to version %s.%s successful", entry.version, entry.minor_version)

    return True
