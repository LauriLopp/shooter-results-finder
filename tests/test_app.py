"""UI smoke test: the app renders, validates input and shows per-athlete results.

The search itself is replaced by a stub so the test runs offline.
"""

from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / "src" / "results_scraper" / "app.py")


def _stub_search(queries, lo, hi, sources, progress=None):
    from results_scraper.models import Kind, ResultRow
    from results_scraper.search import AthleteReport, SearchResult

    reports = []
    for q in queries:
        rows = [
            ResultRow(q.name, "Kaiu Sügisvõistlus", date(2026, 10, 18), date(2026, 10, 18), "60l Õhupüss Mehed",
                      Kind.INDIVIDUAL, "608,8", 4, 18, "https://laskurliit.ee/x.pdf", "laskurliit"),
            ResultRow(q.name, "Eesti noorte MV", date(2026, 3, 14), date(2026, 3, 14), "40l Õhupüss Poisid Võistkondlik",
                      Kind.TEAM, "1172,8", 1, 4, "https://laskurliit.ee/y.pdf", "laskurliit", team="Põlva SpK",
                      own_result="402,7"),
        ]  # fmt: skip
        reports.append(AthleteReport(q, rows, ["2 results"]))
    return SearchResult(lo, hi, reports, [s.label for s in sources], 2, [], ["done"])


def run_app():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


def test_validation_requires_a_name():
    at = run_app()
    at.button[0].click().run()
    assert any("at least one athlete" in e.value for e in at.error)


def test_results_show_tab_per_athlete():
    from results_scraper.names import AthleteQuery

    at = run_app()
    athletes = [AthleteQuery("Robin Kaldma"), AthleteQuery("Darja Kuzmitšova", 2010)]
    at.session_state["result"] = _stub_search(athletes, date(2026, 1, 1), date(2026, 10, 31), [])
    at.run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Robin Kaldma (2)", "Darja Kuzmitšova (2)"]
    assert len(at.dataframe) == 2
    labels = [b.label for b in at.get("download_button")]
    assert "Download all athletes (ZIP)" in labels
    assert labels.count("Download Excel") == 2 and labels.count("Download PDF") == 2


def test_type_filter_hides_team_rows():
    at = run_app()
    from results_scraper.names import AthleteQuery

    at.session_state["result"] = _stub_search([AthleteQuery("Robin Kaldma")], date(2026, 1, 1), date(2026, 10, 31), [])
    at.checkbox(key="kind_TEAM").uncheck()
    at.run()
    assert [t.label for t in at.tabs] == ["Robin Kaldma (1)"]


def test_possible_matches_shown_separately():
    from results_scraper.names import AthleteQuery

    at = run_app()
    res = _stub_search([AthleteQuery("Robin Kaldma")], date(2026, 1, 1), date(2026, 10, 31), [])
    row = res.reports[0].rows[0]
    row.possible, row.notes = True, "Possible match – check: Robn KALDMA ('Robn' ≈ 'Robin')"
    at.session_state["result"] = res
    at.run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Robin Kaldma (1 + 1?)"]
    assert len(at.dataframe) == 2
    assert any("Possible matches" in w.value for w in at.warning)
    at.checkbox(key="show_possible").uncheck()
    at.run()
    assert [t.label for t in at.tabs] == ["Robin Kaldma (1)"] and len(at.dataframe) == 1


def test_sius_is_off_by_default_and_warns_when_on():
    at = run_app()
    assert at.checkbox(key="src_sius").value is False
    assert not any("robots.txt" in e.value for e in at.error)
    at.checkbox(key="src_sius").check()
    at.run()
    assert sum("robots.txt" in e.value for e in at.error) == 2  # sidebar and main page
