from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

from backend.app import main as backend_main


def test_dashboard_metrics_frames_filter_invalid_rows_without_second_metrics_pass(monkeypatch) -> None:
    calls: list[tuple[bool, bool]] = []
    source_df = pd.DataFrame(
        [
            {
                "activity_id": "run-1",
                "sport_type": "running",
                "start_time_utc": "2026-03-31T10:00:00Z",
                "distance_m": 5000.0,
                "is_invalid": 0,
            },
            {
                "activity_id": "run-2",
                "sport_type": "running",
                "start_time_utc": "2026-03-30T10:00:00Z",
                "distance_m": 8000.0,
                "is_invalid": 1,
            },
            {
                "activity_id": "custom-2026-03-31-1",
                "sport_type": "custom",
                "start_time_utc": "2026-03-31T12:00:00Z",
                "distance_m": 0.0,
            },
        ]
    )

    def fake_metrics_for_filters(**kwargs):
        calls.append((bool(kwargs["include_invalid"]), bool(kwargs["include_mechanical_load"])))
        return source_df.copy()

    monkeypatch.setattr(backend_main, "_metrics_for_filters", fake_metrics_for_filters)
    monkeypatch.setattr(
        backend_main,
        "get_activity_local_start_map",
        lambda **kwargs: {
            "run-1": "2026-03-31 07:00:00",
            "run-2": "2026-03-30 08:00:00",
        },
    )

    metrics_df, actual_metrics_df = backend_main._dashboard_metrics_frames(
        db_path=Path("ignored.db"),
        sport=None,
    )

    assert calls == [(True, False)]
    assert set(actual_metrics_df["activity_id"]) == {"run-1", "run-2", "custom-2026-03-31-1"}
    assert set(metrics_df["activity_id"]) == {"run-1", "custom-2026-03-31-1"}
    assert metrics_df.loc[metrics_df["activity_id"] == "run-1", "distance_km_running"].iloc[0] == 5.0
    assert metrics_df.loc[metrics_df["activity_id"] == "custom-2026-03-31-1", "distance_km_running"].iloc[0] == 0.0
    assert actual_metrics_df.loc[actual_metrics_df["activity_id"] == "run-1", "day"].iloc[0].date().isoformat() == "2026-03-31"


def test_week_outlook_uses_yesterday_planned_cutoff_when_today_has_no_activity(monkeypatch) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            current = cls(2026, 4, 1, 9, 0, tzinfo=timezone.utc)
            return current if tz is None else current.astimezone(tz)

    monkeypatch.setattr(
        backend_main,
        "_metrics_for_filters",
        lambda **kwargs: pd.DataFrame(
            [
                {"start_time_utc": "2026-03-30T10:00:00Z", "tss": 80.0, "rtss": 70.0, "distance_proxy_km": 12.0},
                {"start_time_utc": "2026-03-31T10:00:00Z", "tss": 70.0, "rtss": 60.0, "distance_proxy_km": 10.0},
            ]
        ),
    )
    monkeypatch.setattr(
        backend_main,
        "_planned_daily_metric_map",
        lambda **kwargs: (
            {
                pd.Timestamp("2026-03-30"): 100.0,
                pd.Timestamp("2026-03-31"): 120.0,
                pd.Timestamp("2026-04-01"): 90.0,
                pd.Timestamp("2026-04-02"): 80.0,
            },
            {
                pd.Timestamp("2026-03-30"): 100.0,
                pd.Timestamp("2026-03-31"): 120.0,
                pd.Timestamp("2026-04-01"): 90.0,
                pd.Timestamp("2026-04-02"): 80.0,
            },
            170.0,
        ),
    )
    monkeypatch.setattr(backend_main, "_load_curve_points", lambda **kwargs: [])
    monkeypatch.setattr(backend_main, "datetime", FixedDateTime)

    payload = backend_main._build_week_outlook_payload(
        db_path=Path("ignored.db"),
        days=30,
        start_day=None,
        end_day=None,
        sport=None,
        metric="tss",
        compare="planned",
        week_start="2026-03-30",
    )

    assert payload["week_total_current"] == 150.0
    assert payload["week_total_compare"] == 390.0
    assert payload["wtd_compare"] == 220.0
    assert payload["today_day"] == "2026-04-01"
