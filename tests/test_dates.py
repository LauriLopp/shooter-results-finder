from datetime import date

import pytest

from results_scraper.dates import format_range, overlaps, parse_date_range


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Ida-Virumaa MV ja Narva lahtised MV 2026, 30.-31.10.2026 Narva", (date(2026, 10, 30), date(2026, 10, 31))),
        ("Kaiu Sügisvõistlus 18.10 Kaiu", (date(2026, 10, 18), date(2026, 10, 18))),
        ("XVIII Mati Mark’i mälestusvõistlus, 10.10.2026 Männiku", (date(2026, 10, 10), date(2026, 10, 10))),
        ("Põhjamaade MV 5.-8.08 Elva/Tehvandi", (date(2026, 8, 5), date(2026, 8, 8))),
        ("XVIII E. Norgani mälestusvõistlused 31.03-04.04 Käina", (date(2026, 3, 31), date(2026, 4, 4))),
        ("52. Põlva KV 28.-29.03 Põlva", (date(2026, 3, 28), date(2026, 3, 29))),
        ("16-18.10.2026 Kaiu", (date(2026, 10, 16), date(2026, 10, 18))),
        ("Hiiumaa KV IV etapp 05.-12.02", (date(2026, 2, 5), date(2026, 2, 12))),
        ("Euroopa MV U18 25m/50m 21.-26.08 Männiku", (date(2026, 8, 21), date(2026, 8, 26))),
        ("SUN 23 AUG 2026, START TIME 09:00", (date(2026, 8, 23), date(2026, 8, 23))),
        ("EMV haavlilaskmises 2026 Männiku", (None, None)),
        ("Hiiumaa KV 2025-2026", (None, None)),
    ],
)
def test_parse_date_range(text, expected):
    assert parse_date_range(text, 2026) == expected


def test_format_range():
    assert format_range(date(2026, 10, 30), date(2026, 10, 31)) == "30.-31.10.2026"
    assert format_range(date(2026, 3, 31), date(2026, 4, 4)) == "31.03.-04.04.2026"
    assert format_range(date(2026, 10, 18), date(2026, 10, 18)) == "18.10.2026"


def test_overlaps():
    lo, hi = date(2026, 1, 1), date(2026, 6, 30)
    assert overlaps(date(2026, 6, 30), date(2026, 7, 2), lo, hi)
    assert not overlaps(date(2026, 7, 1), None, lo, hi)
    assert not overlaps(None, None, lo, hi)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Tartumaa Tervisespordikeskus 17.mai 2026", date(2026, 5, 17)),
        ("09. dets. 2018 Rapla", date(2018, 12, 9)),
        ("Elva Shooting Sport Center 24th April 2026", None),
    ],
)
def test_estonian_month_names(text, expected):
    assert parse_date_range(text, 2026)[0] == expected
