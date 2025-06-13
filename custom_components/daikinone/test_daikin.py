# test_daikin.py
import asyncio
import getpass
import os
from pprint import pprint

from custom_components.daikinone.daikinone import DaikinOne, DaikinUserCredentials

async def main():
    email = os.getenv("DAIKIN_ONE_EMAIL")
    password = os.getenv("DAIKIN_ONE_PASSWORD")

    if not email:
        email = input("Enter email: ")
    if not password:
        password = getpass.getpass("Enter password: ")
    creds = DaikinUserCredentials(email=email, password=password)
    client = DaikinOne(creds)
    await client.update()
    ths = client.get_thermostats()
    for tid, th in ths.items():
        print(f"Thermostat {th.name} ({tid}):")
        print(f"  Indoor {th.indoor_temperature.celsius}°C, power units:")
        for eq in th.equipment.values():
            pprint(eq)
        print()

if __name__ == "__main__":
    asyncio.run(main())
