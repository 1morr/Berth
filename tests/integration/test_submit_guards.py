"""大批送單的兩道防護（M4 票 03，plan §3.1、§3.2）。

補舊集一次送一百多個是 brief §15 的決定，不改；這裡驗的是那一百多個少的兩道防護：

1. **磁碟門檻算在途量**：比的是「剩餘空間 − 在途 Job 還沒下完的量」。2026-09-26 試跑一次送 144 個，
   每一個送單當下都過門檻，磁碟要到下載途中才滿。
2. **暫時失敗的送單有限重試**：qBittorrent 逾時、停機時那一批落在 `submit_failed`，由 poller 在
   問得到 qBittorrent 的那幾輪自動重送，退避、有上限；再問也一樣的（404、明確拒絕）照舊等人。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters import fs
from berth.adapters.http import ProtocolMismatchError, ServiceUnavailableError
from berth.db import create_session_factory
from berth.domain import EventType, FeedItemStatus, JobState, JobTrigger
from berth.models import DiskSettings, Job, Media, Route
from berth.pipeline.downloads import QbitPoller
from berth.services.events import EventHub
from berth.services.hints import JobHints
from berth.services.jobs import (
    SUBMIT_RETRIES,
    JobRejectedError,
    JobSource,
    add_download,
    read_job_events,
    retry_due,
    retry_job,
)
from berth.services.rss import add_feed, bind_series, list_items, poll_feed
from berth.services.settings import write_settings
from berth.services.setup import complete_setup
from tests.integration.arrange import applied_qbittorrent, factory_for
from tests.integration.factories import FakeClientFactory
from tests.integration.test_jobs import MAGNET, MAGNET_HASH, OTHER_HASH, OTHER_MAGNET, _ready
from tests.integration.test_rss import FEED_URL, KIMI, KIMI_KEY, harbour, series_by_key

pytestmark = pytest.mark.asyncio

GIB = 1024**3
#: 一集的大小。門檻 1 GiB，門檻只扣在途量，所以「夠一個、不夠兩個」是剩 1 GiB + 半集：第一個送單時
#: 沒有在途、過得去；第二個送單時第一個那一整集還沒下，扣掉就低於門檻。
EPISODE = 2 * GIB

TIMEOUT = ServiceUnavailableError("GET /api/v2/torrents/categories: ReadTimeout")


def _source(url: str = MAGNET, *, size: int = EPISODE) -> JobSource:
    return JobSource(url=url, title=f"release {url[-6:]}", size=size)


def _free(monkeypatch: pytest.MonkeyPatch, gigabytes: float) -> None:
    free = int(gigabytes * GIB)
    monkeypatch.setattr(fs, "free_space", lambda _path: free)


async def _threshold(session: AsyncSession, gigabytes: int = 1) -> None:
    await write_settings(session, DiskSettings(min_free_gb=gigabytes))
    await session.commit()


class TestInFlightCountsAgainstTheDisk:
    async def test_room_for_one_but_not_two_stops_the_second(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        media, route, factory = await _ready(session, roots)
        await _threshold(session)
        _free(monkeypatch, 1 + 0.5 * EPISODE / GIB)

        first = await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )
        with pytest.raises(JobRejectedError) as refusal:
            await add_download(
                session,
                factory,
                source=_source(OTHER_MAGNET),
                media_id=media.id,
                route_id=route.id,
                user_id=None,
            )

        assert first.job.state is JobState.SUBMITTED
        assert refusal.value.reason == "low_disk_space"
        # 訊息說得出在途多少：剩的看起來夠，是在途那一筆把它吃掉了。
        assert "2.0 GiB still to download for 1 job" in refusal.value.detail
        assert len(factory.qbittorrent_.added) == 1

    async def test_room_for_two_lets_the_second_through(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        media, route, factory = await _ready(session, roots)
        await _threshold(session)
        _free(monkeypatch, 1 + 1.5 * EPISODE / GIB)

        for url in (MAGNET, OTHER_MAGNET):
            outcome = await add_download(
                session,
                factory,
                source=_source(url),
                media_id=media.id,
                route_id=route.id,
                user_id=None,
            )
            assert outcome.job.state is JobState.SUBMITTED

    async def test_what_is_already_downloaded_no_longer_counts(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """qBittorrent 報得出大小之後用它：`total_size × (1 − progress)`。"""
        media, route, factory = await _ready(session, roots)
        await _threshold(session)
        _free(monkeypatch, 1 + 0.5 * EPISODE / GIB)
        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )
        job = await session.get(Job, MAGNET_HASH)
        assert job is not None
        job.state, job.total_size, job.progress = JobState.DOWNLOADING, 4 * GIB, 0.9
        await session.commit()

        second = await add_download(
            session,
            factory,
            source=_source(OTHER_MAGNET),
            media_id=media.id,
            route_id=route.id,
            user_id=None,
        )

        assert second.job.state is JobState.SUBMITTED

    async def test_a_job_of_unknown_size_is_not_counted_and_says_so(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        media, route, factory = await _ready(session, roots)
        await _threshold(session)
        _free(monkeypatch, 1 + 0.5 * EPISODE / GIB)
        await add_download(
            session,
            factory,
            source=_source(size=0),
            media_id=media.id,
            route_id=route.id,
            user_id=None,
        )

        with caplog.at_level(logging.INFO, logger="berth.services.jobs"):
            second = await add_download(
                session,
                factory,
                source=_source(OTHER_MAGNET),
                media_id=media.id,
                route_id=route.id,
                user_id=None,
            )

        assert second.job.state is JobState.SUBMITTED
        assert any("size unknown" in record.getMessage() for record in caplog.records)

    async def test_the_size_known_at_submission_is_on_the_job_until_qbittorrent_reports(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await _ready(session, roots)

        outcome = await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )

        assert outcome.job.total_size == EPISODE


async def _failed_once(
    session: AsyncSession, roots: dict[str, Path], error: Exception
) -> FakeClientFactory:
    """送一次、qBittorrent 以 `error` 回絕，那一筆落在 `submit_failed`。"""
    media, route, _ = await _ready(session, roots)
    factory = factory_for(roots, qbittorrent=applied_qbittorrent(roots, error=error))
    outcome = await add_download(
        session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
    )
    assert outcome.job.state is JobState.SUBMIT_FAILED
    return factory


async def _media_and_route(session: AsyncSession) -> tuple[Media, Route]:
    media = await session.scalar(select(Media))
    route = await session.scalar(select(Route))
    assert media is not None and route is not None
    return media, route


def _later(delay: timedelta) -> datetime:
    """失敗那一刻（牆上時鐘）之後再過 `delay` 多一點。"""
    return datetime.now(UTC) + delay + timedelta(seconds=5)


async def _state(session: AsyncSession) -> JobState:
    job = await session.get(Job, MAGNET_HASH, populate_existing=True)
    assert job is not None
    return job.state


class TestTransientFailuresAreRetried:
    async def test_a_timeout_is_sent_again_once_its_backoff_is_up(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await _failed_once(session, roots, TIMEOUT)
        factory.qbittorrent_.error = None

        early = await retry_due(session, factory, now=datetime.now(UTC))
        late = await retry_due(session, factory, now=_later(SUBMIT_RETRIES[0]))

        assert (early, late) == (0, 1)
        assert await _state(session) is JobState.SUBMITTED
        events = await read_job_events(session, MAGNET_HASH)
        assert [row.type for row in events] == [
            EventType.CREATED,
            EventType.SUBMIT_FAILED,
            EventType.RETRIED,
            EventType.SUBMITTED,
        ]
        assert events[1].payload["attempt"] == 1
        assert events[1].payload["retry_at"]
        assert events[2].actor == "system"

    async def test_it_stops_after_the_last_attempt_and_waits_for_a_person(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await _failed_once(session, roots, TIMEOUT)
        moment = datetime.now(UTC)

        for delay in SUBMIT_RETRIES:
            moment += delay + timedelta(seconds=5)
            assert await retry_due(session, factory, now=moment) == 1
        assert await retry_due(session, factory, now=moment + timedelta(days=30)) == 0

        assert await _state(session) is JobState.SUBMIT_FAILED
        failures = [
            row.payload
            for row in await read_job_events(session, MAGNET_HASH)
            if row.type == EventType.SUBMIT_FAILED
        ]
        # 逐次記：第一次加上每一次重送各一筆，最後一筆說不再自動重送。
        assert [row["attempt"] for row in failures] == list(range(1, len(SUBMIT_RETRIES) + 2))
        assert failures[-1]["retry_at"] is None

    async def test_each_failure_waits_its_own_step_of_the_backoff(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """第 n 次失敗之後等 `SUBMIT_RETRIES[n-1]`，由失敗那一刻起算。"""
        factory = await _failed_once(session, roots, TIMEOUT)
        moment = datetime.now(UTC)
        for delay in SUBMIT_RETRIES:
            moment += delay + timedelta(seconds=5)
            await retry_due(session, factory, now=moment)

        failures = [
            row
            for row in await read_job_events(session, MAGNET_HASH)
            if row.type == EventType.SUBMIT_FAILED
        ]
        waits = [
            datetime.fromisoformat(row.payload["retry_at"]) - row.created_at
            for row in failures[:-1]
        ]
        assert [round(wait.total_seconds()) for wait in waits] == [
            round(delay.total_seconds()) for delay in SUBMIT_RETRIES
        ]

    async def test_a_round_stops_at_the_first_resend_that_fails_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """qBittorrent 答得了 `sync` 卻還是逾時（大批送單時忙不過來）：一輪只花一筆的次數，其餘的
        留到下一輪，不讓一整批在同一刻各燒掉一次。"""
        factory = await _failed_once(session, roots, TIMEOUT)
        media, route = await _media_and_route(session)
        await add_download(
            session,
            factory,
            source=_source(OTHER_MAGNET),
            media_id=media.id,
            route_id=route.id,
            user_id=None,
        )

        assert await retry_due(session, factory, now=_later(SUBMIT_RETRIES[0])) == 1

        attempts = {
            job_hash: [
                row.payload["attempt"]
                for row in await read_job_events(session, job_hash)
                if row.type == EventType.SUBMIT_FAILED
            ]
            for job_hash in (MAGNET_HASH, OTHER_HASH)
        }
        assert attempts == {MAGNET_HASH: [1, 2], OTHER_HASH: [1]}

    async def test_a_person_pressing_retry_starts_the_count_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await _failed_once(session, roots, TIMEOUT)

        await retry_job(session, factory, MAGNET_HASH)

        failures = [
            row.payload
            for row in await read_job_events(session, MAGNET_HASH)
            if row.type == EventType.SUBMIT_FAILED
        ]
        assert [row["attempt"] for row in failures] == [1, 1]

    async def test_an_explicit_refusal_is_not_retried(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await _failed_once(
            session, roots, ProtocolMismatchError("POST /api/v2/torrents/add: 415")
        )
        factory.qbittorrent_.error = None

        assert await retry_due(session, factory, now=_later(timedelta(days=1))) == 0
        assert await _state(session) is JobState.SUBMIT_FAILED
        (failure,) = [
            row.payload
            for row in await read_job_events(session, MAGNET_HASH)
            if row.type == EventType.SUBMIT_FAILED
        ]
        assert "attempt" not in failure

    async def test_a_torrent_site_that_is_down_is_tried_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """重送時 `.torrent` 那一站 5xx 也是暫時的：排下一次，不停下來等人。"""
        factory = await _failed_once(session, roots, TIMEOUT)
        factory.qbittorrent_.error = None
        factory.torrent_.error = ServiceUnavailableError("GET https://mikanani.me/x.torrent: 502")

        assert await retry_due(session, factory, now=_later(SUBMIT_RETRIES[0])) == 1

        last = [
            row.payload
            for row in await read_job_events(session, MAGNET_HASH)
            if row.type == EventType.SUBMIT_FAILED
        ][-1]
        assert "502" in last["error"]
        assert last["attempt"] == 2
        assert last["retry_at"]

    async def test_a_torrent_that_is_gone_stops_the_retries(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """重送要重抓 `.torrent`；那一條連結 404 了就是再問也一樣，停下來等人。"""
        factory = await _failed_once(session, roots, TIMEOUT)
        factory.qbittorrent_.error = None
        factory.torrent_.error = ProtocolMismatchError("GET https://mikanani.me/x.torrent: 404")

        assert await retry_due(session, factory, now=_later(SUBMIT_RETRIES[0])) == 1
        assert await retry_due(session, factory, now=_later(timedelta(days=1))) == 0

        assert await _state(session) is JobState.SUBMIT_FAILED
        last = [
            row.payload
            for row in await read_job_events(session, MAGNET_HASH)
            if row.type == EventType.SUBMIT_FAILED
        ][-1]
        assert "404" in last["error"]
        assert "attempt" not in last

    async def test_a_disk_below_the_threshold_holds_the_retry_without_spending_it(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        factory = await _failed_once(session, roots, TIMEOUT)
        factory.qbittorrent_.error = None
        await _threshold(session)
        _free(monkeypatch, 0.5)

        assert await retry_due(session, factory, now=_later(SUBMIT_RETRIES[0])) == 0
        assert await _state(session) is JobState.SUBMIT_FAILED

        _free(monkeypatch, 100)
        assert await retry_due(session, factory, now=_later(SUBMIT_RETRIES[0])) == 1
        assert await _state(session) is JobState.SUBMITTED


class TestAnOutageOfQbittorrent:
    async def test_the_rss_batch_sent_while_it_was_down_goes_through_when_it_is_back(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """停機期間 RSS 送出的那一批落在 `submit_failed`；停機時 poller 問不到 qBittorrent，不花
        重送的次數；服務回來的那一輪一起接上，不需要人按。"""
        media, route, factory = await harbour(session, roots)
        await complete_setup(session)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        now = datetime.now(UTC)
        await poll_feed(session, factory, feed.id, now=now)
        down = ServiceUnavailableError("POST /api/v2/auth/login: connection refused")
        factory.qbittorrent_.error = down
        factory.qbittorrent_.add_error = down
        factory.qbittorrent_.sync_error = down

        series = await series_by_key(session, KIMI_KEY)
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )
        jobs = list(await session.scalars(select(Job)))
        assert {(job.trigger, job.state) for job in jobs} == {
            (JobTrigger.RSS, JobState.SUBMIT_FAILED)
        }

        clock = _Clock(now)
        loop = QbitPoller(
            create_session_factory(engine), factory, EventHub(), JobHints(), now=clock
        )
        # 停了一整天：poller 每一輪都問不到，重送一次都沒花。
        for hours in range(1, 25):
            clock.at = now + timedelta(hours=hours)
            await loop.tick()
        factory.qbittorrent_.error = None
        factory.qbittorrent_.add_error = None
        factory.qbittorrent_.sync_error = None
        clock.at = now + timedelta(hours=25)
        await loop.tick()

        jobs = list(await session.scalars(select(Job).execution_options(populate_existing=True)))
        assert {job.hash for job in jobs} == {item.info_hash for item in KIMI}
        assert {job.state for job in jobs} == {JobState.SUBMITTED}
        assert len(factory.qbittorrent_.added) == len(KIMI)
        items = [row for row in await list_items(session) if row.series_id == series.id]
        assert {row.status for row in items} == {FeedItemStatus.DOWNLOADED}


class _Clock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def __call__(self) -> datetime:
        return self.at
