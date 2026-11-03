"""ISSF result-book layout, using text taken from real result books."""

from datetime import date

from results_scraper.models import Kind
from results_scraper.parsing.issf import parse_issf

INDIVIDUAL = """RESULTS
50m RIFLE 3 POSITIONS MEN JUNIOR
INDIVIDUAL
SUN 23 AUG 2026, START TIME 09:00
NOC Series Sub
Rank Bib No Name Position Total Remarks
Code 1 2 Total
15 1071 TAMMIK Kaspar EST Kneeling 94 97 191
Prone 97 93 190
Standing 91 92 183 564-16x
16 1067 KALDMA Kristjan EST Kneeling 93 91 184
Prone 98 98 196
Standing 90 93 183 563-15x
Summary
Number of athletes on this list: 31; Total number of athletes: 31
OFFICIAL ISSF RESULTS PROVIDER"""

TEAM = """RESULTS
50m RIFLE 3 POSITIONS WOMEN JUNIOR
TEAM
SUN 23 AUG 2026, START TIME 14:00
Series Sub
Rank Bib No Name Position Total Remarks
288 288 576
1 EST - Estonia
291 292 583
275 287 562 1721-68x
242 SOKOLEN Valeria Kneeling 97 94 191
Prone 97 98 195
Standing 93 98 191 577-21x
234 KUZMITŠOVA Darja Kneeling 94 96 190
Prone 98 97 195
Standing 92 97 189 574-26x
OFFICIAL ISSF RESULTS PROVIDER"""

MEDAL_MATCH = """RESULTS
50m RIFLE 3 POSITIONS DUET MIXED TEAM
GOLD MEDAL MATCH
TUE 25 AUG 2026, START TIME 16:30
Gold Medal Match
Rank Name Q1 Q2 MM Remarks
1 CZE 1 - Czechia 1 867-36x 861-32x 17Gold
NOVAKOVA Marie
SVOBODA Matej
2 EST 2 - Estonia 2 852-31x 858-30x 7Silver
KUZMITŠOVA Darja
KALDMA Robin
OFFICIAL ISSF RESULTS PROVIDER"""

FINAL = """Nordic Shooting Championship 2026
FINAL RESULTS
10m AIR PISTOL WOMEN JUNIOR
Junior
Elva/Otepää
FRI 7 AUG 2026, START TIME 16:00
Rk Name 2nd Competition Stage - Elimination Total Remarks
1 197 HANSEN NOR 50.2 97.9 116.9 137.0 157.5 175.6 195.0 216.1 236.0
Ingrid Solberg 9.2 9.4 9.2 9.5 10.3 9.3 10.5 10.6 9.5
2 244 SEPPEL EST 49.2 99.9 118.4 138.4 157.9 178.3 196.5 215.1 235.1
Kertu 9.8 9.3 10.2 10.8 9.0 10.2 8.9 9.0 9.2
OFFICIAL ISSF RESULTS PROVIDER"""

FINAL_SHOTS = """RESULTS
FINAL RESULTS
Mark N
Männiku
SAT 10 OCT 2026, START TIME 15:40
Rank Bib No Name Nation Total Remarks
6 21 KUZMITŠOVA Darja NARVA LSK 104.5 103.5 103.1 103.2 103.4 103.0 620.7
Final shots: 10.1 8.9 10.4 10.3 9.6 10.2 10.5 10.0 9.8 10.2 246.9
OFFICIAL ISSF RESULTS PROVIDER"""


def parse(text):
    return parse_issf([text.split("\n")], 2026)


def test_individual():
    (t,) = parse(INDIVIDUAL)
    assert t.kind == Kind.INDIVIDUAL and t.category == "50m RIFLE 3 POSITIONS MEN JUNIOR"
    assert t.date_start == date(2026, 8, 23)
    assert t.participant_count == 31  # stated total, the excerpt lists only two
    e = t.entries[1]
    assert (e.rank, e.result, e.persons[0].name, e.persons[0].club) == (16, "563-15x", "KALDMA Kristjan", "EST")


def test_team():
    (t,) = parse(TEAM)
    assert t.kind == Kind.TEAM
    e = t.entries[0]
    assert (e.rank, e.result, e.team_name) == (1, "1721-68x", "EST - Estonia")
    assert [(p.name, p.result) for p in e.persons] == [("SOKOLEN Valeria", "577-21x"), ("KUZMITŠOVA Darja", "574-26x")]


def test_mixed_team_medal_match():
    (t,) = parse(MEDAL_MATCH)
    assert t.kind == Kind.MIXED_TEAM
    est = t.entries[1]
    assert (est.rank, est.result, est.team_name) == (2, "7", "EST - Estonia 2")
    assert [p.name for p in est.persons] == ["KUZMITŠOVA Darja", "KALDMA Robin"]


def test_final_with_given_name_on_next_line():
    (t,) = parse(FINAL)
    assert t.kind == Kind.FINAL
    assert t.entries[1].persons[0].name == "SEPPEL Kertu"
    assert t.entries[1].result == "235.1"


def test_final_shots_line_holds_final_total():
    (t,) = parse(FINAL_SHOTS)
    assert t.entries[0].result == "246.9"


LETTER_FP = """RESULTS
25m PISTOL MEN JUNIOR
Junior
THU 6 AUG 2026, START TIME 11:30
Rank FP Bib No Name Stage Total Remarks
4 O 0 LARSSON Emil SWE Precision 92 97 96 285
Rapid 87 94 94 275 560-15x
5 Q 0 RAUDSEPP Lepo EST Precision 90 91 92 273
Rapid 94 96 94 284 557-11x
OFFICIAL ISSF RESULTS PROVIDER"""


def test_letter_firing_points():
    (t,) = parse(LETTER_FP)
    assert t.kind == Kind.INDIVIDUAL
    assert [(e.rank, e.persons[0].name, e.result) for e in t.entries] == [
        (4, "LARSSON Emil", "560-15x"),
        (5, "RAUDSEPP Lepo", "557-11x"),
    ]


DUET = """European Championship 10M U16 / U18
RESULTS
10m AIR PISTOL DUET U18
Qualification
Burgas
SAT 7 FEB 2026, START TIME 09:45
Series
Rank Bib No Name Total Remarks
1 2 3
1 UKR 1 - Ukraine 1 196.9 198.5 202.1 597.5 QS ER
1322 PETRENKO Yuliia 100.7 99.9 100.1 300.7
1326 BONDAR Illia 96.2 98.6 102.0 296.8
2 AIN 22 196.5 196.4 195.7 588.6 QS
1263 ORLOVA Evelina 99.9 99.2 97.1 296.2
1249 SMIRNOV Tikhon 96.6 97.2 98.6 292.4
3 EST 3 - Estonia 3 187.3 192.7 187.2 567.2
1116 KÄRKÄNEN Liisa Mari 90.4 93.9 93.7 278.0
1109 MÕTTUS Ott 96.9 98.8 93.5 289.2
Summary
Number of athletes on this list: 6; Total number of athletes: 6; Total number of teams: 3"""


def test_duet_teams_without_country_name():
    (t,) = parse(DUET)
    assert t.kind == Kind.MIXED_TEAM
    assert [(e.rank, e.team_name, e.result) for e in t.entries] == [
        (1, "UKR - Ukraine 1", "597.5"), (2, "AIN 22", "588.6"), (3, "EST - Estonia 3", "567.2"),
    ]  # fmt: skip
    assert t.participant_count == 3
    assert [p.result for p in t.entries[2].persons] == ["278.0", "289.2"]
