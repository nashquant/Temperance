from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from activity_parsing import expand_planned_segments, parse_dated_activity_entry, split_dated_activity_entries


SAMPLE_BLOCK = """2026-03-25:45’ elliptical @ 65%;
2026-03-26:45’ run @ 4:40;
2026-03-26:45’ elliptical @ 75%;
2026-03-27:60’ run @ 4:20;
2026-03-28:75’ elliptical @ 78%;
2026-03-29:50’ run @ 4:40+6x20” @ 3:10;
2026-03-30:75’ run @ 4:15;
2026-03-31:70’ elliptical @ 78%;

2026-04-01:45’ run @ 4:40;
2026-04-01:45’ elliptical @ 75%;
2026-04-02:15’ run @ 4:40+3x8’ @ 3:45 (2’ @ 4:40)+15’ run @ 4:40;
2026-04-03:85’ elliptical @ 78%;
2026-04-04:60’ run @ 4:15;
2026-04-05:15’ run @ 4:40+2x10’ @ 3:45 (3’ @ 4:40)+15’ run @ 4:40;
2026-04-06:90’ run @ 4:15;
2026-04-07:40’ run @ 4:45;
2026-04-07:45’ elliptical @ 75%;

2026-04-08:60’ elliptical @ 75%;
2026-04-09:15’ run @ 4:40+2x10’ @ 3:45 (3’ @ 4:40)+15’ run @ 4:40;
2026-04-10:50’ run @ 4:45;
2026-04-11:15’ run @ 4:40+2x6’ @ 3:50 (2’ @ 4:40)+10’ run @ 4:40+4x20” @ 3:10;
2026-04-12:42.2km run @ 4:20;"""


def test_expand_planned_segments_supports_quoted_seconds_reps() -> None:
    segments, warnings = expand_planned_segments(
        "50’ run @ 4:40+6x20” @ 3:10",
        lthr_bpm=178.0,
        threshold_pace_sec_per_km=300.0,
    )

    assert warnings == []
    assert len(segments) == 7
    assert segments[0]["duration_min"] == pytest.approx(50.0)
    rep_durations = [float(segment["duration_min"]) for segment in segments[1:]]
    assert rep_durations == pytest.approx([20.0 / 60.0] * 6)


def test_expand_planned_segments_supports_parenthetical_recovery_blocks() -> None:
    segments, warnings = expand_planned_segments(
        "15’ run @ 4:40+3x8’ @ 3:45 (2’ @ 4:40)+15’ run @ 4:40",
        lthr_bpm=178.0,
        threshold_pace_sec_per_km=300.0,
    )

    assert warnings == []
    assert [float(segment["duration_min"]) for segment in segments] == pytest.approx([15.0, 8.0, 2.0, 8.0, 2.0, 8.0, 15.0])
    assert [float(segment["pace_s_per_km"]) for segment in segments[1:6:2]] == pytest.approx([225.0, 225.0, 225.0])
    assert [float(segment["pace_s_per_km"]) for segment in segments[2:5:2]] == pytest.approx([280.0, 280.0])


def test_expand_planned_segments_supports_xtrain_alias_for_elliptical() -> None:
    segments, warnings = expand_planned_segments(
        "70min xtrain @ 78%",
        lthr_bpm=178.0,
        threshold_pace_sec_per_km=300.0,
    )

    assert warnings == []
    assert len(segments) == 1
    assert segments[0]["kind"] == "elliptical"
    assert float(segments[0]["duration_min"]) == pytest.approx(70.0)
    assert float(segments[0]["if_input"]) == pytest.approx(0.78)

    hyphen_segments, hyphen_warnings = expand_planned_segments(
        "70min x-train @ 78%",
        lthr_bpm=178.0,
        threshold_pace_sec_per_km=300.0,
    )

    assert hyphen_warnings == []
    assert len(hyphen_segments) == 1
    assert hyphen_segments[0]["kind"] == "elliptical"
    assert float(hyphen_segments[0]["duration_min"]) == pytest.approx(70.0)
    assert float(hyphen_segments[0]["if_input"]) == pytest.approx(0.78)


def test_shared_parser_returns_current_segment_schema_keys() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".." / "v2" / "backend"))
    from app.planning_parsing import expand_planned_segments as backend_expand_planned_segments

    segments, warnings = backend_expand_planned_segments(
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


def test_bulk_schedule_sample_parses_cleanly() -> None:
    entries = split_dated_activity_entries(SAMPLE_BLOCK)

    assert len(entries) == 22
    for entry in entries:
        day_ts, normalized, error = parse_dated_activity_entry(entry)
        assert error is None, entry
        assert day_ts is not None, entry
        segments, warnings = expand_planned_segments(
            normalized,
            lthr_bpm=178.0,
            threshold_pace_sec_per_km=300.0,
        )
        assert segments, entry
        assert warnings == [], f"{entry}: {warnings}"
