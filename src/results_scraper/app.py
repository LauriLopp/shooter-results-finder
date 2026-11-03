"""Streamlit browser UI: names + period in, per-athlete result lists and files out.

Run with `results-scraper` (or `streamlit run src/results_scraper/app.py`).
"""

from __future__ import annotations

import copy
from datetime import date

import streamlit as st

from results_scraper import export
from results_scraper.models import Kind
from results_scraper.names import AthleteQuery
from results_scraper.search import MAX_ATHLETES, SearchResult, search
from results_scraper.sources.esc import ESC
from results_scraper.sources.laskurliit import Laskurliit
from results_scraper.sources.protokollitaja import Protokollitaja
from results_scraper.sources.sius import SIUS

T = {
    "en": {
        "title": "Athlete results finder",
        "intro": "Finds every result of up to five athletes on laskurliit.ee (main source), protokollitaja.eu, "
        "esc-shooting.org and results.sius.com (international championships), without duplicates.",
        "athlete": "Athlete {n}",
        "name_ph": "First and last name",
        "year": "Birth year",
        "year_help": "Optional. Separates athletes with the same name.",
        "from": "From",
        "to": "To",
        "search": "Search",
        "sources": "Sources",
        "kinds": "Result types",
        "kind_names": {Kind.INDIVIDUAL: "Individual", Kind.FINAL: "Finals", Kind.TEAM: "Team", Kind.MIXED_TEAM: "Mixed team",
                       Kind.UNREAD: "Name found, result not read"},  # fmt: skip
        "need_name": "Enter at least one athlete name.",
        "bad_period": "The start date must be before the end date.",
        "bad_year": "Birth year must be a 4-digit year: {v}",
        "no_source": "Select at least one source.",
        "running": "Searching… The first search of a period downloads the result files and can take several "
        "minutes; repeated searches are fast.",
        "done": "Checked {c} competitions in {p}.",
        "errors": "{n} source problem(s) – some results may be missing",
        "found": "{n} results",
        "download": "Download",
        "download_log": "Search log",
        "zip": "Download all athletes (ZIP)",
        "none": "No results found in this period.",
        "sius_note": "SIUS is slow (rate-limited): the first search of a period can take 10+ minutes.",
        "sius_warning": "⚠️ **results.sius.com does not allow automated access.** Its robots.txt asks all "
        "automated clients to stay away. Use this source only if you accept that, only for a short period, and "
        "not repeatedly – international championships are often also found via esc-shooting.org.",
        "log": "Run log",
        "language": "Language / Keel",
        "show_possible": "Show possible matches",
        "show_possible_help": "Results where the name is spelled slightly differently (a letter differs, "
        "a given name is missing). Listed separately so you can check them.",
        "possible": "Possible matches – please check ({n})",
        "possible_hint": "The name is spelled differently in these results; the Notes column says how. "
        "They are listed separately in all downloads too.",
    },
    "et": {
        "title": "Sportlase tulemuste otsing",
        "intro": "Leiab kuni viie sportlase kõik tulemused lehtedelt laskurliit.ee (põhiallikas), protokollitaja.eu, "
        "esc-shooting.org ja results.sius.com (rahvusvahelised võistlused), ilma kordusteta.",
        "athlete": "Sportlane {n}",
        "name_ph": "Ees- ja perekonnanimi",
        "year": "Sünniaasta",
        "year_help": "Valikuline. Eristab samanimelisi sportlasi.",
        "from": "Alates",
        "to": "Kuni",
        "search": "Otsi",
        "sources": "Allikad",
        "kinds": "Tulemuste liigid",
        "kind_names": {Kind.INDIVIDUAL: "Individuaalne", Kind.FINAL: "Finaalid", Kind.TEAM: "Võistkondlik",
                       Kind.MIXED_TEAM: "Segavõistkond", Kind.UNREAD: "Nimi leitud, tulemus lugemata"},  # fmt: skip
        "need_name": "Sisesta vähemalt ühe sportlase nimi.",
        "bad_period": "Alguskuupäev peab olema enne lõppkuupäeva.",
        "bad_year": "Sünniaasta peab olema neljakohaline: {v}",
        "no_source": "Vali vähemalt üks allikas.",
        "running": "Otsin… Perioodi esimene otsing laadib tulemusfailid alla ja võib võtta mitu minutit; "
        "korduvad otsingud on kiired.",
        "done": "Kontrollitud {c} võistlust ({p}).",
        "errors": "{n} allika probleem(i) – mõni tulemus võib puududa",
        "found": "{n} tulemust",
        "download": "Laadi alla",
        "download_log": "Otsingu logi",
        "zip": "Laadi alla kõigi sportlaste failid (ZIP)",
        "none": "Selles perioodis tulemusi ei leitud.",
        "sius_note": "SIUS on aeglane (päringupiirang): perioodi esimene otsing võib võtta üle 10 minuti.",
        "sius_warning": "⚠️ **results.sius.com ei luba automaatset ligipääsu.** Saidi robots.txt palub kõigil "
        "automaatsetel klientidel eemale hoida. Kasuta seda allikat ainult siis, kui oled sellega nõus, lühikese "
        "perioodi jaoks ja mitte korduvalt – rahvusvahelised tiitlivõistlused leiab sageli ka esc-shooting.org kaudu.",
        "log": "Töölogi",
        "language": "Language / Keel",
        "show_possible": "Näita võimalikke vasteid",
        "show_possible_help": "Tulemused, kus nimi on kirjutatud veidi teisiti (erinev täht, puuduv eesnimi). "
        "Need on eraldi, et saaksid neid kontrollida.",
        "possible": "Võimalikud vasted – palun kontrolli ({n})",
        "possible_hint": "Nendes tulemustes on nimi kirjutatud teisiti; veerg Märkused ütleb, kuidas. "
        "Ka allalaaditavates failides on need eraldi.",
    },
}

SOURCES = {
    "laskurliit": (Laskurliit, True),
    "protokollitaja": (Protokollitaja, True),
    "esc": (ESC, True),
    "sius": (SIUS, False),  # opt-in: its robots.txt disallows automated access
}


def filtered(res: SearchResult, kinds: set[Kind], show_possible: bool = True) -> SearchResult:
    out = copy.copy(res)
    out.reports = []
    for rep in res.reports:
        r = copy.copy(rep)
        r.rows = [row for row in rep.rows if row.kind in kinds and (show_possible or not row.possible)]
        out.reports.append(r)
    return out


def table_rows(rows_in, lang: str) -> list[dict]:
    cols = export.LABELS[lang]["cols"]
    rows = []
    for r in rows_in:
        v = export.row_values(r, lang)
        rows.append(dict(zip(cols, v)))
    return rows


def main() -> None:
    st.set_page_config(page_title="Athlete results finder", page_icon="🎯", layout="wide")

    with st.sidebar:
        lang = "et" if st.radio(T["en"]["language"], ["English", "Eesti"], horizontal=True) == "Eesti" else "en"
        t = T[lang]
        st.subheader(t["sources"])
        chosen = []
        for key, (cls, default) in SOURCES.items():
            if st.checkbox(cls.label, value=default, key=f"src_{key}"):
                chosen.append(key)
        if "sius" in chosen:
            st.error(t["sius_warning"])
            st.caption(t["sius_note"])
        st.subheader(t["kinds"])
        kinds = {k for k in Kind if st.checkbox(t["kind_names"][k], value=True, key=f"kind_{k.name}")}
        show_possible = st.checkbox(t["show_possible"], value=True, key="show_possible", help=t["show_possible_help"])

    st.title(t["title"])
    st.caption(t["intro"])
    if "sius" in chosen:
        st.error(t["sius_warning"])

    today = date.today()
    with st.form("search"):
        queries: list[AthleteQuery] = []
        problems: list[str] = []
        for i in range(MAX_ATHLETES):
            c1, c2 = st.columns([4, 1])
            name = c1.text_input(t["athlete"].format(n=i + 1), key=f"name{i}", placeholder=t["name_ph"])
            year = c2.text_input(t["year"], key=f"year{i}", help=t["year_help"], max_chars=4)
            if name.strip():
                y = year.strip()
                if y and not (y.isdigit() and len(y) == 4):
                    problems.append(t["bad_year"].format(v=y))
                    y = ""
                queries.append(AthleteQuery(name.strip(), int(y) if y else None))
        c1, c2, _ = st.columns([1, 1, 3])
        lo = c1.date_input(t["from"], value=date(today.year, 1, 1), format="DD.MM.YYYY")
        hi = c2.date_input(t["to"], value=today, format="DD.MM.YYYY")
        submitted = st.form_submit_button(t["search"], type="primary")

    if submitted:
        if not queries:
            problems.append(t["need_name"])
        if lo > hi:
            problems.append(t["bad_period"])
        if not chosen:
            problems.append(t["no_source"])
        if problems:
            for p in problems:
                st.error(p)
        else:
            bar = st.progress(0.0, text=t["running"])
            sources = [SOURCES[k][0]() for k in chosen]
            res = search(queries, lo, hi, sources, progress=lambda f, m: bar.progress(f, text=m))
            bar.empty()
            st.session_state["result"] = res

    res: SearchResult | None = st.session_state.get("result")
    if res is None:
        return

    view = filtered(res, kinds, show_possible)
    st.success(t["done"].format(c=res.competitions_checked, p=f"{res.lo:%d.%m.%Y} – {res.hi:%d.%m.%Y}"))
    if res.errors:
        with st.expander(t["errors"].format(n=len(res.errors))):
            for e in res.errors:
                st.write("• " + e)

    if len(view.reports) > 1:
        st.download_button(
            t["zip"], export.to_zip(view, lang), file_name=f"results_{res.lo:%Y%m%d}-{res.hi:%Y%m%d}.zip",
            mime="application/zip", type="primary",
        )  # fmt: skip

    def tab_label(rep) -> str:
        n, k = len(rep.confirmed), len(rep.possible)
        return f"{rep.query.name} ({n}" + (f" + {k}?)" if k else ")")

    tabs = st.tabs([tab_label(rep) for rep in view.reports])
    link_col = export.LABELS[lang]["cols"][9]
    for tab, rep in zip(tabs, view.reports):
        with tab:
            st.markdown(f"**{t['found'].format(n=len(rep.confirmed))}**")
            column_config = {link_col: st.column_config.LinkColumn(link_col, display_text="🔗")}
            if rep.confirmed:
                st.dataframe(table_rows(rep.confirmed, lang), hide_index=True, width="stretch",
                             column_config=column_config)  # fmt: skip
            else:
                st.info(t["none"])
            if rep.possible:
                st.warning(f"**{t['possible'].format(n=len(rep.possible))}**  \n{t['possible_hint']}")
                st.dataframe(table_rows(rep.possible, lang), hide_index=True, width="stretch",
                             column_config=column_config, key=f"possible_{rep.query.name}")  # fmt: skip
            stem = export.file_stem(rep, view)
            cols = st.columns(len(export.FORMATS) + 1)
            for col, (ext, (label, fn, mime)) in zip(cols, export.FORMATS.items()):
                col.download_button(
                    f"{t['download']} {label}", fn(rep, view, lang), file_name=f"{stem}.{ext}", mime=mime,
                    key=f"dl_{stem}_{ext}",
                )  # fmt: skip
            cols[-1].download_button(
                t["download_log"], export.log_text(rep, view, lang), file_name=f"{stem}_log.txt",
                mime="text/plain", key=f"dl_{stem}_log",
            )  # fmt: skip

    with st.expander(t["log"]):
        st.code("\n".join(res.log), language=None)


main()
