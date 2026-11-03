"""Parser for the Estonian protocol layout used by most laskurliit.ee files.

    Kaiu Sügisvõistlus 2026                       <- document title
    16-18.10.2026 Kaiu                            <- date + place
    60l Õhupüss Mehed                             <- category title
    Koht Eesnimi Perenimi S.a. Klubi Seeriad Σ 10* KL   <- header
    I Karl Johannes MÄND-KUUSK 1997 Elva LSK 101,1 ... 611,0 42 M
    4. Robin KALDMA 2010 Põlva LSK ... 608,8 32 I

Team ("võistkondlik") tables list a team per rank, members on the following
lines, and the team total after the last member:

    Koht Võistkond Eesnimi Perenimi Tulemus Σ
    1. Narva LSK 1 Darja KUZMITŠOVA 408,8
    Milana BELOZERSKAYA 407,3
    Valeria SOKOLEN 412,1 1228,2
"""

from __future__ import annotations

import re

from ..dates import parse_date_range
from ..models import Entry, Kind, Person, Table
from .tokens import (
    is_number,
    is_title_word,
    is_upper_word,
    is_year,
    num_value,
    parse_rank,
)

_HEADER_RE = re.compile(r"^(koht|place|rank)\b", re.IGNORECASE)
_TEAM_HEADER_RE = re.compile(r"võistkond|team|klubi\s+tulemus", re.IGNORECASE)
# "QF"/"Q": qualified for the final, printed instead of ranks 1-8; ranked by list order
_QUALIFIED_MARKS = {"QF", "Q", "FQ", "F"}
# record note after the category: "... meesjuuniorid EJR 569 Mart Sepp Ülenurme GSK 03.07.2022. Elva"
_RECORD_TAIL = re.compile(r"(?:^|\s+)[A-Z]{1,4}R\s+\d{2,4}(?:[.,]\d+)?\s.*\d{1,2}\.\s?\d{1,2}\.\d{4}.*$")


_STAGE_LINE = re.compile(
    r"^(?:(?:ringmärk|ilmuv märk|aeglane|kiir|täpsus|precision|rapid|series|seeriad)\s*)+$", re.IGNORECASE
)


_RECORD_MARK = re.compile(r"^(?:[A-Z]{0,3}R|PB|SB)$")


def clean_category(text: str) -> str:
    return _RECORD_TAIL.sub("", text).strip()


def _kind(category: str, header: str) -> Kind:
    c = category.lower()
    running_target = any(w in c for w in ("running target", "liikuv", "jooksev", "metssiga"))  # "mix" = mixed speeds
    if ("mix" in c and not running_target) or "segavõistk" in c or "paar" in c:
        return Kind.MIXED_TEAM
    if "võistk" in c or "team" in c or re.search(r"\bvõistkond\b", header, re.IGNORECASE):
        return Kind.TEAM
    if "finaal" in c or "final" in c:
        return Kind.FINAL
    return Kind.INDIVIDUAL


def _best_number(tokens: list[str]) -> str:
    nums = [t for t in tokens if is_number(t)]
    if not nums:
        return ""
    return max(nums, key=num_value)


def parse_individual_line(tokens: list[str]) -> Person | None:
    """Parse the tokens after the rank of an individual result line."""
    if not tokens:
        return None
    year_idx = next((i for i, t in enumerate(tokens) if i >= 1 and is_year(t)), None)
    if year_idx is not None:
        name_toks = tokens[:year_idx]
        rest = tokens[year_idx + 1 :]
        birth_year = int(tokens[year_idx])
    else:
        i = 0
        while i < len(tokens) and is_title_word(tokens[i]):
            i += 1
        j = i
        while j < len(tokens) and is_upper_word(tokens[j]):
            j += 1
        if j == i:  # no surname in capitals: assume "First Last"
            j = min(2, len(tokens))
        name_toks, rest, birth_year = tokens[:j], tokens[j:], None
    if not name_toks or any(is_number(t) for t in name_toks) or not name_toks[0][:1].isupper():
        return None  # also a category title such as "50 m pistol 60 shots"
    club_toks = []
    for t in rest:
        if is_number(t):
            break
        club_toks.append(t)
    num_toks = rest[len(club_toks) :]
    return Person(
        name=" ".join(name_toks),
        birth_year=birth_year,
        club=" ".join(club_toks),
        result=_best_number(num_toks),
    )


def parse_tail_person(tokens: list[str]) -> tuple[str, Person | None, list[str]]:
    """Parse '<prefix> First [Middle] LAST [year] score [total]' from the end.

    Returns (prefix text, person, trailing numbers).
    """
    end = len(tokens)
    while end > 1 and _RECORD_MARK.match(tokens[end - 1]) and is_number(tokens[end - 2]):
        end -= 1  # "Valeria SOKOLEN 568 1715 EJR": record mark after the total
    nums: list[str] = []
    while end > 0 and is_number(tokens[end - 1]):
        end -= 1
        nums.insert(0, tokens[end])
    j = end
    while j > 0 and is_upper_word(tokens[j - 1]):
        j -= 1
    i = j
    while i > 0 and is_title_word(tokens[i - 1]) and j - i < 3:
        i -= 1
    if j == end or i == j:
        return " ".join(tokens), None, nums
    birth_year = None
    if len(nums) >= 2 and is_year(nums[0]):
        birth_year = int(nums.pop(0))
    person = Person(name=" ".join(tokens[i:end]), birth_year=birth_year, result=nums[0] if nums else "")
    return " ".join(tokens[:i]), person, nums


def _looks_like_entry(line: str) -> bool:
    """A ranked line with an athlete in it (not a title like '60 lasku lamades')."""
    toks = line.split()
    if not toks or parse_rank(toks[0]) is None:
        return False
    person = parse_individual_line(toks[1:])
    if person and (person.birth_year or any(is_upper_word(t) for t in person.name.split())):
        return True
    _, tail, nums = parse_tail_person(toks[1:])
    return tail is not None and bool(nums)  # "50 m pistol ... Open JM, JW" has no score


def _is_doc_header_line(line: str, doc_title: str) -> bool:
    if not line:
        return True
    if line == doc_title:
        return True
    start, _ = parse_date_range(line, 2000)
    return start is not None and len(line) < 60


def parse_estonian(pages: list[list[str]]) -> list[Table]:
    tables: list[Table] = []
    doc_title = next((ln for page in pages for ln in page if ln), "")

    table: Table | None = None  # a table may continue on the next page without a new header
    for page in pages:
        prev_line = ""
        before_prev = ""  # the line before prev_line (title above a record line)
        page_title = ""  # title line at the top of a page whose table has no header row
        fresh = True  # no entry or header seen on this page yet
        for line in page:
            if not line:
                continue
            if not any(c.isalpha() for c in line) or _STAGE_LINE.match(line):
                continue  # header fragment ("10*", "Σ", "Ringmärk Ilmuv märk") between title and header
            if _HEADER_RE.match(line):
                if _HEADER_RE.match(prev_line):  # second header row (e.g. English translation)
                    continue
                header = line
                title_line = prev_line if clean_category(prev_line) else before_prev  # skip "EJFR 434,6 ..." line
                if not _is_doc_header_line(title_line, doc_title) and not _looks_like_entry(title_line):
                    category = clean_category(title_line)
                elif tables:
                    category = tables[-1].category  # table continues from previous page
                else:
                    category = doc_title
                kind = _kind(category, header)
                if tables and tables[-1].category == category and tables[-1].kind == kind:
                    table = tables[-1]
                else:
                    table = Table(category=category, kind=kind)
                    tables.append(table)
                before_prev, prev_line = prev_line, line
                fresh = False
                continue

            before_prev, prev_line = prev_line, line
            toks = line.split()
            if parse_rank(toks[0]) is None and _is_doc_header_line(line, doc_title):
                continue  # repeated page title / date, not a team member line
            ranked = _looks_like_entry(line) or (toks[0] in _QUALIFIED_MARKS and len(toks) > 2)
            if fresh and not ranked:
                _, member, nums = parse_tail_person(toks)
                if (member is None or not nums) and clean_category(line):
                    page_title = clean_category(line)  # the line nearest the results
                continue_member = member is not None and bool(nums)
                if not continue_member:
                    continue
            if fresh and ranked and page_title and tables:  # only in real protocols (a header was seen)
                # "50 m püss 3x20 lasku meesjuuniorid VÕISTKONDLIK" followed directly by results
                table = Table(category=page_title, kind=_kind(page_title, ""))
                tables.append(table)
            if ranked:
                fresh = False
            if table is None:
                continue
            rank = parse_rank(toks[0])
            team = table.kind in (Kind.TEAM, Kind.MIXED_TEAM)
            if rank is None and toks[0] in _QUALIFIED_MARKS and len(toks) > 2:
                rank = len(table.entries) + 1

            if not team:
                if rank is None:
                    continue
                person = parse_individual_line(toks[1:])
                if person:
                    table.entries.append(Entry(rank=rank, result=person.result, persons=[person]))
                continue

            # team tables
            if rank is not None:
                prefix, person, nums = parse_tail_person(toks[1:])
                if person is None and not nums:
                    continue  # next category title, e.g. "30 l. Õhupüstol Segapaarid"
                entry = Entry(rank=rank, result="", team_name=prefix)
                table.entries.append(entry)
            elif table.entries:
                prefix, person, nums = parse_tail_person(toks)
                entry = table.entries[-1]
                if person is None and nums and not entry.result:
                    entry.result = nums[-1]
            else:
                continue
            if person:
                entry.persons.append(person)
                if len(nums) >= 2:
                    entry.result = nums[-1]
            elif rank is not None and nums:
                entry.result = nums[-1]

    for t in tables:
        if t.kind in (Kind.TEAM, Kind.MIXED_TEAM):
            for e in t.entries:
                if not e.result and e.persons:
                    total = sum(num_value(p.result) for p in e.persons if is_number(p.result))
                    e.result = f"{total:.1f}".rstrip("0").rstrip(".") if total else ""
    return [t for t in tables if t.entries]
