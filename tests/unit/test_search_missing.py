"""缺集一鍵搜要拿哪幾個關鍵字去問（M1.5 票 10、plan §6 search 群組、§8.4）。

季表已經知道缺哪幾集，所以搜尋不必再從作品名開始。**規則只能有一份實作**：畫面上的預覽
（`GET /search/queries`）與真的送出去的那幾個查詢走同一個函式，前端不重算。

輸入是純資料（快照 + 季表那一份 `SeasonView`），所以這裡不碰資料庫也不打索引站。
"""

from __future__ import annotations

from berth.domain import EpisodeStatus, MediaKind, MediaSnapshot, SeasonSnapshot
from berth.services.inventory import EpisodeView, SeasonView
from berth.services.search import missing_queries

BEAR = MediaSnapshot(
    tmdb_id=136315,
    kind=MediaKind.TV,
    title="熊家餐館",
    title_en="The Bear",
    title_original="The Bear",
    year=2022,
    titles=("The Bear", "熊家餐館"),
)


SPY = MediaSnapshot(
    tmdb_id=120089,
    kind=MediaKind.TV,
    title="間諜家家酒",
    title_en="SPY x FAMILY",
    title_original="SPY×FAMILY",
    year=2022,
    titles=("SPY x FAMILY", "SPY×FAMILY", "間諜家家酒", "间谍过家家"),
)


#: 六季都有缺的作品：季記號也放不下的那一種。快照的季與下面的季表對得起來，
#: 退回去的那一份才是這部作品真的會問的名字（含季號變體）。
LONG = MediaSnapshot(
    tmdb_id=1,
    kind=MediaKind.TV,
    title="長劇",
    title_en="Long Show",
    title_original="Long Show",
    titles=("Long Show", "長劇"),
    seasons=tuple(SeasonSnapshot(season_number=number) for number in range(1, 7)),
)


def episode(number: int, status: EpisodeStatus, absolute: int | None = None) -> EpisodeView:
    return EpisodeView(
        episode_number=number,
        name=f"E{number}",
        air_date=None,
        runtime=None,
        absolute_number=absolute,
        status=status,
    )


def season(number: int, *episodes: EpisodeView) -> SeasonView:
    aired = [row for row in episodes if row.status is not EpisodeStatus.UNAIRED]
    return SeasonView(
        season_number=number,
        name=f"Season {number}",
        episode_count=len(episodes),
        air_date=None,
        imported=sum(row.status is EpisodeStatus.IMPORTED for row in aired),
        aired=len(aired),
        episodes=tuple(episodes),
    )


def test_a_single_missing_episode_asks_for_that_episode() -> None:
    """缺一集：每一個標題各問一次那一集的季集記號。"""
    seasons = (
        season(
            3,
            episode(4, EpisodeStatus.IMPORTED),
            episode(5, EpisodeStatus.MISSING),
        ),
    )

    assert missing_queries(BEAR, seasons) == ("The Bear S03E05", "熊家餐館 S03E05")


def test_a_few_gaps_ask_for_each_of_them() -> None:
    """缺幾集：每一集各一個記號，斷開的也一樣——中間那一集已經入庫，不必再問一次。

    順序是**標題優先**：第一個標題先問完它的每一個記號，缺的每一集才至少都被問過一次。
    """
    seasons = (
        season(
            3,
            episode(4, EpisodeStatus.IMPORTED),
            episode(5, EpisodeStatus.MISSING),
            episode(6, EpisodeStatus.IMPORTED),
            episode(7, EpisodeStatus.MISSING),
        ),
    )

    assert missing_queries(BEAR, seasons) == (
        "The Bear S03E05",
        "The Bear S03E07",
        "熊家餐館 S03E05",
        "熊家餐館 S03E07",
    )


def test_a_season_that_is_missing_every_aired_episode_asks_for_the_season() -> None:
    """整季缺就問季包，不是逐集問——**還沒播的那幾集不算**，不然一季永遠不算「整季缺」。"""
    seasons = (
        season(
            2,
            episode(1, EpisodeStatus.MISSING),
            episode(2, EpisodeStatus.MISSING),
            episode(3, EpisodeStatus.UNAIRED),
        ),
    )

    assert missing_queries(BEAR, seasons) == ("The Bear S02", "熊家餐館 S02")


def test_an_episode_with_an_absolute_number_is_asked_for_by_that_number() -> None:
    """TMDB 給了絕對編號的作品，發佈就是照絕對編號編的——`S02E01` 在那些站上一筆都搜不到。

    **一集只有一個記號**（使用者 2026-09-19 拍板）：兩種寫法都送的話記號數加倍，缺三集就吃掉
    全部配額，中文字幕組認得的那個標題一次都問不到。取上限之後只剩五個，照標題優先序排——
    第一個標題先問完它的每一個記號，缺的每一集至少都被問過一次。
    """
    seasons = (
        season(
            2,
            episode(1, EpisodeStatus.MISSING, absolute=26),
            episode(2, EpisodeStatus.MISSING, absolute=27),
            episode(3, EpisodeStatus.IMPORTED, absolute=28),
        ),
    )

    assert missing_queries(SPY, seasons) == (
        "SPY x FAMILY 26",
        "SPY x FAMILY 27",
        "SPY×FAMILY 26",
        "SPY×FAMILY 27",
        "間諜家家酒 26",
    )


def test_too_many_gaps_to_ask_one_by_one_fall_back_to_the_season() -> None:
    """缺六集就有六個記號，配額只有五個——問前五集等於**默默漏掉一集**，而使用者按的是
    「搜這一季缺的集」。收成季記號之後那一季的每一個發佈都回得來，逐集由結果表的預估去分。
    """
    seasons = (
        season(
            3,
            *(episode(number, EpisodeStatus.MISSING) for number in range(1, 7)),
            *(episode(number, EpisodeStatus.IMPORTED) for number in range(7, 11)),
        ),
    )

    assert missing_queries(BEAR, seasons) == ("The Bear S03", "熊家餐館 S03")


def test_gaps_in_more_seasons_than_the_budget_fall_back_to_the_title_search() -> None:
    """連季記號都放不下（六季以上有缺）就沒有東西收窄得了——退回今天的作品名搜尋，
    而預覽照實顯示那幾個名字，不假裝有逐集。"""
    seasons = tuple(
        season(number, episode(1, EpisodeStatus.MISSING), episode(2, EpisodeStatus.IMPORTED))
        for number in range(1, 7)
    )

    assert missing_queries(LONG, seasons) == (
        "Long Show",
        "長劇",
        "Long Show Season 6",
        "長劇 第6季",
    )


def test_asking_for_one_season_leaves_the_other_seasons_alone() -> None:
    """展開區那一顆搜的是**那一季**：別的季缺什麼與這一次無關（shape §4）。"""
    seasons = (
        season(1, episode(1, EpisodeStatus.MISSING)),
        season(2, episode(1, EpisodeStatus.MISSING), episode(2, EpisodeStatus.IMPORTED)),
    )

    assert missing_queries(BEAR, seasons, season=2) == ("The Bear S02E01", "熊家餐館 S02E01")


def test_nothing_missing_asks_nothing() -> None:
    """沒有缺集就沒有查詢——**不退回作品名**：使用者按的是「搜缺的集」，而缺的集是零。

    畫面上那個入口本來就不會出現（季表沒有缺集時不畫），這一條守的是網址被手改的那一條路。
    """
    seasons = (season(1, episode(1, EpisodeStatus.IMPORTED), episode(2, EpisodeStatus.UNAIRED)),)

    assert missing_queries(BEAR, seasons) == ()
    assert missing_queries(BEAR, ()) == ()
