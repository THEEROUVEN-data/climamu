"""Process raw Open-Meteo hourly data: local time, quality checks, daily summaries."""
from pathlib import Path

import pandas as pd

RAW = Path("data/raw/openmeteo")
HOURLY_OUT = Path("data/processed/hourly")
DAILY_OUT = Path("data/processed/daily.parquet")
REPORT_OUT = Path("docs/quality_report.csv")
UTC_OFFSET_HOURS = 4

LIMITS = {
    "shortwave_radiation": (0, 1500),
    "direct_radiation": (0, 1500),
    "diffuse_radiation": (0, 1000),
    "temperature_2m": (-5, 45),
    "relative_humidity_2m": (0, 100),
    "cloud_cover": (0, 100),
    "wind_speed_10m": (0, 200),
    "precipitation": (0, 200),
}

sites = pd.read_csv("src/sites.csv")


def slug(name):
    return name.replace(" ", "_").replace("'", "")


quality, daily_frames, radiation_2024 = [], [], {}

for name in sites["name"]:
    files = sorted((RAW / f"site={slug(name)}").glob("year=*/data.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)

    # 1. Convert from UTC to Mauritius local time
    df["time"] = df["time"] + pd.Timedelta(hours=UTC_OFFSET_HOURS)

    # 2. Quality checks
    expected = pd.date_range(df["time"].min(), df["time"].max(), freq="h")
    night = df["time"].dt.hour.isin([22, 23, 0, 1, 2, 3])
    by_hour = df.groupby(df["time"].dt.hour)["shortwave_radiation"].mean()
    out_of_range = sum(int(((df[c] < lo) | (df[c] > hi)).sum())
                       for c, (lo, hi) in LIMITS.items())
    quality.append({
        "site": name,
        "rows": len(df),
        "missing_timestamps": len(expected) - len(df),
        "missing_values": int(df[list(LIMITS)].isna().sum().sum()),
        "out_of_range": out_of_range,
        "night_radiation_share": round(float((df.loc[night, "shortwave_radiation"] > 0).mean()), 4),
        "peak_radiation_hour": int(by_hour.idxmax()),
    })

    radiation_2024[name] = df.loc[df["time"].dt.year == 2024].set_index("time")[
        "shortwave_radiation"]

    # 3. Save the cleaned hourly data, partitioned by site and local year
    df["year"] = df["time"].dt.year
    for year, g in df.groupby("year"):
        path = HOURLY_OUT / \
            f"site={slug(name)}" / f"year={year}" / "data.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        g.drop(columns="year").to_parquet(path, index=False)

    df["date"] = df["time"].dt.floor("D")
    df["ghi"] = df["shortwave_radiation"] / 1000
    df["direct"] = df["direct_radiation"] / 1000
    df["diffuse"] = df["diffuse_radiation"] / 1000
    daily = df.groupby("date").agg(
        radiation_kwh=("ghi", "sum"),
        direct_kwh=("direct", "sum"),
        diffuse_kwh=("diffuse", "sum"),
        temp_mean=("temperature_2m", "mean"),
        temp_min=("temperature_2m", "min"),
        temp_max=("temperature_2m", "max"),
        humidity_mean=("relative_humidity_2m", "mean"),
        cloud_mean=("cloud_cover", "mean"),
        wind_mean=("wind_speed_10m", "mean"),
        wind_max=("wind_speed_10m", "max"),
        rain_mm=("precipitation", "sum"),
        hours=("time", "size"),
    ).reset_index()
    daily = daily[daily["hours"] == 24].drop(columns="hours")
    daily["site"] = name
    daily_frames.append(daily)
    print("Processed", name, len(df), "hourly rows")


all_daily = pd.concat(daily_frames, ignore_index=True)
all_daily.to_parquet(DAILY_OUT, index=False)
report = pd.DataFrame(quality)
report.to_csv(REPORT_OUT, index=False)

print("\nQuality report:")
print(report.to_string(index=False))
print("\nDaily table:", all_daily.shape)
print("\nMean daily radiation per site (kWh/m2/day):")
print(all_daily.groupby("site")["radiation_kwh"].mean().round(2).sort_values())


names = list(radiation_2024)
print("\nDuplicate grid-cell check (2024 hourly radiation):")
found = False
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        mae = (radiation_2024[names[i]] -
               radiation_2024[names[j]]).abs().mean()
        if mae < 0.01:
            print(f"  IDENTICAL: {names[i]} and {names[j]}")
            found = True
if not found:
    print("  none found, all sites are distinct")
