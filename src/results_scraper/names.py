"""Athlete-name normalisation and matching.

Result documents write names inconsistently:
  "Darja KUZMITŠOVA", "KUZMITSOVA Darja", "Milana BELOZERSKAJA" vs
  "BELOZERSKAYA", "Karl Johannes MÄND-KUUSK". We compare accent-free,
  lower-cased word tokens; every word of the searched name must appear in the
  printed name (in any order), with a small fuzzy tolerance for long words
  to absorb transliteration differences (j/y, š/sh).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from itertools import permutations

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

_SPECIAL = str.maketrans(
    {"ß": "ss", "ø": "o", "Ø": "o", "đ": "d", "Đ": "d", "ł": "l", "Ł": "l", "æ": "ae", "Æ": "ae", "ı": "i"}
)

FUZZY_MIN_LEN = 6
FUZZY_THRESHOLD = 85


def normalize(text: str) -> str:
    text = (text or "").translate(_SPECIAL)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.casefold()


def tokens(text: str) -> list[str]:
    """Name words: accent-free, lower case; numbers (stray ranks, years) are never names."""
    return [t for t in re.split(r"[^0-9a-z]+", normalize(text)) if t and not t.isdigit()]


def _token_match(q: str, c: str) -> bool:
    """Confirmed-level word match: equal, initial, or close spelling of a long word."""
    if q == c:
        return True
    if len(c) == 1 and len(q) > 1:  # initial: "P." for "Pernille"
        return q[0] == c
    if len(q) >= FUZZY_MIN_LEN and len(c) >= FUZZY_MIN_LEN:
        return fuzz.ratio(q, c) >= FUZZY_THRESHOLD
    return False


def _loose_token_match(q: str, c: str) -> bool:
    """Possible-level word match: also one typo in short words ("Fette" ~ "Jette")."""
    if _token_match(q, c):
        return True
    shortest = min(len(q), len(c))
    if shortest >= 4:
        return Levenshtein.distance(q, c) <= (2 if shortest >= 8 else 1)
    return False


def _assign(q: list[str], cand: list[str], match) -> dict[int, int]:
    """Greedy one-to-one assignment query word -> candidate word (exact matches first)."""
    pairs: dict[int, int] = {}
    used: set[int] = set()
    for exact_only in (True, False):
        for qi, qt in enumerate(q):
            if qi in pairs:
                continue
            for ci, ct in enumerate(cand):
                if ci not in used and (qt == ct if exact_only else match(qt, ct)):
                    pairs[qi] = ci
                    used.add(ci)
                    break
    return pairs


def _has_full_word(pairs: dict[int, int], cand: list[str]) -> bool:
    """At least one searched word matched a whole word, not just an initial:
    "T.K." alone must not match "Toomas Kask"."""
    return any(len(cand[ci]) > 1 for ci in pairs.values())


def _word_tokens(text: str) -> list[tuple[str, str]]:
    """(normalised token, original word) pairs, so notes can quote the source."""
    out = []
    for word in (text or "").split():
        out.extend((t, word) for t in tokens(word))
    return out


CONFIRMED = "confirmed"
POSSIBLE = "possible"


@dataclass(frozen=True)
class Match:
    level: str  # CONFIRMED or POSSIBLE
    note: str = ""  # why it matched, when the source spells the name differently


@dataclass(frozen=True)
class AthleteQuery:
    """A searched athlete: display name plus optional birth year."""

    name: str
    birth_year: int | None = None

    @property
    def query_tokens(self) -> list[str]:
        return tokens(self.name)

    def matches(self, printed_name: str, birth_year: int | None = None) -> bool:
        """Confirmed match (all words of the searched name present)."""
        m = self.match(printed_name, birth_year)
        return m is not None and m.level == CONFIRMED

    def match(self, printed_name: str, birth_year: int | None = None) -> Match | None:
        if self.birth_year and birth_year and self.birth_year != birth_year:
            return None
        q = self.query_tokens
        if not q:
            return None
        words = _word_tokens(printed_name)
        cand = [t for t, _ in words]
        if not cand:
            return None
        source = f"Name in source: {printed_name}"

        # 1. confirmed: every searched word present (any order, accents/case ignored)
        pairs = _assign(q, cand, _token_match)
        if len(pairs) == len(q) and _has_full_word(pairs, cand):
            if sorted(q) == sorted(cand):
                return Match(CONFIRMED)
            return Match(CONFIRMED, source)

        # 2. confirmed: same letters, spaces lost in the document ("Liisa MariKÄRKÄNEN")
        compact = "".join(cand)
        if len(q) <= 4 and any("".join(perm) in compact for perm in permutations(q)):
            return Match(CONFIRMED, f"{source} (written without spaces)")

        # 3. possible: one typo per word allowed, one given name may be missing; the
        #    first or last searched word must match and at least two words overall,
        #    so a sibling (same surname, other first name) is never suggested.
        pairs = _assign(q, cand, _loose_token_match)
        needed = max(2, len(q) - 1) if len(q) >= 2 else 1
        if len(pairs) < needed or not ({0, len(q) - 1} & set(pairs)) or not _has_full_word(pairs, cand):
            return None
        originals = [w for w in self.name.split() for _ in tokens(w)]
        reasons = []
        for qi, qt in enumerate(q):
            if qi not in pairs:
                reasons.append(f"no '{originals[qi]}'")
            elif cand[pairs[qi]] != qt:
                reasons.append(f"'{words[pairs[qi]][1]}' ≈ '{originals[qi]}'")
        if not birth_year:
            reasons.append("birth year not stated")
        note = f"Possible match – check: {printed_name}"
        if reasons:
            note += " (" + "; ".join(reasons) + ")"
        return Match(POSSIBLE, note)


def find_in_text(query: AthleteQuery, lines: list[str], norm_lines: list[str] | None = None) -> str | None:
    """First text line of a document that names the athlete, or None.

    Used for documents whose layout the parsers could not read. Stricter than
    match(): every searched word must appear as a whole word (no initials, no
    typo tolerance below the transliteration level), because a whole line holds
    many other words. A name split over two lines (ISSF finals) is also found.
    """
    q = query.query_tokens
    if not q:
        return None
    norm_lines = norm_lines if norm_lines is not None else [normalize(ln) for ln in lines]
    keys = [t[:4] for t in q]

    def names_athlete(text: str) -> bool:
        cand = [t for t in tokens(text) if len(t) > 1]
        if len(_assign(q, cand, _token_match)) == len(q):
            return True
        compact = "".join(tokens(text))
        return len(q) <= 4 and any("".join(perm) in compact for perm in permutations(q))

    for i, norm in enumerate(norm_lines):
        if not any(k in norm for k in keys):
            continue  # cheap pre-filter: no part of the name on this line
        if _OFFICIAL.search(norm):
            continue  # "Peakohtunik Aivo Kivisaar", "Jury: ..."
        if names_athlete(lines[i]) and _has_score(lines[i]):
            return lines[i]
        if i + 1 < len(lines):
            pair = f"{lines[i]} {lines[i + 1]}"
            if names_athlete(pair) and _has_score(pair) and not _OFFICIAL.search(norm_lines[i + 1]):
                return f"{lines[i]} / {lines[i + 1]}"
    return None


# Officials are listed by name without scores; a result line always has one.
_OFFICIAL = re.compile(
    r"kohtunik|zurii|jury|referee|judge|sekretar|juhataja|korraldaja|\brto\b|\bcro\b|official|tulejoon|markide|abikohtunik"
)
_SCORE = re.compile(r"(?<![\d.,])\d{2,4}(?:[.,]\d{1,2})?(?![\d.,])")


def _has_score(text: str) -> bool:
    """A number that can be a score: 2-4 digits (decimals allowed), not a year
    or a date."""
    for m in _SCORE.finditer(text):
        v = m.group()
        if v.isdigit() and len(v) == 4 and 1920 <= int(v) <= 2035:
            continue
        return True
    return False
