"""Common interface for result sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from ..models import Competition

Progress = Callable[[str], None]


def _noop(_: str) -> None:
    pass


@dataclass
class CompetitionRef:
    """A competition found in a source's index, before its results are loaded."""

    source: str
    name: str
    link: str
    date_start: date | None
    date_end: date | None
    place: str = ""
    date_approx: bool = False  # date guessed from upload folder, not stated
    extra: dict = field(default_factory=dict)


class Source(ABC):
    key: str = ""
    label: str = ""
    priority: int = 99  # lower wins when merging duplicates

    @abstractmethod
    def list_competitions(self, lo: date, hi: date, progress: Progress = _noop) -> list[CompetitionRef]:
        """Competitions that may fall inside [lo, hi]."""

    @abstractmethod
    def load(self, ref: CompetitionRef) -> Competition:
        """Download and parse the results of one competition."""
