"""Turn result documents (PDF / XLS / XLSX) into pages of text lines.

Every parser works on text lines, so spreadsheets are flattened: each sheet
becomes one "page" and each row becomes one line of its non-empty cells
joined by spaces. This lets one table parser handle both PDFs and Excel files
that use the same layout.
"""

from __future__ import annotations

import io
import logging
import warnings

log = logging.getLogger(__name__)


def detect_format(data: bytes, filename: str = "") -> str:
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:4] == b"PK\x03\x04":
        return "xlsx"
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "xls"
    ext = filename.lower().rsplit(".", 1)[-1]
    return ext if ext in ("pdf", "xls", "xlsx") else "unknown"


def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.10g}"
    return str(value).strip()


def _rows_to_lines(rows) -> list[str]:
    lines = []
    for row in rows:
        cells = [_cell_text(c) for c in row]
        cells = [c for c in cells if c]
        lines.append(" ".join(cells))
    return lines


def _pypdf_pages(data: bytes) -> list[str]:
    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    return [(p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages]


def pdf_pages(data: bytes) -> list[list[str]]:
    """Text lines per page. pdfplumber gives the best layout; some PDFs trip a
    pdfminer font bug, and those pages fall back to pypdf."""
    import pdfplumber

    texts: list[str | None] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        logging.getLogger("pdfminer").setLevel(logging.ERROR)
        try:
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages:
                    try:
                        texts.append(page.dedupe_chars().extract_text() or "")
                    except Exception:
                        texts.append(None)
                    page.flush_cache()
        except Exception:
            texts = []
        if not texts or any(t is None for t in texts):
            log.info("pdfplumber failed on some pages; using pypdf for them")
            fallback = _pypdf_pages(data)
            if not texts:
                texts = list(fallback)
            else:
                texts = [t if t is not None else (fallback[i] if i < len(fallback) else "") for i, t in enumerate(texts)]
    return [[ln.strip() for ln in (t or "").split("\n")] for t in texts]


def xls_pages(data: bytes) -> list[list[str]]:
    import xlrd

    book = xlrd.open_workbook(file_contents=data, on_demand=True)
    pages = []
    for i in range(book.nsheets):
        sh = book.sheet_by_index(i)
        pages.append(_rows_to_lines(sh.row_values(r) for r in range(sh.nrows)))
        book.unload_sheet(i)
    return pages


def xlsx_pages(data: bytes) -> list[list[str]]:
    import openpyxl

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    pages = []
    for ws in book.worksheets:
        pages.append(_rows_to_lines(ws.iter_rows(values_only=True)))
    book.close()
    return pages


def document_pages(data: bytes, filename: str = "") -> list[list[str]]:
    fmt = detect_format(data, filename)
    if fmt == "pdf":
        return pdf_pages(data)
    if fmt == "xls":
        return xls_pages(data)
    if fmt == "xlsx":
        return xlsx_pages(data)
    raise ValueError(f"Unsupported document format for {filename!r}")
