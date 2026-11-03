"""Core data structures shared by all sources, parsers and exporters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class Kind(StrEnum):
    INDIVIDUAL = "Individual"
    FINAL = "Final"
    TEAM = "Team"
    MIXED_TEAM = "Mixed team"
    UNREAD = "Not read"  # name found in the document, result could not be extracted


@dataclass
class Person:
    """One athlete inside a parsed result entry."""

    name: str  # as printed, e.g. "Darja KUZMITŠOVA" or "KUZMITŠOVA Darja"
    birth_year: int | None = None
    club: str = ""
    result: str = ""  # the athlete's own score (for team entries: their contribution)


@dataclass
class Entry:
    """One ranked line of a results table: an individual or a team."""

    rank: int | None
    result: str  # final score as printed (team total for team entries)
    persons: list[Person] = field(default_factory=list)
    team_name: str = ""


@dataclass
class Table:
    """One category / event of one competition (e.g. '40l Õhupüss Tüdrukud')."""

    category: str
    kind: Kind
    entries: list[Entry] = field(default_factory=list)
    participants: int | None = None  # explicit count if the document states one
    date_start: date | None = None  # per-event date, if known (overrides competition date)
    link: str = ""  # document for this table, when it differs from the competition link

    @property
    def participant_count(self) -> int:
        """Number of athletes (teams, for team events) with a result in this table.

        Counted from the parsed entries; a count stated by the document is
        only used when the entries look incomplete (e.g. medal-match tables
        list just the medal contenders).
        """
        counted = sum(1 for e in self.entries if has_score(e.result))
        if self.kind in (Kind.TEAM, Kind.MIXED_TEAM):
            return counted
        if self.participants and self.participants > counted and self.kind != Kind.FINAL:
            return self.participants
        return counted


@dataclass
class Competition:
    """A competition and the tables parsed from its result document(s)."""

    name: str
    source: str  # "laskurliit", "protokollitaja", "esc", "sius"
    link: str
    date_start: date | None = None
    date_end: date | None = None
    place: str = ""
    tables: list[Table] = field(default_factory=list)
    date_approx: bool = False  # only the upload month is known
    text: list[str] = field(default_factory=list)  # document text lines, to find names the parsers missed


@dataclass
class ResultRow:
    """One line of the final output for one athlete."""

    athlete: str  # the name the user searched for
    competition: str
    date_start: date | None
    date_end: date | None
    category: str
    kind: Kind
    result: str
    rank: int | None
    participants: int | None
    link: str
    source: str
    team: str = ""
    own_result: str = ""  # for team rows: the athlete's own score
    matched_name: str = ""  # name as printed in the source document
    also_in: list[str] = field(default_factory=list)  # other sources with the same result
    date_approx: bool = False
    possible: bool = False  # name only loosely matches: user should check
    notes: str = ""  # e.g. how the source spelled the name

    @property
    def dates_text(self) -> str:
        from .dates import format_range

        if self.date_approx and self.date_start:
            return f"~{self.date_start.strftime('%m.%Y')}"
        return format_range(self.date_start, self.date_end)

    @property
    def rank_text(self) -> str:
        if self.rank is None:
            return ""
        if self.participants:
            return f"{self.rank}/{self.participants}"
        return str(self.rank)


def has_score(result: str) -> bool:
    """True if a printed result is an actual score (not empty / 0 / DNS)."""
    import re

    m = re.search(r"\d+(?:[.,]\d+)?", result or "")
    if not m:
        return False
    return float(m.group().replace(",", ".")) > 0
