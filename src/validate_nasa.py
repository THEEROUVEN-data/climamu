"""Island-level validation: mean of 12 Open-Meteo sites vs NASA POWER (daily radiation)."""
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")

daily = pd.read_parquet("data/processed/daily.parquet")
island = daily.groupby("date")["radiation_kwh"].mean().rename("open_meteo")

sites = pd.read_csv("src/sites.csv")
lat, lon = sites.loc[sites["name"] == "Port Louis", ["lat", "lon"]].iloc[0]


parts = []
for start, end in [(2006, 2010), (2011, 2015), (2016, 2020), (2021, 2025)]:
    r = requests.get("https://power.larc.nasa.gov/api/temporal/daily/point", params={
        "start": f"{start}0101", "end": f"{end}1231",
        "latitude": lat, "longitude": lon, "community": "re",
        "parameters": "ALLSKY_SFC_SW_DWN", "format": "json",
    }, timeout=180)
    r.raise_for_status()
    s = pd.Series(r.json()["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"])
    parts.append(s)
nasa = pd.concat(parts)
nasa.index = pd.to_datetime(nasa.index, format="%Y%m%d")
nasa = nasa.mask(nasa == -999).rename("nasa")
nasa.to_frame().to_parquet("data/raw/nasa_daily_island.parquet")

both = pd.concat([island, nasa], axis=1, join="inner").dropna()
diff = both["nasa"] - both["open_meteo"]
print("Days compared:", len(both))
print("Correlation:", round(both.corr().iloc[0, 1], 3))
print("Mean bias (NASA minus Open-Meteo), kWh/m2/day:", round(diff.mean(), 3))
print("MAE:", round(diff.abs().mean(), 3))
print("RMSE:", round(float(np.sqrt((diff ** 2).mean())), 3))

print("\nMAE by year:")
print(diff.abs().groupby(both.index.year).mean().round(3))

monthly = both.groupby(both.index.month).mean().round(2)
print("\nMean daily radiation by month (kWh/m2/day):")
print(monthly)
monthly.to_csv("docs/validation_nasa_monthly.csv")

fig, ax = plt.subplots(1, 2, figsize=(12, 4))
ax[0].scatter(both["open_meteo"], both["nasa"], s=2, alpha=0.3)
ax[0].plot([0, 9], [0, 9], color="black", lw=1)
ax[0].set_xlabel("Open-Meteo, mean of 12 sites (kWh/m2/day)")
ax[0].set_ylabel("NASA POWER (kWh/m2/day)")
ax[0].set_title("Daily radiation, 2006 to 2025")
monthly.plot(ax=ax[1], marker="o")
ax[1].set_xlabel("Month")
ax[1].set_ylabel("kWh/m2/day")
ax[1].set_title("Seasonal cycle")
plt.tight_layout()
plt.savefig("docs/figures/validation_nasa.png", dpi=150)
print("\nSaved figure to docs/figures/validation_nasa.png")
