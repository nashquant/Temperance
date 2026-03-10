import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "v2" / "backend" / "app" / "date_parsing.py"
SPEC = importlib.util.spec_from_file_location("temperance_v2_date_parsing", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
parse_supported_day_value = MODULE.parse_supported_day_value


def test_parse_supported_day_value_accepts_compact_month_text() -> None:
    assert parse_supported_day_value("10feb26").isoformat() == "2026-02-10"


def test_parse_supported_day_value_accepts_iso_and_slash_dates() -> None:
    assert parse_supported_day_value("2026-02-10").isoformat() == "2026-02-10"
    assert parse_supported_day_value("10/02/2026").isoformat() == "2026-02-10"


def test_parse_supported_day_value_rejects_invalid_dates() -> None:
    assert parse_supported_day_value("31feb26") is None
    assert parse_supported_day_value("5geb26") is None
