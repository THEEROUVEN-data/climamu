"""Incremental data refresh for ClimaMU.

Fetches new days from Open-Meteo, updates the daily store, rebuilds the monthly outlook
and writes the status files used by the dashboard. If the new data fails its checks,
the script exits with an error and nothing is written.
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

STORE = Path("data/store/daily.parquet")
APP_DATA = Path("app/data")
URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY = ("shortwave_radiation,direct_radiation,diffuse_radiation,temperature_2m,"
          "relative_humidity_2m,cloud_cover,wind_speed_10m,precipitation")
UTC_OFFSET_HOURS = 4
OVERLAP_DAYS = 14
END_LAG_DAYS = 7
MIN_COMPLETE_SHARE = 0.95
PERF_RATIO = 0.80
LOW_DAY = 3.0

LIMITS = {
    "shortwave_radiation": (0, 1500), "direct_radiation": (0, 1500),
    "diffuse_radiation": (0, 1000), "temperature_2m": (-5, 45),
    "relative_humidity_2m": (0, 100), "cloud_cover": (0, 100),
    "wind_speed_10m": (0, 200), "precipitation": (0, 200),
}


def fetch_hourly(lat, lon, start, end):
    params = {"latitude": lat, "longitude": lon,
              "start_date": start.strftime("%Y-%m-%d"), "end_date": end.strftime("%Y-%m-%d"),
              "hourly": HOURLY, "timezone": "UTC"}
    for _ in range(6):
        r = requests.get(URL, params=params, timeout=120)
        if r.status_code == 200:
            df = pd.DataFrame(r.json()["hourly"])
            for col in LIMITS:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        if r.status_code == 429:
            print("  rate limited, waiting 5 minutes")
            time.sleep(300)
            continue
        sys.exit(f"Open-Meteo error {r.status_code}: {r.text[:200]}")
    sys.exit("Open-Meteo kept rate limiting the requests")


def hourly_to_daily(df):
    """Same logic as process_data.py: local time, daily sums and means, complete days only."""
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"]) + \
        pd.Timedelta(hours=UTC_OFFSET_HOURS)
    df["date"] = df["time"].dt.floor("D")
    df["ghi"] = df["shortwave_radiation"] / 1000
    df["direct"] = df["direct_radiation"] / 1000
    df["diffuse"] = df["diffuse_radiation"] / 1000
    df["ok"] = df[list(LIMITS)].notna().all(axis=1)
    daily = df.groupby("date").agg(
        radiation_kwh=("ghi", "sum"), direct_kwh=("direct", "sum"),
        diffuse_kwh=("diffuse", "sum"),
        temp_mean=("temperature_2m", "mean"), temp_min=("temperature_2m", "min"),
        temp_max=("temperature_2m", "max"),
        humidity_mean=("relative_humidity_2m", "mean"), cloud_mean=("cloud_cover", "mean"),
        wind_mean=("wind_speed_10m", "mean"), wind_max=("wind_speed_10m", "max"),
        rain_mm=("precipitation", "sum"),
        hours=("time", "size"), ok_hours=("ok", "sum"),
    ).reset_index()
    daily = daily[(daily["hours"] == 24) & (daily["ok_hours"] == 24)]
    return daily.drop(columns=["hours", "ok_hours"])


def build_outlook(daily):
    """Monthly P10, P50, P90 per site from all stored days (same method as outlook.py)."""
    d = daily.copy()
    d["month"] = d["date"].dt.month
    g = d.groupby(["site", "month"])["radiation_kwh"]
    out = g.quantile([0.1, 0.5, 0.9]).unstack()
    out.columns = ["p10", "p50", "p90"]
    out["mean"] = g.mean()
    out["low_day_share"] = g.apply(lambda s: (s < LOW_DAY).mean())
    out["yield_p50_kwh_per_kwp"] = out["p50"] * PERF_RATIO
    return out.reset_index()


def main():
    if not STORE.exists():
        sys.exit("data/store/daily.parquet is missing")
    store = pd.read_parquet(STORE)
    sites = pd.read_csv("src/sites.csv")
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    end_day = today - pd.Timedelta(days=END_LAG_DAYS)
    last_stored = store.groupby("site")["date"].max()

    frames, expected, out_of_range = [], 0, 0
    for _, s in sites.iterrows():
        if s["name"] not in last_stored.index:
            sys.exit(f"No stored data for {s['name']}")
        start = last_stored[s["name"]] - pd.Timedelta(days=OVERLAP_DAYS - 1)
        if end_day < start:
            continue
        raw = fetch_hourly(s["lat"], s["lon"], start -
                           pd.Timedelta(days=1), end_day)
        for col, (lo, hi) in LIMITS.items():
            out_of_range += int(((raw[col] < lo) | (raw[col] > hi)).sum())
        daily = hourly_to_daily(raw)
        daily = daily[(daily["date"] >= start) & (
            daily["date"] <= end_day)].copy()
        daily["site"] = s["name"]
        frames.append(daily)
        expected += (end_day - start).days + 1
        print(f"{s['name']}: {len(daily)} complete days fetched")
        time.sleep(2)

    if not frames:
        print("Nothing to refresh yet.")
        return
    new = pd.concat(frames, ignore_index=True)

    share = len(new) / expected
    print(
        f"Complete site-days: {share:.1%}, values out of range: {out_of_range}")
    if share < MIN_COMPLETE_SHARE:
        sys.exit(
            f"Only {share:.1%} of the expected site-days are complete; refresh aborted")
    if out_of_range > 0:
        sys.exit(
            f"{out_of_range} values are outside the plausible range; refresh aborted")
    if not 1 < new["radiation_kwh"].mean() < 9:
        sys.exit(
            "Mean daily radiation of the new data is implausible; refresh aborted")

    both = store.merge(new[["site", "date", "radiation_kwh"]], on=["site", "date"],
                       suffixes=("_old", "_new"))
    revision_mae = (float((both["radiation_kwh_old"] - both["radiation_kwh_new"]).abs().mean())
                    if len(both) else 0.0)

    keys = new[["site", "date"]].assign(_replace=1)
    merged = store.merge(keys, on=["site", "date"], how="left")
    kept = merged[merged["_replace"].isna()].drop(columns="_replace")
    updated = (pd.concat([kept, new], ignore_index=True)
               .sort_values(["site", "date"]).reset_index(drop=True))
    new_days = len(updated) - len(store)

    STORE.parent.mkdir(parents=True, exist_ok=True)
    APP_DATA.mkdir(parents=True, exist_ok=True)
    updated.to_parquet(STORE, index=False)
    build_outlook(updated).to_parquet(
        APP_DATA / "outlook.parquet", index=False)

    now = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M")
    status = {
        "exported_at": now + " UTC",
        "first_date": str(updated["date"].min().date()),
        "last_date": str(updated["date"].max().date()),
        "sites": int(updated["site"].nunique()),
        "daily_rows": len(updated),
    }
    (APP_DATA / "status.json").write_text(json.dumps(status, indent=2))

    row = pd.DataFrame([{
        "run_utc": now, "new_days": new_days, "replaced_days": len(new) - new_days,
        "revision_mae_kwh": round(revision_mae, 4), "complete_share": round(share, 4),
        "last_date": status["last_date"],
    }])
    log_path = APP_DATA / "refresh_log.csv"
    if log_path.exists():
        row = pd.concat([pd.read_csv(log_path), row], ignore_index=True)
    row.to_csv(log_path, index=False)
    print(
        f"Done. New site-days added: {new_days}, revision MAE: {revision_mae:.4f} kWh/m2/day")
    print("Status:", status)


if __name__ == "__main__":
    main()
