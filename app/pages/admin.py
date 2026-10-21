"""ClimaMU admin page: pipeline status, data quality and model results (password protected)."""
import hmac
import json
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="ClimaMU Admin", page_icon="🔒", layout="wide")
DATA = Path(__file__).parent.parent / "data"


def password_ok(entered):
    try:
        expected = str(st.secrets["ADMIN_PASSWORD"])
    except Exception:
        return False
    return hmac.compare_digest(entered.encode(), expected.encode())


if not st.session_state.get("admin"):
    st.title("Admin login")
    entered = st.text_input("Password", type="password")
    if st.button("Log in"):
        if password_ok(entered):
            st.session_state["admin"] = True
            st.rerun()
        else:
            time.sleep(1)
            st.error("Wrong password, or no admin password is configured.")
    st.stop()

st.title("Admin panel")
if st.sidebar.button("Log out"):
    st.session_state["admin"] = False
    st.rerun()

status = json.loads((DATA / "status.json").read_text())
tab1, tab2, tab3 = st.tabs(
    ["Pipeline status", "Data quality", "Model results"])

with tab1:
    c = st.columns(4)
    c[0].metric("Sites", status["sites"])
    c[1].metric("First day", status["first_date"])
    c[2].metric("Last day", status["last_date"])
    c[3].metric("Daily rows", f"{status['daily_rows']:,}")

    st.caption(f"Dashboard data last updated {status['exported_at']}.")
    log_path = DATA / "refresh_log.csv"
    if log_path.exists():
        st.subheader("Refresh history")
        st.dataframe(pd.read_csv(log_path).sort_values("run_utc", ascending=False),
                     hide_index=True)
    else:
        st.info("No automatic refresh has run yet.")


with tab2:
    q = pd.read_csv(DATA / "quality_report.csv")
    st.dataframe(q, hide_index=True)
    bad = q[(q["missing_values"] > 0) | (q["out_of_range"] > 0)
            | (q["missing_timestamps"] > 0)]
    if bad.empty:
        st.success("All checks passed for all sites.")
    else:
        st.warning("Some sites have missing or out-of-range values:")
        st.dataframe(bad, hide_index=True)

with tab3:
    r = pd.read_csv(DATA / "forecast_results.csv")
    mae = r.pivot(index="horizon_days", columns="model", values="MAE")
    fig = px.line(mae, markers=True,
                  labels={"value": "MAE (kWh/m²/day)", "horizon_days": "Horizon (days)"})
    st.plotly_chart(fig)
    st.dataframe(mae.round(3))
    st.caption(
        "History-only forecasts beat climatology only at day 1 (test period 2023 to 2025).")
