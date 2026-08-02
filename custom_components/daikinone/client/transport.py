"""Auth state + HTTP transport for the Daikin API."""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp
from aiohttp import ClientError

from custom_components.daikinone.client.models import DaikinUserCredentials
from custom_components.daikinone.client.wire import (
    DAIKIN_API_URL_LOGIN,
    DAIKIN_API_URL_REFRESH_TOKEN,
)
from custom_components.daikinone.exceptions import DaikinAuthException, DaikinServiceException

log = logging.getLogger(__name__)

# Statuses that indicate credentials/tokens were rejected outright, on both the login endpoint
# (bad email/password) and any other request (bad/expired access token). 400 is deliberately
# excluded: the Daikin API also returns it for malformed PUT bodies, so treating it as an auth
# failure would mask real request errors instead of surfacing them.
_AUTH_FAILURE_STATUSES = frozenset({401, 403})

# Errors that indicate a transient problem talking to the auth endpoints (network issues,
# timeouts, or a response body that claims to be JSON but isn't) as opposed to a well-formed
# response that's simply missing a field, which is handled separately via dict.get().
_AUTH_TRANSPORT_ERRORS = (ClientError, TimeoutError, ValueError)


@dataclass
class _AuthState:
    authenticated: bool = False
    refresh_token: str | None = None
    access_token: str | None = None


class DaikinTransport:
    """Handles auth and HTTP requests against the Daikin API."""

    def __init__(self, creds: DaikinUserCredentials) -> None:
        self._creds = creds
        self._auth = _AuthState()
        # Serializes login/refresh so concurrent requests hitting an expired token don't each
        # independently kick off their own re-authentication.
        self._auth_lock = asyncio.Lock()

    async def login(self) -> bool:
        """Log in to the Daikin API with the given credentials to acquire auth tokens.

        Returns False only when the credentials themselves were rejected. Any other failure
        (network error, unexpected status, malformed response) raises DaikinServiceException
        instead, since those don't mean the credentials are wrong.
        """
        log.info("Logging in to Daikin API")
        try:
            async with aiohttp.ClientSession(
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
            ) as session:
                async with session.post(
                    url=DAIKIN_API_URL_LOGIN,
                    json={"email": self._creds.email, "password": self._creds.password},
                ) as response:
                    if response.status != 200:
                        body = await response.text()
                        log.error(f"Request to login failed: status={response.status} body={body}")
                        self._invalidate_auth()
                        if response.status in _AUTH_FAILURE_STATUSES:
                            return False
                        raise DaikinServiceException(
                            f"Failed to log in to Daikin API: status={response.status} body={body}",
                            status=response.status,
                        )

                    payload = await response.json()
                    if not isinstance(payload, dict):
                        log.error(f"Unexpected login response payload type: {type(payload).__name__}")
                        self._invalidate_auth()
                        raise DaikinServiceException(
                            f"Login response was not a JSON object: {type(payload).__name__}",
                            status=response.status,
                        )

                    refresh_token = payload.get("refreshToken")
                    access_token = payload.get("accessToken")

                    if refresh_token is None:
                        log.error("No refresh token found in login response")
                        self._invalidate_auth()
                        raise DaikinServiceException(
                            "Login response did not include a refresh token", status=response.status
                        )
                    if access_token is None:
                        log.error("No access token found in login response")
                        self._invalidate_auth()
                        raise DaikinServiceException(
                            "Login response did not include an access token", status=response.status
                        )

                    self._auth.refresh_token = refresh_token
                    self._auth.access_token = access_token
                    self._auth.authenticated = True

                    return True

        except _AUTH_TRANSPORT_ERRORS as e:
            log.error(f"Request to login failed: {e}")
            self._invalidate_auth()
            raise DaikinServiceException(f"Failed to log in to Daikin API: {e}", status=0) from e

    def _invalidate_auth(self) -> None:
        """Clear auth state so a failed login/refresh can never leave a stale token behind."""
        self._auth.authenticated = False
        self._auth.access_token = None
        self._auth.refresh_token = None

    async def request(
        self,
        url: str,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        retry: bool = True,
    ) -> Any:
        if not self._auth.authenticated:
            async with self._auth_lock:
                # another task may have already logged in while we were waiting on the lock
                if not self._auth.authenticated and not await self.login():
                    log.error(f"Unable to authenticate with Daikin API for request: {method} {url}")
                    raise DaikinAuthException(f"Unable to authenticate with Daikin API for request: {method} {url}")

        token = self._auth.access_token
        log.debug(f"Sending request to Daikin API: {method} {url}")
        async with aiohttp.ClientSession(
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            }
        ) as session:
            async with session.request(method, url, json=body) as response:
                log.debug(f"Got response: {response.status}")

                if response.status == 200:
                    try:
                        return await response.json()
                    except (ClientError, ValueError) as e:
                        # a malformed or unexpected-content-type body on an otherwise successful
                        # response: raise our own exception type instead of letting a raw
                        # aiohttp/stdlib error escape, so callers only ever see DaikinServiceException
                        # or DaikinAuthException (e.g. ConfigEntryNotReady classification during setup)
                        raise DaikinServiceException(
                            f"Failed to parse Daikin API response: method={method} url={url}: {e}",
                            status=response.status,
                        ) from e

                if response.status in _AUTH_FAILURE_STATUSES:
                    if retry:
                        log.info(f"Request rejected with status {response.status}, attempting to re-authenticate")
                        if not await self._reauthenticate(token):
                            log.error(f"Unable to re-authenticate with Daikin API after status {response.status}")
                            raise DaikinAuthException(
                                f"Unable to re-authenticate with Daikin API after status {response.status}",
                                status=response.status,
                            )
                        return await self.request(url, method, body, retry=False)

                    # the retried request, using a freshly (re)authenticated token, was still
                    # rejected: this is an auth failure, not a generic service error, even though
                    # the one-retry cap means we won't attempt re-authentication again
                    body_text = await response.text()
                    log.error(
                        f"Request rejected with status {response.status} even after re-authenticating: {body_text}"
                    )
                    raise DaikinAuthException(
                        f"Daikin API rejected the request with status {response.status} even after "
                        f"re-authenticating: method={method} url={url}",
                        status=response.status,
                    )

                raise DaikinServiceException(
                    f"Failed to send request to Daikin API: method={method} url={url} body={json.dumps(body)}, "
                    f"response_code={response.status} response_body={await response.text()}",
                    status=response.status,
                )

    async def _reauthenticate(self, stale_token: str | None) -> bool:
        """Recover a usable access token: try a refresh first, then fall back to a full login."""
        async with self._auth_lock:
            # another task already rotated the token while we were waiting on the lock
            if self._auth.access_token is not None and self._auth.access_token != stale_token:
                return True
            if await self._refresh_token():
                return True
            log.warning("Access token refresh failed, falling back to full login")
            return await self.login()

    async def _refresh_token(self) -> bool:
        if self._auth.refresh_token is None:
            log.debug("No refresh token available, skipping refresh")
            return False

        log.debug("Refreshing access token")
        try:
            async with aiohttp.ClientSession(
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            ) as session:
                async with session.post(
                    url=DAIKIN_API_URL_REFRESH_TOKEN,
                    json={
                        "email": self._creds.email,
                        "refreshToken": self._auth.refresh_token,
                    },
                ) as response:
                    if response.status != 200:
                        log.error(
                            f"Request to refresh access token failed: "
                            f"status={response.status} body={await response.text()}"
                        )
                        self._auth.authenticated = False
                        return False

                    payload = await response.json()
                    if not isinstance(payload, dict):
                        log.error(f"Unexpected refresh response payload type: {type(payload).__name__}")
                        self._auth.authenticated = False
                        return False

                    access_token = payload.get("accessToken")

                    if access_token is None:
                        log.error("No access token found in refresh response")
                        self._auth.authenticated = False
                        return False

                    # rotate the refresh token too, in case the API issues a new one on use
                    refresh_token = payload.get("refreshToken")
                    if refresh_token is not None:
                        self._auth.refresh_token = refresh_token

                    log.info("Refreshed access token")
                    self._auth.access_token = access_token
                    self._auth.authenticated = True

                    return True

        except _AUTH_TRANSPORT_ERRORS as e:
            log.error(f"Request to refresh access token failed: {e}")
            self._auth.authenticated = False
            return False
