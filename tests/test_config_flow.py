from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.data_entry_flow import FlowResultType

from custom_components.daikinone.config_flow import DaikinOneConfigFlow
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY
from custom_components.daikinone.exceptions import DaikinServiceException


def _user_input() -> dict[str, str]:
    return {"email": "test@example.com", "password": "password"}


def _flow_with_reauth_entry(existing_email: str = "old@example.com") -> tuple[DaikinOneConfigFlow, MagicMock]:
    flow = DaikinOneConfigFlow()
    entry = MagicMock()
    entry.data = {
        "email": existing_email,
        "password": "old-password",
        CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 1,
    }
    flow._get_reauth_entry = MagicMock(return_value=entry)  # type: ignore[method-assign]
    return flow, entry


class TestAsyncStepUser:
    async def test_rejected_credentials_shows_auth_failed(self) -> None:
        flow = DaikinOneConfigFlow()

        with patch("custom_components.daikinone.config_flow.DaikinOne") as mock_daikin_cls:
            mock_daikin_cls.return_value.login = AsyncMock(return_value=False)
            result = await flow.async_step_user(_user_input())

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "auth_failed"}

    async def test_transient_failure_shows_cannot_connect_not_auth_failed(self) -> None:
        """Regression test: a Daikin cloud outage during setup must not be reported as bad credentials."""
        flow = DaikinOneConfigFlow()

        with patch("custom_components.daikinone.config_flow.DaikinOne") as mock_daikin_cls:
            mock_daikin_cls.return_value.login = AsyncMock(
                side_effect=DaikinServiceException("service unavailable", status=503)
            )
            result = await flow.async_step_user(_user_input())

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_successful_login_creates_entry(self) -> None:
        flow = DaikinOneConfigFlow()

        with patch("custom_components.daikinone.config_flow.DaikinOne") as mock_daikin_cls:
            mock_daikin_cls.return_value.login = AsyncMock(return_value=True)
            result = await flow.async_step_user(_user_input())

        assert result["type"] == FlowResultType.CREATE_ENTRY


class TestAsyncStepReauth:
    """Regression tests: rejected stored credentials must be fixable through the UI, not just
    reported, since ConfigEntryAuthFailed starts this flow with no other way to recover."""

    async def test_reauth_shows_confirm_form_prefilled_with_existing_email(self) -> None:
        flow, entry = _flow_with_reauth_entry(existing_email="existing@example.com")

        result = await flow.async_step_reauth(dict(entry.data))

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

    async def test_reauth_confirm_updates_entry_and_reloads_on_success(self) -> None:
        flow, entry = _flow_with_reauth_entry()
        flow.async_update_reload_and_abort = MagicMock(  # type: ignore[method-assign]
            return_value={"type": FlowResultType.ABORT, "reason": "reauth_successful"}
        )

        with patch("custom_components.daikinone.config_flow.DaikinOne") as mock_daikin_cls:
            mock_daikin_cls.return_value.login = AsyncMock(return_value=True)
            result = await flow.async_step_reauth_confirm({"email": "new@example.com", "password": "new-password"})

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"

        flow.async_update_reload_and_abort.assert_called_once()
        _, kwargs = flow.async_update_reload_and_abort.call_args
        assert kwargs["data"]["email"] == "new@example.com"
        assert kwargs["data"]["password"] == "new-password"
        # existing internal options must survive the update
        assert kwargs["data"][CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY] == 1

    async def test_reauth_confirm_rejected_credentials_shows_auth_failed(self) -> None:
        flow, _ = _flow_with_reauth_entry()

        with patch("custom_components.daikinone.config_flow.DaikinOne") as mock_daikin_cls:
            mock_daikin_cls.return_value.login = AsyncMock(return_value=False)
            result = await flow.async_step_reauth_confirm({"email": "new@example.com", "password": "wrong"})

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "auth_failed"}

    async def test_reauth_confirm_transient_failure_shows_cannot_connect(self) -> None:
        flow, _ = _flow_with_reauth_entry()

        with patch("custom_components.daikinone.config_flow.DaikinOne") as mock_daikin_cls:
            mock_daikin_cls.return_value.login = AsyncMock(
                side_effect=DaikinServiceException("service unavailable", status=503)
            )
            result = await flow.async_step_reauth_confirm({"email": "new@example.com", "password": "new-password"})

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
