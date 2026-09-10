"""`qbit_poller` 的狀態機（plan §3.1、§3.2、brief §5.1、票 10）。

送單之後就沒有人在按按鈕了：這一整份測的是「qBittorrent 這樣說的時候，Berth 該把那一列
搬到哪一站」。所以每一條的形狀都一樣——擺一個客戶端狀態，跑一輪，看狀態、事件與那幾欄
實測值。

替身回的是 `TorrentStatus`（協定翻譯的結果），**不是**錄下來的 JSON：`sync/maindata` 的
增量合併與欄位讀法由契約測試對兩個版本的錄製回應驗（`test_adapter_contracts.py`），
這裡驗的是它之後的那一段判斷。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.http import AuthFailedError
from berth.adapters.qbittorrent import BERTH_TAG, IpBannedError, TorrentFile, TorrentStatus
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.db import create_session_factory
from berth.domain import (
    CollectionType,
    HealthStatus,
    IssueType,
    JobState,
    JobTrigger,
    MediaKind,
    Profile,
)
from berth.models import Event, Job, JobFile, Media, PollerSettings, QbittorrentSettings, Route
from berth.services.downloads import (
    ACTIVE_INTERVAL,
    IDLE_INTERVAL,
    STALL_AFTER,
    Downloader,
    next_interval,
    poll_downloads,
    record_poll_failure,
)
from berth.services.events import EventHub, JobSignal
from berth.services.hints import JobHints
from berth.services.jobs import held_locks, job_lock, transition
from berth.services.settings import read_settings, write_settings
from tests.integration.arrange import arrange, factory_for

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
HASH = "4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b"
RELEASE = "[ANi] SPY×FAMILY - 13 [1080P][WEB-DL][AAC AVC][CHT]"
CATEGORY = "berth-anime"
SAVE_PATH = "/data/torrent/complete/anime"

#: 真實發佈的樣子：`torrents/files[].name` 含 torrent 自己的根目錄那一層（brief §20.7）。
FILES = (
    TorrentFile(index=0, name=f"{RELEASE}/E13.mkv", size=1_400_000_000, priority=1, progress=0.0),
    TorrentFile(index=1, name=f"{RELEASE}/E13.cht.ass", size=41_000, priority=1, progress=0.0),
)


def status(
    *,
    state: str = "downloading",
    progress: float = 0.0,
    completion_on: int = 0,
    last_activity: int = 0,
    category: str = CATEGORY,
    tags: tuple[str, ...] = (BERTH_TAG,),
    info_hash: str = HASH,
    save_path: str = SAVE_PATH,
    total_size: int = 1_400_041_000,
) -> TorrentStatus:
    return TorrentStatus(
        hash=info_hash,
        name=RELEASE,
        state=state,
        category=category,
        tags=tags,
        progress=progress,
        completion_on=completion_on,
        last_activity=last_activity or int(NOW.timestamp()),
        added_on=int(NOW.timestamp()),
        save_path=save_path,
        content_path=f"{save_path}/{RELEASE}",
        total_size=total_size,
    )


async def setup_job(
    session: AsyncSession,
    roots: dict[str, Path],
    *,
    state: JobState = JobState.SUBMITTED,
    job_hash: str = HASH,
) -> Job:
    await arrange(session, roots)
    session.add(
        Media(
            id="tv:120089",
            tmdb_id=120089,
            kind=MediaKind.TV,
            title_en="SPY x FAMILY",
            title_original="SPY×FAMILY",
            year=2022,
            folder_name="SPY x FAMILY (2022)",
        )
    )
    route = Route(
        slug="anime",
        name="Anime",
        jellyfin_library_id="item-2",
        jellyfin_library_name="Anime",
        collection_type=CollectionType.TVSHOWS,
        target_path=str(roots["library"] / "anime"),
        category=CATEGORY,
        profile=Profile.ANIME,
        health_status=HealthStatus.OK,
    )
    session.add(route)
    await session.commit()
    job = Job(
        hash=job_hash,
        name=RELEASE,
        source_url="magnet:?xt=urn:btih:" + job_hash,
        trigger=JobTrigger.MANUAL,
        media_id="tv:120089",
        route_id=route.id,
        state=state,
    )
    session.add(job)
    await session.commit()
    return job


async def run(
    session: AsyncSession,
    client: FakeQbittorrentClient,
    *,
    now: datetime = NOW,
    hub: EventHub | None = None,
    hints: JobHints | None = None,
) -> None:
    await poll_downloads(session, client, hub or EventHub(), hints or JobHints(), now=now)


async def events_of(session: AsyncSession, job_hash: str = HASH) -> list[Event]:
    rows = await session.scalars(select(Event).where(Event.job_hash == job_hash).order_by(Event.id))
    return list(rows)


def payload(event: Event) -> dict[str, Any]:
    """事件的 payload。**空的也是一種答案**，所以斷言的那一邊不必每次寫 `or {}`。"""
    return event.payload_json or {}


class TestMetadataReady:
    async def test_the_file_list_moves_the_job_on_and_lands_in_job_files(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`submitted` → `metadata_ready`：state 不是 `metaDL` 而且清單非空（plan §3.1）。"""
        job = await setup_job(session, roots)
        client = FakeQbittorrentClient(torrents=(status(state="downloading"),), files={HASH: FILES})

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.METADATA_READY
        rows = list(await session.scalars(select(JobFile).order_by(JobFile.id)))
        # `rel_path` 是 `torrents/files[].name` **原樣**：相對 save_path，含 torrent 根目錄。
        assert [row.rel_path for row in rows] == [row.name for row in FILES]
        assert [row.size for row in rows] == [row.size for row in FILES]

    async def test_metadl_is_not_metadata_ready_even_though_the_list_would_be_empty(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`metaDL` 期間 `torrents/files` 回的是 `200` + `[]`（實測兩版皆然）。

        所以「清單空的」與「這個 torrent 不存在」同形——只有 state 分得開，而 plan §3.1
        的條件正是兩個都要。
        """
        job = await setup_job(session, roots)
        client = FakeQbittorrentClient(torrents=(status(state="metaDL"),), files={})

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.SUBMITTED
        assert await events_of(session) == []

    async def test_the_event_says_how_many_files_and_how_big(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await setup_job(session, roots)
        client = FakeQbittorrentClient(torrents=(status(),), files={HASH: FILES})

        await run(session, client)

        received = [row for row in await events_of(session) if row.type == "metadata_received"]
        assert len(received) == 1
        assert payload(received[0]) == {
            "file_count": 2,
            "total_size": sum(row.size for row in FILES),
        }

    async def test_files_with_priority_zero_are_kept_but_not_counted(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`priority == 0` 是「不下載」，那種檔案不進 Plan（brief §5.1）。

        列仍然建起來——使用者要在 Job 詳情上看得出這一包裡有什麼，而「有但我們不要」
        與「根本沒有」是兩件事。
        """
        await setup_job(session, roots)
        skipped = TorrentFile(
            index=2, name=f"{RELEASE}/readme.txt", size=900, priority=0, progress=0.0
        )
        client = FakeQbittorrentClient(torrents=(status(),), files={HASH: (*FILES, skipped)})

        await run(session, client)

        rows = list(await session.scalars(select(JobFile)))
        assert len(rows) == 3
        job = await session.get(Job, HASH)
        assert job is not None
        assert job.total_size == sum(row.size for row in FILES)


class TestProgress:
    async def test_progress_moves_the_job_into_downloading(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job = await setup_job(session, roots, state=JobState.METADATA_READY)
        client = FakeQbittorrentClient(torrents=(status(progress=0.1),))

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.DOWNLOADING
        assert job.progress == pytest.approx(0.1)
        assert job.client_state == "downloading"

    async def test_one_event_per_quarter_crossed_and_not_one_per_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """每跨 25% 一筆（plan §3.1）。5 秒一輪的迴圈逐輪寫的話一小時就是七百多筆。"""
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        client = FakeQbittorrentClient(torrents=(status(progress=0.0),))

        for progress in (0.10, 0.24, 0.26, 0.40, 0.51, 0.99):
            client.torrents = (status(progress=progress),)
            await run(session, client)

        reported = [row for row in await events_of(session) if row.type == "progress"]
        # 25% / 50% / 75% 各一筆；0.10、0.24 與 0.40 沒有跨過任何一格。
        assert [payload(row)["progress"] for row in reported] == [0.26, 0.51, 0.99]

    async def test_the_threshold_survives_a_restart(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """門檻比的是資料庫裡上一次存下來的進度，所以重開之後不會把 25% 再寫一次。"""
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        job.progress = 0.30
        await session.commit()
        client = FakeQbittorrentClient(torrents=(status(progress=0.31),))

        await run(session, client)

        assert [row for row in await events_of(session) if row.type == "progress"] == []


class TestStalled:
    async def test_nothing_moving_for_long_enough_becomes_stalled(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        idle_since = int((NOW - STALL_AFTER - timedelta(minutes=1)).timestamp())
        client = FakeQbittorrentClient(
            torrents=(status(state="stalledDL", progress=0.4, last_activity=idle_since),)
        )

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.STALLED
        stalled = [row for row in await events_of(session) if row.type == "stalled"]
        assert stalled and payload(stalled[0])["client_state"] == "stalledDL"

    async def test_a_short_stall_is_not_a_stall(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """門檻刻意偏長：追蹤站重新 announce 之前的幾分鐘不該讓那一列跳來跳去。"""
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        idle_since = int((NOW - timedelta(minutes=2)).timestamp())
        client = FakeQbittorrentClient(
            torrents=(status(state="stalledDL", progress=0.4, last_activity=idle_since),)
        )

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.DOWNLOADING

    async def test_it_comes_back_by_itself_when_data_moves_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job = await setup_job(session, roots, state=JobState.STALLED)
        client = FakeQbittorrentClient(torrents=(status(state="downloading", progress=0.5),))

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.DOWNLOADING
        resumed = [row for row in await events_of(session) if row.type == "progress"]
        assert resumed and payload(resumed[0])["resumed"] is True


class TestCompleted:
    async def test_the_four_conditions_together_mean_completed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        client = FakeQbittorrentClient(
            torrents=(status(state="stalledUP", progress=1.0, completion_on=int(NOW.timestamp())),)
        )

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.COMPLETED
        assert job.completed_at == NOW
        assert [row.type for row in await events_of(session)][-1] == "completed"

    async def test_moving_is_not_completed_even_at_a_hundred_percent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """從 temp path 搬到 save path 期間 state 是 `moving`，此時檔案還不在（brief §20.2）。"""
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        client = FakeQbittorrentClient(
            torrents=(status(state="moving", progress=1.0, completion_on=int(NOW.timestamp())),)
        )

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.DOWNLOADING

    async def test_a_hundred_percent_without_completion_on_is_not_completed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """4.4.5 未完成時 `completion_on` 是 `0`、5.2.3 是 `-1`——判定寫成 `> 0` 才對兩版成立。"""
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        client = FakeQbittorrentClient(torrents=(status(progress=1.0, completion_on=-1),))

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.DOWNLOADING

    async def test_a_visible_save_path_without_the_files_is_missing_files(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """完成判定的第四條（brief §5.1）：Berth 看得到那個目錄，裡面卻沒有那些檔案。"""
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        visible = roots["complete"] / "anime"
        visible.mkdir(parents=True, exist_ok=True)
        session.add_all(
            [
                JobFile(job_hash=HASH, rel_path=row.name, size=row.size, priority=row.priority)
                for row in FILES
            ]
        )
        await session.commit()
        client = FakeQbittorrentClient(
            torrents=(
                status(
                    state="stalledUP",
                    progress=1.0,
                    completion_on=int(NOW.timestamp()),
                    save_path=str(visible),
                ),
            )
        )

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.MISSING_FILES
        issues = [row for row in await events_of(session) if row.type == "issue_detected"]
        assert payload(issues[0])["type"] == IssueType.MISSING_FILES.value

    async def test_a_path_this_machine_cannot_resolve_is_not_checked(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """這台機器把那串字變不成一個完整位置時，它沒有東西可以比對。

        真實的樣子是 **Windows 上的容器路徑**：qBittorrent 報的一律是 `/downloads/complete`，
        而在那裡它少了磁碟機代號，`Path` 會把它當成「目前磁碟機的根目錄底下」——那台機器上
        剛好有一個同名目錄時，這一支就會拿一條完全不相干的目錄去比對（2026-09-10 實跑當場
        踩到：完成的 torrent 被判成 `missing_files`）。`is_absolute()` 對那種路徑回 False。

        這裡用一條相對路徑：它在每個平台上都不是絕對路徑，所以這條規則測得準，
        不必看測試跑在哪一台機器上。
        """
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        session.add_all(
            [
                JobFile(job_hash=HASH, rel_path=row.name, size=row.size, priority=row.priority)
                for row in FILES
            ]
        )
        await session.commit()
        client = FakeQbittorrentClient(
            torrents=(
                status(
                    state="stalledUP",
                    progress=1.0,
                    completion_on=int(NOW.timestamp()),
                    save_path="downloads/complete/anime",
                ),
            )
        )

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.COMPLETED

    async def test_a_save_path_berth_cannot_see_is_not_this_torrents_problem(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """掛載對不上是 Route 的 `download_path` 纜繩在回答的問題（plan §9.5）。

        在這裡把它翻譯成 `missing_files` 會讓每一筆 Job 都紅著，而紅的理由指向錯的地方。
        """
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        client = FakeQbittorrentClient(
            torrents=(
                status(
                    state="stalledUP",
                    progress=1.0,
                    completion_on=int(NOW.timestamp()),
                    save_path="/somewhere/berth/cannot/see",
                ),
            )
        )

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.COMPLETED


class TestIssues:
    async def test_missing_files_from_the_client_is_an_issue(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        client = FakeQbittorrentClient(torrents=(status(state="missingFiles", progress=0.6),))

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.MISSING_FILES

    async def test_a_client_error_beats_a_hundred_percent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """壞掉優先：`error` 的 torrent 也可能報 `progress == 1`，先問完成就會判成下載好了。"""
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        client = FakeQbittorrentClient(
            torrents=(status(state="error", progress=1.0, completion_on=int(NOW.timestamp())),)
        )

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.CLIENT_ERROR
        issues = [row for row in await events_of(session) if row.type == "issue_detected"]
        assert payload(issues[0])["type"] == IssueType.CLIENT_ERROR.value

    async def test_a_torrent_that_left_the_client_is_client_removed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """合併過的清單就是客戶端當下的完整內容，所以「不在裡面」就是答案。"""
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        client = FakeQbittorrentClient(torrents=())

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.CLIENT_REMOVED
        issues = [row for row in await events_of(session) if row.type == "issue_detected"]
        assert payload(issues[0])["type"] == IssueType.CLIENT_REMOVED.value

    async def test_a_requested_job_is_not_missing_just_because_it_is_not_there_yet(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`requested` 的那一刻 `torrents/add` 都還沒回來。"""
        job = await setup_job(session, roots, state=JobState.REQUESTED)
        client = FakeQbittorrentClient(torrents=())

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.REQUESTED


class TestUnknownTorrents:
    async def test_a_berth_torrent_without_a_job_is_reported(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await setup_job(session, roots, state=JobState.COMPLETED)
        orphan = status(info_hash="f" * 40, category=CATEGORY)
        client = FakeQbittorrentClient(torrents=(orphan,))

        await run(session, client)

        settings = await read_settings(session, PollerSettings)
        assert [row.hash for row in settings.unknown_torrents] == ["f" * 40]
        issues = await events_of(session, "f" * 40)
        assert payload(issues[0])["type"] == IssueType.UNKNOWN_TORRENT.value

    async def test_someone_elses_torrent_is_left_alone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """只看本系統 category 的 torrent（plan §3.2）——使用者自己下載的東西不關 Berth 的事。"""
        await setup_job(session, roots, state=JobState.COMPLETED)
        client = FakeQbittorrentClient(
            torrents=(status(info_hash="e" * 40, category="linux-isos", tags=()),)
        )

        await run(session, client)

        settings = await read_settings(session, PollerSettings)
        assert settings.unknown_torrents == []

    async def test_the_event_is_written_once_and_not_once_per_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """迴圈每 5 秒跑一輪；每輪一筆的話一天就是一萬七千筆事件。"""
        await setup_job(session, roots, state=JobState.COMPLETED)
        client = FakeQbittorrentClient(torrents=(status(info_hash="f" * 40),))

        for _ in range(3):
            await run(session, client)

        assert len(await events_of(session, "f" * 40)) == 1

    async def test_the_list_is_this_rounds_truth_not_a_running_tally(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """使用者在 qBittorrent 上清掉那一筆之後，下一輪它就從畫面上消失。"""
        await setup_job(session, roots, state=JobState.COMPLETED)
        client = FakeQbittorrentClient(torrents=(status(info_hash="f" * 40),))
        await run(session, client)

        client.torrents = ()
        await run(session, client)

        assert (await read_settings(session, PollerSettings)).unknown_torrents == []


class TestPollerLoop:
    async def test_a_fresh_submit_is_picked_up_within_one_tick(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """間隔每次醒來重算，不沿用上一輪的答案。

        使用者按下送單的那一刻多半落在一個 30 秒的閒置間隔中間。沿用上一輪算出來的
        30 秒，他要對著那一列等最多半分鐘——而那正是這一票要拿掉的體驗。
        """
        await setup_job(session, roots, state=JobState.IMPORTED, job_hash="b" * 40)
        assert await next_interval(session) == IDLE_INTERVAL

        # 送單之後同一個問題有另一個答案，不必等上一輪的 30 秒過完。
        session.add(
            Job(
                hash=HASH,
                name=RELEASE,
                trigger=JobTrigger.MANUAL,
                state=JobState.SUBMITTED,
            )
        )
        await session.commit()

        assert await next_interval(session) == ACTIVE_INTERVAL


class TestIntervalsAndBackoff:
    async def test_an_active_job_asks_again_in_five_seconds(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        client = FakeQbittorrentClient(torrents=(status(progress=0.2),))

        outcome = await poll_downloads(session, client, EventHub(), JobHints(), now=NOW)

        assert outcome.active is True
        assert await next_interval(session) == ACTIVE_INTERVAL

    async def test_nothing_active_backs_off_to_thirty_seconds(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await setup_job(session, roots, state=JobState.IMPORTED)
        client = FakeQbittorrentClient(torrents=())

        outcome = await poll_downloads(session, client, EventHub(), JobHints(), now=NOW)

        assert outcome.active is False
        assert await next_interval(session) == IDLE_INTERVAL

    async def test_a_failed_round_keeps_the_last_known_unknown_torrents(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """這一輪沒問到，不代表它們不在了。"""
        await setup_job(session, roots, state=JobState.COMPLETED)
        client = FakeQbittorrentClient(torrents=(status(info_hash="f" * 40),))
        await run(session, client)

        failures = await record_poll_failure(session, "qbittorrent is not reachable")

        assert failures == 1
        settings = await read_settings(session, PollerSettings)
        assert settings.error == "qbittorrent is not reachable"
        assert [row.hash for row in settings.unknown_torrents] == ["f" * 40]

    async def test_a_good_round_clears_the_failure_count(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        await record_poll_failure(session, "boom")
        client = FakeQbittorrentClient(torrents=(status(progress=0.2),))

        await run(session, client)

        settings = await read_settings(session, PollerSettings)
        assert settings.failures == 0
        assert settings.error == ""


class TestCompareAndSet:
    async def test_the_second_writer_of_the_same_transition_gives_up(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """轉換一律 compare-and-set，影響 0 列即放棄（plan §3.1）。

        真實的競賽是這個形狀：兩個工作單元**各自**讀到同一個舊狀態（一個是 poller，
        一個是使用者按下的重試），然後先後送出同一個轉換。沒有 `WHERE state = :from`
        的話後到的那一個會把先到的結果蓋掉，而它以為自己成功了。
        """
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)

        first = await transition(session, job, JobState.COMPLETED, expected=JobState.DOWNLOADING)
        second = await transition(session, job, JobState.STALLED, expected=JobState.DOWNLOADING)

        assert first is True
        assert second is False
        await session.refresh(job)
        assert job.state is JobState.COMPLETED

    async def test_two_workers_racing_the_same_transition_only_move_it_once(
        self, session: AsyncSession, roots: dict[str, Path], engine: AsyncEngine
    ) -> None:
        """**真的並發**：兩個工作單元各自讀到同一列的舊狀態，然後同時送出同一個轉換。

        這是 poller 與使用者按下的重試之間真正會發生的形狀（兩個 session、兩條連線）。
        沒有 `WHERE state = :from` 的話後到的那一個會把先到的結果蓋掉，而它以為自己成功了。
        """
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        sessions = create_session_factory(engine)

        async def move(state: JobState) -> bool:
            async with sessions() as other:
                job = await other.get(Job, HASH)
                assert job is not None
                moved = await transition(other, job, state, expected=JobState.DOWNLOADING)
                await other.commit()
                return moved

        # `gather` 而不是先後呼叫：兩邊都在自己的 session 裡讀到 `downloading` 才送出。
        results = await asyncio.gather(move(JobState.COMPLETED), move(JobState.STALLED))

        # 剛好一個成功：另一個看到 `WHERE state = 'downloading'` 影響 0 列，放棄本次操作。
        assert sorted(results) == [False, True]
        landed = await session.scalar(select(Job.state).where(Job.hash == HASH))
        assert landed in (JobState.COMPLETED, JobState.STALLED)

    async def test_two_rounds_over_the_same_job_only_write_one_event(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """同一輪跑兩次不該讓時間線多一筆——冪等是這一整層的規矩（plan §3.3）。"""
        await setup_job(session, roots)
        client = FakeQbittorrentClient(torrents=(status(),), files={HASH: FILES})

        await run(session, client)
        await run(session, client)

        received = [row for row in await events_of(session) if row.type == "metadata_received"]
        assert len(received) == 1
        assert len(list(await session.scalars(select(JobFile)))) == len(FILES)


class TestJobLock:
    async def test_two_workers_on_the_same_job_do_not_overlap(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """一個 job 一把程序內的鎖（plan §3.1、brief §5.3）。

        compare-and-set 保證的是「不會寫壞」，鎖保證的是「不會做兩次」：poller 正在為某一筆
        建 `job_files` 時，使用者按下的重試如果同時跑，兩邊會各打一次 qBittorrent。
        """
        await setup_job(session, roots)
        inside: list[str] = []

        async def worker(name: str) -> None:
            async with job_lock(HASH):
                inside.append(f"{name}-in")
                # 讓出事件迴圈：沒有鎖的話另一個 worker 一定會在這裡插進來。
                await asyncio.sleep(0)
                inside.append(f"{name}-out")

        await asyncio.gather(worker("a"), worker("b"))

        # 兩段各自完整，沒有交錯。
        assert inside in (
            ["a-in", "a-out", "b-in", "b-out"],
            ["b-in", "b-out", "a-in", "a-out"],
        )

    async def test_a_different_job_is_not_held_up(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """鎖是**逐 job** 的：一筆卡住不該讓整份清單停下來。"""
        held = asyncio.Event()
        released = asyncio.Event()

        async def hold() -> None:
            async with job_lock(HASH):
                held.set()
                await released.wait()

        holding = asyncio.create_task(hold())
        await held.wait()
        async with job_lock("b" * 40):
            other = True
        released.set()
        await holding

        assert other is True

    async def test_the_lock_is_dropped_when_nobody_is_waiting(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """長期執行的 Berth 會經手幾千筆 Job；一個永遠長大的字典是個慢性漏洞。"""
        async with job_lock(HASH):
            assert held_locks() == 1

        assert held_locks() == 0


class TestWholeJourney:
    async def test_one_round_can_walk_a_finished_torrent_all_the_way(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """已經做完種的 torrent 加進來時，一輪裡它會走完整條主幹。

        輪詢的間隔不該決定使用者看到幾個階段，而時間線仍然說得出它經過了哪些站。
        """
        job = await setup_job(session, roots)
        client = FakeQbittorrentClient(
            torrents=(status(state="stalledUP", progress=1.0, completion_on=int(NOW.timestamp())),),
            files={HASH: FILES},
        )

        await run(session, client)

        await session.refresh(job)
        assert job.state is JobState.COMPLETED
        assert [row.type for row in await events_of(session)] == [
            "metadata_received",
            "completed",
        ]

    async def test_the_stream_gets_told_about_every_job_it_looked_at(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await setup_job(session, roots)
        hub = EventHub()
        client = FakeQbittorrentClient(torrents=(status(),), files={HASH: FILES})

        with hub.subscribe() as queue:
            await run(session, client, hub=hub)
            signal = queue.get_nowait()

        assert signal.hash == HASH
        assert signal.state == JobState.METADATA_READY.value

    async def test_the_signal_only_goes_out_after_the_transaction_lands(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """推播是「該去問了」的提示，而那件事只有在真相已經寫下去之後才成立。

        2026-09-10 實跑抓到的：commit 之前推播的話，前端收到「這一筆完成了」就立刻重問，
        而那一次讀到的是還沒 commit 的舊狀態——畫面因此**永遠慢一步**，每一筆事件都把它
        推到上一個狀態。
        """
        await setup_job(session, roots)
        seen: list[tuple[str, bool]] = []

        class Spy(EventHub):
            def publish(self, signal: JobSignal) -> None:
                # 發佈的那一刻：推的是哪一個狀態，而那一刻交易還開著嗎。
                seen.append((signal.state, session.in_transaction()))

        client = FakeQbittorrentClient(torrents=(status(),), files={HASH: FILES})
        await poll_downloads(session, client, Spy(), JobHints(), now=NOW)

        assert seen == [(JobState.METADATA_READY.value, False)]


class TestHints:
    async def test_a_round_that_moved_something_wakes_the_planner(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """下載完成到「規劃中」之間不必等 `planner_runner` 的一分鐘（plan §3.2、票 11）。"""
        await setup_job(session, roots)
        hints = JobHints()
        client = FakeQbittorrentClient(torrents=(status(),), files={HASH: FILES})

        await run(session, client, hints=hints)

        assert await hints.wait(0.05) is True

    async def test_a_round_that_changed_nothing_lets_it_sleep(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """5 秒一輪的迴圈每輪叫醒它一次的話，那 60 秒的間隔就形同虛設。"""
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        hints = JobHints()
        client = FakeQbittorrentClient(torrents=(status(progress=0.2),))

        await run(session, client, hints=hints)

        assert await hints.wait(0.05) is False


class TestDownloader:
    async def test_the_connection_is_reused_across_rounds(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """rid 增量掛在 qBittorrent 的 session 上：每輪重造 client 等於每輪都要一份全量。"""
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        factory = factory_for(roots)
        factory.qbittorrent_.torrents = (status(progress=0.2),)
        downloader = Downloader(factory, EventHub(), JobHints())

        await downloader.poll(session, now=NOW)
        await downloader.poll(session, now=NOW)
        await downloader.aclose()

        assert factory.qbittorrent_.syncs == 2

    async def test_a_failed_round_drops_the_connection_so_the_next_one_starts_over(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        factory = factory_for(roots)
        factory.qbittorrent_.sync_error = AuthFailedError("app/version: 403")
        downloader = Downloader(factory, EventHub(), JobHints())

        with pytest.raises(AuthFailedError):
            await downloader.poll(session, now=NOW)

        factory.qbittorrent_.sync_error = None
        factory.qbittorrent_.torrents = (status(progress=0.2),)
        await downloader.poll(session, now=NOW)
        await downloader.aclose()

    async def test_a_round_that_changes_nothing_pushes_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """**一筆 job 一輪最多一個訊號，而且只有真的變了才推。**

        一份 40 筆的下載清單每 5 秒推 40 次的話，每個開著的分頁就每 5 秒重問一次整份
        清單——而那正是這條推播要取代的東西。
        """
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        pushed: list[JobSignal] = []

        class Spy(EventHub):
            def publish(self, signal: JobSignal) -> None:
                pushed.append(signal)

        spy = Spy()
        client = FakeQbittorrentClient(torrents=(status(progress=0.2),))
        await poll_downloads(session, client, spy, JobHints(), now=NOW)
        assert len(pushed) == 1

        # 第二輪 qBittorrent 說的一模一樣：沒有東西動，所以沒有東西要推。
        await poll_downloads(session, client, spy, JobHints(), now=NOW)

        assert len(pushed) == 1

    async def test_an_ip_ban_reaches_the_loop_as_its_own_kind_of_failure(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「被封了」與「帳密不對」的下一步不同（plan §8.1、T1.9 第四條）。

        `sign_in` 刻意吞掉登入的例外好讓錯誤落在 Route 的纜繩上；迴圈沒有纜繩，所以它
        自己接住並記進 `settings.poller`。
        """
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        factory = factory_for(roots)
        factory.qbittorrent_ = FakeQbittorrentClient(
            login_error=IpBannedError(
                "auth/login: Your IP address has been banned after too many failed "
                "authentication attempts."
            )
        )
        credentials = await read_settings(session, QbittorrentSettings)
        credentials.username = "admin"
        credentials.password = "adminadmin"
        await write_settings(session, credentials)
        await session.commit()
        downloader = Downloader(factory, EventHub(), JobHints())

        with pytest.raises(IpBannedError) as banned:
            await downloader.poll(session, now=NOW)
        await downloader.aclose()

        assert "banned" in str(banned.value)
