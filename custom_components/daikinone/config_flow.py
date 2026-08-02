import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN, CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from .client.client import DaikinOne
from .client.models import DaikinUserCredentials
from .exceptions import DaikinServiceException

log = logging.getLogger(__name__)


class DaikinOneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Daikin One config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    @property
    def schema(self):
        """Return current schema."""
        return vol.Schema({vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str})

    async def _async_validate_credentials(self, email: str, password: str) -> str | None:
        """Check the given credentials against the Daikin API.

        Returns None if they're valid, or an error key to show on the form otherwise.
        """
        daikin = DaikinOne(DaikinUserCredentials(email, password))
        try:
            ok = await daikin.login()
        except DaikinServiceException:
            # login() raises for anything other than rejected credentials (network error,
            # unexpected status, malformed response), so this isn't a credentials problem
            return "cannot_connect"
        return None if ok else "auth_failed"

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            error = await self._async_validate_credentials(email, password)
            if error is not None:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="Daikin One",
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        # internal options
                        CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 1,
                    },
                )

        return self.async_show_form(step_id="user", data_schema=self.schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        """Handle re-authentication after the stored credentials are rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            error = await self._async_validate_credentials(email, password)
            if error is not None:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_EMAIL: email, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL, default=entry.data.get(CONF_EMAIL)): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
