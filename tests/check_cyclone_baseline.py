"""Do storm windows differ from ordinary 3-day windows in the same season (November to April)?"""
import pandas as pd

ev = pd.read_parquet("app/data/cyclone_events.parquet")
store = pd.read_parquet("data/store/daily.parquet",
                        columns=["date", "site", "radiation_kwh", "rain_mm", "wind_max"])
day = store.groupby("date").agg(rad=("radiation_kwh", "mean"),
                                rain=("rain_mm", "max"), wind=("wind_max", "max"))
norm = day.groupby(day.index.month)["rad"].mean()
day["ratio"] = day["rad"].to_numpy() / norm.reindex(day.index.month).to_numpy()

w = pd.DataFrame({
    "rain": day["rain"].rolling(3, center=True).max(),
    "wind": day["wind"].rolling(3, center=True).max(),
    "loss": (1 - day["ratio"].rolling(3, center=True).mean()) * 100,
}).dropna()
w = w[w.index.month.isin([11, 12, 1, 2, 3, 4])]

print(f"Ordinary 3-day windows, November to April (n={len(w)}):")
print(w.describe(percentiles=[0.5, 0.9, 0.99]).round(1))

for k in (100, 200, 300):
    e = ev[(ev["min_dist_km"] <= k) & ev["rain_max_mm"].notna()]
    print(
        f"\nStorms within {k} km (n={len(e)}); share of ordinary windows below the storm median:")
    for name, col in (("rain", "rain_max_mm"), ("wind", "wind_max_kmh"), ("solar loss", "solar_loss_pct")):
        med = e[col].median()
        key = {"rain": "rain", "wind": "wind", "solar loss": "loss"}[name]
        print(
            f"  {name}: storm median {med:.1f}, higher than {(w[key] < med).mean():.0%} of ordinary windows")
