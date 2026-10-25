"""Is 2026 really sunnier, or has the newest Open-Meteo data shifted? Compare with NASA POWER."""
import pandas as pd
import requests

daily = pd.read_parquet("data/store/daily.parquet")
island = daily.groupby("date")["radiation_kwh"].mean()


js = island[island.index.month <= 9]
by_year = js.groupby(js.index.year).mean().round(3)
print("Mean daily radiation, January to September, highest years (kWh/m2/day):")
print(by_year.sort_values(ascending=False).head(8))
print("Rank of 2026:", int(by_year.rank(
    ascending=False)[2026]), "of", len(by_year))


sites = pd.read_csv("src/sites.csv")
lat, lon = sites.loc[sites["name"] == "Port Louis", ["lat", "lon"]].iloc[0]
r = requests.get("https://power.larc.nasa.gov/api/temporal/daily/point", params={
    "start": "20260101", "end": "20261014", "latitude": lat, "longitude": lon,
    "community": "re", "parameters": "ALLSKY_SFC_SW_DWN", "format": "json"}, timeout=180)
r.raise_for_status()
n26 = pd.Series(r.json()["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"])
n26.index = pd.to_datetime(n26.index, format="%Y%m%d")
n26 = n26.mask(n26 == -999).dropna()
hist = pd.read_parquet("data/raw/nasa_daily_island.parquet")["nasa"]

om26, om_hist = island.loc["2026"], island.loc[:"2025"]
tab = pd.DataFrame({
    "OM 2026": om26.groupby(om26.index.month).mean(),
    "OM 2006-25": om_hist.groupby(om_hist.index.month).mean(),
    "NASA 2026": n26.groupby(n26.index.month).mean(),
    "NASA 2006-25": hist.groupby(hist.index.month).mean(),
}).loc[1:9]
tab["OM diff"] = tab["OM 2026"] - tab["OM 2006-25"]
tab["NASA diff"] = tab["NASA 2026"] - tab["NASA 2006-25"]
print("\nMonthly means and differences (kWh/m2/day):")
print(tab.round(2))


both = pd.concat([om26, n26], axis=1, join="inner").dropna()
both.columns = ["om", "nasa"]
d = both["nasa"] - both["om"]
print("\n2026 days compared:", len(both))
print("Mean bias NASA minus Open-Meteo:",
      round(d.mean(), 3), "(2006-2025 was +0.068)")
print("MAE:", round(d.abs().mean(), 3), "(2006-2025 was 0.437)")
