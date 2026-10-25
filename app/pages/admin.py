""
import hmac
import json
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="ClimaMU Admin", page_icon="🔒", layout="wide")
DATA = Path(__file__).parent.parent / "data"
API = "https://api.github.com"


def password_ok(entered):
    try:
        expected = str(st.secrets["ADMIN_PASSWORD"])
    except Exception:
        return False
    return hmac.compare_digest(entered.encode(), expected.encode())


def github_settings():
    """Return (repo, workflow, headers), or None when the secrets are missing."""
    try:
        token = str(st.secrets["GITHUB_TOKEN"])
        repo = str(st.secrets["GITHUB_REPO"])
        workflow = str(st.secrets.get("GITHUB_WORKFLOW", "refresh.yml"))
    except Exception:
        return None
    headers = {"Accept": "application/vnd.github+json",
               "Authorization": f"Bearer {token}",
               "X-GitHub-Api-Version": "2022-11-28"}
    return repo, workflow, headers


def latest_runs(repo, workflow, headers, n=5):
    r = requests.get(f"{API}/repos/{repo}/actions/workflows/{workflow}/runs",
                     headers=headers, params={"per_page": n}, timeout=20)
    r.raise_for_status()
    rows = [{"started_utc": run["created_at"].replace("T", " ").replace("Z", ""),
             "trigger": run["event"], "status": run["status"],
             "result": run["conclusion"] or "", "link": run["html_url"]}
            for run in r.json().get("workflow_runs", [])]
    return pd.DataFrame(rows)


def start_refresh(repo, workflow, headers):
    r = requests.post(f"{API}/repos/{repo}/actions/workflows/{workflow}/dispatches",
                      headers=headers, json={"ref": "main"}, timeout=20)
    return r.status_code


ERRORS = {
    401: "GitHub rejected the token (expired or wrong).",
    403: "The token lacks permission. It needs Actions: Read and write on this repository.",
    404: "Repository or workflow not found, or the token has no access to it.",
    422: "GitHub refused the request (does the workflow allow manual runs, and is the branch main?).",
}

# ---------- login ----------
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

    st.subheader("Data refresh")
    cfg = github_settings()
    if cfg is None:
        st.info(
            "Refresh control is not configured: GITHUB_TOKEN and GITHUB_REPO are missing from the secrets.")
    else:
        repo, workflow, headers = cfg
        try:
            runs = latest_runs(repo, workflow, headers)
        except requests.RequestException as err:
            runs = None
            st.warning(
                f"Could not read the refresh runs from GitHub ({type(err).__name__}).")

        busy = bool(runs is not None and not runs.empty
                    and runs["status"].isin(["queued", "in_progress"]).any())
        recent = time.time() - st.session_state.get("last_trigger", 0) < 300
        confirm = st.checkbox(
            "I understand this downloads new data and updates the public dashboard.")
        if busy:
            st.info(
                "A refresh is already running. Wait for it to finish, then press Check status.")
        elif recent:
            st.info(
                "A refresh was started a few minutes ago. Press Check status in a moment.")

        if st.button("Run data refresh now", disabled=busy or recent or not confirm):
            try:
                code = start_refresh(repo, workflow, headers)
            except requests.RequestException as err:
                st.error(f"Could not reach GitHub ({type(err).__name__}).")
            else:
                if code == 204:
                    st.session_state["last_trigger"] = time.time()
                    st.success(
                        "Refresh started. It takes about 3 minutes. Press Check status to follow it.")
                else:
                    st.error(ERRORS.get(
                        code, f"GitHub returned status {code}."))
        st.button("Check status")

        if runs is not None and not runs.empty:
            st.dataframe(runs, hide_index=True, column_config={
                "link": st.column_config.LinkColumn("link", display_text="open")})
        st.caption(
            "When a run finishes, the app is redeployed and you may need to log in again.")

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
