from datetime import date

from results_scraper.dedupe import merge_duplicates
from results_scraper.models import Kind, ResultRow

PRIORITY = {"laskurliit": 0, "protokollitaja": 1, "esc": 2, "sius": 3}


def row(source, competition, result, rank, d=date(2026, 2, 21), kind=Kind.INDIVIDUAL, category="60l Õhupüss", link=None, end=None):
    return ResultRow(
        athlete="Darja Kuzmitšova", competition=competition, date_start=d, date_end=end or d, category=category,
        kind=kind, result=result, rank=rank, participants=22, link=link or f"https://{source}/x", source=source,
    )  # fmt: skip


def test_same_result_on_two_sites_is_merged_keeping_main_source():
    rows = [
        row("protokollitaja", "Eesti meistrivõistlused õhkrelvadest", "620.0", 5),
        row("laskurliit", "Eesti MV õhkrelvadest laskmises", "620,0", 4),
    ]
    kept, dropped = merge_duplicates(rows, PRIORITY)
    assert len(kept) == 1 and len(dropped) == 1
    assert kept[0].source == "laskurliit" and kept[0].rank == 4
    assert kept[0].also_in == ["protokollitaja"]


def test_different_language_names_merge_on_date_rank_score():
    rows = [
        row("esc", "2026 European Championship 25/50m U18", "565-21x", 16, d=date(2026, 8, 21), end=date(2026, 8, 26)),
        row("laskurliit", "Euroopa MV U18 25m/50m", "565-21x", 16, d=date(2026, 8, 21), end=date(2026, 8, 26)),
    ]
    kept, _ = merge_duplicates(rows, PRIORITY)
    assert len(kept) == 1 and kept[0].source == "laskurliit"


def test_final_and_qualification_are_kept_separately():
    rows = [row("laskurliit", "A", "620.7", 3), row("laskurliit", "A", "620.7", 3, kind=Kind.FINAL)]
    assert len(merge_duplicates(rows, PRIORITY)[0]) == 2


def test_different_dates_are_not_merged():
    rows = [row("laskurliit", "A", "608.8", 4), row("protokollitaja", "B", "608.8", 4, d=date(2026, 5, 1))]
    assert len(merge_duplicates(rows, PRIORITY)[0]) == 2


def test_same_document_needs_same_category():
    rows = [
        row("laskurliit", "A", "545", 4, category="3x20 MJ", link="https://l/a.pdf"),
        row("laskurliit", "A", "545", 4, category="3x20 M", link="https://l/a.pdf"),
    ]
    assert len(merge_duplicates(rows, PRIORITY)[0]) == 2


def test_same_score_same_field_size_merges_despite_rank():
    rows = [row("laskurliit", "Eesti MV", "614,0", 1), row("protokollitaja", "Eesti meistrivõistlused", "614.0", 3)]
    kept, _ = merge_duplicates(rows, PRIORITY)
    assert len(kept) == 1 and kept[0].rank == 1


def test_confirmed_row_wins_over_possible_duplicate():
    loose = row("laskurliit", "A", "608.8", 4)
    loose.possible = True
    sure = row("protokollitaja", "A", "608.8", 4)
    kept, _ = merge_duplicates([loose, sure], PRIORITY)
    assert len(kept) == 1 and not kept[0].possible and kept[0].source == "protokollitaja"
