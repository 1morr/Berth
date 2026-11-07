"""給模型讀媒體庫的工具 `inventory.find_in_library`（M5 票 28）。

一次好幾個名字，每個名字在這個人**看得到的每一個媒體庫**裡找（brief §11、§12：權限由 Berth 擋，
媒體庫對允許清單驗過才變成 `parentId`）。經執行器叫，與側面板同一條路：Jellyfin 的使用者照 actor
那一列打開，呼叫端給不了。場景同 `test_media_in_jellyfin.py`：`deckhand` 看得到 Movies 與 TV，
看不到 Anime（Frieren 在那裡）；`skipper` 都看得到。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from berth.adapters.http import NotFoundError, ServiceUnavailableError
from berth.adapters.jellyfin import ITEM_EPISODE, ITEM_SERIES, JellyfinItem
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.domain import PlanAction
from berth.models import LedgerEntry
from berth.services import inventory
from tests.integration.factories import FakeClientFactory
from tests.integration.test_inventory_api import ADMIN, CREW, jellyfin_id
from tests.integration.test_media_in_jellyfin import (
    as_tool,
    client,
    execute,
    factory,
    jellyfin,
    tmdb,
)
from tests.integration.test_watch_area_api import BEAR, BEAR_S01

__all__ = ["client", "factory", "jellyfin", "tmdb"]  # pytest 的 fixture

EDGERUNNERS = "a1" * 16
#: TV 上另一部劇（`test_only_so_many_shows_are_read_per_lookup` 這幾支用）。
OTHER_SERIES = "c1" * 16


def add_series(jellyfin: FakeJellyfinClient, series_id: str, title: str, *episodes: int) -> None:
    """TV 媒體庫多一部劇，每一集一個 item；路徑放在電視庫底下，替身才看得到。"""
    [tv] = [row.locations[0] for row in jellyfin.libraries_ if row.name == "TV"]
    folder = f"{tv}/{title}"
    jellyfin.items_ = [
        *jellyfin.items_,
        JellyfinItem(series_id, ITEM_SERIES, title, folder, ""),
        *(
            JellyfinItem(
                f"{series_id[:30]}{number:02d}",
                ITEM_EPISODE,
                f"Episode {number}",
                f"{folder}/S01E{number:02d}.mkv",
                "",
                series_id=series_id,
                season=1,
                episode_start=number,
            )
            for number in episodes
        ),
    ]


def find(
    client: TestClient, factory: FakeClientFactory, who: dict[str, str], *names: str
) -> Any:  # `Any`：命令的結果照 JSON 讀
    return execute(client, factory, who, "inventory.find_in_library", names=list(names))


def titles(found: Any, name: str) -> list[tuple[str, str, str]]:
    [lookup] = [row for row in found.names if row.name == name]
    return [(row.title, row.library, row.media_id) for row in lookup.titles]


class TestFindInLibrary:
    def test_a_name_in_a_library_this_user_sees_is_found(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        found = find(client, factory, CREW, "bear")

        assert titles(found, "bear") == [("The Bear", "TV", "tv:136315")]
        [row] = found.names[0].titles
        assert (row.kind, row.year, row.in_ledger) == ("tv", None, False)

    def test_a_library_this_user_cannot_see_is_never_searched(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        found = find(client, factory, CREW, "Frieren", "bear")

        assert titles(found, "Frieren") == []
        assert "Anime" not in found.libraries
        assert set(found.libraries) == {"Movies", "TV"}

    def test_the_owner_sees_every_library(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        found = find(client, factory, ADMIN, "Frieren")

        assert titles(found, "Frieren") == [("Frieren", "Anime", "tv:209867")]

    def test_it_says_which_ones_berth_has_records_of(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """Jellyfin 有、帳本也記著的（連到那一部的 Series id）是 `in_ledger`。"""
        app: Any = client.app

        async def record() -> None:
            async with app.state.session_factory() as session:
                session.add(
                    LedgerEntry(
                        source_rel_path="The Bear/S01E01.mkv",
                        source_abs_path="/data/complete/The Bear/S01E01.mkv",
                        source_dev="1",
                        target_path="/data/media/tv/The Bear/Season 01/S01E01.mkv",
                        target_inode="2",
                        action=PlanAction.IMPORT,
                        season=1,
                        episode_start=1,
                        jellyfin_series_id=BEAR,
                    )
                )
                await session.commit()

        asyncio.run(record())

        [row] = find(client, factory, CREW, "bear").names[0].titles
        assert row.in_ledger is True

    def test_case_spaces_and_punctuation_do_not_matter(
        self, client: TestClient, factory: FakeClientFactory, jellyfin: FakeJellyfinClient
    ) -> None:
        """自己複製進去的資料夾名常常少了冒號（Windows 的檔名不收），模型給的是 AniList 的寫法
        （票 28 真模型那一輪的紅燈）；名字是較長標題的一段也算（續作、多了年份）。"""
        [tv] = [row.locations[0] for row in jellyfin.libraries_ if row.name == "TV"]
        jellyfin.items_ = [
            *jellyfin.items_,
            JellyfinItem(EDGERUNNERS, ITEM_SERIES, "Cyberpunk Edgerunners 2", f"{tv}/x", ""),
        ]

        found = find(client, factory, CREW, "Cyberpunk: Edgerunners 2", "EDGERUNNERS", "The Bear!")

        assert titles(found, "Cyberpunk: Edgerunners 2") == [("Cyberpunk Edgerunners 2", "TV", "")]
        assert titles(found, "EDGERUNNERS") == [("Cyberpunk Edgerunners 2", "TV", "")]
        assert titles(found, "The Bear!") == [("The Bear", "TV", "tv:136315")]
        # 整個名字相同的才是 `exact`：只對上一段的多半是另一季、另一部。
        assert [row.exact for row in found.names[0].titles] == [True]
        assert [row.exact for row in found.names[1].titles] == [False]

    def test_a_too_short_name_only_matches_a_whole_title(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """「K」出現在幾乎每一個名字裡：太短的名字只在整個名字相同時算。大小寫不同的同一個名字
        只找一次。"""
        found = find(client, factory, CREW, "e", "BEAR", "bear")

        assert titles(found, "e") == []
        assert [row.name for row in found.names] == ["e", "BEAR"]

    def test_a_show_says_which_episodes_the_library_has(
        self, client: TestClient, factory: FakeClientFactory, jellyfin: FakeJellyfinClient
    ) -> None:
        """劇集的命中多一格 `episodes`（M5.6 票 06）：Jellyfin 自己的季集號，一季一段範圍，
        中間缺的會斷開；一個檔案兩集時兩集都算。"""
        jellyfin.items_ = [
            *jellyfin.items_,
            JellyfinItem(
                "b1" * 16,
                ITEM_EPISODE,
                "Episode 5-6",
                "/x/S01E05-E06.mkv",
                "",
                series_id=BEAR,
                season_id=BEAR_S01,
                season=1,
                episode_start=5,
                episode_end=6,
            ),
            # Jellyfin 數不出來的集（特典、沒編號的檔案）不算進範圍，但要說出來。
            JellyfinItem("b2" * 16, ITEM_EPISODE, "Special", "/x/Special.mkv", "", series_id=BEAR),
        ]

        [row] = find(client, factory, CREW, "bear").names[0].titles

        assert row.episodes == {"1": "1-3, 5-6"}
        assert row.episodes_note == "1 of its episodes have no season or episode number in Jellyfin"

    def test_the_model_gets_episodes_on_shows_only(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """電影沒有 `episodes` 這一格（M5.6 票 06）；劇集讀得到集數時不必帶空的原因。"""
        seen = as_tool(
            client, factory, CREW, "inventory.find_in_library", names=["Oppenheimer", "bear"]
        )

        [movie] = seen["names"][0]["titles"]
        assert "episodes" not in movie
        assert "episodes_note" not in movie
        [show] = seen["names"][1]["titles"]
        assert show["episodes"] == {"1": "1-3"}
        assert "episodes_note" not in show

    def test_each_show_is_read_once_however_many_names_hit_it(
        self, client: TestClient, factory: FakeClientFactory, jellyfin: FakeJellyfinClient
    ) -> None:
        """請求數有上界（M5.6 票 06）：每個名字都對到同一部劇也只讀一次集數；電影不讀。"""
        find(client, factory, CREW, "bear", "The Bear", "BEAR", "Oppenheimer")

        reads = [query for query in jellyfin.watch_area_queries if query[0] == "series_episodes"]
        assert reads == [("series_episodes", jellyfin_id(client, CREW), BEAR)]

    def test_only_so_many_shows_are_read_per_lookup(
        self,
        client: TestClient,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """請求數有上界（M5.6 票 06）：一次查詢最多讀 `FIND_EPISODE_READS` 部劇，其餘的說沒讀。"""
        add_series(jellyfin, OTHER_SERIES, "Severance", 1)
        monkeypatch.setattr(inventory, "FIND_EPISODE_READS", 1)

        found = find(client, factory, CREW, "bear", "severance")

        reads = [query for query in jellyfin.watch_area_queries if query[0] == "series_episodes"]
        assert [query[2] for query in reads] == [BEAR]
        [skipped] = found.names[1].titles
        assert skipped.episodes == {}
        assert "not read" in skipped.episodes_note

    def test_one_show_failing_does_not_take_the_others_episodes_down(
        self,
        client: TestClient,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """一部劇的集數讀不到（權限被收回、Jellyfin 一時答不出來）只影響那一部（M5.6 票 06）。"""
        add_series(jellyfin, OTHER_SERIES, "Severance", 1, 2)
        original = jellyfin.series_episodes

        async def flaky(*, user_id: str, series_id: str) -> tuple[JellyfinItem, ...]:
            if series_id == OTHER_SERIES:
                raise NotFoundError("GET /Shows/x/Episodes: 404")
            return await original(user_id=user_id, series_id=series_id)

        monkeypatch.setattr(jellyfin, "series_episodes", flaky)

        found = find(client, factory, CREW, "bear", "severance")

        [bear] = found.names[0].titles
        assert bear.episodes == {"1": "1-3"}
        [other] = found.names[1].titles
        assert other.episodes == {}
        assert "would not show" in other.episodes_note

    def test_episodes_that_cannot_be_read_say_why_without_failing_the_call(
        self,
        client: TestClient,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """整次呼叫不失敗（M5.6 票 06）：那一部說不出集數與原因，其餘照樣回。"""

        async def down(**_: object) -> None:
            raise ServiceUnavailableError("GET /Shows/x/Episodes: 503")

        monkeypatch.setattr(jellyfin, "series_episodes", down)

        seen = as_tool(
            client, factory, CREW, "inventory.find_in_library", names=["bear", "Oppenheimer"]
        )

        [show] = seen["names"][0]["titles"]
        assert show["episodes"] == {}
        assert "503" in show["episodes_note"]
        [movie] = seen["names"][1]["titles"]
        assert movie["media_id"] == "movie:872585"
        assert "episodes" not in movie
