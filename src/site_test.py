"""Test whether the sources distinguish between sites on a small island."""
from pathlib import Path

import pandas as pd
import requests

SITES = {
    "Port Louis": (-20.16, 57.50),
    "Curepipe": (-20.32, 57.52),
    "Mahebourg": (-20.41, 57.70),
}
Path("data/raw").mkdir(parents=True, exist_ok=True)


def nasa_daily(lat, lon):
    r = requests.get("https://power.larc.nasa.gov/api/temporal/daily/point", params={
        "start": "20190101", "end": "20231231", "latitude": lat, "longitude": lon,
        "community": "re", "parameters": "ALLSKY_SFC_SW_DWN", "format": "json",
    }, timeout=180)
    r.raise_for_status()
    s = pd.Series(r.json()["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"])
    s.index = pd.to_datetime(s.index, format="%Y%m%d")
    return s.mask(s == -999)


def openmeteo_daily(lat, lon):
    r = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
        "latitude": lat, "longitude": lon,
        "start_date": "2019-01-01", "end_date": "2023-12-31",
        "daily": "shortwave_radiation_sum", "timezone": "UTC",
    }, timeout=180)
    r.raise_for_status()
    d = r.json()["daily"]
    s = pd.Series(d["shortwave_radiation_sum"],
                  index=pd.to_datetime(d["time"]))
    return s / 3.6   # MJ/m2 to kWh/m2


nasa = pd.DataFrame({n: nasa_daily(*c) for n, c in SITES.items()})
om = pd.DataFrame({n: openmeteo_daily(*c) for n, c in SITES.items()})
nasa.to_parquet("data/raw/site_test_nasa_daily.parquet")
om.to_parquet("data/raw/site_test_openmeteo_daily.parquet")

print("Mean daily radiation (kWh/m2/day):")
print(pd.concat({"NASA POWER": nasa.mean(),
      "Open-Meteo": om.mean()}, axis=1).round(2))

for name, df in (("NASA POWER", nasa), ("Open-Meteo", om)):
    print(f"\n{name}: largest daily difference between sites (kWh/m2/day)")
    print("Port Louis vs Curepipe:", round(
        (df["Port Louis"] - df["Curepipe"]).abs().max(), 3))
    print("Port Louis vs Mahebourg:", round(
        (df["Port Louis"] - df["Mahebourg"]).abs().max(), 3))

print("\nNASA vs Open-Meteo, mean absolute daily difference per site:")
for n in SITES:
    print(n, round((nasa[n] - om[n]).abs().mean(), 2))
