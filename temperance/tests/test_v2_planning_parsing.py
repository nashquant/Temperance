from __future__ import annotations

import importlib.util
import math
import sys
import types
from datetime import date, datetime, timedelta
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2] / "v2" / "backend"
MODULE_PATH = BACKEND_ROOT / "app" / "planning_parsing.py"


def _coerce_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError(f"Unsupported timestamp value: {value!r}")


def _load_module():
    fake_pandas = types.ModuleType("pandas")
    fake_pandas.Timestamp = _coerce_date
    fake_pandas.Timedelta = timedelta

    sys.modules["pandas"] = fake_pandas
    sys.path.insert(0, str(BACKEND_ROOT))
    try:
        spec = importlib.util.spec_from_file_location("temperance_v2_planning_parsing", MODULE_PATH)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)
        sys.modules.pop("pandas", None)


MODULE = _load_module()
expand_planned_segments = MODULE.expand_planned_segments
parse_dated_activity_entry = MODULE.parse_dated_activity_entry


def test_parse_dated_activity_entry_preserves_meridiem_and_relative_day() -> None:
    day_ts, normalized, error = parse_dated_activity_entry("T+1:45min run @ 4:40 PM")

    assert error is None
    assert day_ts == date.today() + timedelta(days=1)
    assert normalized == "45min run @ 4:40 PM"


def test_expand_planned_segments_supports_parenthetical_recovery_blocks() -> None:
    segments, warnings = expand_planned_segments(
        "15min run @ 4:40 + 3x8min @ 3:45 (2min @ 4:40) + 15min run @ 4:40"
    )

    assert warnings == []
    assert [segment["minutes"] for segment in segments] == [15.0, 8.0, 2.0, 8.0, 2.0, 8.0, 2.0, 15.0]
    assert [segment["pace_sec_per_km"] for segment in segments[1:6:2]] == [225.0, 225.0, 225.0]
    assert [segment["pace_sec_per_km"] for segment in segments[2:7:2]] == [280.0, 280.0, 280.0]


def test_expand_planned_segments_derives_if_from_tss_for_repeated_distance() -> None:
    segments, warnings = expand_planned_segments(
        "6x1km run @ 40TSS / 2min @ 60%",
        threshold_pace_sec_per_km=300.0,
    )

    assert warnings == []
    assert len(segments) == 12
    work_segments = segments[::2]
    recovery_segments = segments[1::2]

    assert all(segment["distance_km"] == 1.0 for segment in work_segments)
    assert all(segment["if_input_source"] == "tss_derived" for segment in work_segments)
    assert all(math.isclose(float(segment["if_input"]), math.sqrt(0.8)) for segment in work_segments)

    assert all(segment["minutes"] == 2.0 for segment in recovery_segments)
    assert all(segment["if_input"] == 0.6 for segment in recovery_segments)
    assert all(segment["if_input_source"] == "explicit" for segment in recovery_segments)
