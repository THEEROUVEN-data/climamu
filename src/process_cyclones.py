"""Process NOAA IBTrACS South Indian basin tracks into storm events near Mauritius
and link each event to local weather from the daily store."""
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("data/raw/ibtracs_SI.csv")
STORE = Path("data/store/daily.parquet")
OUT = Path("app/data")
SUMMARY = Path("docs/cyclone_summary.csv")
CENTER = (-20.25, 57.55)      # approximate centre of Mauritius
NEAR_KM = 300                 # an event is a storm that came at least this close
MAP_KM = 1200                 # track points kept for the map
MIN_STORM_KT = 34             # storm must reach tropical-storm strength somewhere on its track
FIRST_SEASON = 1980           # a season runs July to June and is named by its start year
UTC_PLUS = pd.Timedelta(hours=4)


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def season_start(ts):
    return np.where(ts.dt.month >= 7, ts.dt.year, ts.dt.year - 1)


def season_label(start):
    return start.astype(str) + "/" + ((start + 1) % 100).astype(str).str.zfill(2)


# 1. Read the track points (the second row of the file holds units, so it is skipped)
cols = ["SID", "NAME", "ISO_TIME", "LAT", "LON", "WMO_WIND", "USA_WIND"]
raw = pd.read_csv(RAW, skiprows=[1], usecols=cols, na_values=[" ", ""],
                  keep_default_na=False, low_memory=False)
raw["time"] = pd.to_datetime(raw["ISO_TIME"], errors="coerce")
for c in ["LAT", "LON", "WMO_WIND", "USA_WIND"]:
    raw[c] = pd.to_numeric(raw[c], errors="coerce")
raw = raw.dropna(subset=["time", "LAT", "LON"]).reset_index(drop=True)
raw["wind_kt"] = raw["WMO_WIND"].fillna(raw["USA_WIND"])      # knots; mixes agencies when WMO is missing
raw["dist_km"] = haversine(CENTER[0], CENTER[1], raw["LAT"], raw["LON"])
print("Track points read:", len(raw), "| storms:", raw["SID"].nunique())

# 2. One row per storm: closest approach to Mauritius and intensity
g = raw.groupby("SID")
ev = raw.loc[g["dist_km"].idxmin(), ["SID", "NAME", "time", "LAT", "LON", "dist_km", "wind_kt"]].rename(columns={
    "time": "closest_time", "LAT": "lat_closest", "LON": "lon_closest",
    "dist_km": "min_dist_km", "wind_kt": "wind_at_closest_kt"})
ev = ev.merge(g["wind_kt"].max().rename("max_wind_kt").reset_index(), on="SID")
near_wind = raw[raw["dist_km"] <= NEAR_KM].groupby("SID")["wind_kt"].max().rename("wind_near_kt")
ev = ev.merge(near_wind.reset_index(), on="SID", how="left")
ev["NAME"] = ev["NAME"].fillna("UNNAMED")

today = pd.Timestamp(date.today())
current = today.year if today.month >= 7 else today.year - 1     # the season in progress is left out
ev = ev[(ev["closest_time"] >= pd.Timestamp(f"{FIRST_SEASON}-07-01")) & (ev["max_wind_kt"] >= MIN_STORM_KT)].copy()
ev["season_start"] = season_start(ev["closest_time"])
ev = ev[ev["season_start"] < current].copy()
ev["season"] = season_label(ev["season_start"])

# 3. Seasons table, including seasons with no storm nearby
seasons = pd.DataFrame({"season_start": np.arange(FIRST_SEASON, current)})
seasons["season"] = season_label(seasons["season_start"])
for k in (100, 200, 300):
    counts = ev[ev["min_dist_km"] <= k].groupby("season_start").size()
    seasons[f"n_{k}"] = seasons["season_start"].map(counts).fillna(0).astype(int)

ev = ev[ev["min_dist_km"] <= NEAR_KM].copy()

# 4. Link each event to local weather in a window of one day either side of closest approach
store = pd.read_parquet(STORE, columns=["date", "site", "radiation_kwh", "rain_mm", "wind_max"])
day = store.groupby("date").agg(rad=("radiation_kwh", "mean"), rain=("rain_mm", "max"), wind=("wind_max", "max"))
norm = day.groupby(day.index.month)["rad"].mean()
day["rad_ratio"] = day["rad"].to_numpy() / norm.reindex(day.index.month).to_numpy()

rain, wind, loss = [], [], []
for t in ev["closest_time"]:
    d = (t + UTC_PLUS).floor("D")
    w = day.loc[d - pd.Timedelta(days=1): d + pd.Timedelta(days=1)]
    if len(w) == 3:
        rain.append(w["rain"].max())
        wind.append(w["wind"].max())
        loss.append((1 - w["rad_ratio"].mean()) * 100)
    else:
        rain.append(np.nan); wind.append(np.nan); loss.append(np.nan)
ev["rain_max_mm"], ev["wind_max_kmh"], ev["solar_loss_pct"] = rain, wind, loss
ev = ev.sort_values("closest_time").reset_index(drop=True)

# 5. Track points for the map
tracks = raw[raw["SID"].isin(ev["SID"]) & (raw["dist_km"] <= MAP_KM)][["SID", "time", "LAT", "LON", "wind_kt", "dist_km"]]
tracks = tracks.sort_values(["SID", "time"]).round({"LAT": 2, "LON": 2, "dist_km": 0})

OUT.mkdir(parents=True, exist_ok=True)
SUMMARY.parent.mkdir(parents=True, exist_ok=True)
ev.to_parquet(OUT / "cyclone_events.parquet", index=False)
tracks.to_parquet(OUT / "cyclone_tracks.parquet", index=False)
seasons.to_parquet(OUT / "cyclone_seasons.parquet", index=False)

# 6. Summary for the report
print(f"\nSeasons {seasons['season'].iloc[0]} to {seasons['season'].iloc[-1]}: {len(seasons)} complete seasons")
for k in (100, 200, 300):
    n = seasons[f"n_{k}"]
    print(f"Storms with closest approach within {k} km: {int(n.sum())} "
          f"({n.mean():.2f} per season, {(n > 0).mean():.0%} of seasons have at least one)")
print("Closest approaches by calendar month (within 300 km):")
print(ev["closest_time"].dt.month.value_counts().reindex(range(1, 13), fill_value=0).to_string())

rows = []
for k in (100, 200, 300):
    e = ev[(ev["min_dist_km"] <= k) & ev["rain_max_mm"].notna()]
    rows.append({"within_km": k, "storms_with_weather": len(e), "median_rain_max_mm": e["rain_max_mm"].median(),
                 "median_wind_max_kmh": e["wind_max_kmh"].median(), "median_solar_loss_pct": e["solar_loss_pct"].median()})
summary = pd.DataFrame(rows).round(1)
summary.to_csv(SUMMARY, index=False)
print("\nLocal weather in the 3-day window around closest approach (2006 onward):")
print(summary.to_string(index=False))
print("All days for comparison: median daily max rain %.1f mm, 99th percentile %.1f mm; "
      "median daily max wind %.1f km/h, 99th percentile %.1f km/h" % (
          day["rain"].median(), day["rain"].quantile(0.99), day["wind"].median(), day["wind"].quantile(0.99)))
print("\nSaved events:", len(ev), "| track points:", len(tracks))
