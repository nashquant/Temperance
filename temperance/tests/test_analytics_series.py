from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytics import compute_metrics, ema, ema_alpha_from_days, parse_ma_windows, sma


def test_sma_basic() -> None:
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    out = sma(s, 2)
    assert out.round(3).tolist() == [1.0, 1.5, 2.5, 3.5]


def test_ema_basic() -> None:
    s = pd.Series([10.0, 10.0, 20.0])
    out = ema(s, 2)
    # alpha = 2/(2+1)=0.666..., third value = 0.666*20 + 0.333*10 = 16.666...
    assert round(float(out.iloc[2]), 3) == 16.667


def test_ema_alpha_from_days() -> None:
    assert round(ema_alpha_from_days(14), 6) == round(2.0 / 15.0, 6)


def test_sma_invalid_window() -> None:
    s = pd.Series([1.0])
    try:
        sma(s, 0)
    except ValueError:
        return
    assert False, "Expected ValueError"


def test_parse_ma_windows_supports_spread_pairs() -> None:
    singles, pairs = parse_ma_windows("(20,100)")
    assert singles == []
    assert pairs == [(20, 100)]


def test_parse_ma_windows_supports_mixed_and_dedupes() -> None:
    singles, pairs = parse_ma_windows("7, 14, (20,100), 14, (20,100)")
    assert singles == [7, 14]
    assert pairs == [(20, 100)]


def test_mechanical_load_only_for_running_like() -> None:
    runs_df = pd.DataFrame(
        [
            {
                "activity_id": "1",
                "start_time_utc": "2026-01-01T10:00:00Z",
                "sport_type": "running",
                "distance_m": 5000.0,
                "duration_s": 1500.0,
                "avg_pace_s_per_km": 300.0,
            },
            {
                "activity_id": "2",
                "start_time_utc": "2026-01-01T12:00:00Z",
                "sport_type": "cycling",
                "distance_m": 20000.0,
                "duration_s": 3600.0,
                "avg_pace_s_per_km": None,
            },
        ]
    )
    out = compute_metrics(runs_df, resting_hr=45.0, max_hr=200.0)
    run_ml = out.loc[out["activity_id"] == "1", "mechanical_load"].iloc[0]
    bike_ml = out.loc[out["activity_id"] == "2", "mechanical_load"].iloc[0]
    assert pd.notna(run_ml)
    assert pd.isna(bike_ml)


def test_compute_metrics_includes_rtss_and_tss() -> None:
    runs_df = pd.DataFrame(
        [
            {
                "activity_id": "1",
                "start_time_utc": "2026-01-01T10:00:00Z",
                "sport_type": "running",
                "distance_m": 5000.0,
                "duration_s": 1500.0,
                "avg_pace_s_per_km": 300.0,
                "avg_hr": 170.0,
            }
        ]
    )
    out = compute_metrics(runs_df, resting_hr=45.0, max_hr=200.0)
    assert pd.notna(out.loc[0, "rtss"])
    assert pd.notna(out.loc[0, "tss"])


def test_rtss_only_for_running_or_treadmill() -> None:
    runs_df = pd.DataFrame(
        [
            {
                "activity_id": "run",
                "start_time_utc": "2026-01-01T10:00:00Z",
                "sport_type": "running",
                "distance_m": 5000.0,
                "duration_s": 1500.0,
                "avg_pace_s_per_km": 300.0,
                "avg_hr": 160.0,
            },
            {
                "activity_id": "bike",
                "start_time_utc": "2026-01-01T12:00:00Z",
                "sport_type": "cycling",
                "distance_m": 20000.0,
                "duration_s": 3600.0,
                "avg_pace_s_per_km": 180.0,
                "avg_hr": 150.0,
            },
        ]
    )
    out = compute_metrics(runs_df, resting_hr=45.0, max_hr=200.0)
    run_rtss = out.loc[out["activity_id"] == "run", "rtss"].iloc[0]
    bike_rtss = out.loc[out["activity_id"] == "bike", "rtss"].iloc[0]
    assert pd.notna(run_rtss)
    assert pd.isna(bike_rtss)
