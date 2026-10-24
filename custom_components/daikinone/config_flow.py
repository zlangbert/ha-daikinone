import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN, CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from .client.client import DaikinOne
from .client.models import DaikinUserCredentials

log = logging.getLogger(__name__)


class DaikinOneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Daikin One config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    @property
    def schema(self):
        """Return current schema."""
        return vol.Schema({vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str})

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            # check auth before finishing setup to ensure credentials work
            daikin = DaikinOne(DaikinUserCredentials(email, password))
            ok = await daikin.login()

            if ok is False:
                errors["base"] = "auth_failed"
            else:
                title = "Daikin One"
                try:
                    locations = await daikin.get_locations()
                    if locations:
                        primary_location = next(iter(locations.values()))
                        if getattr(primary_location, "name", None):
                            title = primary_location.name
                except Exception:
                    log.warning("Failed to fetch location name for config entry title", exc_info=True)

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        # internal options
                        CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 1,
                    },
                )

        return self.async_show_form(step_id="user", data_schema=self.schema, errors=errors)
