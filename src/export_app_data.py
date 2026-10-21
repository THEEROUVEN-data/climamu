"""Copy the small result files the dashboard reads into app/data."""
import json
import shutil
from pathlib import Path

import pandas as pd

OUT = Path("app/data")
OUT.mkdir(parents=True, exist_ok=True)

for f in ["outlook.parquet", "hourly_profile.parquet", "best_hours.parquet"]:
    shutil.copy(f"data/processed/{f}", OUT / f)
shutil.copy("src/sites.csv", OUT / "sites.csv")
shutil.copy("docs/quality_report.csv", OUT / "quality_report.csv")
shutil.copy("docs/forecast_results.csv", OUT / "forecast_results.csv")

daily = pd.read_parquet("data/processed/daily.parquet",
                        columns=["date", "site"])
status = {
    "exported_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    "first_date": str(daily["date"].min().date()),
    "last_date": str(daily["date"].max().date()),
    "sites": int(daily["site"].nunique()),
    "daily_rows": len(daily),
}
(OUT / "status.json").write_text(json.dumps(status, indent=2))
print("Exported to", OUT, status)
