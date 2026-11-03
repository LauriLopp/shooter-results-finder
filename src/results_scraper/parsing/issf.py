"""Parser for ISSF-style result books (SIUS "OFFICIAL ISSF RESULTS PROVIDER").

Each event section starts with a block like

    [Nordic Shooting Championship 2026]
    RESULTS | FINAL RESULTS | INTERMEDIATE RESULTS
    50m RIFLE 3 POSITIONS MEN JUNIOR           <- event
    INDIVIDUAL | TEAM | GOLD MEDAL MATCH | Junior | Qualification ...   <- phase (optional)
    [Elva/Otepää]
    SUN 23 AUG 2026, START TIME 09:00          <- date

and continues over the following pages until the next such block.

Entry lines seen in the wild:
    1 1100 MARTIN Louis FRA Kneeling 95 97 192        individual (rank, bib)
    1 33 197 HANSEN Ingrid Solberg NOR 98 ... 580-19x   (rank, FP, bib)
    1 JENSEN Mikkel Holm DEN 22 24 25 24 24 119   shotgun (no bib)
    1 197 HANSEN NOR 50.2 97.9 ... 236.0            final; given name on next line
    34 169 LIEPA Ilze LAT DNS                       no rank (FP, bib)
    1 FRA - France  /  2 EST 2 - Estonia 2 858-30x QG  team
    1064 KUZMITŠOVA Darja Kneeling 146              team member (bib)
    KUZMITŠOVA Darja                                team member (medal match)
"""

from __future__ import annotations

import re

from ..dates import parse_date_range
from ..models import Entry, Kind, Person, Table
from .tokens import is_number, is_title_word, is_upper_word, num_value

_SECTION_START_RE = re.compile(r"^(?:(?:INTERMEDIATE|FINAL|UNOFFICIAL)\s+)*RESULTS$")
_TABLE_HEADER = re.compile(r"^(Rank|Rk|RRaannkk|NOC|Series|Bib|Sub|Code|Gold Medal|Bronze Medal)\b")
_NOC = re.compile(r"^[A-Z]{3}$")
_X_SCORE = re.compile(r"\b(\d{2,4}(?:\.\d)?)-\s?(\d{1,3})x\b")
_TEAM_LINE = re.compile(r"^(\d{1,3})\s+([A-Z]{3})(?:\s+\d{1,2})?\s+-\s+(.+)$")
# team without a country name, e.g. neutral athletes: "2 AIN 22 196.5 196.4 195.7 588.6 QS"
_BARE_TEAM_LINE = re.compile(r"^(\d{1,3})\s+([A-Z]{3}(?:\s+\d{1,2})?)\s+(?=\d+[.,]\d|\d{2,4}\b)")
_PRE = r"(?:\d{1,5}|[A-Z]\d{0,2})\s+"  # firing point / bib columns ("33 197", "J 0")
_ENTRY_START = re.compile(rf"^(\d{{1,3}})\s+((?:{_PRE}){{0,2}})(\S.*)$")
_UNRANKED_START = re.compile(rf"^((?:{_PRE}){{1,2}})(\S.*\b(?:DNS|DNF|DSQ)\b.*)$")
_MEMBER_START = re.compile(r"^(\d{1,5})\s+(\S.+)$")
_GLUED_BIB = re.compile(r"^((?:\d{1,3}\s+)?\d{1,5})(?=[A-ZÀ-ÖØ-Þ]{2})")
_TOTAL_ATHLETES = re.compile(r"Total number of athletes:\s*(\d+)", re.IGNORECASE)
_MEDAL_SUFFIX = re.compile(r"(\d)(Gold|Silver|Bronze)\b")
_TEAM_NAME_END = re.compile(r"\s+(?=\d{2,4}(?:\.\d)?-\s?\d+x|\d{2,}(?:\.\d+)?\b)")
_NOT_RESULT = re.compile(r"\b(DNS|DNF|DSQ)\b")
_PHASE_WORDS = ("INDIVIDUAL", "TEAM", "QUALIFICATION", "FINAL", "MEDAL MATCH", "ELIMINATION", "STAGE", "PART")
_STAGE_WORDS = {"kneeling", "prone", "standing", "precision", "rapid", "slow", "fast", "stage", "series"}
_SKIP_PREFIXES = ("Version of", "OFFICIAL ISSF", "Legend", "History", "Release:", "Summary", "Number of",
                  "Bib No", "Protest", "Total")  # fmt: skip


def is_issf_document(pages: list[list[str]]) -> bool:
    text = "\n".join(ln for page in pages[:60] for ln in page)
    return "OFFICIAL ISSF RESULTS PROVIDER" in text or bool(re.search(r"^(Rank|Rk) .*Bib", text, re.MULTILINE))


def is_issf_page(lines: list[str]) -> bool:
    for ln in lines:
        if ln.startswith("OFFICIAL ISSF RESULTS PROVIDER") or _SECTION_START_RE.match(ln):
            return True
        if re.match(r"^(Rank|Rk)\b.*\bBib\b", ln):
            return True
    return False


def _split_name(toks: list[str]) -> tuple[list[str], list[str]]:
    """Split 'MARTIN Louis FRA Kneeling 95' into (name tokens, rest).

    Surname(s) in capitals come first, then given names; the name ends at the
    NOC code / number / stage word that follows.
    """
    i = 0
    while i < len(toks) and is_upper_word(toks[i]) and not (i > 0 and _NOC.match(toks[i]) and not _has_title_after(toks, i)):
        i += 1
    j = i
    while j < len(toks) and is_title_word(toks[j]) and toks[j].lower() not in _STAGE_WORDS:
        j += 1
    if i == 0:
        return [], toks
    return toks[:j], toks[j:]


def _has_title_after(toks: list[str], i: int) -> bool:
    """Is there a given name after position i (before any number)?"""
    for t in toks[i + 1 :]:
        if is_number(t):
            return False
        if is_title_word(t) and t.lower() not in _STAGE_WORDS:
            return True
    return False


def _score(text: str) -> str:
    xs = _X_SCORE.findall(text)
    if xs:
        total, inner = xs[-1]
        return f"{total}-{inner}x"
    nums = [t for t in text.split() if is_number(t)]
    return nums[-1] if nums else ""


def _best_score(text: str) -> str:
    xs = _X_SCORE.findall(text)
    if xs:
        total, inner = max(xs, key=lambda m: num_value(m[0]))
        return f"{total}-{inner}x"
    nums = [t for t in text.split() if is_number(t)]
    return max(nums, key=num_value) if nums else ""


def _is_mixed(event: str) -> bool:
    """Mixed team events; youth "DUET" events pair a woman and a man."""
    e = event.upper()
    return "MIXED" in e or ("DUET" in e and not re.search(r"\b(WO)?MEN\b", e))


class _Section:
    def __init__(self, event: str, phase: str, header: str, date_start):
        self.event, self.phase, self.header = event, phase, header
        self.is_final = "FINAL" in header or "FINAL" in phase.upper() or "MEDAL MATCH" in phase.upper()
        self.intermediate = "INTERMEDIATE" in header
        p = phase.upper()
        if _is_mixed(event):
            kind = Kind.MIXED_TEAM
        elif p.startswith("TEAM") or " TEAM" in f" {p}":
            kind = Kind.TEAM
        elif self.is_final:
            kind = Kind.FINAL
        else:
            kind = Kind.INDIVIDUAL
        if self.is_final and not phase:
            phase = "Final"
        label = event if not phase or p in ("INDIVIDUAL", "JUNIOR") else f"{event} – {phase.title()}"
        self.table = Table(category=label, kind=kind, date_start=date_start)
        self.decided = kind != Kind.INDIVIDUAL or phase.upper() == "INDIVIDUAL"
        self.block: list[str] = []
        self.member_block: list[str] = []
        self.entry: Entry | None = None
        self.member: Person | None = None

    @property
    def team(self) -> bool:
        return self.table.kind in (Kind.TEAM, Kind.MIXED_TEAM)

    def make_team(self):
        if not self.team:
            self.table.kind = Kind.MIXED_TEAM if _is_mixed(self.event) else Kind.TEAM
            if "Team" not in self.table.category:
                self.table.category += " – Team"
        self.decided = True

    def close_member(self):
        if self.member is not None:
            self.member.result = _score(" ".join(self.member_block))
        self.member, self.member_block = None, []

    def close_entry(self):
        self.close_member()
        e = self.entry
        if e is not None:
            first = self.block[0] if self.block else ""
            text = " ".join(self.block)
            if _NOT_RESULT.search(first):
                e.result, e.rank = _NOT_RESULT.search(first).group(1), None
            elif self.is_final:
                # "Final shots: 10.9 10.3 ... 331.9" carries the final total when the
                # first line repeats the qualification score
                shots = next((ln for ln in self.block if ln.startswith("Final shots")), "")
                nums = [t for t in (shots or first).split() if is_number(t)]
                e.result = nums[-1] if nums else _score(text)
            elif self.team:
                e.result = _best_score(text)
            else:
                e.result = _score(text)
            if not self.team and e.persons:
                e.persons[0].result = e.result
        self.entry, self.block = None, []


def _read_section_header(lines: list[str], i: int, default_year: int):
    """Parse the block after a RESULTS line; returns (section, next index)."""
    header = lines[i]
    event = lines[i + 1] if i + 1 < len(lines) else ""
    phase, when = "", None
    k = i + 2
    while k < len(lines) and k < i + 7 and not _TABLE_HEADER.match(lines[k]):
        ln = lines[k]
        d, _ = parse_date_range(ln, default_year)
        if d and when is None:
            when = d
        elif not phase and any(w in ln.upper() for w in _PHASE_WORDS) and "." not in ln and not ln.endswith("-"):
            phase = ln
        k += 1
    return _Section(event, phase, header, when), k


def parse_issf(pages: list[list[str]], default_year: int) -> list[Table]:
    sections: list[_Section] = []
    sec: _Section | None = None
    lines = [ln for page in pages for ln in page if ln]
    before_start = {k - 1 for k, ln in enumerate(lines) if _SECTION_START_RE.match(ln)}
    before_start |= {k - 1 for k in before_start if k >= 1 and lines[k] in ("REVISED", "UNOFFICIAL")}
    i = 0
    while i < len(lines):
        line = lines[i]
        if i in before_start:
            i += 1
            continue
        if _SECTION_START_RE.match(line) and i + 1 < len(lines):
            if sec:
                sec.close_entry()
            sec, i = _read_section_header(lines, i, default_year)
            sections.append(sec)
            continue
        i += 1
        if sec is None or not line:
            continue
        line = _GLUED_BIB.sub(r"\1 ", _MEDAL_SUFFIX.sub(r"\1 \2", line))
        m = _TOTAL_ATHLETES.search(line)
        if m:
            sec.table.participants = int(m.group(1))
            continue
        if line.startswith(_SKIP_PREFIXES) or _TABLE_HEADER.match(line):
            continue

        m = _TEAM_LINE.match(line)
        if m and sec.decided and not sec.team and not sec.is_final:
            sec.close_entry()
            sec = _Section(sec.event, "TEAM", "RESULTS", sec.table.date_start)
            sections.append(sec)
        if m and (sec.team or not sec.decided):
            sec.make_team()
            sec.close_entry()
            country = _TEAM_NAME_END.split(m.group(3))[0].strip()
            sec.entry = Entry(rank=int(m.group(1)), result="", team_name=f"{m.group(2)} - {country}")
            sec.table.entries.append(sec.entry)
            sec.block = [line]
            continue
        bare = _BARE_TEAM_LINE.match(line) if sec.team else None
        if bare:
            sec.close_entry()
            sec.entry = Entry(rank=int(bare.group(1)), result="", team_name=bare.group(2))
            sec.table.entries.append(sec.entry)
            sec.block = [line[bare.end():]]
            continue

        if sec.team:
            if sec.entry is None:
                continue
            m = _MEMBER_START.match(line)
            if m:
                name_toks, rest = _split_name(m.group(2).split())
                if name_toks:
                    sec.close_member()
                    sec.member = Person(name=" ".join(name_toks))
                    sec.entry.persons.append(sec.member)
                    sec.member_block = [" ".join(rest)]
                    continue
            toks = line.split()
            if toks and not any(c.isdigit() for c in line) and any(is_upper_word(t) for t in toks):
                sec.close_member()
                sec.entry.persons.append(Person(name=line))  # medal-match member list
                continue
            (sec.member_block if sec.member is not None else sec.block).append(line)
            continue

        m = _ENTRY_START.match(line)
        unranked = None if m else _UNRANKED_START.match(line)
        if m or unranked:
            rest_text = m.group(3) if m else unranked.group(2)
            name_toks, rest = _split_name(rest_text.split())
            if name_toks:
                sec.close_entry()
                if m and int(m.group(1)) == 1 and any(e.rank for e in sec.table.entries):
                    # ranking restarts: a second list (e.g. after more rounds) in the same section
                    sec = _Section(sec.event, sec.phase, sec.header, sec.table.date_start)
                    sections.append(sec)
                sec.decided = True
                noc = rest[0] if rest and _NOC.match(rest[0]) else ""
                sec.entry = Entry(rank=int(m.group(1)) if m else None, result="",
                                  persons=[Person(name=" ".join(name_toks), club=noc)])  # fmt: skip
                sec.table.entries.append(sec.entry)
                sec.block = [" ".join(rest[1:] if noc else rest)]
                continue
        if sec.entry is not None:
            person = sec.entry.persons[0] if sec.entry.persons else None
            toks = line.split()
            if person and len(sec.block) == 1 and not any(is_title_word(t) for t in person.name.split()):
                given = []
                for t in toks:
                    if not is_title_word(t):
                        break
                    given.append(t)
                if given:  # final layout: given name on the line below the surname
                    person.name += " " + " ".join(given)
                    toks = toks[len(given) :]
            sec.block.append(" ".join(toks))
    if sec:
        sec.close_entry()

    # Shotgun junior qualifications may only exist as "intermediate" lists;
    # keep those when the event has no other qualification table.
    final_quals = {s.event for s in sections if not s.intermediate and s.table.kind == Kind.INDIVIDUAL and s.table.entries}
    best_intermediate: dict[str, _Section] = {}
    for s in sections:
        if s.intermediate and s.table.kind == Kind.INDIVIDUAL and s.table.entries and s.event not in final_quals:
            cur = best_intermediate.get(s.event)
            if cur is None or _top(s.table) > _top(cur.table):
                best_intermediate[s.event] = s
    keep = {id(s) for s in best_intermediate.values()}
    return [s.table for s in sections if s.table.entries and (not s.intermediate or id(s) in keep)]


def _top(table: Table) -> float:
    nums = [num_value(m) for e in table.entries for m in re.findall(r"\d+(?:\.\d+)?", e.result)[:1]]
    return max(nums, default=0.0)
