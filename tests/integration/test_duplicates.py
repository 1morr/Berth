"""重複版本：規劃時略過、佇列上一列、三顆決定（brief §7.8、M2 票 08）。

起點是**兩筆真的下載**：第一筆整批入庫（S01E01–E03），第二筆帶來一份媒體庫裡已經有的東西。
決定的斷言貼著磁碟（同 `test_rematch.py`）：帳本說取代了不算，媒體庫裡那個名字真的指向新的來源
才算。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    DuplicateDecision,
    DuplicateReason,
    EventType,
    JobState,
    JobTrigger,
    PlanAction,
    PlanStatus,
    RematchRefusal,
    ReviewKind,
)
from berth.models import Job, JobFile, LedgerEntry, Media, Plan, PlanItem, Route
from berth.services.duplicates import decide_duplicate
from berth.services.events import EventHub
from berth.services.importer import sweep_imports
from berth.services.jobs import job_lock
from berth.services.plan import sweep_plans
from berth.services.rematch import RematchRejectedError
from berth.services.review import DuplicateRow, review_queue
from tests.integration.factories import FakeClientFactory
from tests.integration.test_importer import _put_on_disk, ledger_of, same_file, state_of
from tests.integration.test_plan import HASH, NOW, downloaded_job, events_of, plan_of, ready

pytestmark = pytest.mark.asyncio

ACTOR = "7"
SECOND = "5c1e0f7a2d3b4c5d6e7f8091a2b3c4d5e6f70812"

#: 同一集、同一組 Tags：與第一筆入庫的 S01E02 一模一樣的檔名。
SAME = "[Group] SPY×FAMILY S01E02 [1080p][CHT]"
SAME_FILES = ((f"{SAME}/{SAME}.mkv", 1_400_000_000),)

#: 起始集相同、結束集不同：媒體庫裡已經有 S01E01，這一份是 S01E01-E02。
SPAN = "[Group] SPY×FAMILY S01E01-E02 [1080p][CHT]"
SPAN_FILES = ((f"{SPAN}/{SPAN}.mkv", 2_800_000_000),)


async def first_batch(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Media, Route, FakeClientFactory]:
    """第一筆：整批入庫（三集、NCOP、S01E01 的字幕）。"""
    media, route, factory = await ready(session, roots)
    job = await downloaded_job(session, media, route, roots)
    await sweep_plans(session, factory, EventHub(), now=NOW)
    _put_on_disk(roots)
    await sweep_imports(session, factory, EventHub(), now=NOW)
    assert await state_of(session, job) is JobState.IMPORTED
    return media, route, factory


async def second_download(
    session: AsyncSession,
    roots: dict[str, Path],
    media: Media,
    route: Route,
    factory: FakeClientFactory,
    *,
    name: str,
    files: tuple[tuple[str, int], ...],
) -> Job:
    """第二筆：下載完、規劃完、入庫完。重複的那一列在規劃時就被略過了。"""
    save_path = str(roots["complete"] / "anime")
    job = Job(
        hash=SECOND,
        name=name,
        trigger=JobTrigger.MANUAL,
        media_id=media.id,
        route_id=route.id,
        state=JobState.COMPLETED,
        save_path=save_path,
        content_path=f"{save_path}/{name}",
        total_size=sum(size for _, size in files),
        progress=1.0,
        completed_at=NOW,
    )
    session.add(job)
    session.add_all(
        [
            JobFile(job_hash=SECOND, rel_path=rel_path, size=size, priority=1)
            for rel_path, size in files
        ]
    )
    await session.commit()
    await sweep_plans(session, factory, EventHub(), now=NOW)
    _put_on_disk(roots, files)
    await sweep_imports(session, factory, EventHub(), now=NOW)
    factory.jellyfin_.notified.clear()
    return job


async def duplicate_rows(session: AsyncSession) -> list[DuplicateRow]:
    return [row for row in (await review_queue(session)).rows if isinstance(row, DuplicateRow)]


async def entry_at(session: AsyncSession, episode: int) -> LedgerEntry:
    found = await session.scalar(
        select(LedgerEntry).where(
            LedgerEntry.action == PlanAction.IMPORT,
            LedgerEntry.episode_start == episode,
            LedgerEntry.job_hash != SECOND,
        )
    )
    assert found is not None
    return found


def new_source(roots: dict[str, Path], files: tuple[tuple[str, int], ...]) -> Path:
    return roots["complete"] / "anime" / files[0][0]


class TestTheSameVersion:
    async def test_it_is_skipped_and_the_rest_of_the_download_lands(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """自動模式跳過並記事件（brief §7.8），不把整筆擋下來。"""
        media, route, factory = await first_batch(session, roots)

        job = await second_download(
            session, roots, media, route, factory, name=SAME, files=SAME_FILES
        )

        assert await state_of(session, job) is JobState.IMPORTED
        assert (await plan_of(session, SECOND)).status is PlanStatus.APPLIED
        types = {event.type for event in await events_of(session, SECOND)}
        assert EventType.DUPLICATE_SKIPPED in types

    async def test_it_is_one_row_on_the_queue_that_names_the_copy_it_duplicates(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await first_batch(session, roots)
        await second_download(session, roots, media, route, factory, name=SAME, files=SAME_FILES)
        known = await entry_at(session, 2)

        (row,) = await duplicate_rows(session)

        assert row.kind is ReviewKind.DUPLICATE
        assert row.reason is DuplicateReason.SAME_VERSION
        assert row.known_path == known.target_path
        assert (row.season, row.episode_start) == (1, 2)
        assert row.rel_path == SAME_FILES[0][0]
        assert row.actions == (
            DuplicateDecision.REPLACE,
            DuplicateDecision.KEEP_BOTH,
            DuplicateDecision.SKIP,
        )

    async def test_replacing_swaps_the_link_to_the_new_source(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：取代舊版。同一條路徑一步換過去，帳本那一列改指新的來源。"""
        media, route, factory = await first_batch(session, roots)
        await second_download(session, roots, media, route, factory, name=SAME, files=SAME_FILES)
        known = await entry_at(session, 2)
        old_source = Path(known.source_abs_path)
        (row,) = await duplicate_rows(session)

        outcome = await decide_duplicate(
            session, factory, row.item_id, DuplicateDecision.REPLACE, actor=ACTOR
        )

        assert outcome is not None
        assert outcome.target_path == known.target_path
        assert same_file(Path(known.target_path), new_source(roots, SAME_FILES))
        assert old_source.exists()  # complete 裡舊的那一份不動
        await session.refresh(known)
        assert (known.job_hash, known.source_rel_path) == (SECOND, SAME_FILES[0][0])
        assert factory.jellyfin_.notified == [known.target_path]
        assert await duplicate_rows(session) == []
        (event,) = [
            e for e in await events_of(session, SECOND) if e.type == EventType.DUPLICATE_DECIDED
        ]
        assert (event.payload_json or {})["decision"] == "replace"
        assert (event.payload_json or {})["replaced"] == known.target_path

    async def test_replacing_over_a_foreign_file_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """使用者把 Berth 的硬鏈接換成了自己的檔案：取代舊版不覆寫它（同 `deletion.Placed`）。"""
        media, route, factory = await first_batch(session, roots)
        await second_download(session, roots, media, route, factory, name=SAME, files=SAME_FILES)
        known = await entry_at(session, 2)
        target = Path(known.target_path)
        target.unlink()
        target.write_bytes(b"someone else's copy")
        (row,) = await duplicate_rows(session)

        with pytest.raises(RematchRejectedError) as refusal:
            await decide_duplicate(
                session, factory, row.item_id, DuplicateDecision.REPLACE, actor=ACTOR
            )

        assert refusal.value.reason is RematchRefusal.TARGET_TAKEN
        assert target.read_bytes() == b"someone else's copy"
        await session.refresh(known)
        assert known.job_hash != SECOND  # 帳本那一列沒有被改指到新的來源
        assert Path(known.target_path) == target
        assert await duplicate_rows(session) == [row]

    async def test_keeping_both_links_the_new_one_under_a_numbered_tag(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：保留兩者。同一組 Tags 的檔名撞在一起，新的多一個 `[2]`
        （2026-09-23 拍板）。"""
        media, route, factory = await first_batch(session, roots)
        await second_download(session, roots, media, route, factory, name=SAME, files=SAME_FILES)
        known = await entry_at(session, 2)
        (row,) = await duplicate_rows(session)

        outcome = await decide_duplicate(
            session, factory, row.item_id, DuplicateDecision.KEEP_BOTH, actor=ACTOR
        )

        assert outcome is not None
        assert outcome.target_path != known.target_path
        assert outcome.target_path.endswith("[1080p][CHT][Group][2].mkv")
        assert same_file(Path(outcome.target_path), new_source(roots, SAME_FILES))
        assert same_file(Path(known.target_path), Path(known.source_abs_path))
        paths = {entry.target_path for entry in await ledger_of(session)}
        assert {known.target_path, outcome.target_path} <= paths
        assert factory.jellyfin_.notified == [outcome.target_path]
        assert await duplicate_rows(session) == []

    async def test_skipping_changes_nothing_on_disk(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：跳過。新的那一份留在 complete 原位，這一列不再等人。"""
        media, route, factory = await first_batch(session, roots)
        await second_download(session, roots, media, route, factory, name=SAME, files=SAME_FILES)
        known = await entry_at(session, 2)
        before = [(entry.id, entry.target_path) for entry in await ledger_of(session)]
        (row,) = await duplicate_rows(session)

        outcome = await decide_duplicate(
            session, factory, row.item_id, DuplicateDecision.SKIP, actor=ACTOR
        )

        assert outcome is None
        assert [(entry.id, entry.target_path) for entry in await ledger_of(session)] == before
        assert same_file(Path(known.target_path), Path(known.source_abs_path))
        assert factory.jellyfin_.notified == []
        assert await duplicate_rows(session) == []
        item = await session.get(PlanItem, row.item_id)
        assert item is not None
        assert (item.action, item.duplicate_of) == (PlanAction.SKIP, None)
        types = [e.type for e in await events_of(session, SECOND)]
        assert EventType.DUPLICATE_DECIDED in types

    async def test_a_second_tab_finds_it_already_decided(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await first_batch(session, roots)
        await second_download(session, roots, media, route, factory, name=SAME, files=SAME_FILES)
        (row,) = await duplicate_rows(session)
        await decide_duplicate(session, factory, row.item_id, DuplicateDecision.SKIP, actor=ACTOR)

        with pytest.raises(RematchRejectedError) as refused:
            await decide_duplicate(
                session, factory, row.item_id, DuplicateDecision.REPLACE, actor=ACTOR
            )

        assert refused.value.reason is RematchRefusal.NOT_DUPLICATE

    async def test_it_leaves_a_one_row_plan_behind(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """一律經過 Plan（brief §9.4）：取代也是一次 rematch。"""
        media, route, factory = await first_batch(session, roots)
        await second_download(session, roots, media, route, factory, name=SAME, files=SAME_FILES)
        (row,) = await duplicate_rows(session)

        outcome = await decide_duplicate(
            session, factory, row.item_id, DuplicateDecision.REPLACE, actor=ACTOR
        )

        assert outcome is not None
        plan = await session.get(Plan, outcome.plan_id)
        assert plan is not None
        assert plan.job_hash is None


class TestASpanClash:
    """多集檔對同起始集的單集（brief §7.8 後半，2026-09-15 拍板）。"""

    async def test_it_is_a_duplicate_row_that_says_why(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：出現在佇列上；理由是 `span_clash`（畫面照它說出 Jellyfin 會併掉後面
        那一集）。"""
        media, route, factory = await first_batch(session, roots)
        await second_download(session, roots, media, route, factory, name=SPAN, files=SPAN_FILES)
        known = await entry_at(session, 1)

        (row,) = await duplicate_rows(session)

        assert row.reason is DuplicateReason.SPAN_CLASH
        assert (row.season, row.episode_start, row.episode_end) == (1, 1, 2)
        assert (row.known_season, row.known_episode_start, row.known_episode_end) == (1, 1, None)
        assert row.known_path == known.target_path

    async def test_replacing_moves_the_episode_and_takes_the_old_subtitle_away(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """取代：S01E01 拆掉、S01E01-E02 鏈進去；舊的那一集旁邊的字幕屬於被取代的那一份，一起拆。"""
        media, route, factory = await first_batch(session, roots)
        await second_download(session, roots, media, route, factory, name=SPAN, files=SPAN_FILES)
        known = await entry_at(session, 1)
        old_path = known.target_path
        subtitle = await session.scalar(
            select(LedgerEntry).where(LedgerEntry.action == PlanAction.SUBTITLE)
        )
        assert subtitle is not None
        old_subtitle = subtitle.target_path
        (row,) = await duplicate_rows(session)

        outcome = await decide_duplicate(
            session, factory, row.item_id, DuplicateDecision.REPLACE, actor=ACTOR
        )

        assert outcome is not None
        assert "S01E01-E02" in outcome.target_path
        assert not Path(old_path).exists()
        assert not Path(old_subtitle).exists()
        assert same_file(Path(outcome.target_path), new_source(roots, SPAN_FILES))
        await session.refresh(known)
        assert (known.target_path, known.episode_end) == (outcome.target_path, 2)
        assert sorted(factory.jellyfin_.notified) == sorted(
            [outcome.target_path, old_path, old_subtitle]
        )

    async def test_keeping_both_links_the_new_one_beside_the_old(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """保留兩者：路徑本來就不同，不加序號。後果（Jellyfin 會併成一集）畫面在按之前說。"""
        media, route, factory = await first_batch(session, roots)
        await second_download(session, roots, media, route, factory, name=SPAN, files=SPAN_FILES)
        known = await entry_at(session, 1)
        (row,) = await duplicate_rows(session)

        outcome = await decide_duplicate(
            session, factory, row.item_id, DuplicateDecision.KEEP_BOTH, actor=ACTOR
        )

        assert outcome is not None
        assert outcome.target_path.endswith("S01E01-E02 [1080p][CHT][Group].mkv")
        assert same_file(Path(known.target_path), Path(known.source_abs_path))
        assert same_file(Path(outcome.target_path), new_source(roots, SPAN_FILES))


class TestTheOldDownload:
    """取代舊版動的是**另一筆** Job 的鏈接與帳本（code-review 抓到的兩條）。"""

    async def test_its_plan_row_no_longer_claims_the_file(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """舊 Job 那一份 Plan 說的是現況：那一集已經不是它的了。"""
        media, route, factory = await first_batch(session, roots)
        await second_download(session, roots, media, route, factory, name=SAME, files=SAME_FILES)
        known = await entry_at(session, 2)
        old_row = await session.get(PlanItem, known.plan_item_id)
        assert old_row is not None
        (row,) = await duplicate_rows(session)

        await decide_duplicate(
            session, factory, row.item_id, DuplicateDecision.REPLACE, actor=ACTOR
        )

        await session.refresh(old_row)
        assert (old_row.action, old_row.applied_at, old_row.target_path) == (
            PlanAction.SKIP,
            None,
            "",
        )

    async def test_replacing_waits_for_the_old_downloads_lock(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """舊 Job 那邊正有人在動（撤銷 audit、刪除、rematch 都鎖它）時，取代要等，不是同時寫。"""
        media, route, factory = await first_batch(session, roots)
        await second_download(session, roots, media, route, factory, name=SAME, files=SAME_FILES)
        (row,) = await duplicate_rows(session)

        async with job_lock(HASH):
            task = asyncio.create_task(
                decide_duplicate(
                    session, factory, row.item_id, DuplicateDecision.REPLACE, actor=ACTOR
                )
            )
            await asyncio.sleep(0.2)
            assert not task.done()
        assert await task is not None
