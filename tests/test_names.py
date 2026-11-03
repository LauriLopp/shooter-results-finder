from results_scraper.names import AthleteQuery, normalize


def test_normalize_strips_accents():
    assert normalize("KUZMITŠOVA Õie Krzyżański") == "kuzmitsova oie krzyzanski"


def test_order_and_case_insensitive():
    q = AthleteQuery("Darja Kuzmitšova")
    assert q.matches("Darja KUZMITŠOVA")
    assert q.matches("KUZMITSOVA Darja")
    assert not q.matches("Jekaterina KUZMITŠOVA")


def test_transliteration_tolerance():
    assert AthleteQuery("Milana Belozerskaja").matches("Milana BELOZERSKAYA")
    assert AthleteQuery("Darja Kuzmitšova").matches("KUZMITSHOVA Darja")


def test_short_names_need_exact_match():
    assert not AthleteQuery("Robin Kaldma").matches("Kristjan KALDMA")
    assert AthleteQuery("Robin Kaldma").matches("KALDMA Robin")


def test_double_names_and_hyphens():
    assert AthleteQuery("Karl Johannes Mänd-Kuusk").matches("Karl Johannes MÄND-KUUSK")
    assert AthleteQuery("Karl Mänd-Kuusk").matches("Karl Johannes MÄND-KUUSK")


def test_birth_year_disambiguates():
    q = AthleteQuery("Mart Tamm", 2000)
    assert q.matches("Mart TAMM", 2000)
    assert q.matches("Mart TAMM", None)
    assert not q.matches("Mart TAMM", 1975)


# --- confirmed vs possible matches (variants seen in real 2026 result files) ---
from results_scraper.names import CONFIRMED, POSSIBLE  # noqa: E402


def level(query, printed, year=None):
    m = AthleteQuery(query).match(printed, year)
    return m.level if m else None


def test_lost_spaces_are_confirmed_with_note():
    m = AthleteQuery("Liisa Mari Kärkänen").match("Liisa MariKÄRKÄNEN")
    assert m.level == CONFIRMED and "without spaces" in m.note


def test_exact_spelling_has_no_note_other_spelling_does():
    q = AthleteQuery("Liisa Mari Kärkänen")
    assert q.match("KÄRKÄNEN Liisa Mari").note == ""
    assert q.match("KARKONEN Liisa Mari").note == "Name in source: KARKONEN Liisa Mari"


def test_missing_given_name_is_possible():
    m = AthleteQuery("Liisa Mari Kärkänen").match("Liisa KÄRKÄNEN")
    assert m.level == POSSIBLE and "no 'Mari'" in m.note


def test_typo_in_short_name_is_possible():
    assert level("Jette Sofia Lepikson", "Fette Sofia LEPIKSON") == POSSIBLE
    assert level("Jette Sofia Lepikson", "LEPIKSON Jette Sifia") == POSSIBLE
    assert level("Robin Kaldma", "Robn KALDMA") == POSSIBLE


def test_siblings_are_never_suggested():
    assert level("Liisa Mari Kärkänen", "Kaspar KÄRKÄNEN") is None
    assert level("Robin Kaldma", "Kristjan KALDMA") is None
    assert level("Jette Sofia Lepikson", "Eva Maria LEPIKSON") is None


def test_possible_match_with_other_birth_year_is_excluded():
    assert AthleteQuery("Robin Kaldma", 2010).match("Robn KALDMA", 1975) is None


def test_stray_rank_in_printed_name_is_ignored():
    assert AthleteQuery("Jette Sofia Lepikson").match("4. Jette Sofia LEPIKSON").note == ""


def test_initials_alone_never_match():
    # "RAO T.K. Priya" must not be found for Toomas Kask
    assert level("Toomas Kask", "RAO T.K. Priya") is None
    assert level("Hanne Lund", "H. LUND") == CONFIRMED
