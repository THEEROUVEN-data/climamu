"""Probabilistic solar outlook by site and month, validated on 2023 to 2025."""
import numpy as np
import pandas as pd

TRAIN_END = pd.Timestamp("2022-12-31")
# assumed system performance ratio (inverter, wiring, temperature, dust)
PERF_RATIO = 0.80
LOW_DAY = 3.0         # kWh/m2/day below which a day counts as low-yield

daily = pd.read_parquet("data/processed/daily.parquet")
daily["month"] = daily["date"].dt.month
train = daily[daily["date"] <= TRAIN_END]
test = daily[daily["date"] > TRAIN_END]

# 1. Monthly outlook per site, from training years only
g = train.groupby(["site", "month"])["radiation_kwh"]
outlook = g.quantile([0.1, 0.5, 0.9]).unstack()
outlook.columns = ["p10", "p50", "p90"]
outlook["mean"] = g.mean()
outlook["low_day_share"] = g.apply(lambda s: (s < LOW_DAY).mean())
outlook["yield_p50_kwh_per_kwp"] = outlook["p50"] * PERF_RATIO
outlook = outlook.reset_index()
outlook.to_parquet("data/processed/outlook.parquet", index=False)

print("Island average outlook by month (kWh/m2/day):")
print(outlook.groupby("month")[["p10", "p50", "p90", "mean", "low_day_share",
                                "yield_p50_kwh_per_kwp"]].mean().round(2))

# 2. Validation on the test years
t = test.merge(outlook[["site", "month", "p10", "p50", "p90"]], on=[
               "site", "month"])
y = t["radiation_kwh"]
inside = (y >= t["p10"]) & (y <= t["p90"])
print("\nShare of test days inside the P10 to P90 range (target 0.80):",
      round(inside.mean(), 3))
print(inside.groupby(t["month"]).mean().round(2))


def pinball(actual, pred, q):
    d = actual - pred
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))


# same range for every day of the year
flat = train["radiation_kwh"].quantile([0.1, 0.5, 0.9])
print("\nPinball loss, monthly outlook vs one flat range (lower is better):")
for name, col, q in (("P10", "p10", 0.1), ("P50", "p50", 0.5), ("P90", "p90", 0.9)):
    print(name, round(pinball(y, t[col], q), 3),
          "vs", round(pinball(y, flat[q], q), 3))
