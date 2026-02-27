from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from garmin_client import _extract_sleep_row, _extract_wellness_row


def test_extract_sleep_score_nested_value() -> None:
    row = _extract_sleep_row(
        date(2026, 2, 1),
        {
            "dailySleepDTO": {
                "sleepScores": {
                    "overallScore": {"value": 81},
                }
            }
        },
    )
    assert row["sleep_score"] == 81.0


def test_extract_resting_hr_plain_number() -> None:
    row = _extract_wellness_row(
        day=date(2026, 2, 1),
        body_battery=None,
        stress=None,
        hrv=None,
        rhr=47,
        readiness=None,
        stats_body=None,
        respiration=None,
        intensity_minutes=None,
        steps_payload=None,
    )
    assert row["resting_hr"] == 47.0
