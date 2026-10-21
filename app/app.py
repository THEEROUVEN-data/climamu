"""ClimaMU public dashboard (read-only): monthly outlook, daily sun profile and site map."""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="ClimaMU", page_icon="☀️", layout="wide")

DATA = Path(__file__).parent / "data"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
ORANGE, LIGHT = "#E8590C", "#F4B183"


@st.cache_data
def load_data():
    return (pd.read_parquet(DATA / "outlook.parquet"),
            pd.read_parquet(DATA / "hourly_profile.parquet"),
            pd.read_parquet(DATA / "best_hours.parquet"),
            pd.read_csv(DATA / "sites.csv"))


outlook, profile, best, sites = load_data()
names = sites["name"].tolist()

# Sidebar controls
st.sidebar.title("ClimaMU")
st.sidebar.caption("Solar energy outlook for Mauritius")
site = st.sidebar.selectbox("Site", names, index=names.index("Port Louis"))
month_name = st.sidebar.selectbox(
    "Month", MONTHS, index=pd.Timestamp.now().month - 1)
kwp = st.sidebar.number_input("System size (kWp)", min_value=0.5, max_value=100.0,
                              value=3.0, step=0.5)
pr = st.sidebar.slider("Performance ratio", 0.60, 0.90, 0.80, 0.01,
                       help="Share of the ideal output a real system delivers "
                            "(heat, dust, wiring and inverter losses). 0.80 is an assumption.")
month = MONTHS.index(month_name) + 1
region = sites.loc[sites["name"] == site, "region"].iloc[0]

row = outlook[(outlook["site"] == site) & (outlook["month"] == month)].iloc[0]
win = best[(best["site"] == site) & (best["month"] == month)].iloc[0]

st.title("Solar outlook for Mauritius")
st.caption(f"{site} ({region}) | {month_name} | based on 2006 to 2022 history")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Typical day", f"{row['p50']:.2f} kWh/m²",
          help="Median daily solar radiation on a flat surface.")
c2.metric("Poor day (P10)",
          f"{row['p10']:.2f} kWh/m²", help="One day in ten is below this.")
c3.metric("PV energy, typical day", f"{row['p50'] * kwp * pr:.1f} kWh")
c4.metric("Best 3-hour window", win["window"],
          help=f"About {win['share_of_daily_energy']:.0%} of the day's solar energy.")
st.caption(f"Expected energy in {month_name}: about "
           f"{row['mean'] * DAYS[month - 1] * kwp * pr:,.0f} kWh for a {kwp:g} kWp system "
           f"(average day, performance ratio {pr:.2f}).")

tab1, tab2, tab3, tab4 = st.tabs(
    ["Monthly outlook", "Daily sun profile", "Island map", "About"])

with tab1:
    d = outlook[outlook["site"] == site].sort_values("month")
    fig = go.Figure(go.Bar(
        x=[MONTHS[m - 1] for m in d["month"]], y=d["p50"],
        marker_color=[ORANGE if m == month else LIGHT for m in d["month"]],
        error_y=dict(type="data", symmetric=False,
                     array=(d["p90"] - d["p50"]).to_numpy(),
                     arrayminus=(d["p50"] - d["p10"]).to_numpy()),
        customdata=d[["p10", "p90", "low_day_share"]].to_numpy(),
        hovertemplate=("<b>%{x}</b><br>Typical: %{y:.2f} kWh/m²/day"
                       "<br>Poor day (P10): %{customdata[0]:.2f}"
                       "<br>Good day (P90): %{customdata[1]:.2f}"
                       "<br>Days below 3 kWh/m²: %{customdata[2]:.0%}<extra></extra>"),
    ))
    fig.update_layout(height=420, yaxis_title="Daily radiation (kWh/m²)",
                      margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig)
    st.caption(
        "Bars show the typical day; the whisker spans a poor day (P10) to a good day (P90).")
    with st.expander("Show the numbers"):
        st.dataframe(d.drop(columns="site").round(2), hide_index=True)

with tab2:
    p = profile[(profile["site"] == site) & (profile["month"] == month)
                & (profile["mean_wh_m2"] > 0.5)].sort_values("hour_start")
    fig = go.Figure(go.Bar(
        x=[f"{h:02d}:00 to {h + 1:02d}:00" for h in p["hour_start"]],
        y=p["mean_wh_m2"], marker_color=ORANGE,
        customdata=(p["mean_wh_m2"] / 1000 * kwp * pr).to_numpy(),
        hovertemplate=("<b>%{x}</b><br>Radiation: %{y:.0f} Wh/m²"
                       "<br>Estimated PV energy: %{customdata:.2f} kWh<extra></extra>"),
    ))
    fig.update_layout(height=420, yaxis_title="Average radiation (Wh/m² per hour)",
                      margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig)
    st.caption("Average sunlight by hour of the day (Mauritius local time).")

with tab3:
    m = outlook[outlook["month"] == month].merge(
        sites, left_on="site", right_on="name")
    fig = px.scatter_map(
        m, lat="lat", lon="lon", color="p50", size="p50", size_max=22,
        hover_name="site",
        hover_data={"region": True, "p10": ":.2f", "p50": ":.2f", "p90": ":.2f",
                    "lat": False, "lon": False},
        color_continuous_scale="YlOrRd", zoom=8.3, height=520,
        center=dict(lat=-20.25, lon=57.55), map_style="open-street-map",
        labels={"p50": "Typical (kWh/m²/day)"},
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig)
