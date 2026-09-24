"""送單：`add_download` 與 jobs 的讀取端（plan §3.1、§3.3、§6、票 09）。

這一票是**產品第一次真的動到 Berth 以外的東西**。在它之前每個命令都只讀（TMDB、索引站、
健康檢查），從這裡開始 Berth 會在使用者的 qBittorrent 上放一個 torrent，並且把一串字
寫死進 `media.folder_name`——那是整個系統唯一一個定了就改不掉的東西（brief §4.5）。
所以這裡的斷言多半是關於**「什麼時候不做事」**：紅的 Route、重複的 hash、已經凍結過的
資料夾名。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, event, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters import fs
from berth.adapters.http import AuthFailedError, ServiceUnavailableError
from berth.adapters.qbittorrent import QbittorrentCategory
from berth.adapters.torrent import NotATorrentError, TorrentSource
from berth.adapters.torrent_fake import DEFAULT_HASH, FakeTorrentFetcher
from berth.db import create_session_factory
from berth.domain import (
    CollectionType,
    Confidence,
    EventType,
    HealthStatus,
    JobState,
    JobTrigger,
    MediaKind,
    PlanAction,
    PlanStatus,
    Role,
)
from berth.logs import JOB_FIELD, configure_logging, json_line
from berth.models import (
    DiskSettings,
    Event,
    Job,
    Media,
    PathSettings,
    Plan,
    PlanItem,
    Route,
    User,
)
from berth.services.jobs import (
    JobRejectedError,
    JobSource,
    add_download,
    list_jobs,
    read_job,
    read_job_events,
    retry_job,
)
from berth.services.settings import read_settings, write_settings
from berth.services.tracking import is_tracked
from tests.integration.arrange import applied_qbittorrent, arrange, factory_for
from tests.integration.factories import FakeClientFactory

pytestmark = pytest.mark.asyncio

MAGNET = "magnet:?xt=urn:btih:4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b&dn=Spy.x.Family.S03E13"
MAGNET_HASH = "4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b"
RELEASE = "[ANi] SPY×FAMILY - 13 [1080P][WEB-DL][AAC AVC][CHT]"

#: 另一個發佈（同一部作品的第二個版本，brief §7.7）。hash 不同才是另一個 torrent。
OTHER_MAGNET = "magnet:?xt=urn:btih:aa11bb22cc33dd44ee55ff66aa77bb88cc99dd00&dn=Other"
OTHER_HASH = "aa11bb22cc33dd44ee55ff66aa77bb88cc99dd00"


async def _media(session: AsyncSession, *, folder: str = "SPY x FAMILY (2022)") -> Media:
    row = Media(
        id="tv:120089",
        tmdb_id=120089,
        kind=MediaKind.TV,
        title_en="SPY x FAMILY",
        title_original="SPY×FAMILY",
        year=2022,
        folder_name=folder,
    )
    session.add(row)
    await session.commit()
    return row


async def _route(
    session: AsyncSession,
    roots: dict[str, Path],
    *,
    health: HealthStatus = HealthStatus.OK,
    collection_type: CollectionType = CollectionType.TVSHOWS,
    slug: str = "anime",
) -> Route:
    row = Route(
        slug=slug,
        name="Anime",
        jellyfin_library_id="item-2",
        jellyfin_library_name="Anime",
        collection_type=collection_type,
        target_path=str(roots["library"] / "anime"),
        category=f"berth-{slug}",
        health_status=health,
    )
    session.add(row)
    await session.commit()
    return row


def _source(url: str = MAGNET, info_hash: str = "") -> JobSource:
    return JobSource(url=url, title=RELEASE, info_hash=info_hash)


async def _ready(
    session: AsyncSession, roots: dict[str, Path], **route_kwargs: object
) -> tuple[Media, Route, FakeClientFactory]:
    await arrange(session, roots)
    media = await _media(session)
    route = await _route(session, roots, **route_kwargs)  # type: ignore[arg-type]
    return media, route, factory_for(roots)


@contextmanager
def counting(engine: AsyncEngine) -> Iterator[list[str]]:
    """這段期間送到資料庫的每一句 SQL。用它斷言次數，不用計時。"""
    statements: list[str] = []

    def record(
        _conn: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)


async def _plan_backed_jobs(
    session: AsyncSession, media: Media, route: Route, user: User, *, count: int, start: int = 0
) -> None:
    """`count` 筆下載，每一筆都有 Route、Media、送單的人與一份掛著 audit 的計劃。

    四種關聯各一個，逐列問就是每筆四次——這個測試要看見的就是那個倍數。
    """
    for index in range(start, start + count):
        job_hash = f"{index:040x}"
        session.add(
            Job(
                hash=job_hash,
                name=f"Release {index}",
                state=JobState.IMPORTED,
                trigger=JobTrigger.MANUAL,
                media_id=media.id,
                route_id=route.id,
                user_id=user.id,
                added_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index),
            )
        )
        await session.flush()
        plan = Plan(job_hash=job_hash, status=PlanStatus.APPLIED)
        session.add(plan)
        await session.flush()
        session.add(
            PlanItem(
                plan_id=plan.id,
                rel_path=f"{index}.mkv",
                action=PlanAction.IMPORT,
                confidence=Confidence.MEDIUM,
                audit=True,
            )
        )
    await session.commit()


class TestAddDownload:
    async def test_a_job_is_created_and_qbittorrent_takes_the_torrent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await _ready(session, roots)

        outcome = await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        assert outcome.created is True
        assert outcome.job.hash == MAGNET_HASH
        assert outcome.job.state is JobState.SUBMITTED
        assert outcome.job.name == RELEASE
        assert outcome.job.trigger is JobTrigger.MANUAL

    async def test_a_route_deleted_while_the_torrent_is_fetched_is_a_reason_not_a_crash(
        self, session: AsyncSession, roots: dict[str, Path], engine: AsyncEngine
    ) -> None:
        """前提查過之後、建 Job 之前，Route 在另一個請求裡被刪掉了（票 14a）。外鍵在 flush 當下
        就擋下那一列，等不到 commit；那是 `route_missing`（422），不是 500。"""
        media, route, factory = await _ready(session, roots)
        sessions = create_session_factory(engine)

        class DeletingFetcher(FakeTorrentFetcher):
            """去要 torrent 的那幾秒裡，Route 設定頁上有人按了刪除。"""

            async def fetch(self, url: str) -> TorrentSource:
                async with sessions() as other:
                    await other.execute(delete(Route).where(Route.id == route.id))
                    await other.commit()
                return await super().fetch(url)

        factory.torrent_ = DeletingFetcher()

        with pytest.raises(JobRejectedError) as refusal:
            await add_download(
                session,
                factory,
                source=_source(),
                media_id=media.id,
                route_id=route.id,
                user_id=None,
            )

        assert refusal.value.reason == "route_missing"
        assert (await session.scalars(select(Job))).all() == []
        assert factory.qbittorrent_.added == []

    async def test_the_torrent_lands_in_the_routes_category_with_the_berth_tag(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """category 決定 save path（`autoTMM=true`），所以「送對 category」就是
        「存到 `<complete root>/<slug>`」（brief §4.1）。"""
        media, route, factory = await _ready(session, roots)

        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        added = factory.qbittorrent_.added
        assert [row.category for row in added] == ["berth-anime"]
        assert added[0].magnet == MAGNET
        assert await client_category(factory) == (
            "berth-anime",
            f"{roots['complete']}/anime".replace("\\", "/"),
        )

    async def test_the_category_is_created_if_it_is_missing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await _ready(session, roots)

        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        assert [row.name for row in factory.qbittorrent_.created_categories] == ["berth-anime"]

    async def test_an_existing_category_pointing_somewhere_else_stops_the_submission(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """autoTMM 開著時改 category 的 save path 會搬走整個分類的 torrent（brief §20.2）。
        Berth 不覆寫它，所以這一次送不出去——而理由要說得出那兩條路徑。"""
        await arrange(session, roots)
        media = await _media(session)
        route = await _route(session, roots)
        qbittorrent = applied_qbittorrent(
            roots, categories=(QbittorrentCategory(name="berth-anime", save_path="/mnt/old"),)
        )
        factory = factory_for(roots, qbittorrent=qbittorrent)

        outcome = await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        assert outcome.job.state is JobState.SUBMIT_FAILED
        assert "/mnt/old" in outcome.job.error
        assert qbittorrent.added == []

    async def test_two_events_record_the_two_transitions(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await _ready(session, roots)

        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        events = await read_job_events(session, MAGNET_HASH)
        assert [row.type for row in events] == [EventType.CREATED, EventType.SUBMITTED]
        assert events[0].payload["route"] == "anime"
        assert events[1].payload["category"] == "berth-anime"
        assert events[1].payload["save_path"].endswith("/anime")

    async def test_the_person_who_pressed_it_is_on_the_job_and_the_event(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await _ready(session, roots)
        skipper = await _skipper(session)

        outcome = await add_download(
            session,
            factory,
            source=_source(),
            media_id=media.id,
            route_id=route.id,
            user_id=skipper,
        )

        assert outcome.job.user_id == skipper
        events = await read_job_events(session, MAGNET_HASH)
        assert events[0].actor == str(skipper)


class TestDuplicateSubmission:
    async def test_the_same_hash_comes_back_as_the_existing_job(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await _ready(session, roots)
        first = await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        second = await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        assert second.created is False
        assert second.job.hash == first.job.hash
        assert len(factory.qbittorrent_.added) == 1

    async def test_a_hash_the_indexer_already_reported_skips_the_download_entirely(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """索引站報得出 hash 時第二次送單連 torrent 都不必去要——那是一次白花的請求，
        而 Prowlarr 的每一次代理下載都是它去連一次追蹤站。"""
        media, route, factory = await _ready(session, roots)
        source = _source(url="https://prowlarr.invalid/1/download?x=1", info_hash=DEFAULT_HASH)
        await add_download(
            session, factory, source=source, media_id=media.id, route_id=route.id, user_id=None
        )
        factory.torrent_.requested.clear()

        second = await add_download(
            session, factory, source=source, media_id=media.id, route_id=route.id, user_id=None
        )

        assert second.created is False
        assert factory.torrent_.requested == []

    async def test_only_two_events_after_two_submissions(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await _ready(session, roots)
        for _ in range(2):
            await add_download(
                session,
                factory,
                source=_source(),
                media_id=media.id,
                route_id=route.id,
                user_id=None,
            )

        assert len(await read_job_events(session, MAGNET_HASH)) == 2


class TestFolderNameFreeze:
    async def test_a_successful_submission_freezes_the_folder_name(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """送單成功那一刻它第一次真的通向磁碟，而且有人在場（票 04b）。"""
        media, route, factory = await _ready(session, roots)

        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        await session.refresh(media)
        assert media.folder_frozen is True
        assert media.folder_name == "SPY x FAMILY (2022)"

    async def test_a_failed_submission_does_not_freeze_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """磁碟上什麼都沒發生，所以那串字還沒有理由定下來。"""
        await arrange(session, roots)
        media = await _media(session)
        route = await _route(session, roots)
        factory = factory_for(
            roots, qbittorrent=applied_qbittorrent(roots, add_error=ServiceUnavailableError("down"))
        )

        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        await session.refresh(media)
        assert media.folder_frozen is False

    async def test_a_frozen_folder_name_is_not_refrozen_on_the_second_submission(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """第二次送單時 TMDB 可能已經改了標題，而磁碟上的資料夾還是第一次那一個。"""
        media, route, factory = await _ready(session, roots)
        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )
        media.folder_name = "SPY x FAMILY (2022)"
        await session.commit()

        await add_download(
            session,
            factory,
            source=_source(url=OTHER_MAGNET),
            media_id=media.id,
            route_id=route.id,
            user_id=None,
        )

        await session.refresh(media)
        assert media.folder_name == "SPY x FAMILY (2022)"

    async def test_the_route_becomes_the_media_default(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「上次用的」——下一次進詳情頁時下拉就停在這裡（plan §2.2）。"""
        media, route, factory = await _ready(session, roots)

        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        await session.refresh(media)
        assert media.default_route_id == route.id


class TestTracked:
    async def test_a_media_with_a_job_is_tracked(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await _ready(session, roots)
        assert await is_tracked(session, media.id) is False

        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        assert await is_tracked(session, media.id) is True


class TestRefusals:
    async def test_a_red_route_stops_the_submission_before_anything_happens(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """紅的 Route 送單一定失敗（brief §4.4），所以擋在最前面——建一個註定失敗的 Job
        只會在下載列表上多一列要人去清掉的垃圾。"""
        media, route, factory = await _ready(session, roots, health=HealthStatus.FAILED)

        with pytest.raises(JobRejectedError) as failure:
            await add_download(
                session,
                factory,
                source=_source(),
                media_id=media.id,
                route_id=route.id,
                user_id=None,
            )

        assert failure.value.reason == "route_unhealthy"
        assert factory.qbittorrent_.added == []
        assert factory.torrent_.requested == []
        assert await session.scalar(select(Job).limit(1)) is None

    async def test_an_unchecked_route_is_allowed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`unknown` 是「還沒檢查」，不是「壞了」（`HealthStatus` 的三個值）。
        健康迴圈五分鐘才跑一輪，拿它擋人等於精靈剛跑完的五分鐘內誰都送不了單。"""
        media, route, factory = await _ready(session, roots, health=HealthStatus.UNKNOWN)

        outcome = await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        assert outcome.job.state is JobState.SUBMITTED

    async def test_a_route_that_cannot_hold_this_kind_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """劇集進不了 movies 媒體庫（`domain.collection_type_for`）。"""
        media, route, factory = await _ready(
            session, roots, collection_type=CollectionType.MOVIES, slug="movies"
        )

        with pytest.raises(JobRejectedError) as failure:
            await add_download(
                session,
                factory,
                source=_source(),
                media_id=media.id,
                route_id=route.id,
                user_id=None,
            )

        assert failure.value.reason == "route_kind_mismatch"

    async def test_a_disabled_route_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await _ready(session, roots)
        route.enabled = False
        await session.commit()

        with pytest.raises(JobRejectedError) as failure:
            await add_download(
                session,
                factory,
                source=_source(),
                media_id=media.id,
                route_id=route.id,
                user_id=None,
            )

        assert failure.value.reason == "route_disabled"

    async def test_an_unknown_route_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, _, factory = await _ready(session, roots)

        with pytest.raises(JobRejectedError) as failure:
            await add_download(
                session, factory, source=_source(), media_id=media.id, route_id=999, user_id=None
            )

        assert failure.value.reason == "route_missing"

    async def test_an_unknown_media_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await _ready(session, roots)

        with pytest.raises(JobRejectedError) as failure:
            await add_download(
                session,
                factory,
                source=_source(),
                media_id="tv:999999",
                route_id=route.id,
                user_id=None,
            )

        assert failure.value.reason == "media_missing"

    async def test_an_indexer_that_cannot_give_the_torrent_creates_no_job(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """還不知道是哪一個 torrent 就沒有 Job——`jobs.hash` 是主鍵，而 Job 記的正是
        「一個 torrent 的生命週期」（`CONTEXT.md`）。"""
        await arrange(session, roots)
        media = await _media(session)
        route = await _route(session, roots)
        factory = factory_for(roots)
        factory.torrent_.error = NotATorrentError("indexer.invalid: 200 text/html")

        with pytest.raises(JobRejectedError) as failure:
            await add_download(
                session,
                factory,
                source=_source(url="https://indexer.invalid/1"),
                media_id=media.id,
                route_id=route.id,
                user_id=None,
            )

        assert failure.value.reason == "source_unavailable"
        assert "text/html" in failure.value.detail
        assert await session.scalar(select(Job).limit(1)) is None


class TestSubmitFailed:
    @pytest.mark.parametrize(
        ("error", "fragment"),
        [
            pytest.param(
                ServiceUnavailableError("connection refused"), "refused", id="unreachable"
            ),
            pytest.param(AuthFailedError("torrents/add: 403"), "403", id="rejected"),
        ],
    )
    async def test_qbittorrent_saying_no_lands_in_submit_failed_with_the_reason(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        error: Exception,
        fragment: str,
    ) -> None:
        await arrange(session, roots)
        media = await _media(session)
        route = await _route(session, roots)
        factory = factory_for(roots, qbittorrent=applied_qbittorrent(roots, add_error=error))

        outcome = await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        assert outcome.job.state is JobState.SUBMIT_FAILED
        assert fragment in outcome.job.error
        events = await read_job_events(session, MAGNET_HASH)
        assert [row.type for row in events] == [EventType.CREATED, EventType.SUBMIT_FAILED]

    async def test_retrying_goes_back_through_requested_and_succeeds(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)
        media = await _media(session)
        route = await _route(session, roots)
        qbittorrent = applied_qbittorrent(roots, add_error=ServiceUnavailableError("down"))
        factory = factory_for(roots, qbittorrent=qbittorrent)
        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        qbittorrent.add_error = None  # 服務回來了
        job = await retry_job(session, factory, MAGNET_HASH)

        assert job.state is JobState.SUBMITTED
        assert job.error == ""
        types = [row.type for row in await read_job_events(session, MAGNET_HASH)]
        assert types == [
            EventType.CREATED,
            EventType.SUBMIT_FAILED,
            EventType.RETRIED,
            EventType.SUBMITTED,
        ]

    async def test_retrying_uses_the_stored_download_link(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """畫面上那一輪搜尋早就不在了，而 Prowlarr 的代理連結每次搜尋都不一樣
        （brief §20.7）——重新搜一次不會給出同一條。"""
        await arrange(session, roots)
        media = await _media(session)
        route = await _route(session, roots)
        url = "https://prowlarr.invalid/1/download?link=abc"
        fetcher = FakeTorrentFetcher(
            sources={url: TorrentSource(info_hash=DEFAULT_HASH, content=b"d4:infodee")}
        )
        factory = factory_for(
            roots, qbittorrent=applied_qbittorrent(roots, add_error=ServiceUnavailableError("down"))
        )
        factory.torrent_ = fetcher
        await add_download(
            session,
            factory,
            source=_source(url=url),
            media_id=media.id,
            route_id=route.id,
            user_id=None,
        )
        factory.qbittorrent_ = applied_qbittorrent(roots)
        fetcher.requested.clear()

        await retry_job(session, factory, DEFAULT_HASH)

        assert fetcher.requested == [url]
        assert factory.qbittorrent_.added[0].content == b"d4:infodee"

    async def test_a_route_that_went_disabled_cannot_be_retried_into(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """**重試與第一次送單走同一組前提**。只檢查健康的話，一條停用的 Route 上
        「第一次送不出去、重試卻送得出去」——同一個決定兩種答案。"""
        await arrange(session, roots)
        media = await _media(session)
        route = await _route(session, roots)
        factory = factory_for(
            roots, qbittorrent=applied_qbittorrent(roots, add_error=ServiceUnavailableError("down"))
        )
        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )
        route.enabled = False
        await session.commit()

        with pytest.raises(JobRejectedError) as failure:
            await retry_job(session, factory, MAGNET_HASH)

        assert failure.value.reason == "route_disabled"

    async def test_a_route_that_went_red_cannot_be_retried_into(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)
        media = await _media(session)
        route = await _route(session, roots)
        factory = factory_for(
            roots, qbittorrent=applied_qbittorrent(roots, add_error=ServiceUnavailableError("down"))
        )
        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )
        route.health_status = HealthStatus.FAILED
        await session.commit()

        with pytest.raises(JobRejectedError) as failure:
            await retry_job(session, factory, MAGNET_HASH)

        assert failure.value.reason == "route_unhealthy"

    async def test_a_job_that_is_not_failed_cannot_be_retried(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """重試是 `submit_failed` → `requested` 的那一條轉換（plan §3.1），不是一顆
        「再送一次」的按鈕——已經在下載的 torrent 再送一次只會多一次無謂的請求。"""
        media, route, factory = await _ready(session, roots)
        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        with pytest.raises(JobRejectedError) as failure:
            await retry_job(session, factory, MAGNET_HASH)

        assert failure.value.reason == "not_retryable"


#: 比任何一台機器的磁碟都大的門檻（GB）。量出來的一定低於它，所以這一個數字就是「磁碟不夠」。
HUGE = 10**9


async def _threshold(session: AsyncSession, gigabytes: int) -> None:
    await write_settings(session, DiskSettings(min_free_gb=gigabytes))
    await session.commit()


class TestTheDiskGate:
    """送單前看磁碟門檻（M3 票 04）。RSS 送單沒有人按確認，所以原本只開一件 `low_disk_space`
    Issue 的那個門檻改成擋送單；手動與 RSS 走同一支 `add_download`，所以是同一個判斷。"""

    async def test_below_the_threshold_nothing_is_fetched_created_or_sent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await _ready(session, roots)
        await _threshold(session, HUGE)

        with pytest.raises(JobRejectedError) as failure:
            await add_download(
                session,
                factory,
                source=_source(),
                media_id=media.id,
                route_id=route.id,
                user_id=None,
            )

        assert failure.value.reason == "low_disk_space"
        assert str(roots["incomplete"]) in failure.value.detail
        assert factory.torrent_.requested == []
        assert factory.qbittorrent_.added == []
        assert await session.scalar(select(Job)) is None

    async def test_a_threshold_of_zero_does_not_measure(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`0` 是不量（`DiskSettings`）：量這一步自己爆掉也不影響送單。"""
        media, route, factory = await _ready(session, roots)
        await _threshold(session, 0)

        def unmeasurable(path: Path) -> int:
            raise AssertionError(f"measured {path} with the gate off")

        monkeypatch.setattr(fs, "free_space", unmeasurable)

        outcome = await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        assert outcome.job.state is JobState.SUBMITTED

    async def test_an_incomplete_root_it_cannot_see_does_not_block(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """看不到不是「空間不夠」：那是 `download_path` 纜繩要報的事，擋下來只會讓每一次送單
        都說錯理由。"""
        media, route, factory = await _ready(session, roots)
        paths = await read_settings(session, PathSettings)
        paths.incomplete_root = str(roots["incomplete"] / "not-mounted")
        await write_settings(session, paths)
        await _threshold(session, HUGE)

        outcome = await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        assert outcome.job.state is JobState.SUBMITTED

    async def test_a_retry_is_held_to_the_same_threshold(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """重試與第一次送單同一組前提：否則「第一次送不出去、重試卻送得出去」。"""
        await arrange(session, roots)
        media = await _media(session)
        route = await _route(session, roots)
        qbittorrent = applied_qbittorrent(roots, add_error=ServiceUnavailableError("down"))
        factory = factory_for(roots, qbittorrent=qbittorrent)
        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )
        qbittorrent.add_error = None
        await _threshold(session, HUGE)

        with pytest.raises(JobRejectedError) as failure:
            await retry_job(session, factory, MAGNET_HASH)

        assert failure.value.reason == "low_disk_space"
        job = await read_job(session, MAGNET_HASH)
        assert job is not None
        assert job.state is JobState.SUBMIT_FAILED


class TestARemovedHash:
    """刪除過、沒清紀錄的 Job 不能再下載同一個 hash（M3 票 04、plan §3.3）。

    「同 hash 回傳既有 Job」對一筆 `removed` 的來說是錯的答案：送單的人以為成功了，而 RSS 下一輪
    看到同一筆會再送一次、再拿回同一列。那一筆紀錄還在就是還沒決定要不要再下載——拒絕並說出理由。
    """

    async def _removed(self, session: AsyncSession, roots: dict[str, Path]) -> FakeClientFactory:
        media, route, factory = await _ready(session, roots)
        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )
        job = await session.get(Job, MAGNET_HASH)
        assert job is not None
        job.state = JobState.REMOVED
        await session.commit()
        factory.qbittorrent_.added.clear()
        return factory

    async def test_the_same_hash_is_refused_with_the_job_it_belongs_to(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await self._removed(session, roots)

        with pytest.raises(JobRejectedError) as failure:
            await add_download(
                session,
                factory,
                source=_source(),
                media_id="tv:120089",
                route_id=await _route_id(session),
                user_id=None,
            )

        assert failure.value.reason == "job_removed"
        assert failure.value.detail == MAGNET_HASH
        assert factory.qbittorrent_.added == []
        job = await read_job(session, MAGNET_HASH)
        assert job is not None
        assert job.state is JobState.REMOVED

    async def test_a_hash_the_indexer_reported_is_refused_before_anything_is_fetched(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await self._removed(session, roots)
        factory.torrent_.requested.clear()

        with pytest.raises(JobRejectedError) as failure:
            await add_download(
                session,
                factory,
                source=_source(info_hash=MAGNET_HASH),
                media_id="tv:120089",
                route_id=await _route_id(session),
                user_id=None,
            )

        assert failure.value.reason == "job_removed"
        assert factory.torrent_.requested == []

    async def test_once_the_record_is_purged_it_downloads_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """清掉紀錄就是決定了：那時候同一個 hash 是一筆新的下載。"""
        factory = await self._removed(session, roots)
        await session.execute(delete(Event))
        await session.execute(delete(Job))
        await session.commit()

        outcome = await add_download(
            session,
            factory,
            source=_source(),
            media_id="tv:120089",
            route_id=await _route_id(session),
            user_id=None,
        )

        assert outcome.created is True
        assert outcome.job.state is JobState.SUBMITTED


async def _route_id(session: AsyncSession) -> int:
    route = await session.scalar(select(Route))
    assert route is not None
    return route.id


class TestTheJobSurvivesTheSubmission:
    async def test_the_job_row_exists_before_qbittorrent_is_asked(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """**打 qBittorrent 之前那一列就要在資料庫裡**（與精靈每一步「做之前先寫」同理）。

        在那之後任何一個沒接住的例外都會 rollback，而 torrent 可能已經進了下載器——
        那就成了一個沒有 Job 的孤兒（plan §3.2 的 `unknown_torrent`）。這裡讓
        `torrents/add` 丟一個**不是** `ServiceError` 的例外，也就是服務層沒有接住的那一種。
        """
        await arrange(session, roots)
        media = await _media(session)
        route = await _route(session, roots)
        factory = factory_for(
            roots, qbittorrent=applied_qbittorrent(roots, add_error=RuntimeError("the loop died"))
        )

        with pytest.raises(RuntimeError):
            await add_download(
                session,
                factory,
                source=_source(),
                media_id=media.id,
                route_id=route.id,
                user_id=None,
            )

        await session.rollback()
        job = await session.get(Job, MAGNET_HASH)
        assert job is not None
        assert job.state is JobState.REQUESTED

    async def test_the_frozen_name_is_the_one_the_user_confirmed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """**送單不刷新快照**（plan §8.3 的六小時規則留給票 11 的 planning）。

        凍下去的必須就是使用者剛剛在確認畫面上看到的那一串字（brief §4.5、PRODUCT 原則 2）——
        刷新會在他按下去與那串字落地之間把它換掉。這裡的斷言是：整次送單一個 TMDB 請求都沒發。
        """
        media, route, factory = await _ready(session, roots)
        before = media.folder_name

        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        assert factory.tmdb_.requests == []
        await session.refresh(media)
        assert media.folder_name == before


class TestReading:
    async def test_the_list_is_newest_first_and_carries_the_route_and_media(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await _ready(session, roots)
        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )
        await add_download(
            session,
            factory,
            source=JobSource(url=OTHER_MAGNET, title="A second release"),
            media_id=media.id,
            route_id=route.id,
            user_id=None,
        )
        first = await session.get(Job, MAGNET_HASH)
        assert first is not None
        first.added_at = datetime(2026, 1, 1, tzinfo=UTC)
        await session.commit()

        rows = await list_jobs(session)

        assert [row.name for row in rows] == ["A second release", RELEASE]
        assert rows[0].route_name == "Anime"
        # 這一列的 Media 從沒抓過快照：`zh-Hant` 那一格落回英文標題，不是空的。
        assert (rows[0].media_title, rows[0].media_title_en) == ("SPY x FAMILY", "SPY x FAMILY")

    async def test_the_media_title_comes_in_both_languages(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """下載列的作品名跟著 UI 語言走（brief §7.5），所以兩輪都送，畫面挑一個。"""
        media, route, factory = await _ready(session, roots)
        media.tmdb_snapshot_json = (
            media.snapshot()
            .model_copy(update={"title": "SPY×FAMILY 間諜家家酒"})
            .model_dump(mode="json")
        )
        await session.commit()
        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        (row,) = await list_jobs(session)

        assert (row.media_title, row.media_title_en) == ("SPY×FAMILY 間諜家家酒", "SPY x FAMILY")

    async def test_the_query_count_does_not_grow_with_the_list(
        self, session: AsyncSession, engine: AsyncEngine, roots: dict[str, Path]
    ) -> None:
        """一筆與十筆問一樣多次（票 01）。

        逐列問的話一百筆下載就是四百次往返，而這一支是下載列每次重新整理都走的那一支。
        用查詢次數而不是計時：時間在 CI 上量不準，而這裡要釘住的本來就是次數。
        """
        media, route, _ = await _ready(session, roots)
        user = User(jellyfin_user_id="jf-1", name="skipper", role=Role.ADMIN)
        session.add(user)
        await session.commit()
        await _plan_backed_jobs(session, media, route, user, count=1)

        with counting(engine) as one:
            assert len(await list_jobs(session)) == 1

        await _plan_backed_jobs(session, media, route, user, count=9, start=1)

        with counting(engine) as ten:
            assert len(await list_jobs(session)) == 10

        assert len(ten) == len(one)

    async def test_one_job_reads_back_by_hash(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await _ready(session, roots)
        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        assert (await read_job(session, MAGNET_HASH)) is not None
        assert (await read_job(session, "0" * 40)) is None


class TestJobLogging:
    async def test_every_line_written_while_submitting_carries_the_job_id(
        self, session: AsyncSession, roots: dict[str, Path], caplog: pytest.LogCaptureFixture
    ) -> None:
        """plan T1.9：「Job 的每一行 log 都查得到 job id」。

        斷言的是**每一行**而不是「有一行」：id 由上下文帶著（`berth.logs`），所以只要有
        一行漏掉，就表示那一段程式碼跑在上下文之外——而那正是出事時會缺的那一段。
        """
        media, route, factory = await _ready(session, roots)
        # 正式路徑的每一筆 record 在**建立時**就被蓋上 job id（`berth.logs` 的 record
        # factory）。`caplog` 是之後才格式化的，所以測試要走同一條安裝路徑才問得到它。
        configure_logging()

        with caplog.at_level(logging.INFO, logger="berth"):
            await add_download(
                session,
                factory,
                source=_source(),
                media_id=media.id,
                route_id=route.id,
                user_id=None,
            )

        lines = [json.loads(json_line(record)) for record in caplog.records]
        assert lines, "送單至少要留下一行 log"
        assert {line.get(JOB_FIELD) for line in lines} == {MAGNET_HASH}


async def _skipper(session: AsyncSession) -> int:
    """一個登入過的人。`users` 的列來自 Jellyfin 登入，精靈的第 1 步不建它。"""
    user = User(jellyfin_user_id="jf-1", name="skipper", role=Role.ADMIN)
    session.add(user)
    await session.commit()
    return user.id


async def client_category(factory: FakeClientFactory) -> tuple[str, str]:
    rows = await factory.qbittorrent_.categories()
    return (rows[0].name, rows[0].save_path.replace("\\", "/"))
