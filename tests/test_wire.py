from dataclasses import dataclass
from datetime import timedelta

import pytest
from pydantic import ValidationError

from custom_components.daikinone.client.wire import (
    CelsiusField,
    DaikinDeviceDataResponse,
    FloatField,
    IntField,
    PercentField,
    RuntimeField,
    Sentinel,
    StringField,
    TempField,
    capitalize,
    read,
)
from custom_components.daikinone.utils import Temperature


class TestSentinel:
    def test_values(self) -> None:
        assert Sentinel.U8 == 255
        assert Sentinel.U16 == 65535
        assert Sentinel.I16 == 32767
        assert Sentinel.U32 == 4294967295


class TestIntField:
    def test_sentinel_returns_none(self) -> None:
        assert read({"k": 255}, IntField("k", Sentinel.U8)) is None
        assert read({"k": 65535}, IntField("k", Sentinel.U16)) is None
        assert read({"k": 32767}, IntField("k", Sentinel.I16)) is None

    def test_scaled(self) -> None:
        assert read({"k": 100}, IntField("k", Sentinel.U8, 0.5)) == 50
        assert read({"k": 80}, IntField("k", Sentinel.U8, 10)) == 800

    def test_returns_int(self) -> None:
        v = read({"k": 3}, IntField("k", Sentinel.U8, 0.5))
        assert isinstance(v, int)

    def test_zero_preserved(self) -> None:
        assert read({"k": 0}, IntField("k", Sentinel.U8, 0.5)) == 0

    def test_rounds_half_to_even(self) -> None:
        # 3 * 0.5 = 1.5; Python's round() uses banker's rounding → 2
        assert read({"k": 3}, IntField("k", Sentinel.U8, 0.5)) == 2
        # 5 * 0.5 = 2.5 → 2 (banker's rounding)
        assert read({"k": 5}, IntField("k", Sentinel.U8, 0.5)) == 2

    def test_near_sentinel_value_preserved(self) -> None:
        assert read({"k": 254}, IntField("k", Sentinel.U8)) == 254
        assert read({"k": 65534}, IntField("k", Sentinel.U16)) == 65534

    def test_default_scale_returns_raw(self) -> None:
        assert read({"k": 42}, IntField("k", Sentinel.U16)) == 42


class TestFloatField:
    def test_sentinel_returns_none(self) -> None:
        assert read({"k": 65535}, FloatField("k", Sentinel.U16, 0.1)) is None

    def test_scaled(self) -> None:
        assert read({"k": 100}, FloatField("k", Sentinel.U16, 0.1)) == 10.0

    def test_returns_float(self) -> None:
        v = read({"k": 100}, FloatField("k", Sentinel.U16, 0.1))
        assert isinstance(v, float)

    def test_deca_scale(self) -> None:
        # outdoor-power encoding: uint16 as deca-watt
        assert read({"k": 500}, FloatField("k", Sentinel.U16, 10)) == 5000.0

    def test_default_scale_returns_raw_float(self) -> None:
        v = read({"k": 7}, FloatField("k", Sentinel.U16))
        assert v == 7.0
        assert isinstance(v, float)

    def test_zero_preserved(self) -> None:
        assert read({"k": 0}, FloatField("k", Sentinel.U16, 0.1)) == 0.0


class TestTempField:
    def test_deci_fahrenheit_default(self) -> None:
        t = read({"k": 750}, TempField("k"))
        assert t is not None
        assert abs(t.celsius - Temperature.from_fahrenheit(75.0).celsius) < 1e-6

    def test_sentinel_default_i16(self) -> None:
        assert read({"k": 32767}, TempField("k")) is None

    def test_celsius_unit(self) -> None:
        t = read({"k": 40}, TempField("k", Sentinel.U8, scale=1, unit="C"))
        assert t is not None
        assert t.celsius == 40

    def test_celsius_sentinel(self) -> None:
        assert read({"k": 255}, TempField("k", Sentinel.U8, scale=1, unit="C")) is None

    def test_zero_deci_fahrenheit(self) -> None:
        t = read({"k": 0}, TempField("k"))
        assert t is not None
        assert t.fahrenheit == 0.0

    def test_negative_deci_fahrenheit(self) -> None:
        t = read({"k": -100}, TempField("k"))
        assert t is not None
        # Temperature stores as celsius rounded to 1 decimal; allow tolerance on round-trip
        assert abs(t.fahrenheit - (-10.0)) < 0.1

    def test_deci_celsius(self) -> None:
        t = read({"k": 215}, TempField("k", unit="C"))
        assert t is not None
        assert t.celsius == 21.5

    def test_non_default_sentinel(self) -> None:
        assert read({"k": 255}, TempField("k", Sentinel.U8)) is None


class TestRuntimeField:
    def test_hours_to_timedelta(self) -> None:
        t = read({"k": 1000}, RuntimeField("k"))
        assert t is not None
        assert t.total_seconds() == 1000 * 3600

    def test_sentinel_returns_none(self) -> None:
        assert read({"k": 4294967295}, RuntimeField("k")) is None

    def test_zero_hours_is_not_sentinel(self) -> None:
        t = read({"k": 0}, RuntimeField("k"))
        assert t == timedelta(0)

    def test_custom_sentinel(self) -> None:
        assert read({"k": 65535}, RuntimeField("k", Sentinel.U16)) is None
        t = read({"k": 5}, RuntimeField("k", Sentinel.U16))
        assert t == timedelta(hours=5)


class TestStringField:
    def test_strips(self) -> None:
        assert read({"k": "hello   "}, StringField("k")) == "hello"

    def test_replacement_char_returns_none(self) -> None:
        assert read({"k": "he\ufffdlo"}, StringField("k")) is None

    def test_strips_leading_and_trailing(self) -> None:
        assert read({"k": "   hello   "}, StringField("k")) == "hello"

    def test_whitespace_only_strips_to_empty(self) -> None:
        # only the replacement char triggers None; empty string is a valid result
        assert read({"k": "     "}, StringField("k")) == ""

    def test_replacement_char_at_start(self) -> None:
        assert read({"k": "\ufffdhello"}, StringField("k")) is None

    def test_replacement_char_at_end(self) -> None:
        assert read({"k": "hello\ufffd"}, StringField("k")) is None


class TestPercentField:
    def test_valid_range(self) -> None:
        assert read({"k": 0}, PercentField("k")) == 0
        assert read({"k": 50}, PercentField("k")) == 50
        assert read({"k": 100}, PercentField("k")) == 100

    def test_out_of_range_returns_none(self) -> None:
        assert read({"k": -1}, PercentField("k")) is None
        assert read({"k": 101}, PercentField("k")) is None
        assert read({"k": 255}, PercentField("k")) is None

    def test_boundaries_inclusive(self) -> None:
        assert read({"k": 0}, PercentField("k")) == 0
        assert read({"k": 100}, PercentField("k")) == 100


class TestCelsiusField:
    def test_in_range(self) -> None:
        t = read({"k": 21.5}, CelsiusField("k"))
        assert t is not None and t.celsius == 21.5

    def test_out_of_range_returns_none(self) -> None:
        assert read({"k": -99}, CelsiusField("k")) is None
        assert read({"k": 200}, CelsiusField("k")) is None

    def test_custom_bounds(self) -> None:
        assert read({"k": 5}, CelsiusField("k", min_c=10, max_c=30)) is None
        assert read({"k": 15}, CelsiusField("k", min_c=10, max_c=30)) is not None

    def test_default_bounds_inclusive(self) -> None:
        low = read({"k": -60}, CelsiusField("k"))
        high = read({"k": 80}, CelsiusField("k"))
        assert low is not None and low.celsius == -60
        assert high is not None and high.celsius == 80

    def test_just_outside_default_bounds(self) -> None:
        assert read({"k": -60.1}, CelsiusField("k")) is None
        assert read({"k": 80.1}, CelsiusField("k")) is None

    def test_zero_accepted(self) -> None:
        t = read({"k": 0}, CelsiusField("k"))
        assert t is not None and t.celsius == 0


@dataclass(frozen=True)
class _UnknownField:
    key: str


class TestReaderDispatch:
    def test_unknown_spec_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            read({"k": 1}, _UnknownField("k"))

    def test_missing_key_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            read({}, IntField("k", Sentinel.U8))


class TestHelpers:
    def test_capitalize_none_passthrough(self) -> None:
        assert capitalize(None) is None
        assert capitalize("") is None  # empty string is falsy

    def test_capitalize(self) -> None:
        assert capitalize("heat") == "Heat"

    def test_capitalize_idempotent(self) -> None:
        assert capitalize("Heat") == "Heat"

    def test_capitalize_multi_word_lowercases_rest(self) -> None:
        # str.capitalize() lowercases everything after the first char
        assert capitalize("HEAT MODE") == "Heat mode"


class TestDaikinDeviceDataResponse:
    def _minimal_payload(self) -> dict[str, object]:
        return {
            "id": "device123",
            "locationId": "loc456",
            "name": "Test",
            "model": "ONEPLUS",
            "firmware": "1.0.0",
            "online": True,
            "data": {"foo": "bar"},
        }

    def test_parses_valid_payload(self) -> None:
        payload = DaikinDeviceDataResponse(**self._minimal_payload())  # type: ignore[arg-type]
        assert payload.id == "device123"
        assert payload.locationId == "loc456"
        assert payload.online is True
        assert payload.data == {"foo": "bar"}

    def test_missing_required_field_raises(self) -> None:
        data = self._minimal_payload()
        del data["online"]
        with pytest.raises(ValidationError):
            DaikinDeviceDataResponse(**data)  # type: ignore[arg-type]

    def test_data_preserves_nested_dict(self) -> None:
        nested = {"a": 1, "b": {"c": [1, 2, 3]}, "d": None}
        data = self._minimal_payload()
        data["data"] = nested
        payload = DaikinDeviceDataResponse(**data)  # type: ignore[arg-type]
        assert payload.data == nested
