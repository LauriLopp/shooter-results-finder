"""Remove the same result reported by several sources.

Competition names differ between sites and languages ("Euroopa MV U18 25m/50m"
on laskurliit vs "2026 European Championship 25/50m U18" on ESC), so names are
not a reliable key. Instead, two rows for the same athlete are the same result
when their dates overlap and they have the same result type, rank and score.
Within one document, the category must match as well. The row from the
highest-priority source (laskurliit) is kept; the other source is noted in
`also_in`.
"""

from __future__ import annotations

import re
from datetime import timedelta

from .models import Kind, ResultRow

_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def score_value(result: str) -> float | None:
    m = _NUM.search(result or "")
    return float(m.group().replace(",", ".")) if m else None


def _dates_overlap(a: ResultRow, b: ResultRow) -> bool:
    if a.date_start is None or b.date_start is None:
        return True  # unknown date: rely on rank + score
    slack = timedelta(days=31 if (a.date_approx or b.date_approx) else 1)
    a_end = a.date_end or a.date_start
    b_end = b.date_end or b.date_start
    return a.date_start - slack <= b_end and b.date_start - slack <= a_end


def is_duplicate(a: ResultRow, b: ResultRow) -> bool:
    if a.kind != b.kind:
        return False
    if a.kind == Kind.UNREAD:  # same unreadable result book on two sites
        return _dates_overlap(a, b)
    sa, sb = score_value(a.result), score_value(b.result)
    if sa is None or sb is None or abs(sa - sb) > 0.05:
        return False
    if a.link == b.link:
        return a.rank == b.rank and a.category == b.category
    if a.source == b.source and a.rank != b.rank:
        return False
    # Sites may rank ties differently (inner tens vs. list order, combined
    # lists), so across sources an identical score counts as the same result
    # when the rank differs by at most one or the field size is the same.
    if a.rank != b.rank:
        close = a.rank is not None and b.rank is not None and abs(a.rank - b.rank) <= 1
        same_field = a.participants is not None and a.participants == b.participants
        if not (close or same_field):
            return False
    return _dates_overlap(a, b)


def merge_duplicates(rows: list[ResultRow], priority: dict[str, int]) -> tuple[list[ResultRow], list[str]]:
    # confirmed matches first, then by source priority
    ordered = sorted(rows, key=lambda r: (r.possible, priority.get(r.source, 99)))
    kept: list[ResultRow] = []
    dropped: list[str] = []
    for row in ordered:
        dup = next((k for k in kept if is_duplicate(k, row)), None)
        if dup is None:
            kept.append(row)
            continue
        if row.source != dup.source and row.source not in dup.also_in:
            dup.also_in.append(row.source)
        if dup.participants is None and row.participants:
            dup.participants = row.participants
        if row.possible:
            continue  # a loose name match of a result we already have: nothing to add
        dropped.append(f"{row.source}: {row.competition} / {row.category} (same as {dup.source}: {dup.competition})")
    return kept, dropped
