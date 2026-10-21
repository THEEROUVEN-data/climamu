"""Forecast daily solar radiation 1 to 7 days ahead and compare models with baselines."""
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")

HORIZONS = range(1, 8)
TRAIN_END = pd.Timestamp("2022-12-31")

daily = (pd.read_parquet("data/processed/daily.parquet")
         .sort_values(["site", "date"]).reset_index(drop=True))
daily["doy"] = daily["date"].dt.dayofyear.clip(upper=365)


clim = (daily[daily["date"] <= TRAIN_END]
        .groupby(["doy", "site"])["radiation_kwh"].mean().unstack("site"))
padded = pd.concat([clim.iloc[-7:], clim, clim.iloc[:7]])
clim = padded.rolling(15, center=True).mean().iloc[7:-7]
clim_long = clim.stack().rename("clim_target").reset_index()
clim_long.columns = ["target_doy", "site", "clim_target"]


g = daily.groupby("site")["radiation_kwh"]
feat = daily[["site", "date", "radiation_kwh", "temp_mean", "humidity_mean",
              "cloud_mean", "wind_mean", "rain_mm"]].copy()
for k in range(1, 7):
    feat[f"rad_lag{k}"] = g.shift(k)
feat["rad_mean7"] = g.transform(lambda s: s.rolling(7).mean())
feat["rad_mean30"] = g.transform(lambda s: s.rolling(30).mean())
site_cols = pd.get_dummies(feat["site"]).astype(float)
feat = pd.concat([feat, site_cols], axis=1)

base_cols = ["radiation_kwh", "temp_mean", "humidity_mean", "cloud_mean", "wind_mean",
             "rain_mm", "rad_mean7", "rad_mean30"] + [f"rad_lag{k}" for k in range(1, 7)]
feature_cols = base_cols + ["clim_target",
                            "sin_doy", "cos_doy"] + list(site_cols.columns)

results = []
for h in HORIZONS:
    d = feat.copy()
    d["target"] = g.shift(-h)
    d["target_date"] = d["date"] + pd.Timedelta(days=h)
    d["target_doy"] = d["target_date"].dt.dayofyear.clip(upper=365)
    d = d.merge(clim_long, on=["target_doy", "site"], how="left")
    d["sin_doy"] = np.sin(2 * np.pi * d["target_doy"] / 365)
    d["cos_doy"] = np.cos(2 * np.pi * d["target_doy"] / 365)
    d = d.dropna(subset=feature_cols + ["target"])

    train = d[d["target_date"] <= TRAIN_END]
    test = d[d["date"] > TRAIN_END]

    preds = {
        "Persistence": test["radiation_kwh"].values,
        "Climatology": test["clim_target"].values,
    }
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    ridge.fit(train[feature_cols], train["target"])
    preds["Ridge"] = ridge.predict(test[feature_cols])

    gbm = HistGradientBoostingRegressor(
        max_iter=300, learning_rate=0.05, random_state=0)
    gbm.fit(train[feature_cols], train["target"])
    preds["Gradient boosting"] = gbm.predict(test[feature_cols])

    for name, p in preds.items():
        results.append({
            "horizon_days": h, "model": name,
            "MAE": mean_absolute_error(test["target"], p),
            "RMSE": float(np.sqrt(mean_squared_error(test["target"], p))),
        })
    print(f"Horizon {h}: train rows {len(train)}, test rows {len(test)}")

res = pd.DataFrame(results)
mae = res.pivot(index="horizon_days", columns="model", values="MAE")[
    ["Persistence", "Climatology", "Ridge", "Gradient boosting"]]
rmse = res.pivot(index="horizon_days", columns="model",
                 values="RMSE")[mae.columns]
# skill score against climatology, based on MAE
skill = 1 - mae.div(mae["Climatology"], axis=0)

print("\nMAE (kWh/m2/day), lower is better:")
print(mae.round(3))
print("\nRMSE (kWh/m2/day):")
print(rmse.round(3))
print("\nSkill vs climatology (1 = perfect, 0 = same as climatology, negative = worse):")
print(skill.round(3))

res.to_csv("docs/forecast_results.csv", index=False)
mae.plot(marker="o", figsize=(8, 4))
plt.ylabel("MAE (kWh/m2/day)")
plt.xlabel("Forecast horizon (days)")
plt.title("Daily radiation forecast error, test period 2023 to 2025")
plt.tight_layout()
plt.savefig("docs/figures/forecast_mae_by_horizon.png", dpi=150)
print("\nSaved docs/forecast_results.csv and docs/figures/forecast_mae_by_horizon.png")
