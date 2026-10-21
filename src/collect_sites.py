"""Download hourly Open-Meteo archive data for every site in sites.csv."""
import time
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds
import requests

START_YEAR, END_YEAR = 2006, 2025
HOURLY = ("shortwave_radiation,direct_radiation,diffuse_radiation,"
          "temperature_2m,relative_humidity_2m,cloud_cover,"
          "wind_speed_10m,precipitation")
URL = "https://archive-api.open-meteo.com/v1/archive"
OUT = Path("data/raw/openmeteo")

sites = pd.read_csv("src/sites.csv")


def slug(name):
    return name.replace(" ", "_").replace("'", "")


def fetch(lat, lon, year):
    for attempt in range(8):
        r = requests.get(URL, params={
            "latitude": lat, "longitude": lon,
            "start_date": f"{year}-01-01", "end_date": f"{year}-12-31",
            "hourly": HOURLY, "timezone": "UTC",
        }, timeout=180)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            try:
                reason = r.json().get("reason", "")
            except ValueError:
                reason = r.text[:200]
            print("  rate limited:", reason)
            if "daily" in reason.lower():
                raise SystemExit(
                    "Daily limit reached. Rerun tomorrow; finished files are kept.")
            print("  waiting 10 minutes")
            time.sleep(600)
            continue
        print("Error", r.status_code, r.text[:300])
        r.raise_for_status()
    raise RuntimeError("Too many retries")


for _, s in sites.iterrows():
    for year in range(START_YEAR, END_YEAR + 1):
        path = OUT / f"site={slug(s['name'])}" / \
            f"year={year}" / "data.parquet"
        if path.exists():
            continue                      # lets you rerun after an interruption
        body = fetch(s["lat"], s["lon"], year)
        df = pd.DataFrame(body["hourly"])
        df["time"] = pd.to_datetime(df["time"])
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        print(s["name"], year, len(df), "rows")
        time.sleep(5)

print("\nTotal rows stored:",
      ds.dataset(OUT, format="parquet", partitioning="hive").count_rows())

# Duplicate grid cell check, using hourly radiation for one recent year


def load(name, year=2024):
    p = OUT / f"site={slug(name)}" / f"year={year}" / "data.parquet"
    return pd.read_parquet(p).set_index("time")["shortwave_radiation"]


radiation = pd.DataFrame({n: load(n) for n in sites["name"]})
names = list(radiation.columns)
pairs = []
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a, b = names[i], names[j]
        pairs.append((a, b,
                      round((radiation[a] - radiation[b]).abs().mean(), 2),
                      round(radiation[a].corr(radiation[b]), 4)))

pairs = pd.DataFrame(
    pairs, columns=["Site A", "Site B", "MAE W/m2", "Correlation"])
print("\nClosest pairs of sites (2024 hourly radiation):")
print(pairs.sort_values("MAE W/m2").head(10).to_string(index=False))
print("\nPairs with MAE below 0.01 are identical data and share a grid cell.")
