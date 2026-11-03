from datetime import date

from results_scraper.models import Kind
from results_scraper.sources.protokollitaja import Protokollitaja, _comp_dates


def test_dummy_start_date_is_replaced_from_text():
    c = {"competitionName": "Ida-Virumaa MV ja Narva lahtised MV, 30.-31.10.2026, Narva",
         "timeAndPlace": "01.01.2000 30.-31.10.2026, Narva", "startDate": "2000-01-01", "endDate": "2000-01-01"}  # fmt: skip
    assert _comp_dates(c) == (date(2026, 10, 30), date(2026, 10, 31))


def test_normal_dates():
    c = {"timeAndPlace": "26.09.2026 Elva", "startDate": "2026-09-26", "endDate": "2026-09-26"}
    assert _comp_dates(c) == (date(2026, 9, 26), date(2026, 9, 26))


def test_event_tables_with_ranks_finals_and_dns():
    data = {
        "eventName": "3x20l Standard Naised",
        "competitors": [
            {"firstName": "Susanna", "lastName": "KOPPEL", "birthYear": "2004", "club": "Kaiu LK", "totalResult": "571", "finals": "353,7"},
            {"firstName": "Anna", "lastName": "AAS", "birthYear": "", "club": "X", "totalResult": "565", "finals": "360,1"},
            {"firstName": "Mia", "lastName": "MAA", "birthYear": "", "club": "X", "totalResult": "560", "finals": ""},
            {"firstName": "Kätriin", "lastName": "MÕISA", "birthYear": "", "club": "Elva LSK", "totalResult": "0", "finals": ""},
        ],
    }  # fmt: skip
    qual, final = Protokollitaja._tables(data)
    assert qual.kind == Kind.INDIVIDUAL and qual.participant_count == 3
    assert [(e.rank, e.result) for e in qual.entries] == [(1, "571"), (2, "565"), (3, "560"), (None, "0")]
    assert qual.entries[0].persons[0].birth_year == 2004
    assert final.kind == Kind.FINAL and final.category == "3x20l Standard Naised – Final"
    assert [(e.rank, e.persons[0].name, e.result) for e in final.entries] == [(1, "Anna AAS", "360,1"), (2, "Susanna KOPPEL", "353,7")]
