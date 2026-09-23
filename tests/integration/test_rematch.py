"""改一個檔案的處置：rematch（brief §7.4、§9.4、M2 票 08）。

起點都是**真的走完一次入庫**：規劃 → 入庫 → 帳本與磁碟上都有東西。票上的驗收是「新鏈接建起來、
舊鏈接刪掉、帳本改掉、Jellyfin 收到掃描通知」，所以每一條都貼著磁碟斷言（同 `test_review.py`）：
帳本說搬了不算，媒體庫裡那個名字真的換了才算。
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    EventType,
    JobState,
    MediaKind,
    PlanAction,
    PlanEngine,
    PlanStatus,
    ReasonCode,
    RematchRefusal,
    ReviewKind,
    why,
)
from berth.models import Job, JobFile, LedgerEntry, Plan, PlanItem, Route
from berth.services.events import EventHub
from berth.services.importer import sweep_imports
from berth.services.plan import sweep_plans
from berth.services.rematch import Assignment, RematchRejectedError, rematch_file
from berth.services.review import UnmatchedRow, review_queue
from tests.integration.factories import FakeClientFactory
from tests.integration.test_importer import _put_on_disk, ledger_of, same_file, state_of
from tests.integration.test_plan import (
    BATCH,
    BATCH_FILES,
    NOW,
    downloaded_job,
    events_of,
    items_of,
    plan_of,
    ready,
)

pytestmark = pytest.mark.asyncio

ACTOR = "7"

#: 字幕組自己編號的特典：TMDB 上沒有它，所以它對不到、留在 complete 原位（brief §7.6）。
OVA = f"{BATCH}/[Group] SPY×FAMILY OVA 2 [1080p].mkv"
FILES = (*BATCH_FILES, (OVA, 300_000_000))


async def imported(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Job, Route, FakeClientFactory]:
    """一筆入庫完的批次：三集、NCOP、S01E01 的字幕，外加一個對不到的 OVA。"""
    media, route, factory = await ready(session, roots)
    job = await downloaded_job(session, media, route, roots, files=FILES)
    await sweep_plans(session, factory, EventHub(), now=NOW)
    _put_on_disk(roots, FILES)
    await sweep_imports(session, factory, EventHub(), now=NOW)
    assert await state_of(session, job) is JobState.IMPORTED
    factory.jellyfin_.notified.clear()
    return job, route, factory


async def ova(session: AsyncSession) -> JobFile:
    row = await session.scalar(select(JobFile).where(JobFile.rel_path == OVA))
    assert row is not None
    return row


def source_of(roots: dict[str, Path], rel_path: str) -> Path:
    return roots["complete"] / "anime" / rel_path


async def entry_at(session: AsyncSession, episode: int) -> LedgerEntry:
    found = await session.scalar(
        select(LedgerEntry).where(
            LedgerEntry.action == PlanAction.IMPORT, LedgerEntry.episode_start == episode
        )
    )
    assert found is not None
    return found


async def rematch_plans(session: AsyncSession) -> list[Plan]:
    return list(await session.scalars(select(Plan).where(Plan.job_hash.is_(None))))


class TestAnUnmatchedFile:
    async def test_it_starts_out_unmatched_and_left_in_place(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """前提：OVA 對不到，而它不擋其餘三集自動入庫（票 11 的偏差）。"""
        await imported(session, roots)

        row = next(
            item for item in await items_of(session) if item.rel_path.endswith("OVA 2 [1080p].mkv")
        )

        assert row.action is PlanAction.UNMATCHED

    async def test_assigning_it_links_it_records_it_and_tells_jellyfin(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：指派為 S00E03 走完整條路徑——鏈接、帳本、掃描通知、紀錄。"""
        job, _, factory = await imported(session, roots)
        row = await ova(session)

        outcome = await rematch_file(
            session,
            factory,
            job_file_id=row.id,
            to=Assignment(PlanAction.IMPORT, season=0, episode_start=3),
            actor=ACTOR,
        )

        target = Path(outcome.target_path)
        assert "Season 00" in outcome.target_path and "S00E03" in target.name
        assert same_file(target, source_of(roots, OVA))
        entry = next(
            entry for entry in await ledger_of(session) if entry.target_path == outcome.target_path
        )
        assert (entry.season, entry.episode_start, entry.action) == (0, 3, PlanAction.IMPORT)
        assert entry.job_hash == job.hash
        assert factory.jellyfin_.notified == [outcome.target_path]

    async def test_it_leaves_a_one_row_plan_by_the_user_behind(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：`plans` 多一份 `engine = user`、`job_hash = NULL` 的單列 Plan。"""
        _, _, factory = await imported(session, roots)
        row = await ova(session)

        outcome = await rematch_file(
            session,
            factory,
            job_file_id=row.id,
            to=Assignment(PlanAction.IMPORT, season=0, episode_start=3),
            actor=ACTOR,
        )

        (plan,) = await rematch_plans(session)
        assert plan.id == outcome.plan_id
        assert (plan.engine, plan.status, plan.decided_by) == (
            PlanEngine.USER,
            PlanStatus.APPLIED,
            ACTOR,
        )
        (item,) = await session.scalars(select(PlanItem).where(PlanItem.plan_id == plan.id))
        assert (item.job_file_id, item.action, item.season, item.episode_start) == (
            row.id,
            PlanAction.IMPORT,
            0,
            3,
        )
        assert item.applied_at is not None
        entry = next(
            entry for entry in await ledger_of(session) if entry.target_path == outcome.target_path
        )
        assert entry.plan_item_id == item.id

    async def test_the_timeline_says_who_changed_it_from_what_to_what(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：event 說得出誰改的、從什麼改成什麼。"""
        job, _, factory = await imported(session, roots)
        row = await ova(session)

        outcome = await rematch_file(
            session,
            factory,
            job_file_id=row.id,
            to=Assignment(PlanAction.IMPORT, season=0, episode_start=3),
            actor=ACTOR,
        )

        (event,) = [e for e in await events_of(session, job.hash) if e.type == EventType.REMATCHED]
        assert event.actor == ACTOR
        payload = event.payload_json or {}
        assert payload["plan"] == outcome.plan_id
        assert payload["file"] == OVA
        assert payload["from"] == {
            "action": "unmatched",
            "season": None,
            "episode_start": None,
            "episode_end": None,
            "target": "",
        }
        assert payload["to"] == {
            "action": "import",
            "season": 0,
            "episode_start": 3,
            "episode_end": None,
            "target": outcome.target_path,
        }

    async def test_it_is_no_longer_unmatched_in_the_jobs_plan(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Job 的那一份說的是現況：Media 詳情的 Unmatched 區與佇列讀的就是那一列。"""
        _, _, factory = await imported(session, roots)
        row = await ova(session)

        await rematch_file(
            session,
            factory,
            job_file_id=row.id,
            to=Assignment(PlanAction.IMPORT, season=0, episode_start=3),
            actor=ACTOR,
        )

        mirror = next(item for item in await items_of(session) if item.job_file_id == row.id)
        assert mirror.action is PlanAction.IMPORT
        assert mirror.applied_at is not None
        assert why(ReasonCode.SET_BY_USER).model_dump(mode="json") in (mirror.reasons_json or [])
        summary = (await plan_of(session)).summary_json or {}
        assert "unmatched" not in summary["actions"]

    async def test_marking_it_extra_links_it_under_extras(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        row = await ova(session)

        outcome = await rematch_file(
            session, factory, job_file_id=row.id, to=Assignment(PlanAction.EXTRA), actor=ACTOR
        )

        relative = PurePosixPath(outcome.target_path).relative_to(route.target_path)
        assert relative.parts[1] == "extras"
        assert same_file(Path(outcome.target_path), source_of(roots, OVA))
        assert factory.jellyfin_.notified == [outcome.target_path]

    async def test_ignoring_it_links_nothing_and_takes_it_off_the_list(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)
        row = await ova(session)
        before = len(await ledger_of(session))

        outcome = await rematch_file(
            session, factory, job_file_id=row.id, to=Assignment(PlanAction.SKIP), actor=ACTOR
        )

        assert outcome.target_path == ""
        assert len(await ledger_of(session)) == before
        mirror = next(item for item in await items_of(session) if item.job_file_id == row.id)
        assert mirror.action is PlanAction.SKIP
        # 沒有東西進出媒體庫：不必叫 Jellyfin 掃。紀錄照樣留。
        assert factory.jellyfin_.notified == []
        assert len(await rematch_plans(session)) == 1
        assert EventType.REMATCHED in {e.type for e in await events_of(session, job.hash)}

    async def test_a_second_tab_finds_it_already_decided(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)
        row = await ova(session)
        await rematch_file(
            session, factory, job_file_id=row.id, to=Assignment(PlanAction.SKIP), actor=ACTOR
        )

        with pytest.raises(RematchRejectedError) as refused:
            await rematch_file(
                session, factory, job_file_id=row.id, to=Assignment(PlanAction.SKIP), actor=ACTOR
            )

        assert refused.value.reason is RematchRefusal.NOT_UNMATCHED


class TestRefusals:
    @pytest.mark.parametrize(
        ("to", "reason"),
        [
            (Assignment(PlanAction.IMPORT), RematchRefusal.EPISODE_REQUIRED),
            (Assignment(PlanAction.IMPORT, season=1), RematchRefusal.EPISODE_REQUIRED),
            (
                Assignment(PlanAction.IMPORT, season=1, episode_start=5, episode_end=4),
                RematchRefusal.EPISODE_RANGE_REVERSED,
            ),
            (Assignment(PlanAction.EXTRA, season=1), RematchRefusal.EPISODE_NOT_ALLOWED),
            (Assignment(PlanAction.SUBTITLE), RematchRefusal.ACTION_NOT_ALLOWED),
            (Assignment(PlanAction.UNMATCHED), RematchRefusal.ACTION_NOT_ALLOWED),
        ],
    )
    async def test_a_contradictory_assignment_changes_nothing(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        to: Assignment,
        reason: RematchRefusal,
    ) -> None:
        _, _, factory = await imported(session, roots)
        row = await ova(session)
        ledger = len(await ledger_of(session))

        with pytest.raises(RematchRejectedError) as refused:
            await rematch_file(session, factory, job_file_id=row.id, to=to, actor=ACTOR)

        assert refused.value.reason is reason
        assert len(await ledger_of(session)) == ledger
        assert await rematch_plans(session) == []

    async def test_an_unknown_file_or_ledger_row(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)

        with pytest.raises(RematchRejectedError) as file_missing:
            await rematch_file(
                session, factory, job_file_id=999, to=Assignment(PlanAction.SKIP), actor=ACTOR
            )
        with pytest.raises(RematchRejectedError) as ledger_missing:
            await rematch_file(
                session, factory, ledger_id=999, to=Assignment(PlanAction.SKIP), actor=ACTOR
            )

        assert file_missing.value.reason is RematchRefusal.FILE_MISSING
        assert ledger_missing.value.reason is RematchRefusal.LEDGER_MISSING

    async def test_a_file_that_is_already_linked_is_not_unmatched(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """已入庫的要帶 `ledger_id`：`job_file_id` 那條路只收對不到的。"""
        _, _, factory = await imported(session, roots)
        episode = await session.scalar(select(JobFile).where(JobFile.rel_path == BATCH_FILES[1][0]))
        assert episode is not None

        with pytest.raises(RematchRejectedError) as refused:
            await rematch_file(
                session,
                factory,
                job_file_id=episode.id,
                to=Assignment(PlanAction.SKIP),
                actor=ACTOR,
            )

        assert refused.value.reason is RematchRefusal.NOT_UNMATCHED

    async def test_a_target_another_file_holds_is_refused_before_anything_moves(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """指派到 S01E02，而那一條路徑上已經是另一個來源：Berth 不覆寫，什麼都不動。"""
        _, _, factory = await imported(session, roots)
        first = await entry_at(session, 1)
        second = await entry_at(session, 2)

        with pytest.raises(RematchRejectedError) as refused:
            await rematch_file(
                session,
                factory,
                ledger_id=first.id,
                to=Assignment(PlanAction.IMPORT, season=1, episode_start=2),
                actor=ACTOR,
            )

        assert refused.value.reason is RematchRefusal.TARGET_TAKEN
        assert same_file(Path(first.target_path), Path(first.source_abs_path))
        assert same_file(Path(second.target_path), Path(second.source_abs_path))
        assert await rematch_plans(session) == []


class TestALinkedFile:
    async def test_reassigning_it_moves_the_link_and_rewrites_its_ledger_row(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：新鏈接建起來、舊鏈接刪掉、帳本改掉、Jellyfin 收到兩條路徑。"""
        _, _, factory = await imported(session, roots)
        entry = await entry_at(session, 3)
        old = entry.target_path

        outcome = await rematch_file(
            session,
            factory,
            ledger_id=entry.id,
            to=Assignment(PlanAction.IMPORT, season=1, episode_start=5),
            actor=ACTOR,
        )

        assert not Path(old).exists()
        assert same_file(Path(outcome.target_path), Path(entry.source_abs_path))
        await session.refresh(entry)
        # 同一列帳本改寫，不是刪了再建：佇列與畫面指向的是它的 id。
        assert (entry.target_path, entry.episode_start) == (outcome.target_path, 5)
        assert sorted(factory.jellyfin_.notified) == sorted([outcome.target_path, old])

    async def test_its_subtitle_follows_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """字幕跟著影片走（brief §6.7）：S01E01 改成 S01E05，旁邊那一條字幕改名跟過去。"""
        _, _, factory = await imported(session, roots)
        video = await entry_at(session, 1)
        subtitle = await session.scalar(
            select(LedgerEntry).where(LedgerEntry.action == PlanAction.SUBTITLE)
        )
        assert subtitle is not None
        old_subtitle = subtitle.target_path

        outcome = await rematch_file(
            session,
            factory,
            ledger_id=video.id,
            to=Assignment(PlanAction.IMPORT, season=1, episode_start=5),
            actor=ACTOR,
        )

        await session.refresh(subtitle)
        new_stem = str(PurePosixPath(outcome.target_path).with_suffix(""))
        assert subtitle.target_path.startswith(f"{new_stem}.")
        assert subtitle.episode_start == 5
        assert not Path(old_subtitle).exists()
        assert same_file(Path(subtitle.target_path), Path(subtitle.source_abs_path))
        (plan,) = await rematch_plans(session)
        items = list(await session.scalars(select(PlanItem).where(PlanItem.plan_id == plan.id)))
        assert [item.action for item in items] == [PlanAction.IMPORT, PlanAction.SUBTITLE]

    async def test_marking_it_extra_takes_its_subtitle_away(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)
        video = await entry_at(session, 1)
        old = video.target_path
        subtitle = await session.scalar(
            select(LedgerEntry).where(LedgerEntry.action == PlanAction.SUBTITLE)
        )
        assert subtitle is not None
        old_subtitle = subtitle.target_path

        outcome = await rematch_file(
            session, factory, ledger_id=video.id, to=Assignment(PlanAction.EXTRA), actor=ACTOR
        )

        assert "/extras/" in outcome.target_path
        assert not Path(old).exists()
        assert not Path(old_subtitle).exists()
        await session.refresh(video)
        assert video.action is PlanAction.EXTRA
        assert video.resolve_after is None
        remaining = {entry.target_path for entry in await ledger_of(session)}
        assert old_subtitle not in remaining

    async def test_ignoring_it_unlinks_it_and_drops_its_ledger_row(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)
        entry = await entry_at(session, 3)
        old, entry_id = entry.target_path, entry.id

        outcome = await rematch_file(
            session, factory, ledger_id=entry_id, to=Assignment(PlanAction.SKIP), actor=ACTOR
        )

        assert outcome.target_path == ""
        assert not Path(old).exists()
        assert Path(entry.source_abs_path).exists()  # complete 裡的來源不動
        assert await session.get(LedgerEntry, entry_id) is None
        assert factory.jellyfin_.notified == [old]
        (event,) = [e for e in await events_of(session, job.hash) if e.type == EventType.REMATCHED]
        assert (event.payload_json or {})["from"]["target"] == old
        assert (event.payload_json or {})["to"]["action"] == "skip"


class TestTheQueue:
    """佇列的 `unmatched` 那一類（plan §6）：Job 那一份定案了的 Plan 裡對不到的檔案。"""

    async def test_an_unmatched_file_is_one_row_with_what_it_can_become(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, _ = await imported(session, roots)
        row = await ova(session)

        (found,) = [r for r in (await review_queue(session)).rows if isinstance(r, UnmatchedRow)]

        assert found.kind is ReviewKind.UNMATCHED
        assert found.job_file_id == row.id
        assert (found.job_hash, found.rel_path) == (job.hash, OVA)
        assert found.source_path == str(source_of(roots, OVA))
        assert found.media_kind is MediaKind.TV
        assert found.actions == (PlanAction.IMPORT, PlanAction.EXTRA, PlanAction.SKIP)
        assert why(ReasonCode.OWN_NUMBERED_SPECIAL) in found.reasons

    async def test_it_leaves_the_queue_once_decided(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)
        row = await ova(session)

        await rematch_file(
            session, factory, job_file_id=row.id, to=Assignment(PlanAction.SKIP), actor=ACTOR
        )

        kinds = [r.kind for r in (await review_queue(session)).rows]
        assert ReviewKind.UNMATCHED not in kinds

    async def test_a_plan_still_waiting_for_review_keeps_its_unmatched_files_to_itself(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """等審核的那一份裡，它是 Plan 編輯的一列（`plan` 那一類）——不另外算一件事。"""
        media, route, factory = await ready(session, roots, medium_auto_import=False)
        await downloaded_job(session, media, route, roots, files=((OVA, 300_000_000),))
        await sweep_plans(session, factory, EventHub(), now=NOW)
        assert (await plan_of(session)).status is PlanStatus.PENDING_REVIEW

        kinds = [r.kind for r in (await review_queue(session)).rows]

        assert kinds == [ReviewKind.PLAN]
