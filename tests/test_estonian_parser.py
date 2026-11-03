"""Estonian protocol layout, using text taken from real laskurliit.ee files."""

from results_scraper.models import Kind
from results_scraper.parsing.estonian import parse_estonian

KAIU = """Kaiu Sügisvõistlus 2026
16-18.10.2026 Kaiu
60l Õhupüss Mehed
Koht Eesnimi Perenimi S.a. Klubi Seeriad Σ 10* KL
I Karl Johannes MÄND-KUUSK 1997 Elva LSK 101,1 100,0 103,6 100,7 102,8 102,8 611,0 42 M
II Andreas JAKOVLEV 1976 Põlva LSK 101,3 100,3 100,8 101,3 103,4 102,9 610,0 34 M
4. Robin KALDMA 2010 Põlva LSK 100,0 100,1 101,1 102,6 102,4 102,6 608,8 32 I
60l Õhupüss Naised
Koht Eesnimi Perenimi S.a. Klubi Seeriad Σ 10* KL
I Susanna KOPPEL 2004 Kaiu LK 102,9 104,8 103,6 104,5 104,2 104,3 624,3 48 SM
InBand elektroonilised märgid
Kohtunikud:
Endel Varik"""

TEAM = """Eesti Noorte MV 2026
14-15.03.2026 Haapsalu
40l Õhupüss Tüdrukud Võistkondlik
Koht Võistkond Eesnimi Perenimi Tulemus Σ
1. Narva LSK 1 Darja KUZMITŠOVA 408,8
Milana BELOZERSKAYA 407,3
Valeria SOKOLEN 412,1 1228,2
2. KL MäLK Sandra LAANESTE 364
Lola KASELA 359
Eva Maria LEPIKSON 340 1063"""

# Spreadsheet rows flattened to lines (from Kuldne-Leht-2026-protokoll-1.xls)
XLS = """Kuldne Leht 2026
3x20l Standard
Koht Eesnimi Perenimi S.a. Klubi Põlvelt Lamades Püsti Σ
I Anastassia NOWAK 2004 Narva LSK 97 94 191 99 99 198 95 95 190 579
II Jekaterina KUZMITŠOVA 2006 Narva LSK 95 95 190 100 99 199 94 94 188 577
13. Kätriin MÕISA 0 Elva LSK 0 0 0 0
14. Valter KUKERMAN 2010 Kaiu LK 0 0 0 0"""

# Category title starting with a number + venue/date line (JÕUD MV PDF)
JOUD = """Eestimaa Spordiliit JÕUD meistrivõistlused
Tartumaa Tervisespordikeskus 17.mai 2026
60 lasku lamades meesjuuniorid
Koht Ees-ja perekonnanimi Sa Maakond Seeriad Kokku Klass Punkte
I Timur ZAITSEV 2008 Ida-Virumaa 102,7 102,7 102,3 101,7 102,1 102,7 614,2 I 25
III Robin KALDMA 2010 Põlvamaa 99,1 100,9 100,9 103,4 99,1 102,8 606,2 II 20
Eestimaa Spordiliit JÕUD meistrivõistlused
Tartumaa Tervisespordikeskus 17.mai 2026
60 lasku lamades naised
Koht Ees-ja perekonnanimi Sa Maakond Seeriad Kokku Klass Punkte
I Kaia ROOSMA 1986 Viljandimaa 99,0 99,0 99,0 99,0 99,0 99,0 594,0 II 25"""

# Bilingual double header (Heli Rass memorial XLSX)
BILINGUAL = """Heli Rassi 54. mälestusvõistlused
25m military rapid fire pistol 3x20 shots M
Koht Ees- ja perekonnanimi S.a. Klubi 10'' 8'' 6'' Summa 10*
Rank Name Team Total
I Marko VIRTANEN 1976 FIN/LehA 99 98 197 96 97 193 97 96 193 583 16"""


def parse(text):
    return parse_estonian([text.split("\n")])


def test_individual_table():
    (men, women) = parse(KAIU)
    assert men.category == "60l Õhupüss Mehed" and men.kind == Kind.INDIVIDUAL
    assert men.participant_count == 3
    e = men.entries[2]
    assert (e.rank, e.result) == (4, "608,8")
    assert e.persons[0].name == "Robin KALDMA"
    assert e.persons[0].birth_year == 2010
    assert e.persons[0].club == "Põlva LSK"
    assert men.entries[0].persons[0].name == "Karl Johannes MÄND-KUUSK"
    assert women.entries[0].result == "624,3"


def test_team_table():
    (t,) = parse(TEAM)
    assert t.kind == Kind.TEAM and t.participant_count == 2
    first, second = t.entries
    assert (first.rank, first.result, first.team_name) == (1, "1228,2", "Narva LSK 1")
    assert [p.name for p in first.persons] == ["Darja KUZMITŠOVA", "Milana BELOZERSKAYA", "Valeria SOKOLEN"]
    assert first.persons[0].result == "408,8"
    assert second.team_name == "KL MäLK"  # club code is not mistaken for a first name
    assert second.persons[0].name == "Sandra LAANESTE"


def test_did_not_start_rows_are_not_participants():
    (t,) = parse(XLS)
    assert t.participant_count == 2
    assert t.entries[1].result == "577"


def test_numeric_category_titles():
    tables = parse(JOUD)
    assert [t.category for t in tables] == ["60 lasku lamades meesjuuniorid", "60 lasku lamades naised"]
    assert tables[0].entries[1].result == "606,2"


def test_bilingual_header():
    (t,) = parse(BILINGUAL)
    assert t.category == "25m military rapid fire pistol 3x20 shots M"
    assert t.entries[0].result == "583"


HELI_RASS = """Heli Rassi 53. mälestusvõistlused
Elva Shooting Sport Center 25th April 2025
50m püstol 60 lasku Open JM, JW
50 m pistol 60 shots Open JM, JW
Koht Ees-ja perekonnanimi S.a Klubi Seeriad Summa Klass
10*
Rank Name Team Series Total
I Daniels BERZINS 2004 LAT/Dobele 92 86 91 90 88 91 538 7 I
II Alise KALNINA 2008 LAT/Tukums 86 83 87 91 87 86 520 4 II
Heli Rassi 53. mälestusvõistlused
Elva Shooting Sport Center 26th April 2025
50 m Liikuv märk 20+20 lasku mix mehed
50m Running Target 20+20 shots mix M
Koht Ees-ja perekonnanimi S.a. Klubi Seeriad Summa
I Hillar ROOTSI 1991 KL MäLK 92 98 97 287 91 83 90 264 551 10 II"""

EJMV = """Eesti juunioride meistrivõistlused 2025
50 m püss 3x20 lasku meesjuuniorid EJR 569 Mart Sepp Ülenurme GSK 03.07.2022. Elva
Koht Ees- ja perekonnanimi Sa Klubi Põlvelt Lamades Püsti Summa 10* Klass
QF Robin KALDMA 2010 Põlva SpK 97 94 191 94 99 193 90 94 184 568 17 I
QF Kaspar TAMMIK 2009 Järvamaa LSK 95 93 188 96 96 192 92 90 182 562 16 I
9 Hendrik LAASIK 2009 Ülenurme GSK 91 92 183 93 92 185 86 76 162 530 8 II
DNS Andres PIHLAKAS 2010 Elva LSK 0 0 0 0 0 0 0 0 0 0 0"""


def test_header_fragment_between_header_rows_is_not_the_category():
    tables = parse_estonian([HELI_RASS.splitlines()])
    assert [t.category for t in tables] == ["50 m pistol 60 shots Open JM, JW", "50m Running Target 20+20 shots mix M"]
    assert tables[1].kind == Kind.INDIVIDUAL  # running target "mix" = mixed speeds


def test_qualified_marks_count_and_record_note_is_dropped():
    (t,) = parse_estonian([EJMV.splitlines()])
    assert t.category == "50 m püss 3x20 lasku meesjuuniorid"
    assert [e.rank for e in t.entries[:3]] == [1, 2, 9]
    assert t.participant_count == 3


PAGE1 = """Eesti juunioride meistrivõistlused 2025
Tartumaa Tervisespordikeskus 14.juuni 2025
30 l. Õhupüstol Segapaarid
Koht Võistkond Eesnimi Perenimi Seeriad 10*Tulemus Σ
Q Viljandi LK 1 Marja KOITLA 96 96 97 9 289
Silver PALUMÄE 97 92 97 7 286 575
16. SK Haapsalu 7 Annika RANDLA 87 87 82 3 256"""
PAGE2 = """Kaius KÕIVA 85 85 94 7 264 520
17. Viljandi LK 2 Karolin PALUMÄE 90 91 84 5 265
Andreas TOOMLA 84 88 82 1 254 519"""
PAGE3 = """Eesti juunioride meistrivõistlused 2025
Tartumaa Tervisespordikeskus 15.juuni 2025
50 m püss 3x20 lasku naisjuuniorid VÕISTKONDLIK
EJR 1711 Eesti koondis (Anastassia Nowak, Marleen Metsa, Susanna Koppel) 01.06.2024. Osijek
I Narva LSK I Darja KUZMITŠOVA 576
Anastassia NOWAK 571
Valeria SOKOLEN 568 1715 EJR"""


def test_tables_continue_across_pages_and_start_from_page_titles():
    mixed, team = parse_estonian([PAGE1.splitlines(), PAGE2.splitlines(), PAGE3.splitlines()])
    assert mixed.kind == Kind.MIXED_TEAM
    assert [(e.rank, e.result) for e in mixed.entries] == [(1, "575"), (16, "520"), (17, "519")]
    assert team.category == "50 m püss 3x20 lasku naisjuuniorid VÕISTKONDLIK"
    assert team.kind == Kind.TEAM
    assert team.entries[0].result == "1715" and len(team.entries[0].persons) == 3
