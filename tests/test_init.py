from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.daikinone import DaikinOneData, async_setup_entry
from custom_components.daikinone.const import DOMAIN
from custom_components.daikinone.exceptions import DaikinAuthException, DaikinServiceException


def _entry_with_data(**data: str) -> SimpleNamespace:
    return SimpleNamespace(data=data, async_start_reauth=MagicMock())


class TestAsyncSetupEntry:
    async def test_raises_config_entry_not_ready_on_initial_update_failure(self) -> None:
        """Regression test: a transient setup failure must be retryable, not permanently failed."""
        hass = SimpleNamespace(data={})
        entry = _entry_with_data(**{CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"})

        with patch("custom_components.daikinone.DaikinOne") as mock_daikin_cls:
            mock_daikin_cls.return_value.update = AsyncMock(side_effect=DaikinServiceException("boom", status=503))

            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(hass, entry)  # type: ignore[arg-type]

        assert DOMAIN not in hass.data

    async def test_raises_config_entry_auth_failed_on_rejected_credentials(self) -> None:
        """Rejected credentials must surface distinctly from a transient outage, so HA marks the
        entry as needing re-authentication instead of retrying forever with dead credentials."""
        hass = SimpleNamespace(data={})
        entry = _entry_with_data(**{CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"})

        with patch("custom_components.daikinone.DaikinOne") as mock_daikin_cls:
            mock_daikin_cls.return_value.update = AsyncMock(side_effect=DaikinAuthException("boom"))

            with pytest.raises(ConfigEntryAuthFailed):
                await async_setup_entry(hass, entry)  # type: ignore[arg-type]

        assert DOMAIN not in hass.data


class TestDaikinOneDataUpdate:
    async def test_auth_failure_during_runtime_poll_starts_reauth_and_reraises(self) -> None:
        """Regression test: credentials revoked after setup (e.g. a changed password) must
        prompt the user to re-authenticate, not just fail every poll silently forever until
        someone notices and manually reloads the integration."""
        entry = SimpleNamespace(async_start_reauth=MagicMock())
        daikin = MagicMock()
        daikin.update = AsyncMock(side_effect=DaikinAuthException("boom"))

        data = DaikinOneData(None, entry, daikin)  # type: ignore[arg-type]

        with pytest.raises(DaikinAuthException):
            await data.update()

        entry.async_start_reauth.assert_called_once_with(None)
