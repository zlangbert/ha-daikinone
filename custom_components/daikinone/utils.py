from pydantic import BaseModel


class Temperature(BaseModel):
    """A class representing a temperature value in various units.

    It is intended to be instantiated via its static methods:
    - from_celsius
    - from_fahrenheit
    - from_kelvin

    Example usage:
        temp = Temperature.from_celsius(0)
        print(temp.fahrenheit)  # Prints the temperature in Fahrenheit
    """

    _temp_c: float

    def __init__(self, temp_c: float) -> None:
        super().__init__()
        self._temp_c = round(temp_c, 1)

    @staticmethod
    def from_celsius(temp_c: float) -> "Temperature":
        return Temperature(temp_c)

    @staticmethod
    def from_fahrenheit(temp_f: float) -> "Temperature":
        return Temperature((temp_f - 32) * 5 / 9)

    @staticmethod
    def from_kelvin(temp_k: float) -> "Temperature":
        return Temperature(temp_k - 273.15)

    @property
    def celsius(self) -> float:
        return round(self._temp_c, 1)

    @property
    def fahrenheit(self) -> float:
        return round(self._temp_c * 9 / 5 + 32, 1)

    @property
    def kelvin(self) -> float:
        return round(self._temp_c + 273.15, 1)

    def __eq__(self, o: object) -> bool:
        return isinstance(o, Temperature) and self._temp_c == o._temp_c

    def __str__(self) -> str:
        return f"{self.celsius}°C"
