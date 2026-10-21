"""Download hourly weather for the same site from the Open-Meteo archive."""
from pathlib import Path

import pandas as pd
import requests

LAT, LON = -20.16, 57.50
URL = "https://archive-api.open-meteo.com/v1/archive"
OUT = Path("data/raw/openmeteo_portlouis_hourly.parquet")
OUT.parent.mkdir(parents=True, exist_ok=True)

r = requests.get(URL, params={
    "latitude": LAT, "longitude": LON,
    "start_date": "2019-01-01", "end_date": "2023-12-31",
    "hourly": "shortwave_radiation,temperature_2m,wind_speed_10m,cloud_cover",
    "timezone": "UTC",
}, timeout=180)
if r.status_code != 200:
    print("Error", r.status_code, r.text[:500])
    r.raise_for_status()

body = r.json()
print("Units:", body["hourly_units"])
data = pd.DataFrame(body["hourly"])
data["time_utc"] = pd.to_datetime(data["time"])
data = data.drop(columns="time").set_index("time_utc")
data.to_parquet(OUT)
print(len(data), "rows")
print(data.describe())
