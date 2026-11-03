"""Document parsing entry point with a persistent cache of parsed tables."""

from __future__ import annotations

import hashlib
import logging
import pickle
from dataclasses import dataclass, field
from datetime import date

from ..dates import parse_date_range
from ..models import Table
from ..net import cache_dir
from .documents import document_pages
from .estonian import parse_estonian
from .issf import is_issf_document, is_issf_page, parse_issf
from .loose import parse_loose

log = logging.getLogger(__name__)

# Bump when parser output changes, to invalidate cached parse results.
PARSER_VERSION = 17


@dataclass
class ParsedDocument:
    tables: list[Table] = field(default_factory=list)
    date_start: date | None = None  # date found in the document's own header
    date_end: date | None = None
    error: str = ""
    lines: list[str] = field(default_factory=list)  # all text lines of the document


def parse_document(data: bytes, filename: str, default_year: int) -> ParsedDocument:
    try:
        pages = document_pages(data, filename)
    except Exception as exc:  # corrupt / password protected / unknown format
        log.warning("Cannot read %s: %s", filename, exc)
        return ParsedDocument(error=f"unreadable: {exc}")

    head = [ln for page in pages[:1] for ln in page if ln][:8]
    start = end = None
    for ln in head:
        start, end = parse_date_range(ln, default_year)
        if start:
            break

    # Documents can mix layouts (Estonian qualification tables + ISSF final
    # pages), so classify page by page.
    issf_pages = [pg for pg in pages if is_issf_page(pg)]
    other_pages = [pg for pg in pages if not is_issf_page(pg)]
    tables = parse_issf(issf_pages, default_year) if issf_pages else []
    tables += parse_estonian(other_pages) if other_pages else []
    if not tables and is_issf_document(pages):
        tables = parse_issf(pages, default_year)
    if not tables:
        tables = parse_loose(pages)
    if not tables and not any(ln for page in pages for ln in page):
        return ParsedDocument(error="no text in document (scanned/image PDF)")
    if start is None:
        dated = [t.date_start for t in tables if t.date_start]
        if dated:
            start, end = min(dated), max(dated)
    lines = [ln for page in pages for ln in page if ln]
    return ParsedDocument(tables=tables, date_start=start, date_end=end, lines=lines)


def _parsed_path(key: str):
    h = hashlib.sha256(f"{PARSER_VERSION}:{key}".encode()).hexdigest()
    d = cache_dir() / "parsed"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{h}.pkl"


def parse_cached(key: str, loader, filename: str, default_year: int) -> ParsedDocument:
    """Parse a document once and cache the result on disk.

    `loader` is called only on a cache miss and must return the file bytes.
    """
    path = _parsed_path(key)
    if path.exists():
        try:
            return pickle.loads(path.read_bytes())
        except Exception:
            path.unlink(missing_ok=True)
    doc = parse_document(loader(), filename, default_year)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(pickle.dumps(doc))
    tmp.replace(path)
    return doc
