"""protokollitaja.eu — electronic-target results with a JSON API.

API (https://www.protokollitaja.eu/api/v1):
  /competitions                     -> [{id, competitionName, timeAndPlace, startDate, endDate, country}]
  /competitions/{id}                -> [{id, eventName}]
  /competitions/{id}/{eventId}      -> {eventName, competitors: [{firstName, lastName, birthYear, club,
                                        totalResult, innerTens, finals, subtotals...}]}

Competitors come in ranking order. A "0" total means the shooter did not
compete. Some competitions carry a dummy startDate of 2000-01-01; their real
date is in `timeAndPlace`. The site is a single-page app without per-competition
URLs, so rows link to the home page.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from .. import net
from ..dates import overlaps, parse_date_range, parse_iso
from ..models import Competition, Entry, Kind, Person, Table, has_score
from .base import CompetitionRef, Progress, Source, _noop

API = "https://www.protokollitaja.eu/api/v1"
SITE = "https://protokollitaja.eu/"


def _comp_dates(c: dict) -> tuple[date | None, date | None]:
    start, end = parse_iso(c.get("startDate")), parse_iso(c.get("endDate"))
    if start is None or start.year < 2005:
        year = date.today().year
        m = re.search(r"\b(20\d\d)\b", c.get("timeAndPlace", "") + " " + c.get("competitionName", ""))
        if m:
            year = int(m.group(1))
        # "01.01.2000 30.-31.10.2026, Narva": skip the dummy date
        text = re.sub(r"\b01\.01\.2000\b", "", c.get("timeAndPlace", ""))
        start, end = parse_date_range(text, year)
    return start, end


def _place(c: dict) -> str:
    text = c.get("timeAndPlace", "")
    text = re.sub(r"[\d.\-–\s]+(?:\d{4})?[,\s]*", " ", text, count=1)
    return text.strip(" ,")


def _num(text: str) -> float:
    try:
        return float(str(text).replace(",", "."))
    except ValueError:
        return 0.0


class Protokollitaja(Source):
    key = "protokollitaja"
    label = "protokollitaja.eu"
    priority = 1

    def list_competitions(self, lo: date, hi: date, progress: Progress = _noop) -> list[CompetitionRef]:
        progress("protokollitaja.eu: reading competition list")
        comps = net.fetch_json(f"{API}/competitions")
        refs = []
        for c in comps:
            start, end = _comp_dates(c)
            if not overlaps(start, end, lo, hi):
                continue
            name = c.get("competitionName", "").strip()
            refs.append(
                CompetitionRef(self.key, name, SITE, start, end, _place(c), extra={"id": c["id"], "country": c.get("country")})
            )
        return refs

    def load(self, ref: CompetitionRef) -> Competition:
        cid = ref.extra["id"]
        # results of finished competitions do not change; recent ones might
        finished = ref.date_end and ref.date_end < date.today() - timedelta(days=14)
        ttl = net.DOCUMENT_TTL if finished else net.LISTING_TTL
        events = net.fetch_json(f"{API}/competitions/{cid}", ttl)
        tables: list[Table] = []
        for ev in events:
            data = net.fetch_json(f"{API}/competitions/{cid}/{ev['id']}", ttl)
            tables.extend(self._tables(data))
        return Competition(
            name=ref.name, source=self.key, link=ref.link, date_start=ref.date_start, date_end=ref.date_end,
            place=ref.place, tables=tables,
        )  # fmt: skip

    @staticmethod
    def _tables(data: dict) -> list[Table]:
        name = (data.get("eventName") or "").strip()
        people = data.get("competitors") or []
        qual = Table(category=name, kind=Kind.INDIVIDUAL)
        rank = 0
        for c in people:
            total = str(c.get("totalResult") or "")
            if has_score(total):
                rank += 1
            year = str(c.get("birthYear") or "")
            person = Person(
                name=f"{c.get('firstName', '')} {c.get('lastName', '')}".strip(),
                birth_year=int(year) if year.isdigit() and len(year) == 4 else None,
                club=c.get("club") or "",
                result=total,
            )
            qual.entries.append(Entry(rank=rank if has_score(total) else None, result=total, persons=[person]))
        tables = [qual] if qual.entries else []

        finalists = [(e, c) for e, c in zip(qual.entries, people) if has_score(str(c.get("finals") or ""))]
        if finalists:
            final = Table(category=f"{name} – Final", kind=Kind.FINAL)
            finalists.sort(key=lambda ec: _num(ec[1]["finals"]), reverse=True)
            for i, (e, c) in enumerate(finalists, start=1):
                p = e.persons[0]
                final.entries.append(
                    Entry(rank=i, result=str(c["finals"]), persons=[Person(p.name, p.birth_year, p.club, str(c["finals"]))])
                )
            tables.append(final)
        return tables
