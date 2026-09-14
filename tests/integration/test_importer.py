"""importer：Import Plan → 媒體庫（plan §3.1、§3.2、§3.3、brief §4.4、§5.3、票 12）。

**這是整個產品唯一會在媒體庫裡放東西的地方**，而且沒有人在場。所以這一份的斷言分成四組：

- **磁碟上真的發生了什麼**：硬鏈接成立的定義是兩條路徑同一個 inode，這裡逐個 `stat`
  比，不是看 importer 回報了什麼（票上那一條驗收）。
- **帳本寫下了什麼**：一個檔案一筆，而且它自己站得住（`models/ledger.py`）。
- **什麼時候停下來**：目標上已經有別人的檔案（review）、鏈接失敗（`import_failed`）。
- **重來一次會怎樣**：重跑、重試、重啟之後都不能多鏈接一次、多寫一筆（plan §3.3）。

檔案是真的寫在 `tmp_path` 底下的——`roots` 是同一個掛載底下的三層路徑，所以硬鏈接真的
建得起來（`tests/integration/conftest.py`）。
"""

from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters import fs
from berth.adapters.http import ServiceUnavailableError
from berth.db import create_session_factory
from berth.domain import (
    EventType,
    JellyfinRequest,
    JobState,
    LedgerStatus,
    PlanAction,
    PlanStatus,
    ReviewReason,
)
from berth.models import Job, JobFile, LedgerEntry, PlanItem, Route
from berth.pipeline import Importer, PlannerRunner
from berth.services.events import EventHub, JobSignal
from berth.services.hints import JobHints
from berth.services.importer import UNMANAGED_TARGET, ImportOutcome, sweep_imports
from berth.services.jobs import retry_job
from berth.services.plan import sweep_plans
from berth.services.resolver import RESOLVE_DELAYS
from berth.services.setup import complete_setup
from tests.integration.factories import FakeClientFactory
from tests.integration.test_plan import (
    BATCH,
    BATCH_FILES,
    HASH,
    NOW,
    downloaded_job,
    events_of,
    items_of,
    plan_of,
    ready,
)

pytestmark = pytest.mark.asyncio

#: 這一包裡會被寫進媒體庫的那五個：三集、一個 NCOP、一條字幕。readme 是 skip。
WRITTEN = {PlanAction.IMPORT, PlanAction.EXTRA, PlanAction.SUBTITLE}


def _put_on_disk(roots: dict[str, Path], files: tuple[tuple[str, int], ...] = BATCH_FILES) -> None:
    """把那一包真的寫到 qBittorrent 說的位置上。內容逐檔不同，所以誰鏈到誰一眼看得出來。"""
    for rel_path, _ in files:
        path = roots["complete"] / "anime" / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(rel_path.encode())


async def importing(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Job, Route, FakeClientFactory]:
    """一筆走到 `importing` 的 Job：Plan 是 planner 真的算出來的，檔案真的在 complete 底下。

    檔案在**規劃之後**才寫：規劃那一輪看得到檔案的話會逐個問 mediainfo，而這幾個檔案不是
    影片——那是票 11 的事，不是這一份要測的。
    """
    media, route, factory = await ready(session, roots)
    job = await downloaded_job(session, media, route, roots)
    await sweep_plans(session, factory, EventHub(), now=NOW)
    assert await state_of(session, job) is JobState.IMPORTING
    _put_on_disk(roots)
    return job, route, factory


async def run(
    session: AsyncSession, factory: FakeClientFactory, *, hub: EventHub | None = None
) -> ImportOutcome:
    return await sweep_imports(session, factory, hub or EventHub(), now=NOW)


async def state_of(session: AsyncSession, job: Job) -> JobState:
    """重讀一次再回答。**不直接斷言 `job.state`**：同一個測試裡先後斷言兩個狀態時，
    mypy 會把第一個斷言當成永遠成立，第二個就成了到不了的程式碼。"""
    await session.refresh(job)
    return job.state


async def placements(
    session: AsyncSession, job: Job, route: Route
) -> list[tuple[PlanItem, Path, Path]]:
    """每一個會被寫出去的決定：它的來源檔案在哪、它該出現在媒體庫的哪裡。"""
    sources = {
        row.id: row.rel_path
        for row in await session.scalars(select(JobFile).where(JobFile.job_hash == job.hash))
    }
    return [
        (
            item,
            fs.under(job.save_path, sources[item.job_file_id or 0]),
            fs.under(route.target_path, item.target_path),
        )
        for item in await items_of(session)
        if item.action in WRITTEN
    ]


async def ledger_of(session: AsyncSession) -> list[LedgerEntry]:
    return list(await session.scalars(select(LedgerEntry).order_by(LedgerEntry.id)))


def same_file(a: Path, b: Path) -> bool:
    """**自己比**，不借 `fs.same_inode`：這一條驗收要的是磁碟上的事實，不是 importer 的說法。"""
    left, right = a.stat(), b.stat()
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


class TestLinking:
    async def test_every_written_file_is_a_hard_link_of_its_source(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, route, factory = await importing(session, roots)

        await run(session, factory)

        placed = await placements(session, job, route)
        assert len(placed) == 5
        for _, source, target in placed:
            assert target.is_file()
            assert same_file(source, target)

    async def test_the_targets_land_in_the_planned_folder_under_the_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await importing(session, roots)

        await run(session, factory)

        route_dir = roots["library"] / "anime"
        assert [path.name for path in route_dir.iterdir()] == [
            "SPY x FAMILY (2022) [tmdbid-120089]"
        ]
        assert any(path.suffix == ".mkv" for path in route_dir.rglob("*S01E01*"))

    async def test_a_skipped_file_never_reaches_the_library(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await importing(session, roots)

        await run(session, factory)

        assert not any(path.name == "readme.txt" for path in roots["library"].rglob("*"))

    async def test_the_source_is_left_exactly_where_it_was(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """永不移動、改名或修改 complete 底下的檔案——做種靠它們（brief §5.3）。"""
        _, _, factory = await importing(session, roots)

        await run(session, factory)

        for rel_path, _ in BATCH_FILES:
            source = roots["complete"] / "anime" / rel_path
            assert source.read_bytes() == rel_path.encode()

    async def test_the_job_is_imported_and_its_plan_applied(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await importing(session, roots)

        outcome = await run(session, factory)

        assert outcome.imported == 1
        assert await state_of(session, job) is JobState.IMPORTED
        assert job.imported_at == NOW
        assert (await plan_of(session)).status is PlanStatus.APPLIED
        written = [item for item in await items_of(session) if item.action in WRITTEN]
        assert all(item.applied_at == NOW for item in written)

    async def test_the_stream_is_told_after_the_transaction_lands(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await importing(session, roots)
        seen: list[tuple[str, bool]] = []

        class Spy(EventHub):
            def publish(self, signal: JobSignal) -> None:
                seen.append((signal.state, session.in_transaction()))

        await run(session, factory, hub=Spy())

        assert seen == [(JobState.IMPORTED.value, False)]


class TestLedger:
    async def test_one_entry_per_linked_file(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, route, factory = await importing(session, roots)

        await run(session, factory)

        placed = await placements(session, job, route)
        entries = await ledger_of(session)
        assert len(entries) == len(placed)
        by_target = {Path(entry.target_path): entry for entry in entries}
        for item, source, target in placed:
            entry = by_target[target]
            assert entry.job_hash == HASH
            assert entry.plan_item_id == item.id
            assert entry.action is item.action
            assert (entry.season, entry.episode_start) == (item.season, item.episode_start)
            assert entry.media_id == item.media_id
            assert Path(entry.source_abs_path) == source
            assert entry.source_rel_path.endswith(item.rel_path)
            assert entry.source_inode == str(source.stat().st_ino)
            assert entry.source_dev == str(source.stat().st_dev)
            assert entry.target_inode == entry.source_inode
            assert entry.status is LedgerStatus.OK
            assert entry.link_mode == "hardlink"

    async def test_only_the_features_wait_for_a_jellyfin_item(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """字幕是一條串流、特典掛在作品底下——兩者在 Jellyfin 裡都不是自己查得到的 item。"""
        _, _, factory = await importing(session, roots)

        await run(session, factory)

        for entry in await ledger_of(session):
            if entry.action is PlanAction.IMPORT:
                assert entry.resolve_after == NOW + RESOLVE_DELAYS[0]
            else:
                assert entry.resolve_after is None
            assert entry.resolve_attempts == 0
            assert entry.jellyfin_item_id == ""


class TestJellyfin:
    async def test_jellyfin_is_told_about_every_new_file(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await importing(session, roots)

        await run(session, factory)

        targets = sorted(entry.target_path for entry in await ledger_of(session))
        assert sorted(factory.jellyfin_.notified) == targets
        requested = [
            row for row in await events_of(session) if row.type == "jellyfin_scan_requested"
        ]
        assert len(requested) == 1
        assert (requested[0].payload_json or {})["count"] == 5

    async def test_jellyfin_being_down_does_not_hold_back_imported(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """檔案已經在媒體庫裡了；Jellyfin 自己的掃描遲早看得到它們（plan §3.3）。"""
        job, _, factory = await importing(session, roots)
        factory.jellyfin_.notify_error = ServiceUnavailableError("POST /Library/Media/Updated")

        await run(session, factory)

        assert await state_of(session, job) is JobState.IMPORTED
        failed = [row for row in await events_of(session) if row.type == "jellyfin_request_failed"]
        assert len(failed) == 1
        assert (failed[0].payload_json or {})["request"] == JellyfinRequest.SCAN.value


class TestEvents:
    async def test_one_linked_event_per_file(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await importing(session, roots)

        await run(session, factory)

        linked = [row for row in await events_of(session) if row.type == EventType.LINKED.value]
        assert len(linked) == 5
        assert all(set(row.payload_json or {}) >= {"file", "target"} for row in linked)


class TestIdempotency:
    async def test_running_it_again_links_nothing_twice(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """重啟之後那一列可能還停在 `importing`，而磁碟上的鏈接已經在了（plan §3.3）。"""
        job, _, factory = await importing(session, roots)
        await run(session, factory)
        job.state = JobState.IMPORTING
        for item in await items_of(session):
            item.applied_at = None
        await session.commit()

        await run(session, factory)

        assert await state_of(session, job) is JobState.IMPORTED
        assert len(await ledger_of(session)) == 5
        linked = [row for row in await events_of(session) if row.type == EventType.LINKED.value]
        assert len(linked) == 5

    async def test_a_link_that_is_already_there_is_adopted_into_the_ledger(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """鏈接建好了、帳本還沒寫就被關掉：目標 inode 等於來源 → 視為已完成，補上帳本。"""
        job, route, factory = await importing(session, roots)
        _, source, target = (await placements(session, job, route))[0]
        target.parent.mkdir(parents=True, exist_ok=True)
        os.link(source, target)

        await run(session, factory)

        assert await state_of(session, job) is JobState.IMPORTED
        entries = await ledger_of(session)
        assert Path(entries[0].target_path) == target
        assert len(entries) == 5

    async def test_somebody_elses_file_at_the_target_sends_the_job_to_review(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """媒體庫裡不是 Berth 鏈接的東西永不覆寫（brief §5.3、plan §3.3）。"""
        job, route, factory = await importing(session, roots)
        item, _, target = (await placements(session, job, route))[0]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"someone else's copy")

        await run(session, factory)

        assert await state_of(session, job) is JobState.REVIEW
        assert target.read_bytes() == b"someone else's copy"
        await session.refresh(item)
        assert item.error == UNMANAGED_TARGET
        assert item.applied_at is None
        plan = await plan_of(session)
        assert plan.status is PlanStatus.PENDING_REVIEW
        assert (plan.summary_json or {})["review_reason"] == ReviewReason.TARGET_EXISTS.value
        required = [row for row in await events_of(session) if row.type == "review_required"]
        assert (required[-1].payload_json or {})["reason"] == ReviewReason.TARGET_EXISTS.value
        # 其餘四個照樣進去了：它們彼此獨立，而且重來一次時會被跳過。
        assert len(await ledger_of(session)) == 4


class TestFailures:
    async def test_a_link_that_fails_marks_the_job_import_failed_with_the_os_error(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        job, _, factory = await importing(session, roots)

        def cross_device(source: object, target: object) -> None:
            raise OSError(errno.EXDEV, "Invalid cross-device link")

        monkeypatch.setattr(os, "link", cross_device)

        outcome = await run(session, factory)

        assert outcome.failed == 1
        assert await state_of(session, job) is JobState.IMPORT_FAILED
        assert "cross-device" in job.error
        assert (await plan_of(session)).status is PlanStatus.FAILED
        failed = [row for row in await events_of(session) if row.type == "link_failed"]
        assert failed
        assert (failed[0].payload_json or {})["errno"] == errno.EXDEV
        # 正片鏈接不成擋住整筆入庫，畫面才把它塗紅（DESIGN.md 的 The One Meaning Rule）。
        assert (failed[0].payload_json or {})["blocking"] is True
        assert "mount" in (failed[0].payload_json or {})["error"]
        assert await ledger_of(session) == []
        assert factory.jellyfin_.notified == []

    async def test_a_subtitle_that_fails_does_not_hold_back_the_episodes(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """一條字幕或一個 NCOP 鏈接不成，那一集仍然看得了——整季擋下來換不到任何東西。"""
        job, _, factory = await importing(session, roots)
        real_link = os.link

        def no_subtitles(source: str, target: str) -> None:
            if str(target).endswith(".ass"):
                raise OSError(errno.EACCES, "Permission denied")
            real_link(source, target)

        monkeypatch.setattr(os, "link", no_subtitles)

        await run(session, factory)

        assert await state_of(session, job) is JobState.IMPORTED
        subtitle = next(
            item for item in await items_of(session) if item.action is PlanAction.SUBTITLE
        )
        assert "Permission denied" in subtitle.error
        failed = [row for row in await events_of(session) if row.type == "link_failed"]
        assert [(row.payload_json or {})["blocking"] for row in failed] == [False]
        assert subtitle.applied_at is None
        assert len(await ledger_of(session)) == 4

    async def test_retrying_skips_what_is_already_linked(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """重試回 `importing`，已完成的 item 跳過（plan §3.1）。"""
        job, _, factory = await importing(session, roots)
        real_link = os.link

        def not_the_third(source: str, target: str) -> None:
            if "S01E03" in str(target):
                raise OSError(errno.EXDEV, "Invalid cross-device link")
            real_link(source, target)

        monkeypatch.setattr(os, "link", not_the_third)
        await run(session, factory)
        assert await state_of(session, job) is JobState.IMPORT_FAILED
        monkeypatch.setattr(os, "link", real_link)

        view = await retry_job(session, factory, HASH)
        assert view.state is JobState.IMPORTING
        await run(session, factory)

        assert await state_of(session, job) is JobState.IMPORTED
        assert job.error == ""
        assert len(await ledger_of(session)) == 5
        linked = [row for row in await events_of(session) if row.type == EventType.LINKED.value]
        assert len(linked) == 5
        assert "retried" in [row.type for row in await events_of(session)]

    async def test_a_target_outside_every_route_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """寫入媒體庫的路徑一定在某個 Route 的 `target_path` 底下（plan §8.6）。"""
        job, _, factory = await importing(session, roots)
        episode = next(item for item in await items_of(session) if item.action is PlanAction.IMPORT)
        episode.target_path = "../../outside.mkv"
        await session.commit()

        await run(session, factory)

        assert await state_of(session, job) is JobState.IMPORT_FAILED
        await session.refresh(episode)
        assert "outside every Berth route target" in episode.error
        assert not (roots["library"].parent / "outside.mkv").exists()


class TestRound:
    async def test_a_job_that_is_not_importing_is_left_alone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await importing(session, roots)
        job.state = JobState.REVIEW
        await session.commit()

        outcome = await run(session, factory)

        assert outcome.imported == 0
        assert await ledger_of(session) == []


class TestRunner:
    async def test_it_does_nothing_until_the_wizard_is_done(
        self, session: AsyncSession, roots: dict[str, Path], engine: AsyncEngine
    ) -> None:
        _, _, factory = await importing(session, roots)
        importer = Importer(create_session_factory(engine), factory, EventHub(), JobHints())

        assert await importer.tick() is None

    async def test_one_tick_imports_what_is_due(
        self, session: AsyncSession, roots: dict[str, Path], engine: AsyncEngine
    ) -> None:
        _, _, factory = await importing(session, roots)
        await complete_setup(session)
        await session.commit()
        importer = Importer(create_session_factory(engine), factory, EventHub(), JobHints())

        outcome = await importer.tick()

        assert outcome is not None
        assert outcome.imported == 1

    async def test_a_plan_that_lands_in_importing_wakes_the_importer(
        self, session: AsyncSession, roots: dict[str, Path], engine: AsyncEngine
    ) -> None:
        """planner 算完就叫醒 importer，不必等它自己的 60 秒（plan §3.2 的事件驅動）。"""
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots, name=BATCH)
        await complete_setup(session)
        await session.commit()
        imports = JobHints()
        planner = PlannerRunner(
            create_session_factory(engine), factory, EventHub(), JobHints(), import_hints=imports
        )

        await planner.tick()

        assert await imports.wait(0.01) is True
