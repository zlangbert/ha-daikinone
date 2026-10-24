"""Tests for Daikin One 7-day thermostat schedule services (get_schedule and set_schedule)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import ATTR_ENTITY_ID, UnitOfTemperature
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.daikinone import DaikinOneData
from custom_components.daikinone.client.client import DaikinOne
from custom_components.daikinone.client.models import DaikinUserCredentials
from custom_components.daikinone.client.wire import DAIKIN_API_URL_DEVICE_DATA
from custom_components.daikinone.const import CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY, DOMAIN
from custom_components.daikinone.exceptions import DaikinServiceException
from custom_components.daikinone.services import (
    SERVICE_GET_SCHEDULE,
    SERVICE_SET_SCHEDULE,
    _async_handle_get_schedule,
    _async_handle_set_schedule,
    async_register_services,
    async_unregister_services,
)
from tests.test_mapping import _make_device


def _build_full_schedule_payload() -> dict[str, Any]:
    """Build a complete 7-day x 6-period wire schedule payload."""
    sched: dict[str, Any] = {
        "schedEnabled": True,
        "schedOverride": 0,
        "tempDeltaMin": 2,
        "hspSched": 20.0,
        "cspSched": 24.0,
        "EquipProtocolMinHeatSetpoint": 10.0,
        "EquipProtocolMaxHeatSetpoint": 32.2,
        "EquipProtocolMinCoolSetpoint": 10.0,
        "EquipProtocolMaxCoolSetpoint": 32.2,
    }
    days = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    parts = [
        (1, True, 24, 20.0, 24.0, "wake"),
        (2, True, 51, 20.0, 24.0, "afternoon"),
        (3, True, 68, 20.0, 24.0, "dinner"),
        (4, True, 76, 20.0, 24.0, "evening"),
        (5, True, 84, 18.0, 24.0, "sleep"),
        (6, False, 0, 17.5, 22.0, ""),
    ]
    for day in days:
        for part, enabled, slot, hsp, csp, label in parts:
            prefix = f"sched{day}Part{part}"
            sched[f"{prefix}Action"] = 0
            sched[f"{prefix}Enabled"] = enabled
            sched[f"{prefix}Label"] = label
            sched[f"{prefix}Time"] = slot
            sched[f"{prefix}hsp"] = hsp
            sched[f"{prefix}csp"] = csp
    return sched


@pytest.fixture
async def setup_schedule_env() -> tuple[SimpleNamespace, DaikinOne, DaikinOneData]:
    """Create a populated DaikinOne client and mock HomeAssistant instance."""
    creds = DaikinUserCredentials(email="test@example.com", password="password")
    client = DaikinOne(creds)
    client._DaikinOne__thermostats.clear()  # type: ignore[attr-defined]

    dev = _make_device(_build_full_schedule_payload())
    dev["id"] = "3edbb7b4-7237-11ec-a442-473204fe7b80"
    dev["name"] = "MainFloor"

    with patch.object(client._transport, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = [dev]
        await client.update()

    entry = SimpleNamespace(data={CONF_OPTION_ENTITY_UID_SCHEMA_VERSION_KEY: 1})
    hass = SimpleNamespace(
        data={},
        config=SimpleNamespace(units=SimpleNamespace(temperature_unit=UnitOfTemperature.CELSIUS)),
        services=MagicMock(),
    )
    data = DaikinOneData(_hass=hass, entry=entry, daikin=client)  # type: ignore[arg-type]
    hass.data[DOMAIN] = data
    return hass, client, data


class TestGetScheduleService:
    """Tests for daikinone.get_schedule."""

    async def test_get_schedule_celsius_from_ram_zero_http(
        self, setup_schedule_env: tuple[SimpleNamespace, DaikinOne, DaikinOneData]
    ) -> None:
        """Verify get_schedule reads from local RAM in °C with zero HTTP calls."""
        hass, client, _ = setup_schedule_env
        hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS

        call = SimpleNamespace(
            hass=hass,
            data={ATTR_ENTITY_ID: "climate.mainfloor_thermostat"},
        )

        with patch.object(client._transport, "request", new_callable=AsyncMock) as mock_http:
            response = await _async_handle_get_schedule(call)  # type: ignore[arg-type]
            mock_http.assert_not_called()

        assert response["entity_id"] == "climate.mainfloor_thermostat"
        assert response["thermostat_id"] == "3edbb7b4-7237-11ec-a442-473204fe7b80"
        assert response["name"] == "MainFloor"
        assert response["schedule_enabled"] is True
        assert response["schedule_override"] is False
        assert response["temperature_unit"] == UnitOfTemperature.CELSIUS
        assert response["min_temp"] == 10.0
        assert response["max_temp"] == 32.2
        assert response["min_temp_delta"] == 2.0

        days = response["days"]
        assert set(days.keys()) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        mon_p1 = days["mon"][0]
        assert mon_p1 == {
            "part": 1,
            "enabled": True,
            "start_time": "06:00",
            "start_slot": 24,
            "heat_target": 20.0,
            "cool_target": 24.0,
            "label": "wake",
        }
        mon_p6 = days["mon"][5]
        assert mon_p6 == {
            "part": 6,
            "enabled": False,
            "start_time": "00:00",
            "start_slot": 0,
            "heat_target": 17.5,
            "cool_target": 22.0,
            "label": "",
        }

    async def test_get_schedule_fahrenheit_conversion(
        self, setup_schedule_env: tuple[SimpleNamespace, DaikinOne, DaikinOneData]
    ) -> None:
        """Verify get_schedule automatically converts setpoints and bounds to °F."""
        hass, _, _ = setup_schedule_env
        hass.config.units.temperature_unit = UnitOfTemperature.FAHRENHEIT

        call = SimpleNamespace(
            hass=hass,
            data={ATTR_ENTITY_ID: ["climate.mainfloor_thermostat"]},
        )
        response = await _async_handle_get_schedule(call)  # type: ignore[arg-type]

        assert response["temperature_unit"] == UnitOfTemperature.FAHRENHEIT
        assert response["min_temp"] == 50.0
        assert response["max_temp"] == 90.0
        assert response["min_temp_delta"] == 3.0

        mon_p1 = response["days"]["mon"][0]
        assert mon_p1["heat_target"] == 68.0  # 20.0°C -> 68.0°F
        assert mon_p1["cool_target"] == 75.2  # 24.0°C -> 75.2°F

        mon_p5 = response["days"]["mon"][4]
        assert mon_p5["heat_target"] == 64.4  # 18.0°C -> 64.4°F

    async def test_get_schedule_unknown_entity_raises(
        self, setup_schedule_env: tuple[SimpleNamespace, DaikinOne, DaikinOneData]
    ) -> None:
        """Verify get_schedule raises ServiceValidationError when entity does not match any thermostat."""
        hass, _, _ = setup_schedule_env
        call = SimpleNamespace(
            hass=hass,
            data={ATTR_ENTITY_ID: "climate.nonexistent_thermostat"},
        )
        with pytest.raises(ServiceValidationError, match="Could not find a Daikin One thermostat"):
            await _async_handle_get_schedule(call)  # type: ignore[arg-type]


class TestSetScheduleService:
    """Tests for daikinone.set_schedule."""

    async def test_set_schedule_atomic_batch_multi_day_celsius(
        self, setup_schedule_env: tuple[SimpleNamespace, DaikinOne, DaikinOneData]
    ) -> None:
        """Verify set_schedule batches multiple days and periods into a single PUT call and updates RAM."""
        hass, client, _ = setup_schedule_env
        hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS

        call = SimpleNamespace(
            hass=hass,
            data={
                ATTR_ENTITY_ID: "climate.mainfloor_thermostat",
                "schedule_enabled": True,
                "days": {
                    "mon": [
                        {
                            "part": 1,
                            "enabled": True,
                            "start_time": "06:30",
                            "heat_target": 21.0,
                            "cool_target": 24.5,
                            "label": "wake",
                        },
                        {
                            "part": 2,
                            "enabled": False,
                            "start_time": "09:15",
                            "heat_target": 18.5,
                            "cool_target": 25.0,
                            "label": "away",
                        },
                    ],
                    "sat": {
                        "1": {
                            "enabled": True,
                            "start_time": 32,  # 08:00
                            "heat_target": 20.5,
                            "cool_target": 24.0,
                            "label": "weekend",
                        }
                    },
                },
            },
        )

        with patch.object(client._transport, "request", new_callable=AsyncMock) as mock_put:
            await _async_handle_set_schedule(call)  # type: ignore[arg-type]
            mock_put.assert_called_once_with(
                url=f"{DAIKIN_API_URL_DEVICE_DATA}/3edbb7b4-7237-11ec-a442-473204fe7b80",
                method="PUT",
                body={
                    "schedEnabled": True,
                    "schedOverride": 0,
                    "schedMonPart1Time": 26,
                    "schedMonPart1Enabled": True,
                    "schedMonPart1hsp": 21.0,
                    "schedMonPart1csp": 24.5,
                    "schedMonPart1Label": "wake",
                    "schedMonPart2Time": 37,
                    "schedMonPart2Enabled": False,
                    "schedMonPart2hsp": 18.5,
                    "schedMonPart2csp": 25.0,
                    "schedMonPart2Label": "away",
                    "schedSatPart1Time": 32,
                    "schedSatPart1Enabled": True,
                    "schedSatPart1hsp": 20.5,
                    "schedSatPart1csp": 24.0,
                    "schedSatPart1Label": "weekend",
                },
            )

        # Verify subsequent get_schedule immediately reflects optimistic cache update
        get_call = SimpleNamespace(
            hass=hass,
            data={ATTR_ENTITY_ID: "climate.mainfloor_thermostat"},
        )
        res = await _async_handle_get_schedule(get_call)  # type: ignore[arg-type]
        assert res["days"]["mon"][0]["start_time"] == "06:30"
        assert res["days"]["mon"][0]["heat_target"] == 21.0
        assert res["days"]["mon"][1]["enabled"] is False
        assert res["days"]["mon"][1]["start_time"] == "09:15"
        assert res["days"]["sat"][0]["start_time"] == "08:00"
        assert res["days"]["sat"][0]["label"] == "weekend"

    async def test_set_schedule_fahrenheit_to_celsius_conversion(
        self, setup_schedule_env: tuple[SimpleNamespace, DaikinOne, DaikinOneData]
    ) -> None:
        """Verify set_schedule converts °F setpoints to rounded °C wire values."""
        hass, client, _ = setup_schedule_env
        hass.config.units.temperature_unit = UnitOfTemperature.FAHRENHEIT

        call = SimpleNamespace(
            hass=hass,
            data={
                ATTR_ENTITY_ID: "climate.mainfloor_thermostat",
                "days": {
                    "Friday": [
                        {
                            "part": 1,
                            "enabled": True,
                            "start_time": "07:00",
                            "heat_target": 68.0,  # 20.0°C
                            "cool_target": 75.0,  # 23.9°C
                            "label": "wake",
                        }
                    ]
                },
            },
        )

        with patch.object(client._transport, "request", new_callable=AsyncMock) as mock_put:
            await _async_handle_set_schedule(call)  # type: ignore[arg-type]
            mock_put.assert_called_once_with(
                url=f"{DAIKIN_API_URL_DEVICE_DATA}/3edbb7b4-7237-11ec-a442-473204fe7b80",
                method="PUT",
                body={
                    "schedFriPart1Time": 28,
                    "schedFriPart1Enabled": True,
                    "schedFriPart1hsp": 20.0,
                    "schedFriPart1csp": 23.9,
                    "schedFriPart1Label": "wake",
                },
            )

    async def test_set_schedule_fahrenheit_exact_3f_deadband_accepted_and_2f_rejected(
        self, setup_schedule_env: tuple[SimpleNamespace, DaikinOne, DaikinOneData]
    ) -> None:
        """Verify 3.0°F deadband (72°F/75°F -> 22.2°C/23.9°C) succeeds and 2.0°F (73°F/75°F) is rejected."""
        hass, client, _ = setup_schedule_env
        hass.config.units.temperature_unit = UnitOfTemperature.FAHRENHEIT

        valid_3f_call = SimpleNamespace(
            hass=hass,
            data={
                ATTR_ENTITY_ID: "climate.mainfloor_thermostat",
                "days": {
                    "mon": [
                        {
                            "part": 1,
                            "enabled": True,
                            "start_time": "06:00",
                            "heat_target": 72.0,  # 22.2°C
                            "cool_target": 75.0,  # 23.9°C
                            "label": "wake",
                        }
                    ]
                },
            },
        )
        with patch.object(client._transport, "request", new_callable=AsyncMock) as mock_put:
            await _async_handle_set_schedule(valid_3f_call)  # type: ignore[arg-type]
            mock_put.assert_called_once_with(
                url=f"{DAIKIN_API_URL_DEVICE_DATA}/3edbb7b4-7237-11ec-a442-473204fe7b80",
                method="PUT",
                body={
                    "schedMonPart1Time": 24,
                    "schedMonPart1Enabled": True,
                    "schedMonPart1hsp": 22.2,
                    "schedMonPart1csp": 23.9,
                    "schedMonPart1Label": "wake",
                },
            )

        invalid_2f_call = SimpleNamespace(
            hass=hass,
            data={
                ATTR_ENTITY_ID: "climate.mainfloor_thermostat",
                "days": {
                    "mon": [
                        {
                            "part": 1,
                            "enabled": True,
                            "start_time": "06:00",
                            "heat_target": 73.0,
                            "cool_target": 75.0,
                            "label": "wake",
                        }
                    ]
                },
            },
        )
        with (
            patch.object(client._transport, "request", new_callable=AsyncMock) as mock_put_fail,
            pytest.raises(ServiceValidationError, match="Deadband violation"),
        ):
            await _async_handle_set_schedule(invalid_2f_call)  # type: ignore[arg-type]
        mock_put_fail.assert_not_called()

    @pytest.mark.parametrize(
        ("invalid_payload", "expected_error_match"),
        [
            (
                {"days": {"funday": [{"part": 1, "start_time": "06:00"}]}},
                "Invalid day key 'funday'",
            ),
            (
                {"days": {"mon": [{"part": 7, "start_time": "06:00"}]}},
                "Invalid part number",
            ),
            (
                {"days": {"mon": [{"part": 1, "start_time": "06:07"}]}},
                "15-minute increments",
            ),
            (
                {"days": {"mon": [{"part": 1, "start_time": "25:00"}]}},
                "hour must be 0-23",
            ),
            (
                {"days": {"mon": [{"part": 1, "start_time": 96}]}},
                "integer slot must be between 0",
            ),
            (
                {"days": {"mon": [{"part": 1, "heat_target": 5.0, "cool_target": 24.0}]}},
                "outside hardware bounds",
            ),
            (
                {"days": {"mon": [{"part": 1, "heat_target": 25.0, "cool_target": 22.0}]}},
                "cannot exceed cooling target",
            ),
            (
                {"days": {"mon": [{"part": 1, "heat_target": 21.0, "cool_target": 22.0}]}},
                "Deadband violation",
            ),
        ],
    )
    async def test_set_schedule_validation_errors(
        self,
        setup_schedule_env: tuple[SimpleNamespace, DaikinOne, DaikinOneData],
        invalid_payload: dict[str, Any],
        expected_error_match: str,
    ) -> None:
        """Verify invalid schedule inputs raise ServiceValidationError before any cloud call."""
        hass, client, _ = setup_schedule_env
        call = SimpleNamespace(
            hass=hass,
            data={ATTR_ENTITY_ID: "climate.mainfloor_thermostat", **invalid_payload},
        )

        with (
            patch.object(client._transport, "request", new_callable=AsyncMock) as mock_put,
            pytest.raises((ServiceValidationError, Exception), match=expected_error_match),
        ):
            await _async_handle_set_schedule(call)  # type: ignore[arg-type]

        mock_put.assert_not_called()

    async def test_set_schedule_transport_failure_raises_homeassistant_error(
        self, setup_schedule_env: tuple[SimpleNamespace, DaikinOne, DaikinOneData]
    ) -> None:
        """Verify DaikinServiceException during PUT surfaces as HomeAssistantError."""
        hass, client, _ = setup_schedule_env
        call = SimpleNamespace(
            hass=hass,
            data={
                ATTR_ENTITY_ID: "climate.mainfloor_thermostat",
                "schedule_enabled": False,
            },
        )

        with (
            patch.object(
                client._transport,
                "request",
                new_callable=AsyncMock,
                side_effect=DaikinServiceException("cloud timeout", status=504),
            ),
            pytest.raises(HomeAssistantError, match="Failed to update schedule"),
        ):
            await _async_handle_set_schedule(call)  # type: ignore[arg-type]

    async def test_set_schedule_accepts_raw_get_schedule_response_payload(
        self, setup_schedule_env: tuple[SimpleNamespace, DaikinOne, DaikinOneData]
    ) -> None:
        """Verify set_schedule accepts the full get_schedule response dictionary without errors."""
        hass, client, _ = setup_schedule_env
        get_call = SimpleNamespace(
            hass=hass,
            data={ATTR_ENTITY_ID: "climate.mainfloor_thermostat"},
        )
        response = await _async_handle_get_schedule(get_call)  # type: ignore[arg-type]
        assert "days" in response
        assert "thermostat_id" in response

        from custom_components.daikinone.services import SET_SCHEDULE_SCHEMA

        validated_data = SET_SCHEDULE_SCHEMA(dict(response))
        assert "thermostat_id" not in validated_data

        set_call = SimpleNamespace(
            hass=hass,
            data=validated_data,
        )

        with patch.object(client._transport, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {}
            await _async_handle_set_schedule(set_call)  # type: ignore[arg-type]
            assert mock_req.call_count == 1


class TestServiceRegistrationLifecycle:
    """Tests for async_register_services and async_unregister_services."""

    def test_register_and_unregister_services(self) -> None:
        """Verify services are registered with SupportsResponse.ONLY for get_schedule and removed cleanly."""
        hass = SimpleNamespace(services=MagicMock())
        hass.services.has_service.return_value = False

        async_register_services(hass)  # type: ignore[arg-type]
        assert hass.services.async_register.call_count == 2

        get_call_args = hass.services.async_register.call_args_list[0]
        assert get_call_args.args[0] == DOMAIN
        assert get_call_args.args[1] == SERVICE_GET_SCHEDULE
        assert get_call_args.kwargs["supports_response"] == SupportsResponse.ONLY

        set_call_args = hass.services.async_register.call_args_list[1]
        assert set_call_args.args[0] == DOMAIN
        assert set_call_args.args[1] == SERVICE_SET_SCHEDULE

        hass.services.has_service.return_value = True
        async_unregister_services(hass)  # type: ignore[arg-type]
        assert hass.services.async_remove.call_count == 2
