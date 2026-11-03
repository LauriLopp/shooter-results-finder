from datetime import date

from results_scraper.models import Competition, Entry, Kind, Person, Table
from results_scraper.names import AthleteQuery
from results_scraper.search import match_competition


def table(category, *names):
    return Table(category=category, kind=Kind.INDIVIDUAL,
                 entries=[Entry(rank=i + 1, result="500", persons=[Person(name=n)]) for i, n in enumerate(names)])  # fmt: skip


def comp(*tables):
    return Competition(name="Freimanis", source="laskurliit", link="x", date_start=date(2026, 9, 18),
                       date_end=date(2026, 9, 20), place="", tables=list(tables))  # fmt: skip


def test_misspelling_promoted_when_confirmed_elsewhere_in_competition():
    rows = match_competition(comp(table("10m", "PÄRTEL Anna"), table("25m", "BÄRTEL Anna")), AthleteQuery("Anna Pärtel"))
    assert [r.possible for r in rows] == [False, False]
    assert "BÄRTEL Anna" in rows[1].notes


def test_misspelling_stays_possible_alone_or_in_same_event():
    rows = match_competition(comp(table("25m", "BÄRTEL Anna")), AthleteQuery("Anna Pärtel"))
    assert [r.possible for r in rows] == [True]
    rows = match_competition(comp(table("10m", "PÄRTEL Anna", "BÄRTEL Anna")), AthleteQuery("Anna Pärtel"))
    assert [r.possible for r in rows] == [False, True]


from results_scraper.models import ResultRow  # noqa: E402
from results_scraper.names import find_in_text  # noqa: E402
from results_scraper.search import drop_covered_unread, unread_row  # noqa: E402

POLONIA = [
    'International shooting competition "POLONIA 2026"',
    "Air Pistol Girls 2009-2010",
    "I PÄRTEL Anna 2009 ÜLENURME GSK EST 92 95 90 91 368 4",
]


def test_name_in_unreadable_document_gives_unread_row():
    c = comp()
    c.text = POLONIA
    row = unread_row(c, AthleteQuery("Anna Pärtel"))
    assert row.kind == Kind.UNREAD and row.result == "" and row.rank is None
    assert "could not be read automatically" in row.notes and "PÄRTEL Anna 2009" in row.notes
    assert unread_row(c, AthleteQuery("Anna Kask")) is None


def test_text_search_is_strict():
    assert find_in_text(AthleteQuery("Toomas Kask"), ["RAO T.K. Priya IND 81"]) is None
    assert find_in_text(AthleteQuery("Anna Pärtel"), ["BÄRTEL Anna EST 541"]) is None
    assert find_in_text(AthleteQuery("Janis Ozolins"), ["1 297 OZOLINS LAT 51.2", "Janis 10.2 9.5"])


def test_unread_row_dropped_when_another_source_has_results_those_days():
    c = comp()
    c.text = POLONIA
    unread = unread_row(c, AthleteQuery("Anna Pärtel"))
    other = ResultRow(athlete="Anna Pärtel", competition="X", date_start=date(2026, 9, 19), date_end=None,
                      category="10m", kind=Kind.INDIVIDUAL, result="541", rank=4, participants=34, link="y",
                      source="sius")  # fmt: skip
    assert drop_covered_unread([unread, other]) == [other]
    other.date_start = date(2026, 10, 19)
    assert drop_covered_unread([unread, other]) == [unread, other]


def test_officials_are_not_participants():
    q = AthleteQuery("Aivo Kivisaar")
    assert find_in_text(q, ["Žürii", "Aivo Kivisaar", "Meelis Org"]) is None
    assert find_in_text(q, ["Peakohtunik Aivo Kivisaar 02.01.2026"]) is None
    assert find_in_text(q, ["5 Aivo KIVISAAR 1975 Elva LSK 95 96 191"])
    assert find_in_text(AthleteQuery("Anna Pärtel"), POLONIA)
