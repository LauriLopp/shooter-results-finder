"""laskurliit.ee — the Estonian Shooting Sport Federation (main source).

Each year has a page ("Tulemused 2026") linking result files (PDF/XLS/XLSX)
with link texts like "Kaiu Sügisvõistlus 18.10 Kaiu". The year pages have
irregular URLs (tulemused-2023-2, 2016-tulemused-2), so they are discovered
from the site menu.
"""

from __future__ import annotations

import html
import re
from datetime import date, timedelta
from urllib.parse import unquote, urljoin

from .. import net
from ..dates import (
    _CROSS_MONTH,
    _SAME_MONTH,
    _SINGLE,
    overlaps,
    parse_date_range,
)
from ..models import Competition
from ..parsing import parse_cached
from .base import CompetitionRef, Progress, Source, _noop

HOME = "https://laskurliit.ee/"
_LINK = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
_YEAR_LINK = re.compile(r"Tulemused\s+(\d{4})", re.I)
_DOC_EXT = re.compile(r"\.(pdf|xlsx?|xlsm)(?:$|\?)", re.I)
_UPLOAD_MONTH = re.compile(r"/uploads/(\d{4})/(\d{2})/")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def split_link_text(text: str, default_year: int) -> tuple[str, date | None, date | None, str]:
    """'Kaiu Sügisvõistlus 18.10 Kaiu' -> ('Kaiu Sügisvõistlus', 18.10, 18.10, 'Kaiu')."""
    start, end = parse_date_range(text, default_year)
    if start is None:
        return text.strip(" ,"), None, None, ""
    for rx in (_CROSS_MONTH, _SAME_MONTH, _SINGLE):
        m = rx.search(text)
        if m:
            name = text[: m.start()].strip(" ,–-")
            place = text[m.end() :].strip(" ,–-")
            return name or text, start, end, place
    return text, start, end, ""


class Laskurliit(Source):
    key = "laskurliit"
    label = "laskurliit.ee"
    priority = 0

    def year_pages(self) -> dict[int, str]:
        pages: dict[int, str] = {}
        page = net.fetch_text(HOME)
        for href, inner in _LINK.findall(page):
            m = _YEAR_LINK.search(_text(inner))
            if m and "laskurliit.ee" in urljoin(HOME, href):
                pages.setdefault(int(m.group(1)), urljoin(HOME, href))
        return pages

    def list_competitions(self, lo: date, hi: date, progress: Progress = _noop) -> list[CompetitionRef]:
        pages = self.year_pages()
        refs: list[CompetitionRef] = []
        seen: set[str] = set()
        for year in range(lo.year, hi.year + 2):  # next year's page may list late-uploaded results
            url = pages.get(year)
            if not url:
                continue
            progress(f"laskurliit.ee: reading results index {year}")
            page = net.fetch_text(url)
            for href, inner in _LINK.findall(page):
                link = urljoin(url, html.unescape(href))
                if link in seen or "laskurliit.ee/wp-content/uploads" not in link or not _DOC_EXT.search(link):
                    continue
                seen.add(link)
                text = _text(inner) or unquote(link.rsplit("/", 1)[-1])
                name, start, end, place = split_link_text(text, year)
                approx = False
                if start is None:
                    m = _UPLOAD_MONTH.search(link)
                    if m:
                        start = end = date(int(m.group(1)), int(m.group(2)), 1)
                        approx = True
                ref = CompetitionRef(self.key, name, link, start, end, place, approx, {"year": year})
                if approx:
                    # uploaded within ~2 months after the event; keep for a closer look
                    if start and lo - timedelta(days=31) <= start <= hi + timedelta(days=62):
                        refs.append(ref)
                elif overlaps(start, end, lo, hi):
                    refs.append(ref)
        return refs

    def load(self, ref: CompetitionRef) -> Competition:
        filename = unquote(ref.link.rsplit("/", 1)[-1])
        doc = parse_cached(ref.link, lambda: net.fetch(ref.link), filename, ref.extra.get("year", date.today().year))
        if doc.error and not doc.tables:
            raise RuntimeError(f"{doc.error} – check {ref.link} manually")
        start, end, approx = ref.date_start, ref.date_end, ref.date_approx
        if approx and doc.date_start:
            start, end, approx = doc.date_start, doc.date_end or doc.date_start, False
        elif start and doc.date_start and doc.date_end and doc.date_start <= start <= doc.date_end:
            # link text "14.03" but document header "14-15.03.2026": use the full range
            if (doc.date_end - doc.date_start).days <= 14:
                start, end = doc.date_start, doc.date_end
        return Competition(
            name=ref.name,
            source=self.key,
            link=ref.link,
            date_start=start,
            date_end=end,
            place=ref.place,
            tables=doc.tables,
            date_approx=approx,
            text=doc.lines,
        )
