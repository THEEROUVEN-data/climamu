"""Look up site coordinates with the Open-Meteo geocoding API and write sites.csv."""
import csv
import math

import requests


SITES = {
    "Grand Baie": "North",
    "Grand Gaube": "North",
    "Port Louis": "North-West",
    "Flic en Flac": "West",
    "Tamarin": "West",
    "Le Morne": "South-West",
    "Chamarel": "South-West",
    "Souillac": "South",
    "Bel Ombre": "South",
    "Mahebourg": "South-East",
    "Trou d'Eau Douce": "East",
    "Belle Mare": "East",
    "Centre de Flacq": "East",
    "Curepipe": "Central",
    "Vacoas": "Central",
}
URL = "https://geocoding-api.open-meteo.com/v1/search"


def km(a, b):
    """Distance in km between two (lat, lon) points."""
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = p2 - p1
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * \
        math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


rows = []
for name, region in SITES.items():
    r = requests.get(URL, params={"name": name, "count": 10,
                                  "language": "en", "format": "json"}, timeout=60)
    r.raise_for_status()
    hits = [h for h in r.json().get("results", [])
            if h.get("country_code") == "MU"]
    if not hits:
        print("NOT FOUND:", name)
        continue
    h = hits[0]
    rows.append({"name": name, "region": region,
                 "lat": round(h["latitude"], 3), "lon": round(h["longitude"], 3)})
    print(
        f"{name:18} {h['latitude']:8.3f} {h['longitude']:8.3f}   {h.get('admin1', '')}")

with open("src/sites.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["name", "region", "lat", "lon"])
    w.writeheader()
    w.writerows(rows)
print(f"\nWrote {len(rows)} sites to src/sites.csv")

print("\nPairs closer than 5 km (they may share a grid cell):")
for i in range(len(rows)):
    for j in range(i + 1, len(rows)):
        d = km((rows[i]["lat"], rows[i]["lon"]),
               (rows[j]["lat"], rows[j]["lon"]))
        if d < 5:
            print(f"  {rows[i]['name']} and {rows[j]['name']}: {d:.1f} km")
