"""命令登錄表的乾跑（M5 票 06）：確認卡的預覽要先跑命令的驗證。

prototype 實測（brief §20.24）：`route_required`（加 Feed 漏了電影 Route）與 `route_kind_mismatch`
（劇場版送進只收劇集的 Route）都是按了確認才被 Berth 擋下。這裡證明送單、加 Feed、兩種訂閱的
`validate` 在不改任何狀態的情況下就擋得下這兩種，而且說得跟真的執行一樣。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    CollectionType,
    FeedKind,
    JobRefusal,
    JobState,
    JobTrigger,
    RssRefusal,
    label_of,
)
from berth.models import Job, Media, Route, RssFeed, RssSeries
from berth.services import registry
from berth.services.downloading import add_manual_download
from berth.services.jobs import JobRejectedError, JobSource
from berth.services.registry import Verdict, dry_run
from berth.services.rss import RssRejectedError, add_feed, subscribe_mikan, subscribe_search
from tests.integration.arrange import arrange, factory_for
from tests.integration.test_rss import FEED_URL, anime_route, count, kimi

pytestmark = pytest.mark.asyncio

SOURCE = JobSource(url="https://example.test/one.torrent", title="[Sub] Kimi - 01 [1080p]")
HASH = "a" * 40
#: 模型送來的長相：`source` 是一個物件。
SOURCE_ARGUMENT = {"url": SOURCE.url, "title": SOURCE.title}


async def harbour(session: AsyncSession, roots: dict[str, Path]) -> tuple[Media, Route, Route]:
    """精靈跑完、《与你相恋》（劇集）打開過；一條收劇集的 anime、一條收電影的 movies。"""
    await arrange(session, roots)
    media = await kimi(session)
    anime = await anime_route(session, roots)
    movies = await anime_route(
        session,
        roots,
        slug="movies",
        name="Movies",
        jellyfin_library_id="item-3",
        jellyfin_library_name="Movies",
        collection_type=CollectionType.MOVIES,
        target_path=str(roots["library"] / "movies"),
        category="berth-movies",
    )
    return media, anime, movies


async def unchanged(session: AsyncSession) -> tuple[int, ...]:
    return tuple([await count(session, model) for model in (RssFeed, RssSeries, Job)])


async def check(session: AsyncSession, name: str, arguments: dict[str, object]) -> Verdict:
    before = await unchanged(session)
    verdict = await dry_run(registry.commands()[name], session, arguments)
    assert await unchanged(session) == before
    assert not session.new
    assert not session.dirty
    return verdict


class TestAddFeed:
    async def test_a_kind_with_routes_but_none_chosen_is_route_required(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, anime, _ = await harbour(session, roots)

        verdict = await check(session, "rss.add_feed", {"url": FEED_URL, "tv_route_id": anime.id})

        assert verdict == Verdict(checked=True, refusal=RssRefusal.ROUTE_REQUIRED, detail="movie")
        with pytest.raises(RssRejectedError) as refused:
            await add_feed(session, url=FEED_URL, tv_route_id=anime.id)
        assert refused.value.reason is verdict.refusal

    async def test_a_route_of_the_other_kind_is_route_kind_mismatch(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, anime, _ = await harbour(session, roots)

        verdict = await check(
            session,
            "rss.add_feed",
            {"url": FEED_URL, "tv_route_id": anime.id, "movie_route_id": anime.id},
        )

        assert verdict.refusal is RssRefusal.ROUTE_KIND_MISMATCH

    async def test_a_feed_that_would_be_added_passes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, anime, movies = await harbour(session, roots)
        arguments = {"url": FEED_URL, "tv_route_id": anime.id, "movie_route_id": movies.id}

        assert await check(session, "rss.add_feed", arguments) == Verdict(checked=True)
        await add_feed(session, url=FEED_URL, tv_route_id=anime.id, movie_route_id=movies.id)
        assert (await check(session, "rss.add_feed", arguments)).refusal is (
            RssRefusal.FEED_DUPLICATE
        )


class TestSubmit:
    async def test_a_route_of_the_other_kind_is_route_kind_mismatch(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, _, movies = await harbour(session, roots)
        arguments = {"source": SOURCE_ARGUMENT, "media_id": media.id, "route_id": movies.id}

        verdict = await check(session, "downloading.add_manual_download", arguments)

        assert verdict.refusal is JobRefusal.ROUTE_KIND_MISMATCH
        with pytest.raises(JobRejectedError) as refused:
            await add_manual_download(
                session,
                factory_for(roots),
                source=SOURCE,
                media_id=media.id,
                route_id=movies.id,
                user_id=1,
                actor="1",
            )
        assert refused.value.reason is verdict.refusal

    async def test_the_right_route_passes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        arguments = {"source": SOURCE_ARGUMENT, "media_id": media.id, "route_id": anime.id}

        assert await check(session, "downloading.add_manual_download", arguments) == Verdict(
            checked=True
        )

    async def test_a_removed_job_with_the_reported_hash_is_job_removed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """索引站報了 hash 而那一筆刪掉過：執行時是 `job_removed`，預覽也要是。"""
        media, anime, _ = await harbour(session, roots)
        session.add(
            Job(
                hash=HASH,
                name=SOURCE.title,
                source_url=SOURCE.url,
                trigger=JobTrigger.MANUAL,
                media_id=media.id,
                route_id=anime.id,
                state=JobState.REMOVED,
            )
        )
        await session.commit()
        arguments = {
            "source": SOURCE_ARGUMENT | {"info_hash": HASH},
            "media_id": media.id,
            "route_id": anime.id,
        }

        verdict = await check(session, "downloading.add_manual_download", arguments)

        assert verdict == Verdict(checked=True, refusal=JobRefusal.JOB_REMOVED, detail=HASH)


class TestSubscribe:
    async def test_mikan_into_a_route_of_the_other_kind_is_route_kind_mismatch(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, _, movies = await harbour(session, roots)
        arguments = {"bangumi_id": 3310, "subgroup_id": 370, "media_id": media.id}

        verdict = await check(session, "rss.subscribe_mikan", arguments | {"route_id": movies.id})

        assert verdict.refusal is RssRefusal.ROUTE_KIND_MISMATCH
        with pytest.raises(RssRejectedError) as refused:
            await subscribe_mikan(
                session,
                factory_for(roots),
                bangumi_id=3310,
                subgroup_id=370,
                media_id=media.id,
                route_id=movies.id,
                user_id=1,
                actor=label_of(1),
            )
        assert refused.value.reason is verdict.refusal

    async def test_mikan_into_the_right_route_passes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        arguments = {"bangumi_id": 3310, "subgroup_id": 370, "media_id": media.id}

        verdict = await check(session, "rss.subscribe_mikan", arguments | {"route_id": anime.id})

        assert verdict == Verdict(checked=True)

    async def test_a_search_feed_into_a_route_of_the_other_kind_is_route_kind_mismatch(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, movies = await harbour(session, roots)
        arguments = {"kind": "nyaa", "term": "Kimi", "subgroup": "ANi", "media_id": media.id}

        verdict = await check(session, "rss.subscribe_search", arguments | {"route_id": movies.id})

        assert verdict.refusal is RssRefusal.ROUTE_KIND_MISMATCH
        with pytest.raises(RssRejectedError) as refused:
            await subscribe_search(
                session,
                factory_for(roots),
                kind=FeedKind.NYAA,
                term="Kimi",
                subgroup="ANi",
                media_id=media.id,
                route_id=movies.id,
                user_id=1,
            )
        assert refused.value.reason is verdict.refusal
        right = await check(session, "rss.subscribe_search", arguments | {"route_id": anime.id})
        assert right == Verdict(checked=True)


async def test_a_command_without_a_validator_only_shows_its_arguments(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    await harbour(session, roots)

    assert await check(session, "rss.set_feed_interval", {"feed_id": 1, "interval_sec": 7}) == (
        Verdict(checked=False)
    )
