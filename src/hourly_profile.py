"""Average hourly solar profile per site and month, and the best 3-hour window."""
from pathlib import Path

import pandas as pd

sites = pd.read_csv("src/sites.csv")
slug_to_name = {n.replace(" ", "_").replace("'", ""): n for n in sites["name"]}

frames = []
for p in sorted(Path("data/processed/hourly").glob("site=*/year=*/data.parquet")):
    site = slug_to_name[p.parent.parent.name.split("=", 1)[1]]
    d = pd.read_parquet(p, columns=["time", "shortwave_radiation"])
    d["site"] = site
    frames.append(d)
d = pd.concat(frames, ignore_index=True)

d["month"] = d["time"].dt.month
# value is the mean of the preceding hour
d["hour_start"] = (d["time"] - pd.Timedelta(hours=1)).dt.hour

prof = (d.groupby(["site", "month", "hour_start"])["shortwave_radiation"]
        .mean().rename("mean_wh_m2").reset_index())
prof.to_parquet("data/processed/hourly_profile.parquet", index=False)


def best_windows(pivot):
    # column h = sum of hours h-2, h-1, h
    roll = pivot.T.rolling(3).sum().T
    end = roll.idxmax(axis=1)
    return pd.DataFrame({
        "window": [f"{e - 2:02d}:00 to {e + 1:02d}:00" for e in end],
        "share_of_daily_energy": (roll.max(axis=1) / pivot.sum(axis=1)).round(3).values,
    }, index=pivot.index)


pivot = prof.pivot_table(
    index=["site", "month"], columns="hour_start", values="mean_wh_m2")
windows = best_windows(pivot).reset_index()
windows.to_parquet("data/processed/best_hours.parquet", index=False)

island = best_windows(pivot.groupby("month").mean())
print("Island average: best 3-hour window by month (local time)")
print(island)

print("\nIsland average hourly profile, June and December (Wh/m2 per hour):")
print(pivot.groupby("month").mean().loc[[6, 12]].T.round(0))
