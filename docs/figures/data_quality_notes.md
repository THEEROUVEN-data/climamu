# Data quality notes

Project: ClimaMU | Date: [20.10..2026]

## Test 1: NASA POWER vs Open-Meteo, Port Louis, 2019 to 2023 (hourly)

- 43,824 rows in each source, no missing values.
- The two sources label hours differently. Correlation of radiation was highest when Open-Meteo was shifted by one hour (0.981, against 0.932 unshifted). After the shift, radiation MAE fell from 71.1 to 27.8 W/m2.
- Wind speed units differ (NASA POWER in m/s, Open-Meteo in km/h). After conversion, wind MAE was 1.16 m/s.
- Temperature MAE was 1.57 C, a steady offset of about 0.75 C (NASA POWER warmer).
- Mean daily radiation: NASA POWER 5.61 kWh/m2/day, Open-Meteo 5.52 kWh/m2/day.
- Times in the raw data are UTC. Mauritius is UTC+4, so the pipeline must convert to local time.

## Test 2: Can the sources tell sites apart? (Port Louis, Curepipe, Mahebourg, 2019 to 2023, daily)

| Site | NASA POWER (kWh/m2/day) | Open-Meteo (kWh/m2/day) |
|---|---|---|
| Port Louis | 5.61 | 5.52 |
| Curepipe | 5.61 | 4.94 |
| Mahebourg | 5.61 | 5.14 |

NASA POWER returned identical values for all three sites (largest daily difference 0.0), so it cannot separate sites on Mauritius. Open-Meteo gives different values per site. Decision: Open-Meteo is the source for site-level data, and NASA POWER is used only as an island-level cross-check.

## Test 3: Duplicate grid cells across 15 candidate sites (2024, hourly radiation)

Total stored: 2,629,800 hourly rows (15 sites, 2006 to 2025).

Three pairs had identical data (MAE 0.00, correlation 1.0000):

- Tamarin and Chamarel
- Le Morne and Bel Ombre
- Trou d'Eau Douce and Belle Mare

Decision: one site from each pair was excluded (Chamarel, Bel Ombre, Trou d'Eau Douce), leaving 12 distinct sites (about 2.1 million hourly rows). The excluded data is kept in data/raw/_excluded. The duplicate check (MAE below 0.01) will run as a permanent pipeline step.

## Test 4: Processing results (12 sites, 2006 to 2025, hourly)

- 175,320 hourly rows per site (2,103,840 in total). No missing timestamps, no missing values, no out-of-range values at any site.
- Times converted from UTC to local time (UTC+4). Night radiation share is 0.0 at every site, so the conversion is correct.
- Radiation peaks in the hour labelled 13:00 at every site. This is consistent with Open-Meteo labelling each value with the end of its hour (to verify in its documentation).
- Daily table: 87,648 rows (12 sites x 7,304 full days). Partial first and last days were dropped.
- Mean daily radiation by site ranges from 5.31 (Curepipe) to 5.67 (Le Morne) kWh/m2/day, island average about 5.52.
- Duplicate grid-cell check passes: all 12 sites are distinct.

## Test 5: Island-level validation (12-site Open-Meteo mean vs NASA POWER, daily radiation, 2006 to 2025)

- 7,304 days compared. Correlation 0.916, mean bias +0.068 kWh/m2/day, MAE 0.437, RMSE 0.602.
- Monthly means agree within about 0.13 kWh/m2/day; both peak in December and are lowest in June.
- MAE is higher in 2017 to 2021 (0.52 to 0.56) than in other years (about 0.36 to 0.45). Cause not yet known.

## Test 6: Forecast experiment (history-only models, test period 2023 to 2025)

- Only day 1 shows skill against climatology (ridge +0.052, gradient boosting +0.041). From day 2 skill is zero or negative. Persistence is worse than climatology at every horizon.
- Decision: the main forecasting product is a probabilistic monthly outlook with PV yield, and short-range forecasts on the dashboard come from the Open-Meteo forecast API, labelled as third-party.

## Test 7: Probabilistic monthly outlook (trained 2006 to 2022, tested 2023 to 2025)

- Share of test days inside the P10 to P90 range: 0.815 (target 0.80). By month: 0.72 (July) to 0.85. May to July are below target; the sites share weather, so the effective sample is small.
- Pinball loss, monthly outlook vs one flat range: P10 0.195 vs 0.242, P50 0.313 vs 0.581, P90 0.112 vs 0.215.
- Open-Meteo documents hourly radiation as the mean of the preceding hour (forecast and satellite API pages; archive API assumed the same). A value stamped 13:00 covers 12:00 to 13:00.
- PV yield estimate assumes a flat surface and a fixed performance ratio of 0.8. Needs a comparison with a published yield figure.

## Test 8: Hourly profile (12 sites, local time, hour = start of the preceding-hour interval)

- Island average June and December hourly profiles sum to 3.79 and 7.10 kWh/m2/day, matching the daily means.
- Profile is symmetric around midday. Best 3-hour window is 11:00 to 14:00 (Jan to Sep) and 10:00 to 13:00 (Oct to Dec), holding 37% to 44% of daily energy. Windows in Oct to Dec are a near-tie.