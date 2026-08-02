import asyncio

import pytest
from aiohttp import ClientConnectionError
from aioresponses import CallbackResult, aioresponses

from custom_components.daikinone.client.models import DaikinUserCredentials
from custom_components.daikinone.client.transport import DaikinTransport
from custom_components.daikinone.client.wire import (
    DAIKIN_API_URL_DEVICE_DATA,
    DAIKIN_API_URL_LOGIN,
    DAIKIN_API_URL_REFRESH_TOKEN,
)
from custom_components.daikinone.exceptions import DaikinAuthException, DaikinServiceException


def _transport() -> DaikinTransport:
    return DaikinTransport(DaikinUserCredentials(email="test@example.com", password="password"))


def _authenticated_transport(access_token: str = "stale", refresh_token: str = "refresh-1") -> DaikinTransport:
    transport = _transport()
    transport._auth.authenticated = True
    transport._auth.access_token = access_token
    transport._auth.refresh_token = refresh_token
    return transport


@pytest.fixture
def mock_api():
    with aioresponses() as m:
        yield m


class TestLogin:
    async def test_login_success_stores_tokens(self, mock_api: aioresponses) -> None:
        mock_api.post(DAIKIN_API_URL_LOGIN, payload={"accessToken": "access-1", "refreshToken": "refresh-1"})

        transport = _transport()
        assert await transport.login() is True
        assert transport._auth.access_token == "access-1"
        assert transport._auth.refresh_token == "refresh-1"
        assert transport._auth.authenticated is True

    async def test_login_rejected_credentials_returns_false(self, mock_api: aioresponses) -> None:
        mock_api.post(DAIKIN_API_URL_LOGIN, status=401, body="bad credentials")

        transport = _authenticated_transport()
        assert await transport.login() is False
        assert transport._auth.authenticated is False
        assert transport._auth.access_token is None
        assert transport._auth.refresh_token is None

    async def test_login_missing_access_token_raises_service_exception(self, mock_api: aioresponses) -> None:
        """A malformed 200 response isn't evidence the credentials are wrong."""
        mock_api.post(DAIKIN_API_URL_LOGIN, payload={"refreshToken": "refresh-1"})

        transport = _transport()
        with pytest.raises(DaikinServiceException):
            await transport.login()
        assert transport._auth.authenticated is False

    async def test_login_network_error_raises_service_exception(self, mock_api: aioresponses) -> None:
        """A network error reaching the login endpoint isn't evidence the credentials are wrong."""
        mock_api.post(DAIKIN_API_URL_LOGIN, exception=ClientConnectionError())

        transport = _authenticated_transport()
        with pytest.raises(DaikinServiceException):
            await transport.login()
        assert transport._auth.authenticated is False
        assert transport._auth.access_token is None

    async def test_login_server_error_raises_service_exception_not_auth_exception(self, mock_api: aioresponses) -> None:
        """Regression test: a 5xx from the login endpoint must not be mistaken for bad credentials."""
        mock_api.post(DAIKIN_API_URL_LOGIN, status=503, body="service unavailable")

        transport = _transport()
        with pytest.raises(DaikinServiceException) as exc_info:
            await transport.login()

        assert not isinstance(exc_info.value, DaikinAuthException)
        assert exc_info.value.status == 503

    async def test_login_non_object_payload_raises_service_exception(self, mock_api: aioresponses) -> None:
        """Regression test: valid JSON that isn't an object (e.g. a proxy error page returning
        `[]`) must not escape as a raw AttributeError from payload.get(...)."""
        mock_api.post(DAIKIN_API_URL_LOGIN, payload=[])

        transport = _transport()
        with pytest.raises(DaikinServiceException) as exc_info:
            await transport.login()

        assert not isinstance(exc_info.value, DaikinAuthException)
        assert transport._auth.authenticated is False


class TestRequestAuthRecovery:
    async def test_logs_in_before_first_request(self, mock_api: aioresponses) -> None:
        mock_api.post(DAIKIN_API_URL_LOGIN, payload={"accessToken": "access-1", "refreshToken": "refresh-1"})
        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, payload=[{"foo": "bar"}])

        transport = _transport()
        result = await transport.request(DAIKIN_API_URL_DEVICE_DATA)

        assert result == [{"foo": "bar"}]

    async def test_malformed_success_response_raises_service_exception(self, mock_api: aioresponses) -> None:
        """Regression test: a 200 with an unparsable body must raise our own exception type,
        not a raw aiohttp/stdlib error, so callers (e.g. ConfigEntryNotReady classification
        during setup) can rely on request() only ever raising DaikinServiceException/
        DaikinAuthException."""
        transport = _authenticated_transport()

        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, status=200, body="not json", content_type="application/json")

        with pytest.raises(DaikinServiceException) as exc_info:
            await transport.request(DAIKIN_API_URL_DEVICE_DATA)

        assert not isinstance(exc_info.value, DaikinAuthException)

    async def test_failed_login_raises_auth_exception_without_issuing_request(self, mock_api: aioresponses) -> None:
        mock_api.post(DAIKIN_API_URL_LOGIN, status=401)
        # deliberately no mock registered for DAIKIN_API_URL_DEVICE_DATA: if the client fell
        # through and issued a request with a `Bearer None` header anyway, aioresponses would
        # raise a connection error here instead of the expected DaikinAuthException.

        transport = _transport()
        with pytest.raises(DaikinAuthException):
            await transport.request(DAIKIN_API_URL_DEVICE_DATA)

    async def test_login_outage_during_initial_auth_raises_service_exception_not_auth(
        self, mock_api: aioresponses
    ) -> None:
        """Regression test: a transient outage at startup must not be mistaken for bad credentials."""
        mock_api.post(DAIKIN_API_URL_LOGIN, status=503, body="service unavailable")

        transport = _transport()
        with pytest.raises(DaikinServiceException) as exc_info:
            await transport.request(DAIKIN_API_URL_DEVICE_DATA)

        assert not isinstance(exc_info.value, DaikinAuthException)

    @pytest.mark.parametrize("status", [401, 403])
    async def test_rejected_token_triggers_refresh_and_retry(self, mock_api: aioresponses, status: int) -> None:
        transport = _authenticated_transport()

        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, status=status)
        mock_api.post(DAIKIN_API_URL_REFRESH_TOKEN, payload={"accessToken": "fresh"})
        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, payload=[{"ok": True}])

        result = await transport.request(DAIKIN_API_URL_DEVICE_DATA)

        assert result == [{"ok": True}]
        assert transport._auth.access_token == "fresh"

    async def test_retry_still_rejected_after_successful_reauth_raises_auth_exception(
        self, mock_api: aioresponses
    ) -> None:
        """Regression test: if re-authentication succeeds but the endpoint still rejects the
        retried request (e.g. account access itself was revoked), that must surface as an auth
        failure, not a generic service error — the one-retry cap shouldn't hide the real cause."""
        transport = _authenticated_transport()

        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, status=401)
        mock_api.post(DAIKIN_API_URL_REFRESH_TOKEN, payload={"accessToken": "fresh"})
        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, status=403, body="account access revoked")

        with pytest.raises(DaikinAuthException) as exc_info:
            await transport.request(DAIKIN_API_URL_DEVICE_DATA)

        assert exc_info.value.status == 403

    async def test_refresh_rotates_refresh_token(self, mock_api: aioresponses) -> None:
        transport = _authenticated_transport(refresh_token="refresh-1")

        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, status=401)
        mock_api.post(DAIKIN_API_URL_REFRESH_TOKEN, payload={"accessToken": "fresh-1", "refreshToken": "refresh-2"})
        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, payload=[{"ok": True}])

        await transport.request(DAIKIN_API_URL_DEVICE_DATA)
        assert transport._auth.refresh_token == "refresh-2"

        # a subsequent refresh must use the rotated token, not the original one
        transport._auth.authenticated = True
        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, status=401)

        captured: dict[str, object] = {}

        def refresh_callback(url: object, **kwargs: object) -> CallbackResult:
            captured["body"] = kwargs.get("json")
            return CallbackResult(payload={"accessToken": "fresh-2"})

        mock_api.post(DAIKIN_API_URL_REFRESH_TOKEN, callback=refresh_callback)
        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, payload=[{"ok": True}])

        await transport.request(DAIKIN_API_URL_DEVICE_DATA)
        assert captured["body"]["refreshToken"] == "refresh-2"

    async def test_refresh_failure_falls_back_to_full_login(self, mock_api: aioresponses) -> None:
        transport = _authenticated_transport()

        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, status=401)
        mock_api.post(DAIKIN_API_URL_REFRESH_TOKEN, status=400)
        mock_api.post(DAIKIN_API_URL_LOGIN, payload={"accessToken": "fresh-login", "refreshToken": "refresh-2"})
        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, payload=[{"ok": True}])

        result = await transport.request(DAIKIN_API_URL_DEVICE_DATA)

        assert result == [{"ok": True}]
        assert transport._auth.access_token == "fresh-login"

    async def test_refresh_missing_access_token_key_falls_back_to_login(self, mock_api: aioresponses) -> None:
        transport = _authenticated_transport()

        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, status=401)
        mock_api.post(DAIKIN_API_URL_REFRESH_TOKEN, payload={"refreshToken": "refresh-2"})
        mock_api.post(DAIKIN_API_URL_LOGIN, payload={"accessToken": "fresh-login", "refreshToken": "refresh-3"})
        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, payload=[{"ok": True}])

        result = await transport.request(DAIKIN_API_URL_DEVICE_DATA)

        assert result == [{"ok": True}]

    async def test_refresh_non_object_payload_falls_back_to_login(self, mock_api: aioresponses) -> None:
        """Regression test: valid JSON that isn't an object during refresh must not escape as a
        raw AttributeError from payload.get(...); it should fall back to a full login instead."""
        transport = _authenticated_transport()

        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, status=401)
        mock_api.post(DAIKIN_API_URL_REFRESH_TOKEN, payload=[])
        mock_api.post(DAIKIN_API_URL_LOGIN, payload={"accessToken": "fresh-login", "refreshToken": "refresh-2"})
        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, payload=[{"ok": True}])

        result = await transport.request(DAIKIN_API_URL_DEVICE_DATA)

        assert result == [{"ok": True}]

    async def test_refresh_network_error_falls_back_to_login(self, mock_api: aioresponses) -> None:
        transport = _authenticated_transport()

        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, status=401)
        mock_api.post(DAIKIN_API_URL_REFRESH_TOKEN, exception=ClientConnectionError())
        mock_api.post(DAIKIN_API_URL_LOGIN, payload={"accessToken": "fresh-login", "refreshToken": "refresh-2"})
        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, payload=[{"ok": True}])

        result = await transport.request(DAIKIN_API_URL_DEVICE_DATA)

        assert result == [{"ok": True}]

    async def test_refresh_and_login_both_fail_raises_auth_exception(self, mock_api: aioresponses) -> None:
        transport = _authenticated_transport()

        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, status=403)
        mock_api.post(DAIKIN_API_URL_REFRESH_TOKEN, status=400)
        mock_api.post(DAIKIN_API_URL_LOGIN, status=401)

        with pytest.raises(DaikinAuthException):
            await transport.request(DAIKIN_API_URL_DEVICE_DATA)

    async def test_refresh_and_login_outage_raises_service_exception_not_auth(self, mock_api: aioresponses) -> None:
        """Regression test: a full Daikin cloud outage must not be mistaken for bad credentials."""
        transport = _authenticated_transport()

        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, status=401)
        mock_api.post(DAIKIN_API_URL_REFRESH_TOKEN, status=503)
        mock_api.post(DAIKIN_API_URL_LOGIN, status=503, body="service unavailable")

        with pytest.raises(DaikinServiceException) as exc_info:
            await transport.request(DAIKIN_API_URL_DEVICE_DATA)

        assert not isinstance(exc_info.value, DaikinAuthException)

    async def test_recovers_on_next_call_after_full_auth_failure(self, mock_api: aioresponses) -> None:
        """Regression test: a 403 must not permanently wedge the client until a reload."""
        transport = _authenticated_transport()

        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, status=403)
        mock_api.post(DAIKIN_API_URL_REFRESH_TOKEN, status=400)
        mock_api.post(DAIKIN_API_URL_LOGIN, status=401)

        with pytest.raises(DaikinAuthException):
            await transport.request(DAIKIN_API_URL_DEVICE_DATA)

        assert transport._auth.authenticated is False

        # a later call must attempt to log in again rather than staying permanently wedged
        mock_api.post(DAIKIN_API_URL_LOGIN, payload={"accessToken": "recovered", "refreshToken": "refresh-2"})
        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, payload=[{"ok": True}])

        result = await transport.request(DAIKIN_API_URL_DEVICE_DATA)
        assert result == [{"ok": True}]

    async def test_ordinary_400_is_not_treated_as_auth_failure(self, mock_api: aioresponses) -> None:
        """A malformed request body should surface as a service error, not trigger re-auth."""
        transport = _authenticated_transport()

        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, status=400, body="bad request")

        with pytest.raises(DaikinServiceException) as exc_info:
            await transport.request(DAIKIN_API_URL_DEVICE_DATA)

        assert exc_info.value.status == 400

    async def test_concurrent_requests_only_login_once(self, mock_api: aioresponses) -> None:
        login_calls = 0

        def login_callback(url: object, **kwargs: object) -> CallbackResult:
            nonlocal login_calls
            login_calls += 1
            return CallbackResult(payload={"accessToken": "access-1", "refreshToken": "refresh-1"})

        mock_api.post(DAIKIN_API_URL_LOGIN, callback=login_callback, repeat=True)
        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, payload=[{"a": 1}], repeat=True)

        transport = _transport()
        results = await asyncio.gather(
            transport.request(DAIKIN_API_URL_DEVICE_DATA),
            transport.request(DAIKIN_API_URL_DEVICE_DATA),
        )

        assert login_calls == 1
        assert all(r == [{"a": 1}] for r in results)

    async def test_concurrent_rejections_only_reauthenticate_once(self, mock_api: aioresponses) -> None:
        """Two requests racing on the same stale token must trigger exactly one refresh."""
        refresh_calls = 0
        stale_call_count = 0
        both_rejected = asyncio.Event()

        async def device_data_callback(url: object, **kwargs: object) -> CallbackResult:
            nonlocal stale_call_count
            headers = kwargs.get("headers") or {}
            if headers.get("Authorization") == "Bearer stale":
                # force both concurrent requests to actually be in flight, holding their 401
                # response, before either proceeds to call _reauthenticate — otherwise asyncio
                # may run one request to full completion before the other even starts, and the
                # race this test targets never happens
                stale_call_count += 1
                if stale_call_count >= 2:
                    both_rejected.set()
                else:
                    await both_rejected.wait()
                return CallbackResult(status=401)
            return CallbackResult(payload=[{"a": 1}])

        def refresh_callback(url: object, **kwargs: object) -> CallbackResult:
            nonlocal refresh_calls
            refresh_calls += 1
            return CallbackResult(payload={"accessToken": "fresh"})

        transport = _authenticated_transport()

        mock_api.get(DAIKIN_API_URL_DEVICE_DATA, callback=device_data_callback, repeat=True)
        mock_api.post(DAIKIN_API_URL_REFRESH_TOKEN, callback=refresh_callback, repeat=True)

        results = await asyncio.gather(
            transport.request(DAIKIN_API_URL_DEVICE_DATA),
            transport.request(DAIKIN_API_URL_DEVICE_DATA),
        )

        assert refresh_calls == 1
        assert all(r == [{"a": 1}] for r in results)
