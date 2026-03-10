from __future__ import annotations

import re
from datetime import date, datetime


_MONTH_ABBR_TO_NUMBER = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def parse_supported_day_value(raw_value: str) -> date | None:
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except Exception:
        pass
    slash_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if slash_match:
        try:
            day = int(slash_match.group(1))
            month = int(slash_match.group(2))
            year = int(slash_match.group(3))
            return date(year, month, day)
        except Exception:
            return None
    compact_match = re.fullmatch(r"(\d{1,2})([A-Za-z]{3})(\d{2})", value)
    if compact_match:
        month = _MONTH_ABBR_TO_NUMBER.get(compact_match.group(2).lower())
        if month is None:
            return None
        try:
            day = int(compact_match.group(1))
            year = 2000 + int(compact_match.group(3))
            return date(year, month, day)
        except Exception:
            return None
    return None
