"""Download the NOAA IBTrACS South Indian basin file (version v04r01).

Citation to use in the report: NOAA's International Best Track Archive for Climate
Stewardship (IBTrACS) data, doi:10.25921/82ty-9e16, accessed on the date printed below.
"""
from datetime import date
from pathlib import Path

import requests

URL = ("https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-"
       "ibtracs/v04r01/access/csv/ibtracs.SI.list.v04r01.csv")
OUT = Path("data/raw/ibtracs_SI.csv")
OUT.parent.mkdir(parents=True, exist_ok=True)

r = requests.get(URL, stream=True, timeout=(15, 300))
if r.status_code != 200:
    raise SystemExit(
        f"Download failed (HTTP {r.status_code}). Open the IBTrACS csv folder in a browser, "
        "find the South Indian file (ibtracs.SI.list...csv) and fix the URL in this script.")

with open(OUT, "wb") as f:
    for chunk in r.iter_content(1 << 20):
        f.write(chunk)

print("Saved", OUT, round(OUT.stat().st_size / 1e6, 1), "MB")
print("Accessed on:", date.today().isoformat())
