"""送單時不說 Route 就送到哪一條（`media.preselected_route`）：搜尋頁的下拉與 AI 送單讀同一個值
（M5 票 12 把這條規則從前端搬到後端，只留一份）。"""

from __future__ import annotations

from berth.domain import CollectionType
from berth.services.media import RouteChoice, preselected_route

TV = RouteChoice(id=1, name="TV", slug="tv", collection_type=CollectionType.TVSHOWS)
ANIME = RouteChoice(id=2, name="Anime", slug="anime", collection_type=CollectionType.TVSHOWS)


def test_the_route_of_the_last_submit_comes_first() -> None:
    assert preselected_route(2, (TV, ANIME)) == 2


def test_the_only_route_is_chosen_when_there_is_no_last_one() -> None:
    assert preselected_route(None, (ANIME,)) == 2


def test_a_last_route_that_no_longer_holds_the_work_falls_back() -> None:
    """上次那一條被刪了或停用了：不在收得下的那幾條裡。"""
    assert preselected_route(9, (ANIME,)) == 2
    assert preselected_route(9, (TV, ANIME)) is None


def test_two_routes_and_no_history_choose_nothing() -> None:
    """猜一條的代價是檔案進錯媒體庫（票 04b）。"""
    assert preselected_route(None, (TV, ANIME)) is None
