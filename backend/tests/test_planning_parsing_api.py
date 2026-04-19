import pytest

from backend.app.planning_parsing import expand_planned_segments


def test_backend_parser_returns_current_segment_schema_keys() -> None:
    segments, warnings = expand_planned_segments(
        "70min xtrain @ 138bpm",
        lthr_bpm=178.0,
        threshold_pace_sec_per_km=300.0,
    )

    assert warnings == []
    assert len(segments) == 1
    assert segments[0]["kind"] == "elliptical"
    assert float(segments[0]["duration_min"]) == pytest.approx(70.0)
    assert float(segments[0]["avg_hr_bpm"]) == pytest.approx(138.0)
    assert "minutes" not in segments[0]
    assert "bpm" not in segments[0]
