"""Fallback parser for result files that follow neither the Estonian protocol
nor the ISSF layout (small club competitions, Latvian/Lithuanian protocols,
cup standings, shotgun sheets).

Used only when the specific parsers find nothing in a document. A result line
is: optional rank and bib/start number, a name of 2+ words, then 2+ numbers:

    1 Rainer Kuusik 2009 Hiiumaa 94.4 96.8 96.8 99.5 387.5
    1 35 Andrei Petrov M Skeet 23 25 22 70 24 23 47 117 F
    1 Alise KALNIŅA Tukums (LAT) 2008 96 94 96 286 4
    Edik Lillemets 98 98 98 97 99 100 590 24 I        (no rank: list order)

The result is the largest number (birth years excluded); the category is the
nearest meaningful text line above the results. If a table has ranks, unranked
result lines belong to the entry above (pairs / teams, e.g. "Muna & Kana").
"""

from __future__ import annotations

import re

from ..dates import parse_date_range
from ..models import Entry, Kind, Person, Table, has_score
from .tokens import is_number, is_year, num_value, parse_rank

_HEADER_WORDS = {
    "nimi", "eesnimi", "perenimi", "perekonnanimi", "nimi,", "name", "vārds", "uzvārds", "pavardė", "vardas",
    "koht", "vieta", "place", "rank", "nr", "nr.", "klubi", "klass", "class", "tulemus", "summa", "suma",
    "total", "kokku", "seeriad", "sünd.", "sünniaasta", "s.a.", "gads", "komanda", "bib", "kategorija",
    "kateg.", "vals.", "pavardė,", "taškai", "points", "rezultāti", "results", "tulemused", "partic.",
    "įvykdyta", "įvykdita", "reitingo", "vieta",
}  # fmt: skip
_GLUED_RANK = re.compile(r"^(\d{1,3})(?=[^\W\d_]{2})")
_ROMAN_ONLY = re.compile(r"^(?:[IVX]+\s*)+\*?$")
_WORD = re.compile(r"^[^\W\d_][\w'’\-.]*$", re.UNICODE)
_FINAL = re.compile(r"\b(final|finaal|fināls|finalas)\b", re.I)


def _is_headerish(line: str) -> bool:
    toks = [t.lower().strip(":") for t in line.split()]
    hits = sum(t in _HEADER_WORDS for t in toks)
    return hits >= 2 or (hits >= 1 and hits == len(toks)) or bool(_ROMAN_ONLY.match(line))


def parse_result_line(line: str) -> tuple[int | None, Person, int] | None:
    """(rank, person, number of score columns) for a result line, else None."""
    if _is_headerish(line):
        return None
    toks = _GLUED_RANK.sub(r"\1 ", line).split()
    if len(toks) < 4:
        return None
    rank = parse_rank(toks[0])
    i = 1 if rank is not None else 0
    if rank is not None and i < len(toks) and toks[i].isdigit() and len(toks[i]) <= 4 and not is_year(toks[i]):
        i += 1  # bib / start number
    name: list[str] = []
    while i < len(toks) and len(name) < 5 and _WORD.match(toks[i]) and not is_number(toks[i]):
        name.append(toks[i])
        i += 1
    if len(name) < 2 or not any(t[0].isupper() for t in name):
        return None
    rest = toks[i:]
    birth_year = None
    scores: list[str] = []
    club: list[str] = []
    for t in rest:
        if is_year(t) and birth_year is None and not scores:
            birth_year = int(t)
        elif is_number(t):
            scores.append(t)
        elif not scores:
            club.append(t)
    if len(scores) < 2:
        return None
    best = max(scores, key=num_value)
    return rank, Person(name=" ".join(name), birth_year=birth_year, club=" ".join(club), result=best), len(scores)


def parse_loose(pages: list[list[str]]) -> list[Table]:
    lines = [ln for page in pages for ln in page if ln]
    if not lines:
        return []
    doc_title = lines[0]
    tables: list[Table] = []
    table: Table | None = None
    texts: list[str] = []  # non-result lines since the last result line
    category = doc_title
    ranked = False
    last_ncols = 0  # score columns of the previous ranked line

    def heading(block: list[str]) -> str | None:
        useful = []
        for ln in block:
            if ln == doc_title or _is_headerish(ln):
                continue
            d, _ = parse_date_range(ln, 2000)
            if d and len(ln) < 40:
                continue
            useful.append(ln)
        if not useful:
            return None
        last = useful[-1]
        if last[:1].islower() and len(useful) >= 2:  # "20 l toelt" + "kuni 10. a"
            return f"{useful[-2]} {last}"
        return last

    for line in lines:
        parsed = parse_result_line(line)
        if parsed is None:
            texts.append(line)
            continue
        rank, person, ncols = parsed
        if table is None or texts:
            new_heading = heading(texts)
            if new_heading:
                if new_heading[:1].islower() and table is not None and not texts[-1:] == [new_heading]:
                    category = f"{category.split(' – ')[0]} – {new_heading}"
                else:
                    category = new_heading
            if table is None or texts:
                table = Table(category=category, kind=Kind.FINAL if _FINAL.search(category) else Kind.INDIVIDUAL)
                tables.append(table)
                ranked = rank is not None
            texts = []
        if rank is None and ranked and table.entries and ncols == last_ncols - 1:
            # partner in a pair / team: same layout minus the team-total column
            table.entries[-1].persons.append(person)
            table.kind = Kind.TEAM
            continue
        if rank is not None:
            last_ncols = ncols
        if rank is None:
            rank = sum(1 for e in table.entries if has_score(e.result)) + 1 if has_score(person.result) else None
        table.entries.append(Entry(rank=rank, result=person.result, persons=[person]))
    return [t for t in tables if len(t.entries) >= 1]
