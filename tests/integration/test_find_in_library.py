"""給模型讀媒體庫的工具 `inventory.find_in_library`（M5 票 28）。

一次好幾個名字，每個名字在這個人**看得到的每一個媒體庫**裡找（brief §11、§12：權限由 Berth 擋，
媒體庫對允許清單驗過才變成 `parentId`）。經執行器叫，與側面板同一條路：Jellyfin 的使用者照 actor
那一列打開，呼叫端給不了。場景同 `test_media_in_jellyfin.py`：`deckhand` 看得到 Movies 與 TV，
看不到 Anime（Frieren 在那裡）；`skipper` 都看得到。
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi.testclient import TestClient

from berth.adapters.jellyfin import ITEM_SERIES, JellyfinItem
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.domain import PlanAction
from berth.models import LedgerEntry
from tests.integration.factories import FakeClientFactory
from tests.integration.test_inventory_api import ADMIN, CREW
from tests.integration.test_media_in_jellyfin import client, execute, factory, jellyfin, tmdb
from tests.integration.test_watch_area_api import BEAR

__all__ = ["client", "factory", "jellyfin", "tmdb"]  # pytest 的 fixture

EDGERUNNERS = "a1" * 16


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
