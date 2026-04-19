from backend.app import main as backend_main
from backend.app import planning_parsing


def test_main_uses_shared_planning_parser_entry_points() -> None:
    assert backend_main._normalize_plan_text is planning_parsing.normalize_plan_text
    assert (
        backend_main._parse_dated_activity_entry
        is planning_parsing.parse_dated_activity_entry
    )
    assert (
        backend_main._split_dated_activity_entries
        is planning_parsing.split_dated_activity_entries
    )
    assert backend_main._planned_row_signature is planning_parsing.planned_row_signature
