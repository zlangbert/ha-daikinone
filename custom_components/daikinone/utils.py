from typing import Any


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

    def _init(self, temp_c: float) -> None:
        self._temp_c: float = temp_c

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
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: Any) -> "Temperature":
        if not isinstance(v, cls):
            raise TypeError(f"Expected an instance of Temperature, received {type(v)}")

        if not hasattr(v, "_temp_c") or getattr(v, "_temp_c") is None:
            raise TypeError("Temperature instance is not initialized")

        return v
