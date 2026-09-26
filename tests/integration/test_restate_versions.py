"""新版本入庫時，哪幾列帳本重新排反查（`importer.restate_versions`，M1 票 14b、M4 票 02）。

Jellyfin 12 的版本名是「去掉各版本檔名的共同前綴」，多一個版本會改掉**同一集**其他版本的名字。
範圍就是 Jellyfin 12 的版本分組：同一個資料夾、同一季、集號範圍重疊。以前是整個資料夾——一季
每入庫一集就把前面每一集重反查一次，而且正好撞在新檔案觸發的重掃上（2026-09-26 試跑）。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import PlanAction, Tags
from berth.models import LedgerEntry, Media, PlanItem, Route
from berth.services.importer import restate_versions
from berth.services.resolve_schedule import first_resolve_at
from tests.integration.test_inventory import film, linked, route, title

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 9, 26, 4, 30, tzinfo=UTC)
SECOND_GROUP = Tags(resolution="1080p", group="Other")


async def resolved(
    session: AsyncSession,
    media: Media,
    under: Route,
    *,
    season_number: int | None = 1,
    episode: int | None = 1,
    episode_end: int | None = None,
) -> LedgerEntry:
    """一列早就反查完、不再排程的帳本。"""
    return await linked(
        session,
        media,
        under,
        season_number=season_number,
        episode=episode,
        episode_end=episode_end,
        item=f"item-{season_number}-{episode}",
    )


async def a_new_version(
    session: AsyncSession,
    media: Media,
    under: Route,
    *,
    season_number: int | None = 1,
    episode: int | None = 1,
    episode_end: int | None = None,
) -> None:
    """同一部作品新入庫的一個版本：目標路徑照 `linked` 的形狀、換一個發佈組。"""
    row = await linked(
        session,
        media,
        under,
        season_number=season_number,
        episode=episode,
        episode_end=episode_end,
        tags=SECOND_GROUP,
    )
    item = PlanItem(
        action=PlanAction.IMPORT,
        media_id=media.id,
        season=season_number,
        episode_start=episode,
        episode_end=episode_end,
    )
    await restate_versions(session, item, row.target_path, NOW)
    await session.commit()


def restated(entry: LedgerEntry) -> bool:
    return entry.resolve_after == first_resolve_at(NOW) and entry.resolve_attempts == 0


class TestTheSameEpisode:
    async def test_only_the_other_versions_of_that_episode_are_asked_again(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session)
        first = await resolved(session, spy, tv, episode=1)
        others = [await resolved(session, spy, tv, episode=n) for n in (2, 3)]

        await a_new_version(session, spy, tv, episode=1)

        assert restated(first)
        assert [entry.resolve_after for entry in others] == [None, None]

    async def test_a_multi_episode_file_that_covers_it_is_asked_again(
        self, session: AsyncSession
    ) -> None:
        """集號範圍重疊：`S01E01-E02` 那一份與新的 `S01E02` 在 Jellyfin 裡是同一組的候選。"""
        tv = await route(session)
        spy = await title(session)
        double = await resolved(session, spy, tv, episode=1, episode_end=2)
        third = await resolved(session, spy, tv, episode=3)

        await a_new_version(session, spy, tv, episode=2)

        assert restated(double)
        assert third.resolve_after is None

    async def test_the_same_number_in_another_season_is_left_alone(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session)
        other_season = await resolved(session, spy, tv, season_number=2, episode=1)

        await a_new_version(session, spy, tv, season_number=1, episode=1)

        assert other_season.resolve_after is None

    async def test_the_same_episode_under_another_route_is_left_alone(
        self, session: AsyncSession
    ) -> None:
        """另一個資料夾就是另一個媒體庫：Jellyfin 不會把它們併成一組。"""
        tv = await route(session)
        anime = await route(session, "anime")
        spy = await title(session)
        elsewhere = await resolved(session, spy, anime, episode=1)

        await a_new_version(session, spy, tv, episode=1)

        assert elsewhere.resolve_after is None


class TestMovies:
    async def test_every_other_version_in_the_folder_is_asked_again(
        self, session: AsyncSession
    ) -> None:
        """電影沒有季集：同一個資料夾裡的正片都是同一部的版本。"""
        movies = await route(session, "movies")
        oppenheimer = await film(session)
        first = await resolved(session, oppenheimer, movies, season_number=None, episode=None)

        await a_new_version(session, oppenheimer, movies, season_number=None, episode=None)

        assert restated(first)
