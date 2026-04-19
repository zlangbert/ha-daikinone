"""Auth state + HTTP transport for the Daikin API."""

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
from custom_components.daikinone.exceptions import DaikinServiceException

log = logging.getLogger(__name__)


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

    async def login(self) -> bool:
        """Log in to the Daikin API with the given credentials to acquire auth tokens."""
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
                        log.error(f"Request to login failed: {response}")
                        return False

                    payload = await response.json()
                    refresh_token = payload["refreshToken"]
                    access_token = payload["accessToken"]

                    if refresh_token is None:
                        log.error("No refresh token found in login response")
                        return False
                    if access_token is None:
                        log.error("No access token found in login response")
                        return False

                    self._auth.refresh_token = refresh_token
                    self._auth.access_token = access_token
                    self._auth.authenticated = True

                    return True

        except ClientError as e:
            log.error(f"Request to login failed: {e}")
            return False

    async def request(
        self,
        url: str,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        retry: bool = True,
    ) -> Any:
        if self._auth.authenticated is not True:
            await self.login()

        log.debug(f"Sending request to Daikin API: {method} {url}")
        async with aiohttp.ClientSession(
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._auth.access_token}",
            }
        ) as session:
            async with session.request(method, url, json=body) as response:
                log.debug(f"Got response: {response.status}")

                if response.status == 200:
                    return await response.json()

                if response.status == 401 and retry:
                    await self._refresh_token()
                    return await self.request(url, method, body, retry=False)

                raise DaikinServiceException(
                    f"Failed to send request to Daikin API: method={method} url={url} body={json.dumps(body)}, "
                    f"response_code={response.status} response_body={await response.text()}",
                    status=response.status,
                )

    async def _refresh_token(self) -> bool:
        log.debug("Refreshing access token")
        if self._auth.authenticated is not True:
            await self.login()

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
                    log.error(f"Request to refresh access token: {response}")
                    self._auth.authenticated = False
                    return False

                payload = await response.json()
                access_token = payload["accessToken"]

                if access_token is None:
                    log.error("No access token found in refresh response")
                    self._auth.authenticated = False
                    return False

                log.info("Refreshed access token")
                self._auth.access_token = access_token
                self._auth.authenticated = True

                return True
