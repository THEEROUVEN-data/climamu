"""ClimaMU cyclone page: how often and how close tropical cyclones pass Mauritius."""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Cyclone risk | ClimaMU", page_icon="🌀", layout="wide")

DATA = Path(__file__).parent.parent / "data"
CENTER = (-20.25, 57.55)
ORANGE, DARK = "#E8590C", "#1F2933"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@st.cache_data
def load():
    return (pd.read_parquet(DATA / "cyclone_events.parquet"),
            pd.read_parquet(DATA / "cyclone_tracks.parquet"),
            pd.read_parquet(DATA / "cyclone_seasons.parquet"))


def circle(km, n=120):
    b = np.linspace(0, 2 * np.pi, n)
    lat0, lon0, d = np.radians(CENTER[0]), np.radians(CENTER[1]), km / 6371
    lat = np.arcsin(np.sin(lat0) * np.cos(d) + np.cos(lat0) * np.sin(d) * np.cos(b))
    lon = lon0 + np.arctan2(np.sin(b) * np.sin(d) * np.cos(lat0), np.cos(d) - np.sin(lat0) * np.sin(lat))
    return np.degrees(lat), np.degrees(lon)


events, tracks, seasons = load()

st.sidebar.title("Cyclone risk")
dist = st.sidebar.selectbox("Closest approach within", [100, 200, 300], index=2, format_func=lambda k: f"{k} km")
first, last = int(seasons["season_start"].min()), int(seasons["season_start"].max())
years = st.sidebar.slider("Seasons (start year)", first, last, (first, last))

ev = events[(events["min_dist_km"] <= dist) & events["season_start"].between(*years)].copy()
ev["label"] = ev["NAME"].str.title() + " (" + ev["season"] + "), closest " + ev["min_dist_km"].round().astype(int).astype(str) + " km"
ss = seasons[seasons["season_start"].between(*years)]
col = f"n_{dist}"

st.title("Cyclone risk")
st.caption(f"Tropical storms in the South Indian Ocean that came within {dist} km of Mauritius, "
           f"seasons {ss['season'].iloc[0]} to {ss['season'].iloc[-1]} (a season runs July to June).")

c = st.columns(4)
c[0].metric("Storms", int(ss[col].sum()))
c[1].metric("Per season", f"{ss[col].mean():.2f}")
c[2].metric("Seasons with at least one", f"{(ss[col] > 0).mean():.0%}")
if len(ev):
    closest = ev.loc[ev["min_dist_km"].idxmin()]
    c[3].metric("Closest approach", f"{closest['min_dist_km']:.0f} km", help=f"{closest['NAME'].title()} ({closest['season']})")
else:
    c[3].metric("Closest approach", "none")

tab1, tab2, tab3 = st.tabs(["Storm tracks", "Seasons and months", "Local weather impact"])

with tab1:
    tr = tracks[tracks["SID"].isin(ev["SID"])].merge(ev[["SID", "label"]], on="SID")
    if tr.empty:
        st.info("No storms match these settings.")
    else:
        fig = px.line_map(tr.sort_values(["SID", "time"]), lat="LAT", lon="LON", line_group="SID",
                          hover_name="label", hover_data={"SID": False, "LAT": False, "LON": False, "wind_kt": True},
                          color_discrete_sequence=[ORANGE], zoom=4.2, height=560,
                          center=dict(lat=CENTER[0], lon=CENTER[1]), map_style="open-street-map")
        clat, clon = circle(dist)
        fig.add_trace(go.Scattermap(lat=clat, lon=clon, mode="lines", line=dict(color=DARK, width=2),
                                    name=f"{dist} km", hoverinfo="skip"))
        fig.add_trace(go.Scattermap(lat=[CENTER[0]], lon=[CENTER[1]], mode="markers",
                                    marker=dict(size=12, color=DARK), name="Mauritius", hoverinfo="name"))
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), showlegend=False)
        st.plotly_chart(fig)
        st.caption("Each orange line is one storm. Hover over a line to see its name, season and wind (knots).")

with tab2:
    left, right = st.columns(2)
    left.plotly_chart(px.bar(ss, x="season", y=col, color_discrete_sequence=[ORANGE],
                             labels={"season": "Season", col: "Storms"}, title="Storms per season"))
    m = ev["closest_time"].dt.month.value_counts().reindex(range(1, 13), fill_value=0)
    right.plotly_chart(px.bar(x=MONTHS, y=m.to_numpy(), color_discrete_sequence=[ORANGE],
                              labels={"x": "Month of closest approach", "y": "Storms"}, title="When they come"))
    st.caption("These are historical frequencies, not a forecast. A season in progress is left out.")

with tab3:
    ei = ev.dropna(subset=["rain_max_mm"]).copy()
    if ei.empty:
        st.info("No storms in the weather record (2006 onward) match these settings.")
    else:
        ei["date"] = (ei["closest_time"] + pd.Timedelta(hours=4)).dt.date
        st.plotly_chart(px.scatter(ei, x="min_dist_km", y="solar_loss_pct", hover_name="label",
                                   hover_data={"rain_max_mm": ":.0f", "wind_max_kmh": ":.0f", "min_dist_km": ":.0f", "solar_loss_pct": ":.0f"},
                                   color_discrete_sequence=[ORANGE],
                                   labels={"min_dist_km": "Closest approach (km)", "solar_loss_pct": "Solar energy below normal (%)"},
                                   title="Solar energy lost around each storm"))
        show = ei[["NAME", "season", "date", "min_dist_km", "wind_near_kt", "rain_max_mm", "wind_max_kmh", "solar_loss_pct"]].copy()
        show.columns = ["Storm", "Season", "Date (local)", "Closest (km)", "Wind near (kt)", "Max rain (mm/day)", "Max wind (km/h)", "Solar loss (%)"]
        st.dataframe(show.sort_values("Date (local)", ascending=False).round(1), hide_index=True)
    st.caption("Local values use model data for the 12 sites, over the day of closest approach and the days either side. "
               "Solar loss compares the island mean radiation with the long-run mean for the same months. "
               "These are modelled values, not measured damage.")

st.caption("Cyclone tracks: NOAA IBTrACS v04r01 (doi:10.25921/82ty-9e16). Weather data by Open-Meteo.com.")
