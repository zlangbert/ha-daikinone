"""Tests for DaikinOne client methods, including set_thermostat_schedule."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.models import DaikinUserCredentials
from custom_components.daikinone.client.wire import DAIKIN_API_URL_DEVICE_DATA
from tests.test_mapping import _make_device


@pytest.fixture
def daikin_client() -> DaikinOne:
    creds = DaikinUserCredentials(email="test@example.com", password="password")
    client = DaikinOne(creds)
    client._DaikinOne__thermostats.clear()  # type: ignore[attr-defined]
    return client


class TestClientScheduleMethods:
    """Tests for DaikinOne schedule client methods."""

    async def test_set_thermostat_schedule_atomic_put_and_optimistic_cache(self, daikin_client: DaikinOne) -> None:
        """Verify set_thermostat_schedule sends a single atomic PUT and updates cached thermostat schedule."""
        valid_dev = _make_device(
            {
                "schedMonPart1Time": 24,
                "schedMonPart1Enabled": True,
                "schedMonPart1hsp": 20.0,
                "schedMonPart1csp": 24.0,
                "schedMonPart1Label": "wake",
            }
        )
        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [valid_dev]
            await daikin_client.update()

        batch_payload = {
            "schedEnabled": True,
            "schedOverride": 0,
            "schedMonPart1Time": 26,
            "schedMonPart1Enabled": True,
            "schedMonPart1hsp": 21.0,
            "schedMonPart1csp": 25.0,
            "schedMonPart1Label": "morning",
            "schedTuePart1Time": 28,
            "schedTuePart1Enabled": True,
            "schedTuePart1hsp": 19.5,
            "schedTuePart1csp": 24.0,
            "schedTuePart1Label": "work",
        }

        with patch.object(daikin_client._transport, "request", new_callable=AsyncMock) as mock_put:
            await daikin_client.set_thermostat_schedule("device123", batch_payload)
            mock_put.assert_called_once_with(
                url=f"{DAIKIN_API_URL_DEVICE_DATA}/device123",
                method="PUT",
                body=batch_payload,
            )

        # Verify optimistic update in client RAM cache
        cached = daikin_client.get_thermostat("device123")
        assert cached.schedule.days is not None
        mon_p1 = cached.schedule.days["mon"].periods[1]
        assert mon_p1.start_slot == 26
        assert mon_p1.start_time_str == "06:30"
        assert mon_p1.heat_setpoint.celsius == 21.0
        assert mon_p1.cool_setpoint.celsius == 25.0
        assert mon_p1.label == "morning"

        tue_p1 = cached.schedule.days["tue"].periods[1]
        assert tue_p1.start_slot == 28
        assert tue_p1.start_time_str == "07:00"
        assert tue_p1.heat_setpoint.celsius == 19.5
        assert tue_p1.cool_setpoint.celsius == 24.0
        assert tue_p1.label == "work"

    async def test_set_thermostat_schedule_empty_payload_raises(self, daikin_client: DaikinOne) -> None:
        """Verify set_thermostat_schedule rejects an empty dictionary."""
        with pytest.raises(ValueError, match="Schedule payload must not be empty"):
            await daikin_client.set_thermostat_schedule("device123", {})
