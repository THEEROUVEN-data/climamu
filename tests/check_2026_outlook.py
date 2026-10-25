"""Out-of-sample check: do 2026 days fall inside the P10 to P90 range built from 2006 to 2025?"""
import pandas as pd

daily = pd.read_parquet("data/store/daily.parquet")
daily["month"] = daily["date"].dt.month
train = daily[daily["date"] < "2026-01-01"]
new = daily[daily["date"] >= "2026-01-01"].copy()

q = train.groupby(["site", "month"])[
    "radiation_kwh"].quantile([0.1, 0.5, 0.9]).unstack()
q.columns = ["p10", "p50", "p90"]
t = new.merge(q.reset_index(), on=["site", "month"])
inside = (t["radiation_kwh"] >= t["p10"]) & (t["radiation_kwh"] <= t["p90"])

print("Site-days in 2026:", len(t))
print("Share inside P10 to P90 (target 0.80):", round(inside.mean(), 3))
print(inside.groupby(t["month"]).mean().round(2))

print("\nMean daily radiation by month (kWh/m2/day):")
print(pd.DataFrame({
    "2026": new.groupby("month")["radiation_kwh"].mean(),
    "2006-2025": train.groupby("month")["radiation_kwh"].mean(),
}).round(2))
