"""Token classification helpers shared by the text-table parsers."""

from __future__ import annotations

import re

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
_RANK_RE = re.compile(r"^(\d{1,3})\.?$")
_NUM_RE = re.compile(r"^-?\d+(?:[.,]\d+)?$")


def parse_rank(tok: str) -> int | None:
    """'I' -> 1, 'III' -> 3, '4.' -> 4, '12' -> 12; anything else -> None."""
    t = tok.strip()
    if t.rstrip(".") in ROMAN and (t.rstrip(".") == t or len(t) - len(t.rstrip(".")) == 1):
        return ROMAN[t.rstrip(".")]
    m = _RANK_RE.match(t)
    if m:
        v = int(m.group(1))
        return v if v > 0 else None
    return None


def is_number(tok: str) -> bool:
    return bool(_NUM_RE.match(tok))


def num_value(tok: str) -> float:
    return float(tok.replace(",", "."))


def is_year(tok: str, lo: int = 1920, hi: int = 2035) -> bool:
    return len(tok) == 4 and tok.isdigit() and lo <= int(tok) <= hi


def is_upper_word(tok: str) -> bool:
    """Surname style: 'KUZMITŠOVA', 'MÄND-KUUSK', "O'NEIL"."""
    letters = [c for c in tok if c.isalpha()]
    return len(letters) >= 2 and all(c.isupper() for c in letters)


def is_title_word(tok: str) -> bool:
    """Given-name style: 'Darja', 'Liis-Beth', 'Ly', initial 'P.' (not club codes like 'MäLK', 'SpK')."""
    if len(tok) == 2 and tok[0].isupper() and tok[1] == ".":
        return True
    parts = tok.split("-")
    return all(
        len(p) >= 2 and p[0].isupper() and all(c.islower() or c in "'’" for c in p[1:]) for p in parts
    )
