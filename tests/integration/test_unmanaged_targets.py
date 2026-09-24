"""會拆掉媒體庫鏈接的三條路，刪之前先認一次那個檔案（M3 票 01、plan §11.4）。

三條路是刪除範圍的「移除鏈接」、audit 撤銷、rematch 拆舊鏈接。使用者把 Berth 的硬鏈接換成
自己的檔案之後（一份複製品、一個重新壓制的版本），那條路徑上的已經是 **Unmanaged**
（CONTEXT.md）——Berth 只刪得掉自己放下去的那一個。三條路之前都照路徑刪，會把它刪掉。

判斷只有一份（`deletion.Placed.holds`）：帳本記的 inode，或來源現在的 inode，兩者都對不上就
不是 Berth 放的。`TestOneJudgement` 把它換成「一律是」，三條路一起變回照路徑刪——證明三條都
走它，而不是各自一份（票上那一條驗收）。

「inode 相同時照常刪」各有既有的測試守著：`test_deletion.py` 的
`test_unlink_removes_the_library_links_and_nothing_else`、`test_review.py` 的
`test_the_hard_link_is_gone_and_the_source_stays`、`test_rematch.py` 的
`test_reassigning_it_moves_the_link_and_rewrites_its_ledger_row`。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import EventType, JobState, LedgerStatus, PlanAction
from berth.services import deletion
from berth.services.deletion import DeleteScope, delete_job
from berth.services.rematch import Assignment, rematch_file
from berth.services.review import undo_audit
from tests.integration.test_deletion import deleted_event, imported
from tests.integration.test_importer import ledger_of, same_file, state_of
from tests.integration.test_plan import events_of
from tests.integration.test_rematch import entry_at
from tests.integration.test_rematch import imported as imported_batch
from tests.integration.test_review import ACTOR, audited

pytestmark = pytest.mark.asyncio

#: 使用者自己的那一份。內容與 Berth 鏈接的不同，所以「原封不動」讀得出來。
OWN = b"the user's own re-encode"


def swap_for_own_file(target: Path) -> None:
    """使用者把硬鏈接換成自己的檔案：同一條路徑，另一個 inode。"""
    target.unlink()
    target.write_bytes(OWN)


@dataclass(frozen=True, slots=True)
class Pressed:
    """按下去之後：那條路徑，以及回應與時間線有沒有說出「那不是 Berth 放的」。"""

    path: Path
    response_says: bool
    timeline_says: bool


async def by_deleting(session: AsyncSession, roots: dict[str, Path]) -> Pressed:
    job, _, factory = await imported(session, roots)
    # 回應與時間線說的是**帳本記的那一串字**（容器裡的 POSIX 路徑），不是這台機器的 `Path`。
    target = (await ledger_of(session))[0].target_path
    swap_for_own_file(Path(target))

    outcome = await delete_job(session, factory, job.hash, DeleteScope(unlink=True), actor="user")

    payload = (await deleted_event(session)).payload_json or {}
    return Pressed(
        path=Path(target),
        response_says=outcome.unmanaged == (target,),
        timeline_says=payload.get("unmanaged") == [target],
    )


async def by_undoing(session: AsyncSession, roots: dict[str, Path]) -> Pressed:
    _, entry = await audited(session, roots)
    path = Path(entry.target_path)
    swap_for_own_file(path)

    outcome = await undo_audit(session, entry.id, actor=ACTOR)

    (event,) = [row for row in await events_of(session) if row.type == EventType.AUDIT_UNDONE]
    payload = event.payload_json or {}
    return Pressed(
        path=path,
        response_says=outcome.unmanaged and not outcome.unlinked,
        timeline_says=payload.get("unmanaged") is True and payload.get("unlinked") is False,
    )


async def by_rematching(session: AsyncSession, roots: dict[str, Path]) -> Pressed:
    job, _, factory = await imported_batch(session, roots)
    entry = await entry_at(session, 3)
    target = entry.target_path
    swap_for_own_file(Path(target))

    outcome = await rematch_file(
        session,
        factory,
        ledger_id=entry.id,
        to=Assignment(PlanAction.IMPORT, season=1, episode_start=5),
        actor=ACTOR,
    )

    (event,) = [e for e in await events_of(session, job.hash) if e.type == EventType.REMATCHED]
    return Pressed(
        path=Path(target),
        response_says=outcome.unmanaged == (target,),
        timeline_says=(event.payload_json or {}).get("unmanaged") == [target],
    )


Press = Callable[[AsyncSession, dict[str, Path]], Awaitable[Pressed]]
PATHS = pytest.mark.parametrize("press", [by_deleting, by_undoing, by_rematching])


class TestTheUsersOwnFileIsLeftAlone:
    @PATHS
    async def test_it_is_not_deleted_and_not_touched(
        self, session: AsyncSession, roots: dict[str, Path], press: Press
    ) -> None:
        pressed = await press(session, roots)

        assert pressed.path.read_bytes() == OWN

    @PATHS
    async def test_the_response_and_the_timeline_say_it_was_not_berths(
        self, session: AsyncSession, roots: dict[str, Path], press: Press
    ) -> None:
        pressed = await press(session, roots)

        assert pressed.response_says
        assert pressed.timeline_says


class TestOneJudgement:
    """三條路走同一個判斷：把它換成「一律是 Berth 放的」，三條都回到照路徑刪。"""

    @PATHS
    async def test_without_it_every_path_deletes_the_users_file(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        press: Press,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(deletion.Placed, "holds", lambda self, facts: True)

        pressed = await press(session, roots)

        assert not pressed.path.exists()


class TestWhatEachPathStillDoes:
    """認出來不是 Berth 的之後，其餘照常：只是那一個檔案不刪。"""

    async def test_deleting_removes_the_other_links_and_leaves_the_row_to_the_reconciler(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)
        first, *others = await ledger_of(session)
        swap_for_own_file(Path(first.target_path))

        outcome = await delete_job(
            session, factory, job.hash, DeleteScope(unlink=True), actor="user"
        )

        assert outcome.links == len(others)
        assert not any(Path(row.target_path).exists() for row in others)
        # 那一列說的不是「使用者拆掉了」：目標還在，現況交給下一輪對帳（`inode_mismatch`）。
        await session.refresh(first)
        assert first.status is LedgerStatus.OK

    async def test_undoing_still_sends_the_job_back_to_review(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """撤銷說的是「這一個入庫是錯的」：帳本那一列與 Job 照樣處理，只是檔案不是 Berth 的。"""
        job, entry = await audited(session, roots)
        swap_for_own_file(Path(entry.target_path))

        await undo_audit(session, entry.id, actor=ACTOR)

        assert await ledger_of(session) == []
        assert await state_of(session, job) is JobState.REVIEW

    async def test_rematching_still_links_the_new_place(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported_batch(session, roots)
        entry = await entry_at(session, 3)
        old = entry.target_path
        swap_for_own_file(Path(old))

        outcome = await rematch_file(
            session,
            factory,
            ledger_id=entry.id,
            to=Assignment(PlanAction.IMPORT, season=1, episode_start=5),
            actor=ACTOR,
        )

        assert same_file(Path(outcome.target_path), Path(entry.source_abs_path))
        # 舊路徑上沒有東西被拆，Jellyfin 那邊不必為它重讀。
        assert factory.jellyfin_.notified == [outcome.target_path]
