from backend.app.main import _collapse_merged_cards


def test_collapse_merged_cards_uses_weighted_average_pace() -> None:
    cards = [
        {
            "activity_id": "act-1",
            "sport": "Running",
            "start_time_utc": "2026-04-10T07:00:00",
            "start_time_hhmm": "07:00",
            "duration_s": 8 * 60,
            "duration_label": "8min",
            "distance_km": (8 * 60) / 248,
            "distance_label": "2 km",
            "hr_label": "150b",
            "pace_label": "4:08/km",
            "if_pct": 80,
            "tss": 10,
            "rtss": 11,
            "intensity": "blue",
        },
        {
            "activity_id": "act-2",
            "sport": "Running",
            "start_time_utc": "2026-04-10T07:10:00",
            "start_time_hhmm": "07:10",
            "duration_s": 35 * 60,
            "duration_label": "35min",
            "distance_km": (35 * 60) / 208,
            "distance_label": "10 km",
            "hr_label": "155b",
            "pace_label": "3:28/km",
            "if_pct": 90,
            "tss": 35,
            "rtss": 36,
            "intensity": "orange",
        },
    ]
    merge = {"id": 8, "activity_ids": ["act-1", "act-2"]}

    collapsed = _collapse_merged_cards(
        cards, {activity_id: merge for activity_id in merge["activity_ids"]}
    )

    assert collapsed[0]["pace_label"] == "3:34/km"
