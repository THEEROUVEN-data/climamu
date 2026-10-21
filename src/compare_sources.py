"""Compare NASA POWER and Open-Meteo for the same site and period."""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")

nasa = pd.read_parquet("data/raw/nasa_portlouis_hourly.parquet")
om = pd.read_parquet("data/raw/openmeteo_portlouis_hourly.parquet")

om = om.shift(-1)
om["wind_speed_10m"] = om["wind_speed_10m"] / 3.6
both = nasa.join(om, how="inner")
print("Overlapping hours:", len(both))
print("Share missing:\n", both.isna().mean().round(4))

# Is there a time offset between the two radiation series?
for lag in (-1, 0, 1):
    pair = pd.concat([both["ALLSKY_SFC_SW_DWN"],
                      both["shortwave_radiation"].shift(lag)], axis=1).dropna()
    print(f"Radiation correlation at lag {lag}:", round(
        pair.corr().iloc[0, 1], 3))

rad = both[["ALLSKY_SFC_SW_DWN", "shortwave_radiation"]].dropna()
diff = rad["ALLSKY_SFC_SW_DWN"] - rad["shortwave_radiation"]
print("Radiation mean bias (NASA minus Open-Meteo):", round(diff.mean(), 1))
print("Radiation MAE:", round(diff.abs().mean(), 1))

temp = both[["T2M", "temperature_2m"]].dropna()
print("Temperature MAE (deg C):", round(
    (temp["T2M"] - temp["temperature_2m"]).abs().mean(), 2))

daily = rad.resample("D").sum() / 1000
print("Mean daily radiation (kWh/m2/day):")
print(daily.mean().round(2))

week = both.loc["2023-03-01":"2023-03-07"]
ax = week[["ALLSKY_SFC_SW_DWN", "shortwave_radiation"]].plot(figsize=(10, 4))
ax.set_ylabel("Radiation (see units printed earlier)")
ax.set_title("NASA POWER vs Open-Meteo, one week")
plt.tight_layout()
plt.savefig("docs/figures/data_test_comparison.png", dpi=150)
print("Saved figure to docs/figures/data_test_comparison.png")
wind = both[["WS10M", "wind_speed_10m"]].dropna()
print("Wind MAE (m/s):",
      round((wind["WS10M"] - wind["wind_speed_10m"]).abs().mean(), 2))
