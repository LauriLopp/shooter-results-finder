"""Fallback parser, using text from real files no other parser understands."""

from results_scraper.models import Kind
from results_scraper.parsing.loose import parse_loose

NORGANI = """E.Norgani XVIII mälestusvõistlused
31.03-04.04.2026
Nimi sünniaasta klubi I II III IV Kokku 1 lask sisekümned
PÜSS MEHED
1 Rainer Kuusik 2009 Hiiumaa 94.4 96.8 96.8 99.5 387.5
2 Kalmar Kuusik 1966 Hiiumaa 95.9 97 95.6 92.8 381.3
PÜSS NOORED s 2008-2012
1 Rainer Kuusik 2009 Hiiumaa 97.2 96.9 95.6 98.7 388.4"""

NO_RANKS = """Tulemused:
Harjutus: 60 Lasku lamades
I II III IV V VI *
Edik Lillemets 98 98 98 97 99 100 590 24 I
Andres Kallas 93 95 96 98 97 97 576 20 II
I II III IV V VI *
Anžela Volkova 97 96 95 100 99 97 584 25 I"""

LATVIAN = """JĀŅA OSKARA ŠALMA 1. PIEMIŅAS SACENSĪBAS
Aizpute, 9.-11.10.2026.
MP-30 (sievietes) - sport  pistol, Women REZULTĀTI
Vieta Vārds Uzvārds Komanda Gads 1 2 3 Summa 10x
1 Alise KALNIŅA Tukums (LAT) 2008 96 94 96 286 4
4 Annika RANDLA Haapsalu (EST) 2011 91 92 87 270 3"""

PAIRS = """Läänemaa Spordikooli MUNA & KANA
Sportpüss
I Mirtel Viirpuu 2014 10 10 10 8 8 46 96
Raigo Viirpuu 1978 10 10 10 10 10 50
II Markus Neumann 2013 10 10 10 9 9 48 95
Peter Hoffmann 1973 10 10 10 10 7 47"""

GLUED = """Hiiumaa KV 2025-2026
naised
9Alex Orgla 2006 Hiiumaa 90,5 84,9 88,0 85,9 82,2 92,9 524,4
10Karel Otto Laur 2012 Järvamaa 0,0 99,0 101,2 97,5 98,5 102,4 98,4 597,0 597,0"""


def parse(text):
    return parse_loose([text.split("\n")])


def test_title_case_names_and_categories():
    men, youth = parse(NORGANI)
    assert men.category == "PÜSS MEHED" and youth.category == "PÜSS NOORED s 2008-2012"
    e = men.entries[0]
    assert (e.rank, e.result, e.persons[0].name, e.persons[0].birth_year) == (1, "387.5", "Rainer Kuusik", 2009)


def test_rank_from_order_when_missing():
    men, women = parse(NO_RANKS)
    assert [(e.rank, e.result) for e in men.entries] == [(1, "590"), (2, "576")]
    assert women.entries[0].rank == 1 and women.category == "Harjutus: 60 Lasku lamades"


def test_header_with_numbers_is_not_an_athlete_and_year_after_club():
    (t,) = parse(LATVIAN)
    assert t.category.startswith("MP-30 (sievietes)")
    assert [(e.rank, e.result) for e in t.entries] == [(1, "286"), (4, "270")]
    assert t.entries[1].persons[0].birth_year == 2011


def test_pairs():
    (t,) = parse(PAIRS)
    assert t.kind == Kind.TEAM
    assert [p.name for p in t.entries[0].persons] == ["Mirtel Viirpuu", "Raigo Viirpuu"]
    assert t.entries[0].result == "96"


def test_rank_glued_to_name():
    (t,) = parse(GLUED)
    assert [(e.rank, e.persons[0].name) for e in t.entries] == [(9, "Alex Orgla"), (10, "Karel Otto Laur")]
