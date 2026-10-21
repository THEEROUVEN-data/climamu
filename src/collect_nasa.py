"""Download hourly solar and weather data for one test site from NASA POWER."""
from pathlib import Path

import pandas as pd
import requests

LAT, LON = -20.16, 57.50
START_YEAR, END_YEAR = 2019, 2023
PARAMS = "ALLSKY_SFC_SW_DWN,T2M,WS10M"
URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"
OUT = Path("data/raw/nasa_portlouis_hourly.parquet")
OUT.parent.mkdir(parents=True, exist_ok=True)

frames = []
for year in range(START_YEAR, END_YEAR + 1):
    r = requests.get(URL, params={
        "start": f"{year}0101", "end": f"{year}1231",
        "latitude": LAT, "longitude": LON,
        "community": "re", "parameters": PARAMS,
        "format": "json", "time-standard": "utc",
    }, timeout=180)
    if r.status_code != 200:
        print("Error", r.status_code, r.text[:500])
        r.raise_for_status()
    body = r.json()
    if year == START_YEAR:
        print("Units:", {k: v["units"] for k, v in body["parameters"].items()})
    df = pd.DataFrame(body["properties"]["parameter"])
    df.index = pd.to_datetime(df.index, format="%Y%m%d%H")
    frames.append(df)
    print(year, "downloaded", len(df), "rows")

data = pd.concat(frames)
data.index.name = "time_utc"
data = data.mask(data == -999)
data.to_parquet(OUT)
print(data.describe())
