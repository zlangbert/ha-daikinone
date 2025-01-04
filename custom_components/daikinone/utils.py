from typing import Any
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

class Temperature:
    """A class representing a temperature value in various units.

    It is intended to be instantiated via its static methods:
    - from_celsius
    - from_fahrenheit
    - from_kelvin

    Example usage:
        temp = Temperature.from_celsius(0)
        print(temp.fahrenheit)  # Prints the temperature in Fahrenheit
    """

    @staticmethod
    def from_celsius(temp_c: float) -> "Temperature":
        temp = Temperature()
        temp._init(temp_c)
        return temp

    @staticmethod
    def from_fahrenheit(temp_f: float) -> "Temperature":
        temp = Temperature()
        temp._init((temp_f - 32) * 5 / 9)
        return temp

    @staticmethod
    def from_kelvin(temp_k: float) -> "Temperature":
        temp = Temperature()
        temp._init(temp_k - 273.15)
        return temp

    def _init(self, temp_c: float) -> None:
        self._temp_c: float = round(temp_c, 1)

    @property
    def celsius(self) -> float:
        return round(self._temp_c, 1)

    @property
    def fahrenheit(self) -> float:
        return round(self._temp_c * 9 / 5 + 32, 1)

    @property
    def kelvin(self) -> float:
        return round(self._temp_c + 273.15, 1)

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        """Define the core schema for Pydantic v2 compatibility."""
        return core_schema.no_info_after_validator_function(
            cls.validate, core_schema.any_schema()
        )

    @classmethod
    def validate(cls, value: Any, field: core_schema.FieldValidationInfo = None) -> "Temperature":
        """Validate the input and convert it to a Temperature instance if necessary."""
        if isinstance(value, cls):
            return value  # Already a Temperature instance
        elif isinstance(value, (int, float)):
            return cls.from_celsius(float(value))
        else:
            raise TypeError(f"Cannot validate Temperature from type {type(value)}")

    def __eq__(self, o: object) -> bool:
        return isinstance(o, Temperature) and self._temp_c == o._temp_c

    def __str__(self) -> str:
        return f"{self.celsius}°C"
