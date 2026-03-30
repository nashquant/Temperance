from pathlib import Path
import importlib.util
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "temperance"))
sys.path.insert(0, str(ROOT / "v2" / "backend"))

BACKEND_MAIN_PATH = ROOT / "v2" / "backend" / "app" / "main.py"
BACKEND_MAIN_SPEC = importlib.util.spec_from_file_location("temperance_v2_backend_main_dashboard", BACKEND_MAIN_PATH)
assert BACKEND_MAIN_SPEC is not None and BACKEND_MAIN_SPEC.loader is not None
backend_main = importlib.util.module_from_spec(BACKEND_MAIN_SPEC)
BACKEND_MAIN_SPEC.loader.exec_module(backend_main)


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
