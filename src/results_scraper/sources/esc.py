"""esc-shooting.org — European Shooting Confederation.

The site is a Next.js app over a Strapi API (https://api.esc-shooting.org).
Its structured results endpoint is empty; results are published as a
"Result Book" PDF attached to each event, in the ISSF layout.
"""

from __future__ import annotations

from datetime import date
from urllib.parse import quote

from .. import net
from ..dates import parse_iso
from ..models import Competition
from ..parsing import parse_cached
from .base import CompetitionRef, Progress, Source, _noop

API = "https://api.esc-shooting.org"
SITE = "https://esc-shooting.org"


def _result_book_url(event: dict) -> str | None:
    for doc in event.get("documents") or []:
        name = (doc.get("name") or "").lower()
        url = (doc.get("file") or {}).get("url")
        if url and "result" in name and "start" not in name:
            return url if url.startswith("http") else API + url
    return None


class ESC(Source):
    key = "esc"
    label = "esc-shooting.org"
    priority = 2

    def list_competitions(self, lo: date, hi: date, progress: Progress = _noop) -> list[CompetitionRef]:
        progress("esc-shooting.org: reading event list")
        refs: list[CompetitionRef] = []
        page = 1
        while True:
            url = (
                f"{API}/api/events?filters[date][$lte]={hi.isoformat()}&filters[endDate][$gte]={lo.isoformat()}"
                "&filters[hasResultBook][$eq]=true"
                "&fields[0]=slug&fields[1]=name&fields[2]=date&fields[3]=endDate&fields[4]=location"
                f"&populate[documents][populate]=file&pagination[pageSize]=100&pagination[page]={page}&sort=date:asc"
            )
            data = net.fetch_json(url)
            for ev in data.get("data", []):
                book = _result_book_url(ev)
                if not book:
                    continue
                start = parse_iso(ev.get("date"))
                end = parse_iso(ev.get("endDate")) or start
                refs.append(
                    CompetitionRef(
                        self.key,
                        ev.get("name", "").strip(),
                        book,
                        start,
                        end,
                        ev.get("location") or "",
                        extra={"page": f"{SITE}/events/{quote(ev.get('slug', ''))}"},
                    )
                )
            meta = data.get("meta", {}).get("pagination", {})
            if page >= meta.get("pageCount", 1):
                break
            page += 1
        return refs

    def load(self, ref: CompetitionRef) -> Competition:
        year = ref.date_start.year if ref.date_start else date.today().year
        doc = parse_cached(ref.link, lambda: net.fetch(ref.link), ref.link.rsplit("/", 1)[-1], year)
        if doc.error and not doc.tables:
            raise RuntimeError(f"{doc.error} – check {ref.link} manually")
        return Competition(
            name=ref.name, source=self.key, link=ref.link, date_start=ref.date_start, date_end=ref.date_end,
            place=ref.place, tables=doc.tables, text=doc.lines,
        )  # fmt: skip
