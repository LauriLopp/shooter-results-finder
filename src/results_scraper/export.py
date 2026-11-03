"""Export one athlete's results to XLSX, PDF, CSV or TXT (plus a ZIP of all athletes)."""

from __future__ import annotations

import csv
import io
import re
import zipfile
from datetime import date, datetime
from importlib import resources

from .models import Kind, ResultRow
from .search import AthleteReport, SearchResult

LABELS = {
    "en": {
        "title": "Competition results",
        "athlete": "Athlete",
        "period": "Period",
        "generated": "Generated",
        "sources": "Sources",
        "count": "Results",
        "none": "No results found in this period.",
        "log": "Search log",
        "cols": ["Date(s)", "Competition", "Category / event", "Type", "Result", "Rank", "Participants",
                 "Team", "Own result", "Link", "Source", "Notes"],  # fmt: skip
        "possible": "Possible matches – please check",
        "possible_hint": "The name in these results is spelled differently (a letter differs or a name is missing). "
        "Check that it is the right athlete before using them.",
        "kinds": {Kind.INDIVIDUAL: "Individual", Kind.FINAL: "Final", Kind.TEAM: "Team", Kind.MIXED_TEAM: "Mixed team",
                  Kind.UNREAD: "Not read"},  # fmt: skip
        "also": "also on",
    },
    "et": {
        "title": "Võistlustulemused",
        "athlete": "Sportlane",
        "period": "Periood",
        "generated": "Koostatud",
        "sources": "Allikad",
        "count": "Tulemusi",
        "none": "Selles perioodis tulemusi ei leitud.",
        "log": "Otsingu logi",
        "cols": ["Kuupäev", "Võistlus", "Kategooria / harjutus", "Liik", "Tulemus", "Koht", "Osalejaid",
                 "Võistkond", "Oma tulemus", "Link", "Allikas", "Märkused"],  # fmt: skip
        "possible": "Võimalikud vasted – palun kontrolli",
        "possible_hint": "Nendes tulemustes on nimi kirjutatud teisiti (erinev täht või puuduv nimi). "
        "Kontrolli enne kasutamist, et tegu on õige sportlasega.",
        "kinds": {Kind.INDIVIDUAL: "Individuaalne", Kind.FINAL: "Finaal", Kind.TEAM: "Võistkondlik",
                  Kind.MIXED_TEAM: "Segavõistkond", Kind.UNREAD: "Lugemata"},  # fmt: skip
        "also": "ka",
    },
}

SOURCE_NAMES = {
    "laskurliit": "laskurliit.ee",
    "protokollitaja": "protokollitaja.eu",
    "esc": "esc-shooting.org",
    "sius": "results.sius.com",
}


def row_values(r: ResultRow, lang: str = "en") -> list:
    L = LABELS[lang]
    source = SOURCE_NAMES.get(r.source, r.source)
    if r.also_in:
        source += f" ({L['also']} " + ", ".join(SOURCE_NAMES.get(s, s) for s in r.also_in) + ")"
    return [
        r.dates_text,
        r.competition,
        r.category,
        L["kinds"][r.kind],
        r.result,
        r.rank if r.rank is not None else "",
        r.participants if r.participants else "",
        r.team,
        r.own_result,
        r.link,
        source,
        r.notes,
    ]


def safe_filename(name: str) -> str:
    base = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")
    return base or "athlete"


def _header_lines(rep: AthleteReport, res: SearchResult, lang: str) -> list[tuple[str, str]]:
    L = LABELS[lang]
    athlete = rep.query.name + (f" ({rep.query.birth_year})" if rep.query.birth_year else "")
    return [
        (L["athlete"], athlete),
        (L["period"], f"{res.lo:%d.%m.%Y} – {res.hi:%d.%m.%Y}"),
        (L["count"], str(len(rep.confirmed)) + (f" (+{len(rep.possible)} ?)" if rep.possible else "")),
        (L["sources"], ", ".join(res.sources_checked)),
        (L["generated"], datetime.now().strftime("%d.%m.%Y %H:%M")),
    ]


# --------------------------------------------------------------------- CSV / TXT


def to_csv(rep: AthleteReport, res: SearchResult, lang: str = "en") -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")  # ';' opens correctly in Excel with Estonian locale
    w.writerow(LABELS[lang]["cols"])
    for r in rep.confirmed + rep.possible:  # possible matches last; their Notes say so
        w.writerow(row_values(r, lang))
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so Excel detects UTF-8


def _txt_rows(rows: list[ResultRow], lang: str) -> list[str]:
    L = LABELS[lang]
    out = []
    for i, r in enumerate(rows, start=1):
        v = row_values(r, lang)
        place = f"{v[5]}/{v[6]}" if v[5] != "" and v[6] != "" else str(v[5])
        out.append(f"{i}. {v[0]}  {v[1]}")
        out.append(f"   {v[2]} ({v[3]})")
        line = f"   {L['cols'][4]}: {v[4]}"
        if place:
            line += f"   {L['cols'][5]}: {place}"
        if r.team:
            line += f"   {L['cols'][7]}: {r.team}" + (f" ({L['cols'][8].lower()} {r.own_result})" if r.own_result else "")
        out.append(line)
        if r.notes:
            out.append(f"   {L['cols'][11]}: {r.notes}")
        out.append(f"   {r.link}")
        out.append("")
    return out


def to_txt(rep: AthleteReport, res: SearchResult, lang: str = "en") -> bytes:
    L = LABELS[lang]
    out = [f"{L['title']}", "=" * len(L["title"])]
    out += [f"{k}: {v}" for k, v in _header_lines(rep, res, lang)]
    out.append("")
    if not rep.confirmed:
        out.append(L["none"])
    out += _txt_rows(rep.confirmed, lang)
    if rep.possible:
        out += ["", L["possible"], "-" * len(L["possible"]), L["possible_hint"], ""]
        out += _txt_rows(rep.possible, lang)
    out += ["", L["log"], "-" * len(L["log"])] + rep.log
    return "\n".join(out).encode("utf-8")


def log_text(rep: AthleteReport, res: SearchResult, lang: str = "en") -> bytes:
    L = LABELS[lang]
    lines = [f"{L['log']}: {rep.query.name}"] + [f"{k}: {v}" for k, v in _header_lines(rep, res, lang)]
    lines += ["", *rep.log, "", "Run log:", *res.log]
    if res.errors:
        lines += ["", "Errors:", *res.errors]
    return "\n".join(lines).encode("utf-8")


# --------------------------------------------------------------------- XLSX


def to_xlsx(rep: AthleteReport, res: SearchResult, lang: str = "en") -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    L = LABELS[lang]
    widths = [14, 38, 38, 13, 11, 7, 12, 18, 11, 40, 22, 45]

    def write_table(ws, row: int, rows: list[ResultRow], fill_color: str) -> None:
        header_row = row
        fill = PatternFill("solid", fgColor=fill_color)
        for c, name in enumerate(L["cols"], start=1):
            cell = ws.cell(row=row, column=c, value=name)
            cell.font = Font(bold=True)
            cell.fill = fill
        for r in rows:
            row += 1
            for c, value in enumerate(row_values(r, lang), start=1):
                cell = ws.cell(row=row, column=c, value=value)
                cell.alignment = Alignment(vertical="top", wrap_text=c in (2, 3, 12))
                if c == 10 and value:
                    cell.hyperlink = value
                    cell.font = Font(color="0563C1", underline="single")
        for c, wdt in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(c)].width = wdt
        ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
        if rows:
            ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(widths))}{row}"

    wb = Workbook()
    ws = wb.active
    ws.title = L["title"][:31]
    row = 1
    ws.cell(row=row, column=1, value=L["title"]).font = Font(bold=True, size=14)
    for k, v in _header_lines(rep, res, lang):
        row += 1
        ws.cell(row=row, column=1, value=k).font = Font(bold=True)
        ws.cell(row=row, column=2, value=v)
    write_table(ws, row + 2, rep.confirmed, "DDE6F0")

    if rep.possible:
        pws = wb.create_sheet(L["possible"][:31].rstrip(" –"))
        pws.cell(row=1, column=1, value=L["possible"]).font = Font(bold=True, size=13)
        pws.cell(row=2, column=1, value=L["possible_hint"])
        write_table(pws, 4, rep.possible, "FCE4C4")

    log_ws = wb.create_sheet(L["log"][:31])
    for i, line in enumerate(log_text(rep, res, lang).decode("utf-8").split("\n"), start=1):
        log_ws.cell(row=i, column=1, value=line)
    log_ws.column_dimensions["A"].width = 120

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --------------------------------------------------------------------- PDF


def to_pdf(rep: AthleteReport, res: SearchResult, lang: str = "en") -> bytes:
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    L = LABELS[lang]
    fonts = resources.files("results_scraper").joinpath("fonts")
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_font("DejaVu", "", str(fonts.joinpath("DejaVuSans.ttf")))
    pdf.add_font("DejaVu", "B", str(fonts.joinpath("DejaVuSans-Bold.ttf")))
    pdf.set_title(f"{L['title']} – {rep.query.name}")
    pdf.add_page()

    pdf.set_font("DejaVu", "B", 15)
    pdf.cell(0, 9, f"{L['title']}: {rep.query.name}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 9)
    for k, v in _header_lines(rep, res, lang)[1:]:
        pdf.cell(0, 5, f"{k}: {v}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    def table_of(rows: list[ResultRow], fill: tuple[int, int, int]) -> None:
        cols = [L["cols"][i] for i in (0, 1, 2, 3, 4, 5, 7, 11)]
        widths = (27, 54, 52, 21, 21, 15, 36, 51)
        pdf.set_font("DejaVu", "", 7.5)
        heading = FontFace(emphasis="BOLD", fill_color=fill)
        with pdf.table(col_widths=widths, headings_style=heading, line_height=4, text_align="LEFT") as table:
            table.row(cols)
            for r in rows:
                v = row_values(r, lang)
                place = f"{v[5]}/{v[6]}" if v[5] != "" and v[6] != "" else str(v[5])
                team = r.team + (f" ({r.own_result})" if r.own_result else "")
                cells = table.row()
                cells.cell(v[0])
                cells.cell(v[1], link=r.link or None)
                for text in (v[2], v[3], v[4], place, team, r.notes):
                    cells.cell(text)

    if rep.confirmed:
        table_of(rep.confirmed, (221, 230, 240))
    else:
        pdf.set_font("DejaVu", "", 11)
        pdf.cell(0, 8, L["none"], new_x="LMARGIN", new_y="NEXT")

    if rep.possible:
        pdf.ln(5)
        pdf.set_font("DejaVu", "B", 12)
        pdf.cell(0, 7, L["possible"], new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("DejaVu", "", 8)
        pdf.multi_cell(0, 4, L["possible_hint"], new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        table_of(rep.possible, (252, 228, 196))

    pdf.ln(2)
    pdf.set_font("DejaVu", "", 7)
    note = {"en": "Competition names link to the source result document.",
            "et": "Võistluse nimi on link tulemuste dokumendile."}[lang]  # fmt: skip
    pdf.cell(0, 4, note)
    return bytes(pdf.output())


# --------------------------------------------------------------------- bundle

FORMATS = {
    "xlsx": ("Excel", to_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "pdf": ("PDF", to_pdf, "application/pdf"),
    "csv": ("CSV", to_csv, "text/csv"),
    "txt": ("TXT", to_txt, "text/plain"),
}


def file_stem(rep: AthleteReport, res: SearchResult) -> str:
    return f"{safe_filename(rep.query.name)}_{res.lo:%Y%m%d}-{res.hi:%Y%m%d}"


def to_zip(res: SearchResult, lang: str = "en") -> bytes:
    """All formats for every athlete, one folder per athlete, plus their search logs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rep in res.reports:
            stem = file_stem(rep, res)
            folder = safe_filename(rep.query.name)
            for ext, (_, fn, _) in FORMATS.items():
                zf.writestr(f"{folder}/{stem}.{ext}", fn(rep, res, lang))
            zf.writestr(f"{folder}/{stem}_log.txt", log_text(rep, res, lang))
    return buf.getvalue()


def today() -> date:
    return date.today()
