"""Jellyfin 裡已有、Berth 的帳本沒有的集（M5 票 28）。

作品頁與給模型的 `media.read_media` 是同一份：一集分得出「帳本有」（`imported`）、
「只有 Jellyfin 有」（`in_jellyfin`）與「缺」（`missing`），作品多一格 `jellyfin`。
缺集搜尋不搜 `in_jellyfin` 的集。

權限照觀看區（`test_watch_area_api.py`）：找作品不帶 `parentId`，看不到的媒體庫裡的那一份與不在
Jellyfin 是同一個答案。場景沿用那一份：The Bear 在 TV（`deckhand` 看得到，Jellyfin 有第 1 季
前三集），Frieren 在 Anime（只有 `skipper` 看得到）。
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_core import to_jsonable_python
from sqlalchemy import select

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin import ITEM_EPISODE, ITEM_SERIES, JellyfinItem
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.tmdb import TmdbDetail, TmdbEpisode, TmdbSeason, TmdbSeasonEntry
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.domain import Actor, MediaKind
from berth.models import TmdbSettings, User
from berth.services.agent_tools import MODEL_VIEWS
from berth.services.executor import Executor
from berth.services.hints import JobHints
from berth.services.settings import write_settings
from tests.conftest import TMDB_API_KEY
from tests.integration.arrange import factory_for
from tests.integration.factories import FakeClientFactory
from tests.integration.test_inventory_api import ADMIN, CREW, sign_in
from tests.integration.test_watch_area_api import BEAR, FRIEREN, client, jellyfin

__all__ = ["client", "jellyfin"]  # pytest 的 fixture，從觀看區的測試借來


def show(
    tmdb_id: int, title: str, *seasons: tuple[int, date]
) -> tuple[TmdbDetail, list[TmdbSeason]]:
    """每一季（集數, 首播日）、每週一集、都播完了的劇。"""
    built = [
        TmdbSeason(
            season_number=number,
            name=f"Season {number}",
            air_date=first,
            episodes=tuple(
                TmdbEpisode(
                    season_number=number,
                    episode_number=episode,
                    name=f"Episode {episode}",
                    air_date=first + timedelta(weeks=episode - 1),
                    runtime=30,
                )
                for episode in range(1, count + 1)
            ),
        )
        for number, (count, first) in enumerate(seasons, start=1)
    ]
    detail = TmdbDetail(
        tmdb_id=tmdb_id,
        kind=MediaKind.TV,
        title=title,
        original_title=title,
        year=seasons[0][1].year,
        first_air_date=seasons[0][1],
        overview="",
        poster_path="",
        titles=(title,),
        seasons=tuple(
            TmdbSeasonEntry(
                season_number=row.season_number,
                name=row.name,
                episode_count=len(row.episodes),
                air_date=row.air_date,
            )
            for row in built
        ),
    )
    return detail, built


#: TMDB 上 The Bear 第 1 季 8 集（Jellyfin 有前三集）、Frieren 第 1 季 4 集（Jellyfin 有第 1 集）。
BEAR_FIRST = date(2022, 6, 23)
BEAR_TMDB = show(136315, "The Bear", (8, BEAR_FIRST))
FRIEREN_FIRST = date(2023, 9, 29)
FRIEREN_TMDB = show(209867, "Frieren", (4, FRIEREN_FIRST))
#: TMDB 上 Kaiju No. 8 第 1 季 14 集、第 2 季 2 集（`TestTheNumbering`）。
KAIJU = 207468
KAIJU_FIRST = date(2024, 4, 13)
KAIJU_TMDB = show(KAIJU, "Kaiju No. 8", (14, KAIJU_FIRST), (2, date(2025, 7, 19)))
#: Jellyfin 的 TV 媒體庫裡 Kaiju No. 8 的 id。
KAIJU_SERIES = "c" * 32


#: 電影沒有季表，只有作品那一格（替身 Jellyfin 的 Movies 有它）。
OPPENHEIMER_TMDB = TmdbDetail(
    tmdb_id=872585,
    kind=MediaKind.MOVIE,
    title="Oppenheimer",
    original_title="Oppenheimer",
    year=2023,
    first_air_date=date(2023, 7, 19),
    overview="",
    poster_path="",
    runtime=180,
    titles=("Oppenheimer",),
)


@pytest.fixture
def factory(roots: dict[str, Path], jellyfin: FakeJellyfinClient) -> FakeClientFactory:
    """觀看區那一份 Jellyfin 的集補上播出日（Jellyfin 從 metadata 拿到的 `PremiereDate`）：
    集照播出日對到 TMDB（M5 票 28），不照 Jellyfin 的季集號。"""
    aired = {BEAR: BEAR_FIRST, FRIEREN: FRIEREN_FIRST}
    jellyfin.items_ = [
        replace(item, premiere_date=aired[item.series_id] + timedelta(weeks=item.episode_start - 1))
        if item.type == ITEM_EPISODE and item.series_id in aired and item.episode_start
        else item
        for item in jellyfin.items_
    ]
    shows = (BEAR_TMDB, FRIEREN_TMDB, KAIJU_TMDB)
    tmdb = FakeTmdbClient(
        details=[*(detail for detail, _ in shows), OPPENHEIMER_TMDB],
        seasons={detail.tmdb_id: seasons for detail, seasons in shows},
    )
    return factory_for(roots, jellyfin=jellyfin, tmdb=tmdb)


@pytest.fixture(autouse=True)
def tmdb(client: TestClient) -> None:
    """觀看區不讀 TMDB；作品頁的季集表要它（替身照 `tests/fixtures/tmdb` 回）。"""

    async def write() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]  # Starlette 的型別
        async with sessions() as session:
            await write_settings(session, TmdbSettings(api_key=TMDB_API_KEY))
            await session.commit()

    asyncio.run(write())


def as_tool(
    client: TestClient, factory: FakeClientFactory, who: dict[str, str], name: str, **arguments: Any
) -> Any:  # `Any`：給模型的是 JSON
    """側面板交給模型的樣子：結果轉成 JSON、再套 `MODEL_VIEWS`（`agent.Turn.run_tool`）。"""
    plain = to_jsonable_python(execute(client, factory, who, name, **arguments))
    view = MODEL_VIEWS.get(name)
    return plain if view is None else view(plain)


def execute(
    client: TestClient, factory: FakeClientFactory, who: dict[str, str], name: str, **arguments: Any
) -> Any:  # `Any`：結果型別隨命令
    """以 `who` 的身分（AI 替他）經執行器叫一次。先登入一次：`users` 那一列是登入時鏡像的。"""
    sign_in(client, who)
    app: Any = client.app
    executor = Executor(
        factory=factory,
        hub=app.state.events,
        sources=app.state.sources,
        plans=JobHints(),
        imports=JobHints(),
        access=app.state.jellyfin_access,
    )

    async def run() -> Any:
        async with app.state.session_factory() as session:
            user = await session.scalar(select(User).where(User.name == who["username"]))
            assert user is not None
            return await executor.execute(session, name, arguments, Actor.ai(user.id, user.role))

    return asyncio.run(run())


def statuses(media: dict[str, Any], season: int) -> dict[int, str]:
    [found] = [row for row in media["seasons"] if row["season_number"] == season]
    return {row["episode_number"]: row["status"] for row in found["episodes"]}


class TestTheWorkPage:
    def test_episodes_jellyfin_has_are_not_missing(self, client: TestClient) -> None:
        sign_in(client, CREW)

        media = client.get("/api/media/tv:136315").json()

        assert media["jellyfin"] == "found"
        episodes = statuses(media, 1)
        assert {number for number, status in episodes.items() if status == "in_jellyfin"} == {
            1,
            2,
            3,
        }
        assert {number for number, status in episodes.items() if status == "missing"} == set(
            range(4, 9)
        )

    def test_a_film_in_jellyfin_is_found(self, client: TestClient) -> None:
        sign_in(client, CREW)

        media = client.get("/api/media/movie:872585").json()

        assert (media["jellyfin"], media["files"]) == ("found", [])

    def test_a_library_this_user_cannot_see_is_the_same_as_not_in_jellyfin(
        self, client: TestClient
    ) -> None:
        sign_in(client, CREW)

        media = client.get("/api/media/tv:209867").json()

        assert media["jellyfin"] == "absent"
        assert "in_jellyfin" not in statuses(media, 1).values()

    def test_the_owner_who_sees_that_library_gets_it(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        media = client.get("/api/media/tv:209867").json()

        assert media["jellyfin"] == "found"
        assert statuses(media, 1)[1] == "in_jellyfin"

    def test_jellyfin_out_of_reach_leaves_the_page_as_it_was(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client, CREW)
        jellyfin.error = ServiceUnavailableError("GET /Items: 503")

        response = client.get("/api/media/tv:136315")

        assert response.status_code == 200
        media = response.json()
        assert media["jellyfin"] == "unknown"
        assert set(statuses(media, 1).values()) == {"missing"}


class TestTheMissingSearch:
    """缺集搜尋不搜 Jellyfin 已有的集：預覽與真的送出去的是同一份（`search._texts`）。"""

    def test_the_preview_asks_only_for_what_jellyfin_lacks(self, client: TestClient) -> None:
        sign_in(client, CREW)

        queries = client.get("/api/search/queries?media=tv:136315&missing=true&season=1").json()[
            "queries"
        ]

        asked = {token for query in queries for token in query.split() if token.startswith("S01")}
        assert asked == {f"S01E0{number}" for number in range(4, 9)}

    def test_the_search_sends_the_same(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        sign_in(client, CREW)
        preview = client.get("/api/search/queries?media=tv:136315&missing=true&season=1").json()[
            "queries"
        ]

        client.get("/api/search?media=tv:136315&missing=true&season=1")

        assert [query.text for query in factory.indexer_search_.queries] == preview
        assert not any("S01E01" in query for query in preview)


class TestWhatTheModelGets:
    def test_the_assistant_tells_imported_jellyfin_only_and_missing_apart(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """側面板的那一份（執行器 → JSON → `MODEL_VIEWS`）：逐集收成「狀態 → 範圍」。"""
        given = as_tool(client, factory, CREW, "media.read_media", media_id="tv:136315")

        assert given["jellyfin"] == "found"
        [season] = [row for row in given["seasons"] if row["season_number"] == 1]
        assert season["episodes"] == {"in_jellyfin": "1-3", "missing": "4-8"}


def kaiju_in_jellyfin(jellyfin: FakeJellyfinClient, *, last: JellyfinItem) -> None:
    """Jellyfin 照 TVDB 的編法：TMDB 第 1 季的 14 集在它那裡是 S01E01–E13 加 S02E01（`last`）。
    前 13 集都帶播出日（Jellyfin 的集沒有 TMDB 的集 id，12.1.0 實測）。"""
    [tv] = [row.locations[0] for row in jellyfin.libraries_ if row.name == "TV"]
    folder = f"{tv}/Kaiju No. 8 (2024) [tmdbid-{KAIJU}]"
    jellyfin.items_ = [
        *jellyfin.items_,
        JellyfinItem(KAIJU_SERIES, ITEM_SERIES, "Kaiju No. 8", folder, str(KAIJU)),
        *(
            JellyfinItem(
                f"{number:032x}",
                ITEM_EPISODE,
                f"Episode {number}",
                f"{folder}/Season 01/S01E{number:02d}.mkv",
                "",
                series_id=KAIJU_SERIES,
                season=1,
                episode_start=number,
                premiere_date=KAIJU_FIRST + timedelta(weeks=number - 1),
            )
            for number in range(1, 14)
        ),
        last,
    ]


def tvdb_s02e01(*, premiere: date | None = None) -> JellyfinItem:
    """Jellyfin 的 S02E01：其實是 TMDB 的 S01E14。"""
    return JellyfinItem(
        "e" * 32,
        ITEM_EPISODE,
        "Episode 14",
        "/x/Season 02/S02E01.mkv",
        "",
        series_id=KAIJU_SERIES,
        season=2,
        episode_start=1,
        premiere_date=premiere,
    )


def episode(media: dict[str, Any], season: int, number: int) -> dict[str, Any]:
    [found] = [row for row in media["seasons"] if row["season_number"] == season]
    [row] = [row for row in found["episodes"] if row["episode_number"] == number]
    picked: dict[str, Any] = row
    return picked


class TestTheNumbering:
    """Jellyfin 的季集號不算數（使用者 2026-10-30）：照播出日（±1 天）對 TMDB；對不上的不算
    Jellyfin 已有，照舊是缺，只標「Jellyfin 可能有」。寧可多下一集，不要漏一集。原本要的「先照
    TMDB 的集 id」做不了：Jellyfin 的集不帶它（12.1.0 實測）。"""

    def test_the_air_date_is_next_within_a_day(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        """TMDB 的 S01E14 是 2024-07-13 播出；Jellyfin 記成隔天（時區）也算。Jellyfin 的季集號
        （S02E01）指向的 TMDB S02E01 不算有。"""
        kaiju_in_jellyfin(jellyfin, last=tvdb_s02e01(premiere=date(2024, 7, 14)))
        sign_in(client, CREW)

        media = client.get(f"/api/media/tv:{KAIJU}").json()

        assert episode(media, 1, 14)["status"] == "in_jellyfin"
        assert episode(media, 2, 1)["status"] == "missing"

    def test_an_episode_matching_nothing_is_still_missing_but_flagged(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        """沒有集 id、播出日差兩天以上：不算有（缺集搜尋照問），但 Jellyfin 的那一集說得出來，
        同編號的 TMDB 那一集標「Jellyfin 可能有」。"""
        kaiju_in_jellyfin(jellyfin, last=tvdb_s02e01(premiere=date(2024, 7, 20)))
        sign_in(client, CREW)

        media = client.get(f"/api/media/tv:{KAIJU}").json()

        assert episode(media, 1, 14)["status"] == "missing"
        assert episode(media, 2, 1)["status"] == "missing"
        assert episode(media, 2, 1)["jellyfin_maybe"] is True
        assert episode(media, 1, 14)["jellyfin_maybe"] is False
        assert media["jellyfin_unmatched"] == [
            {"season": 2, "episode_start": 1, "episode_end": None, "premiere_date": "2024-07-20"}
        ]
        queries = client.get(f"/api/search/queries?media=tv:{KAIJU}&missing=true&season=2").json()[
            "queries"
        ]
        assert any("S02E01" in query or "S02" in query.split() for query in queries)

    def test_the_assistant_sees_the_unsure_ones_too(
        self, client: TestClient, factory: FakeClientFactory, jellyfin: FakeJellyfinClient
    ) -> None:
        kaiju_in_jellyfin(jellyfin, last=tvdb_s02e01())

        given = as_tool(client, factory, CREW, "media.read_media", media_id=f"tv:{KAIJU}")

        [first, second] = [row for row in given["seasons"] if row["season_number"] in (1, 2)]
        assert first["episodes"] == {"in_jellyfin": "1-13", "missing": "14"}
        assert (second["episodes"], second["jellyfin_maybe"]) == ({"missing": "1-2"}, "1")
        assert given["jellyfin_unmatched"] == {"2": "1"}
