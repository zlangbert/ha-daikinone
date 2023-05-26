import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN
from .daikinone import DaikinOne, DaikinUserCredentials

log = logging.getLogger(__name__)


class DaikinSkyportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Daikin One config flow."""

    VERSION = 1

    @property
    def schema(self):
        """Return current schema."""
        return vol.Schema({
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): str
        })

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            # check auth before finishing setup to ensure credentials work
            daikin = DaikinOne(self.hass, DaikinUserCredentials(email, password))
            ok = await daikin.login()

            if ok is False:
                errors["base"] = "auth_failed"
            else:
                return self.async_create_entry(
                    title="Daikin One",
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                    }
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.schema,
            errors=errors
        )

