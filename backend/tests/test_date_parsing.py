from backend.app.date_parsing import parse_supported_day_value


def test_parse_supported_day_value_accepts_compact_month_text() -> None:
    assert parse_supported_day_value("10feb26").isoformat() == "2026-02-10"


def test_parse_supported_day_value_accepts_iso_and_slash_dates() -> None:
    assert parse_supported_day_value("2026-02-10").isoformat() == "2026-02-10"
    assert parse_supported_day_value("10/02/2026").isoformat() == "2026-02-10"


def test_parse_supported_day_value_rejects_invalid_dates() -> None:
    assert parse_supported_day_value("31feb26") is None
    assert parse_supported_day_value("5geb26") is None
