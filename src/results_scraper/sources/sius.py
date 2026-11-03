"""results.sius.com — SIUS electronic-target results (worldwide).

Structure (ASP.NET / DevExpress grids):
  Championships.aspx[?seo...=pageN...]   20 championships per page, newest first;
                                          row keys (GUIDs) are in the grid state ('keys':[...])
  Events.aspx?Championship=GUID          links ShootEvent.aspx?Championship=GUID&ShootEvent=CODE
  ShootEvent.aspx?...                     documents grid: Phase / Product / Date rows; row keys are
                                          file paths, downloaded through
  DownloadFile.aspx?Championship=GUID&FileName=PATH   (ISSF-layout PDF)

SIUS lists hundreds of championships a year (Swiss club finals, Japanese
national games, ...). As agreed, only international championships are
searched, selected by name.
"""

from __future__ import annotations

import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from urllib.parse import quote

from .. import net
from ..dates import parse_date_range
from ..models import Competition, Table
from ..parsing import parse_cached
from .base import CompetitionRef, Progress, Source, _noop

BASE = "https://results.sius.com/"
PAGE_URL = (
    BASE + "Championships.aspx?seoctl00_ContentPlaceHolder_ASPxGridViewChampionships="
    "page{n}%257csort1%257cd0%257cfilter23%257cHideChampionship%253d%253dfalse"
)
MAX_PAGES = 40
CHAMPIONSHIP_MAX_DAYS = 14  # rows only show the start date

INTERNATIONAL = re.compile(
    r"\b(ISSF|ESC|World|European?|Europa|Euro|Grand\s+Prix|GP|Nordic|Baltic|International|Intershoot|"
    r"Lapua|H&N|Meyton|Polonia|Masped|Pilsen|Junior\s+Cup|Youth\s+League|Champions\s+League|Olympic)\b",
    re.IGNORECASE,
)
NOT_RELEVANT = re.compile(r"\b(Para|WSPS|Asian|Suramericanos|Centroamericanos|Pan\s*Am|GCC|Arab|African|Oceania)\b", re.I)

_ROW = re.compile(r'<tr[^>]*class="dxgvDataRow[^"]*"[^>]*>(.*?)</tr>', re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


def _cells(row_html: str) -> list[str]:
    return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", c))).strip() for c in _CELL.findall(row_html)]


def _grid_keys(page: str, grid: str) -> list[str]:
    m = re.search(re.escape(grid) + r"',\s*'stateObject':\{[^{}]*?'keys':\[([^\]]*)\]", page)
    if not m:
        m = re.search(r"'keys':\[([^\]]*)\]", page)
    if not m or not m.group(1).strip():
        return []
    return [k.strip().strip("'").replace("\\\\", "/").replace("\\", "/") for k in m.group(1).split(",")]


def is_international(name: str) -> bool:
    return bool(INTERNATIONAL.search(name)) and not NOT_RELEVANT.search(name)


class SIUS(Source):
    key = "sius"
    label = "results.sius.com"
    priority = 3

    def list_competitions(self, lo: date, hi: date, progress: Progress = _noop) -> list[CompetitionRef]:
        refs: list[CompetitionRef] = []
        earliest = lo - timedelta(days=CHAMPIONSHIP_MAX_DAYS)
        for n in range(1, MAX_PAGES + 1):
            progress(f"results.sius.com: reading championship list page {n}")
            page = net.fetch_text(BASE + "Championships.aspx" if n == 1 else PAGE_URL.format(n=n))
            rows = _ROW.findall(page)
            keys = _grid_keys(page, "ASPxGridViewChampionships")
            if not rows:
                break
            oldest = None
            for key, row in zip(keys, rows):
                cells = _cells(row)
                if len(cells) < 2:
                    continue
                start, _ = parse_date_range(cells[0], date.today().year)
                if start is None:
                    continue
                oldest = start if oldest is None else min(oldest, start)
                name = cells[1].replace("**", "").strip()
                if not (earliest <= start <= hi) or not is_international(name):
                    continue
                place = ", ".join(c for c in cells[2:4] if c)
                refs.append(
                    CompetitionRef(
                        self.key, name, f"{BASE}Events.aspx?Championship={key}", start,
                        start + timedelta(days=CHAMPIONSHIP_MAX_DAYS - 1), place, extra={"guid": key},
                    )  # fmt: skip
                )
            if oldest is not None and oldest < earliest:
                break
        return refs

    def _rank_list_files(self, guid: str, code: str, ttl) -> list[tuple[str, str]]:
        """(phase label, file path) of the result PDFs of one shoot event."""
        page = net.fetch_text(f"{BASE}ShootEvent.aspx?Championship={guid}&ShootEvent={quote(code)}", ttl)
        grid = page.find("ASPxGridViewShootEventFiles")
        if grid < 0:
            return []
        keys = _grid_keys(page[grid:], "ASPxGridViewShootEventFiles")
        rows = _ROW.findall(page[grid:])
        files = []
        for key, row in zip(keys, rows):
            cells = _cells(row)
            product = cells[1] if len(cells) > 1 else ""
            if re.search(r"rank|result", product, re.I) and key.lower().endswith(".pdf"):
                files.append((cells[0] if cells else "", key))
        return files

    def load(self, ref: CompetitionRef) -> Competition:
        guid = ref.extra["guid"]
        finished = ref.date_end and ref.date_end < date.today() - timedelta(days=7)
        ttl = net.DOCUMENT_TTL if finished else net.LISTING_TTL
        events_page = net.fetch_text(ref.link, ttl)
        codes = list(dict.fromkeys(re.findall(r"ShootEvent\.aspx\?Championship=" + guid + r"&(?:amp;)?ShootEvent=([^\"&<]+)", events_page)))

        def event_tables(code: str) -> tuple[list[Table], list[str]]:
            tables: list[Table] = []
            lines: list[str] = []
            for _phase, path in self._rank_list_files(guid, html.unescape(code), ttl):
                url = f"{BASE}DownloadFile.aspx?Championship={guid}&FileName={quote(path, safe='/')}"
                year = ref.date_start.year if ref.date_start else date.today().year
                doc = parse_cached(url, lambda u=url: net.fetch(u), path.rsplit("/", 1)[-1], year)
                for t in doc.tables:
                    t.link = url
                tables.extend(doc.tables)
                lines.extend(doc.lines)
            return tables, lines

        with ThreadPoolExecutor(max_workers=2) as pool:  # requests are throttled per host anyway
            loaded = list(pool.map(event_tables, codes))
        all_tables = [t for ts, _ in loaded for t in ts]
        all_lines = [ln for _, ls in loaded for ln in ls]

        dated = [t.date_start for t in all_tables if t.date_start]
        start = min(dated) if dated else ref.date_start
        end = max(dated) if dated else ref.date_end
        return Competition(
            name=ref.name, source=self.key, link=ref.link, date_start=start, date_end=end, place=ref.place,
            tables=all_tables, text=all_lines,
        )  # fmt: skip
