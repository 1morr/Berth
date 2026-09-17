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
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.http import AuthFailedError, ServiceUnavailableError
from berth.adapters.qbittorrent import QbittorrentCategory
from berth.adapters.torrent import NotATorrentError, TorrentSource
from berth.adapters.torrent_fake import DEFAULT_HASH, FakeTorrentFetcher
from berth.db import create_session_factory
from berth.domain import (
    CollectionType,
    EventType,
    HealthStatus,
    JobState,
    JobTrigger,
    MediaKind,
    Role,
)
from berth.logs import JOB_FIELD, configure_logging, json_line
from berth.models import Job, Media, Route, User
from berth.services.jobs import (
    JobRejectedError,
    JobSource,
    add_download,
    list_jobs,
    read_job,
    read_job_events,
    retry_job,
)
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
        assert rows[0].media_title == "SPY x FAMILY"

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
