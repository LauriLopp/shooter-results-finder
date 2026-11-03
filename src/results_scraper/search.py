"""Search orchestration: list competitions, load them once, match all athletes."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime

from .dates import overlaps
from .models import Competition, Kind, ResultRow, has_score
from .names import POSSIBLE, AthleteQuery, find_in_text, normalize
from .sources.base import CompetitionRef, Source

log = logging.getLogger(__name__)

MAX_ATHLETES = 5
WORKERS = 4

ProgressFn = Callable[[float, str], None]


@dataclass
class AthleteReport:
    """Everything the user gets for one athlete: results plus a search log."""

    query: AthleteQuery
    rows: list[ResultRow] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    @property
    def confirmed(self) -> list[ResultRow]:
        return [r for r in self.rows if not r.possible]

    @property
    def possible(self) -> list[ResultRow]:
        return [r for r in self.rows if r.possible]


@dataclass
class SearchResult:
    lo: date
    hi: date
    reports: list[AthleteReport]
    sources_checked: list[str]
    competitions_checked: int
    errors: list[str]
    log: list[str]


def match_competition(comp: Competition, athlete: AthleteQuery) -> list[ResultRow]:
    rows = []
    for table in comp.tables:
        participants = table.participant_count
        for entry in table.entries:
            for person in entry.persons:
                m = athlete.match(person.name, person.birth_year)
                if m is None:
                    continue
                team = table.kind in (Kind.TEAM, Kind.MIXED_TEAM)
                if not has_score(entry.result) and not (team and has_score(person.result)):
                    continue  # did not start / no result
                rows.append(
                    ResultRow(
                        athlete=athlete.name,
                        competition=comp.name,
                        date_start=comp.date_start,
                        date_end=comp.date_end,
                        category=table.category,
                        kind=table.kind,
                        result=entry.result,
                        rank=entry.rank,
                        participants=participants or None,
                        link=table.link or comp.link,
                        source=comp.source,
                        team=entry.team_name,
                        own_result=person.result if team else "",
                        matched_name=person.name,
                        date_approx=comp.date_approx,
                        possible=m.level == POSSIBLE,
                        notes=m.note,
                    )
                )
    return _promote_same_competition(rows)


def _promote_same_competition(rows: list[ResultRow]) -> list[ResultRow]:
    """A misspelling ("BÄRTEL Anna") in a competition where the athlete is
    confirmed in another event is the same person: promote it to confirmed.
    Not within one event, where a similar name is a different athlete."""
    confirmed_cats = {r.category for r in rows if not r.possible}
    if not confirmed_cats:
        return rows
    for r in rows:
        if r.possible and r.category not in confirmed_cats:
            r.possible = False
            r.notes = f"Name in source: {r.matched_name} (spelling differs; same athlete confirmed in another event here)"
    return rows


UNREAD_NOTE = "Name found in the document, but the result could not be read automatically – check the link. Text: "


def unread_row(comp: Competition, athlete: AthleteQuery, norm_lines: list[str] | None = None) -> ResultRow | None:
    """A row for a competition whose document names the athlete although no
    result table could be matched (unusual layout)."""
    if not comp.text:
        return None
    line = find_in_text(athlete, comp.text, norm_lines)
    if line is None:
        return None
    snippet = line if len(line) <= 120 else line[:117] + "…"
    return ResultRow(
        athlete=athlete.name, competition=comp.name, date_start=comp.date_start, date_end=comp.date_end,
        category="", kind=Kind.UNREAD, result="", rank=None, participants=None, link=comp.link,
        source=comp.source, matched_name="", date_approx=comp.date_approx, notes=UNREAD_NOTE + f"“{snippet}”",
    )  # fmt: skip


def drop_covered_unread(rows: list[ResultRow]) -> list[ResultRow]:
    """An athlete cannot be at two competitions at once: drop a 'not read' row
    when another source has real results for the same days (e.g. a European
    Championship result book on laskurliit that is also on SIUS)."""
    real = [r for r in rows if r.kind != Kind.UNREAD and not r.possible and r.date_start]
    keep = []
    for r in rows:
        if r.kind == Kind.UNREAD and r.date_start and not r.date_approx:
            end = r.date_end or r.date_start
            if any(
                x.source != r.source
                and (x.date_start - end).days <= 1
                and (r.date_start - (x.date_end or x.date_start)).days <= 1
                for x in real
            ):
                continue
        keep.append(r)
    return keep


def _sort_key(r: ResultRow):
    return (r.date_start or date.min, r.competition, list(Kind).index(r.kind), r.category)


def search(
    athletes: Iterable[AthleteQuery],
    lo: date,
    hi: date,
    sources: list[Source],
    progress: ProgressFn | None = None,
) -> SearchResult:
    from .dedupe import merge_duplicates

    athletes = [a for a in athletes if a.query_tokens][:MAX_ATHLETES]
    reports = [AthleteReport(a) for a in athletes]
    run_log: list[str] = []
    errors: list[str] = []

    def say(frac: float, msg: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        run_log.append(f"{stamp}  {msg}")
        log.info(msg)
        if progress:
            progress(min(max(frac, 0.0), 1.0), msg)

    say(0.0, f"Searching {lo:%d.%m.%Y}–{hi:%d.%m.%Y} for: " + ", ".join(a.name for a in athletes))

    # 1. list competitions from every source
    refs: list[tuple[Source, CompetitionRef]] = []
    for i, src in enumerate(sources):
        try:
            found = src.list_competitions(lo, hi, lambda m: say(0.05 + 0.1 * i / max(len(sources), 1), m))
            say(0.05 + 0.1 * (i + 1) / max(len(sources), 1), f"{src.label}: {len(found)} competitions in period")
            refs.extend((src, r) for r in found)
        except Exception as exc:
            msg = f"{src.label}: could not read competition list ({exc})"
            errors.append(msg)
            say(0.1, "ERROR " + msg)

    # 2. load (download + parse) each competition once
    comps: list[Competition] = []
    done = 0
    # One pool per source: a slow, rate-limited site (SIUS) must not hold up
    # the others, and gets only one competition at a time.
    pools = {src.key: ThreadPoolExecutor(max_workers=1 if src.key == "sius" else WORKERS) for src in sources}
    try:
        futures = {pools[src.key].submit(src.load, ref): (src, ref) for src, ref in refs}
        for fut in as_completed(futures):
            src, ref = futures[fut]
            done += 1
            frac = 0.15 + 0.8 * done / max(len(futures), 1)
            try:
                comp = fut.result()
            except Exception as exc:
                msg = f"{src.label}: {ref.name}: could not load results ({exc})"
                errors.append(msg)
                say(frac, "ERROR " + msg)
                continue
            if comp.date_start and not comp.date_approx and not overlaps(comp.date_start, comp.date_end, lo, hi):
                say(frac, f"{src.label}: {ref.name}: outside period, skipped")
                continue
            comps.append(comp)
            say(frac, f"{src.label}: {ref.name}: {len(comp.tables)} result tables")
    finally:
        for pool in pools.values():
            pool.shutdown(wait=False, cancel_futures=True)

    # 3. match every athlete against every competition
    norm_text = {id(c): [normalize(ln) for ln in c.text] for c in comps}
    for rep in reports:
        rows: list[ResultRow] = []
        for comp in comps:
            found = match_competition(comp, rep.query)
            if found:
                rep.log.append(f"{comp.source}: {comp.name} ({len(found)} result rows)")
            else:
                unread = unread_row(comp, rep.query, norm_text[id(comp)])
                if unread:
                    found = [unread]
                    rep.log.append(f"{comp.source}: {comp.name}: name found, but no result could be read – check {comp.link}")
            rows.extend(found)
        rows = drop_covered_unread(rows)
        merged, dropped = merge_duplicates(rows, {s.key: s.priority for s in sources})
        for d in dropped:
            rep.log.append(f"duplicate removed: {d}")
        rep.rows = sorted(merged, key=_sort_key)
        n_possible = sum(r.possible for r in rep.rows)
        rep.log.insert(0, f"{len(rep.rows) - n_possible} results found for {rep.query.name}"
                          + (f", plus {n_possible} possible matches to check" if n_possible else ""))
    say(1.0, f"Done: checked {len(comps)} competitions from {len(sources)} sources")

    return SearchResult(
        lo=lo,
        hi=hi,
        reports=reports,
        sources_checked=[s.label for s in sources],
        competitions_checked=len(comps),
        errors=errors,
        log=run_log,
    )
