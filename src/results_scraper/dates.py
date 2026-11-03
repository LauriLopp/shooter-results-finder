"""Parsing the many date notations used on the result sites."""

from __future__ import annotations

import re
from datetime import date

_D = r"(\d{1,2})"
_M = r"(\d{1,2})"
_Y = r"(\d{4}|\d{2})"

# 31.03-04.04  /  30.04.-02.05.2026
_CROSS_MONTH = re.compile(rf"(?<![\d.]){_D}\.{_M}\.?\s*[-–]\s*{_D}\.{_M}(?:\.{_Y})?(?![\d])")
# 30.-31.10.2026  /  16-18.10.2026  /  5.-8.08
_SAME_MONTH = re.compile(rf"(?<![\d.]){_D}\.?\s*[-–]\s*{_D}\.{_M}(?:\.{_Y})?(?![\d])")
# 18.10  /  10.10.2026
_SINGLE = re.compile(rf"(?<![\d.]){_D}\.{_M}(?:\.{_Y})?(?![\d])")

_MONTHS = {
    m: i
    for i, names in enumerate(
        [
            ("jan", "january", "jaan", "jaanuar"),
            ("feb", "february", "veebr", "veebruar"),
            ("mar", "march", "märts", "marts"),
            ("apr", "april", "aprill"),
            ("may", "mai"),
            ("jun", "june", "juuni"),
            ("jul", "july", "juuli"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october", "okt", "oktoober"),
            ("nov", "november"),
            ("dec", "december", "dets", "detsember"),
        ],
        start=1,
    )
    for m in names
}
# 23 AUG 2026  /  24 Aug 2026
_TEXT_MONTH = re.compile(r"\b(\d{1,2})\.?\s*([A-Za-zä]{3,10})\.?\s+(\d{4})\b")


def _year(y: str | None, default: int) -> int:
    if not y:
        return default
    y_int = int(y)
    return y_int + 2000 if y_int < 100 else y_int


def _mk(y: int, m: str | int, d: str | int) -> date | None:
    try:
        return date(y, int(m), int(d))
    except ValueError:
        return None


def parse_date_range(text: str, default_year: int) -> tuple[date | None, date | None]:
    """Find the first date or date range in free text.

    Returns (start, end); end equals start for single-day events, and both are
    None when no date is found.
    """
    if not text:
        return None, None

    m = _CROSS_MONTH.search(text)
    if m:
        d1, m1, d2, m2, y = m.groups()
        year = _year(y, default_year)
        start = _mk(year if int(m1) <= int(m2) else year - 1, m1, d1)
        end = _mk(year, m2, d2)
        if start and end:
            return start, end

    m = _SAME_MONTH.search(text)
    if m:
        d1, d2, mo, y = m.groups()
        year = _year(y, default_year)
        start, end = _mk(year, mo, d1), _mk(year, mo, d2)
        if start and end and start <= end:
            return start, end

    m = _SINGLE.search(text)
    if m:
        d, mo, y = m.groups()
        start = _mk(_year(y, default_year), mo, d)
        if start:
            return start, start

    m = _TEXT_MONTH.search(text)
    if m:
        d, mon, y = m.groups()
        mo = _MONTHS.get(mon.lower())
        if mo:
            start = _mk(int(y), mo, d)
            if start:
                return start, start

    return None, None


def parse_iso(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def format_range(start: date | None, end: date | None) -> str:
    if start is None:
        return ""
    if end is None or end == start:
        return start.strftime("%d.%m.%Y")
    if start.year == end.year and start.month == end.month:
        return f"{start.day:02d}.-{end.strftime('%d.%m.%Y')}"
    if start.year == end.year:
        return f"{start.strftime('%d.%m')}.-{end.strftime('%d.%m.%Y')}"
    return f"{start.strftime('%d.%m.%Y')}-{end.strftime('%d.%m.%Y')}"


def overlaps(start: date | None, end: date | None, lo: date, hi: date) -> bool:
    """True if the event [start, end] overlaps the query period [lo, hi]."""
    if start is None:
        return False
    return start <= hi and (end or start) >= lo
