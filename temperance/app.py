from __future__ import annotations

from datetime import datetime, timezone

import altair as alt
import pandas as pd
import streamlit as st

from analytics import compute_metrics, display_table, weekly_summary
from config import load_config
from db import (
    get_activity_raw,
    get_last_sync,
    get_latest_activity_time,
    get_runs_df,
    get_setting,
    init_db,
    log_sync,
    save_setting,
    upsert_activities,
)
from garmin_client import fetch_garmin_runs, import_runs_from_folder
from synthetic_data import generate_synthetic_runs


st.set_page_config(page_title="Temperance", layout="wide")
st.title("Temperance")
st.caption("Local-first running load tracker (aerobic + mechanical)")

cfg = load_config()
init_db(cfg.db_path)
cfg.import_dir.mkdir(parents=True, exist_ok=True)


with st.sidebar:
    st.header("Navigation")
    view = st.radio("Page", ["Dashboard", "Activity Detail"], index=0)


st.header("Settings")
def_resting = float(get_setting(cfg.db_path, "resting_hr") or 60)
def_max = float(get_setting(cfg.db_path, "max_hr") or 190)
sex = get_setting(cfg.db_path, "sex") or "male"

col1, col2, col3 = st.columns(3)
with col1:
    resting_hr = st.number_input("Resting HR", min_value=30, max_value=100, value=int(def_resting))
with col2:
    max_hr = st.number_input("Max HR", min_value=120, max_value=230, value=int(def_max))
with col3:
    sex = st.selectbox("Sex constant (TRIMP)", ["male", "female"], index=0 if sex == "male" else 1)

if st.button("Save settings"):
    save_setting(cfg.db_path, "resting_hr", str(resting_hr))
    save_setting(cfg.db_path, "max_hr", str(max_hr))
    save_setting(cfg.db_path, "sex", sex)
    st.success("Settings saved.")

st.divider()
st.header("Sync")

last_sync = get_last_sync(cfg.db_path)
if last_sync:
    ok = "success" if last_sync["success"] else "failed"
    st.caption(
        f"Last sync: {last_sync['sync_time_utc']} | source={last_sync['source']} | {ok} | {last_sync['message']}"
    )
else:
    st.caption("No sync has been run yet.")

sync_cols = st.columns([1, 1, 1, 1])
with sync_cols[0]:
    days_back = st.number_input("Days to sync", min_value=7, max_value=365, value=90)
with sync_cols[1]:
    source = st.selectbox("Source", ["Garmin API", "File Import", "Both"], index=2)
with sync_cols[2]:
    run_sync = st.button("Sync activities")
with sync_cols[3]:
    generate_demo = st.button("Generate demo data")

st.caption(f"Import folder: {cfg.import_dir}")

if run_sync:
    total_rows = 0
    messages: list[str] = []

    latest = get_latest_activity_time(cfg.db_path)

    if source in {"Garmin API", "Both"}:
        if cfg.garmin_email and cfg.garmin_password:
            try:
                rows = fetch_garmin_runs(
                    email=cfg.garmin_email,
                    password=cfg.garmin_password,
                    days_back=int(days_back),
                    since_utc=latest,
                )
                changed = upsert_activities(cfg.db_path, rows)
                total_rows += len(rows)
                messages.append(f"Garmin: fetched {len(rows)} runs ({changed} DB row changes).")
            except Exception as exc:
                msg = (
                    "Garmin login/fetch failed. Verify GARMIN_EMAIL / GARMIN_PASSWORD in .env or env vars. "
                    f"Error: {exc}"
                )
                messages.append(msg)
                st.warning(msg)
        else:
            messages.append("Garmin credentials not set. Skipped Garmin API sync.")

    if source in {"File Import", "Both"}:
        rows = import_runs_from_folder(cfg.import_dir, days_back=int(days_back))
        changed = upsert_activities(cfg.db_path, rows)
        total_rows += len(rows)
        messages.append(f"File import: found {len(rows)} runs ({changed} DB row changes).")

    success = total_rows > 0 or any("Skipped" in m for m in messages)
    log_sync(cfg.db_path, source=source.lower().replace(" ", "_"), success=success, message=" | ".join(messages))

    if total_rows > 0:
        st.success("Sync complete. " + " ".join(messages))
    else:
        st.info(
            "No activities found. If Garmin sync fails, place .FIT/.TCX files in "
            f"{cfg.import_dir} and run sync again."
        )

if generate_demo:
    demo_rows = generate_synthetic_runs(days_back=int(days_back))
    changes = upsert_activities(cfg.db_path, demo_rows)
    log_sync(
        cfg.db_path,
        source="synthetic",
        success=True,
        message=f"Generated {len(demo_rows)} synthetic runs ({changes} DB row changes).",
    )
    st.success(f"Added {len(demo_rows)} synthetic runs for demo.")

runs_df = get_runs_df(cfg.db_path)
metrics_df = compute_metrics(runs_df, resting_hr=float(resting_hr), max_hr=float(max_hr), sex=sex)

if view == "Dashboard":
    st.divider()
    st.header("Dashboard")

    if metrics_df.empty:
        st.info(
            "No running activities yet. Use Sync above."
            " If Garmin fails, import .FIT/.TCX files into the local import folder."
        )
    else:
        table_df = display_table(metrics_df)
        st.subheader("Runs")
        st.dataframe(
            table_df,
            use_container_width=True,
            column_config={
                "distance_km": st.column_config.NumberColumn(format="%.2f km"),
                "duration_min": st.column_config.NumberColumn(format="%.1f min"),
                "avg_pace_s_per_km": st.column_config.NumberColumn(format="%.1f s/km"),
                "aerobic_load": st.column_config.NumberColumn(format="%.1f"),
                "mechanical_load": st.column_config.NumberColumn(format="%.1f"),
            },
        )

        weekly = weekly_summary(metrics_df)
        weekly["week_start"] = pd.to_datetime(weekly["week_start"])

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Weekly Aerobic Load")
            ch = (
                alt.Chart(weekly)
                .mark_bar()
                .encode(x="week_start:T", y="total_aerobic_load:Q", tooltip=list(weekly.columns))
            )
            st.altair_chart(ch, use_container_width=True)

        with c2:
            st.subheader("Weekly Mechanical Load")
            ch2 = (
                alt.Chart(weekly)
                .mark_bar(color="#f58518")
                .encode(x="week_start:T", y="total_mechanical_load:Q", tooltip=list(weekly.columns))
            )
            st.altair_chart(ch2, use_container_width=True)

        st.subheader("Daily Run Scatter: Mechanical vs Aerobic")
        scatter = (
            alt.Chart(metrics_df)
            .mark_circle(size=90)
            .encode(
                x="aerobic_load:Q",
                y="mechanical_load:Q",
                color=alt.Color("distance_m:Q", scale=alt.Scale(scheme="viridis")),
                tooltip=[
                    "activity_id",
                    "start_time_utc",
                    "distance_m",
                    "duration_s",
                    "avg_hr",
                    "aerobic_load",
                    "mechanical_load",
                ],
            )
        )
        st.altair_chart(scatter, use_container_width=True)

        st.subheader("Weekly Totals")
        st.dataframe(weekly, use_container_width=True)

if view == "Activity Detail":
    st.divider()
    st.header("Activity Detail")

    if metrics_df.empty:
        st.info("No activities available.")
    else:
        options_df = metrics_df.copy().sort_values("start_time_utc", ascending=False)
        options_df["label"] = (
            options_df["start_time_utc"].dt.strftime("%Y-%m-%d")
            + " | "
            + options_df["distance_m"].div(1000).round(2).astype(str)
            + " km | "
            + options_df["activity_id"].astype(str)
        )
        selected = st.selectbox("Select activity", options_df["label"].tolist())
        activity_id = options_df.loc[options_df["label"] == selected, "activity_id"].iloc[0]

        row = options_df.loc[options_df["activity_id"] == activity_id].iloc[0]

        m1, m2, m3 = st.columns(3)
        m1.metric("Aerobic Load", f"{row['aerobic_load']:.1f}")
        m2.metric("Mechanical Load", f"{row['mechanical_load']:.1f}")
        m3.metric("Avg Pace", f"{row['avg_pace_s_per_km']:.1f} s/km")

        st.write(
            {
                "activity_id": row["activity_id"],
                "start_time_utc": row["start_time_utc"],
                "sport_type": row["sport_type"],
                "distance_m": row["distance_m"],
                "duration_s": row["duration_s"],
                "avg_hr": row["avg_hr"],
                "max_hr": row["max_hr"],
                "elevation_gain_m": row["elevation_gain_m"],
                "source": row["source"],
            }
        )

        raw = get_activity_raw(cfg.db_path, str(activity_id))
        if raw:
            with st.expander("Raw activity payload"):
                st.json(raw)

st.caption(f"Now: {datetime.now(timezone.utc).isoformat()} UTC")
