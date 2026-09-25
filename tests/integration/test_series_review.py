"""RSS Series 的季號與 offset：第一批審核、套用到整個 Series、確認後不再 audit（M3 票 13）。

起點同 `test_rss.py`：票 07 錄下來的 Mikan 聚合 feed，《与你相恋》喵萌奶茶屋&LoliHouse 的
11、12 兩集一路走到帳本。**split-cour** 用另一份快照：TMDB 把兩個 cour 併成一季 24 集，
字幕組的第二 cour 從 01 重數——feed 上的 11、12 其實是 S01E23、S01E24，而解析器只看得到
「只有集號、TMDB 一季、那一集存在」，照字面落在 S01E11、S01E12（medium，錯的）。
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.rss.fake import FakeFeedFetcher
from berth.domain import (
    AuditReason,
    EpisodeSnapshot,
    JobState,
    MediaSnapshot,
    PlanAction,
    PlanStatus,
    RematchRefusal,
)
from berth.models import Job, LedgerEntry, Plan, PlanItem, RssSeries
from berth.services.events import EventHub
from berth.services.importer import sweep_imports
from berth.services.plan_review import ItemEdit, edit_items
from berth.services.rematch import Assignment, RematchRejectedError
from berth.services.review import AuditRow, review_queue, undo_audit
from berth.services.rss import add_feed, bind_series, poll_feed
from berth.services.series_review import confirm_series, correct_series
from tests.integration.arrange import arrange, factory_for
from tests.integration.factories import FakeClientFactory
from tests.integration.test_rss import (
    FEED,
    FEED_URL,
    KIMI_KEY,
    NOW,
    anime_route,
    episode_pages,
    kimi,
    kimi_snapshot,
    run_pipeline,
    series_by_key,
    torrents,
)

pytestmark = pytest.mark.asyncio

ACTOR = "1"


def split_cour() -> MediaSnapshot:
    """TMDB 併成一季的 split-cour：第一 cour 1–12（一月起）、第二 cour 13–24（七月起）。"""
    first, second = date(2026, 1, 8), date(2026, 7, 2)
    episodes = tuple(
        EpisodeSnapshot(
            episode_number=number,
            name=f"Episode {number}",
            air_date=(first + timedelta(days=7 * (number - 1)))
            if number <= 12
            else (second + timedelta(days=7 * (number - 13))),
        )
        for number in range(1, 25)
    )
    season = (
        kimi_snapshot()
        .seasons[0]
        .model_copy(update={"episode_count": 24, "air_date": first, "episodes": episodes})
    )
    return kimi_snapshot().model_copy(update={"first_air_date": first, "seasons": (season,)})


async def delivered(
    session: AsyncSession,
    roots: dict[str, Path],
    *,
    snapshot: MediaSnapshot | None = None,
    season: int | None = None,
    offset: int | None = None,
    confirmed: bool = False,
) -> tuple[RssSeries, FakeClientFactory]:
    """feed 輪一次 → 綁定 → 兩集下載完、規劃、入庫。Series 的值在綁定之前設好。"""
    await arrange(session, roots)
    media = await kimi(session, snapshot=snapshot)
    route = await anime_route(session, roots)
    factory = factory_for(roots)
    factory.rss_ = FakeFeedFetcher({FEED_URL: FEED, **episode_pages()})
    factory.torrent_ = torrents()
    feed = await add_feed(session, url=FEED_URL, name="Mikan")
    await poll_feed(session, factory, feed.id, now=NOW)
    series = await series_by_key(session, KIMI_KEY)
    series.season = season
    series.episode_offset = offset
    series.confirmed = confirmed
    await session.commit()
    await bind_series(session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1)
    await run_pipeline(session, factory, roots)
    return series, factory


async def ledger(session: AsyncSession) -> list[LedgerEntry]:
    rows = await session.scalars(
        select(LedgerEntry)
        .where(LedgerEntry.action == PlanAction.IMPORT)
        .order_by(LedgerEntry.source_rel_path)
    )
    return list(rows)


async def audits(session: AsyncSession) -> list[AuditRow]:
    queue = await review_queue(session)
    return [row for row in queue.rows if isinstance(row, AuditRow)]


class TestThePlanRemembers:
    async def test_each_plan_records_the_season_and_offset_it_used(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, _ = await delivered(session, roots, snapshot=split_cour(), season=1, offset=12)

        plans = list(await session.scalars(select(Plan).where(Plan.job_hash.is_not(None))))
        assert len(plans) == 2
        assert {(p.rss_series_id, p.season_hint, p.episode_offset) for p in plans} == {
            (series.id, 1, 12)
        }
        assert sorted((row.season, row.episode_start) for row in await ledger(session)) == [
            (1, 23),
            (1, 24),
        ]

    async def test_a_series_without_values_records_that_it_had_none(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, _ = await delivered(session, roots)

        plans = list(await session.scalars(select(Plan).where(Plan.job_hash.is_not(None))))
        assert {(p.rss_series_id, p.season_hint, p.episode_offset) for p in plans} == {
            (series.id, None, None)
        }


class TestTheFirstBatch:
    async def test_it_waits_for_a_look_even_when_high(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Series 帶了季號時解析器給 high；第一批照樣進 audit，理由說的是第一批而不是 medium。"""
        series, _ = await delivered(session, roots, season=1)

        items = list(await session.scalars(select(PlanItem).where(PlanItem.action == "import")))
        assert {item.confidence.value for item in items} == {"high"}
        rows = await audits(session)
        assert len(rows) == 2
        assert {(row.series.id if row.series else None) for row in rows} == {series.id}
        assert {row.reason for row in rows} == {AuditReason.FIRST_BATCH}

    async def test_confirming_the_series_confirms_its_rows_and_the_series(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, _ = await delivered(session, roots)
        ids = [row.ledger_id for row in await audits(session)]

        outcome = await confirm_series(session, series.id, ids, actor=ACTOR)

        assert (outcome.confirmed, outcome.skipped) == (2, 0)
        await session.refresh(series)
        assert series.confirmed is True
        assert await audits(session) == []
        assert {row.audit for row in await ledger(session)} == {False}

    async def test_nothing_confirmed_leaves_the_series_unconfirmed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """送來的列都已被別處撤銷：沒有人看過任何一集，Series 不算確認過。"""
        series, _ = await delivered(session, roots)
        ids = [row.ledger_id for row in await audits(session)]
        for ledger_id in ids:
            await undo_audit(session, ledger_id, actor=ACTOR)

        outcome = await confirm_series(session, series.id, ids, actor=ACTOR)

        assert (outcome.confirmed, outcome.skipped) == (0, 2)
        await session.refresh(series)
        assert series.confirmed is False

    async def test_only_the_rows_on_screen_are_confirmed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """同票 05 的整段確認：送來的 id 才算，按下前一刻才進來的留著等人。"""
        series, _ = await delivered(session, roots)
        first, second = await audits(session)

        await confirm_series(session, series.id, [first.ledger_id], actor=ACTOR)

        assert [row.ledger_id for row in await audits(session)] == [second.ledger_id]


class TestAfterConfirmation:
    """已確認的 Series 的 medium 入庫不進 audit 清單；未確認的照舊進（雙向，M3 驗收最後一條）。"""

    async def test_a_confirmed_series_imports_medium_without_audit(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await delivered(session, roots, confirmed=True)

        items = list(await session.scalars(select(PlanItem).where(PlanItem.action == "import")))
        assert {item.confidence.value for item in items} == {"medium"}
        assert {row.audit for row in await ledger(session)} == {False}
        assert await audits(session) == []

    async def test_an_unconfirmed_series_still_audits_medium(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await delivered(session, roots, confirmed=False)

        items = list(await session.scalars(select(PlanItem).where(PlanItem.action == "import")))
        assert {item.confidence.value for item in items} == {"medium"}
        assert {row.audit for row in await ledger(session)} == {True}
        assert len(await audits(session)) == 2


class TestApplyingToTheSeries:
    """split-cour：第一批換算錯 → 改一集並套用到 Series → 其餘未確認的跟著對，鏈接搬到正確路徑。"""

    async def test_one_correction_fixes_the_rest(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, factory = await delivered(session, roots, snapshot=split_cour())
        eleven, twelve = await ledger(session)
        assert [(row.season, row.episode_start) for row in (eleven, twelve)] == [(1, 11), (1, 12)]
        old_paths = [Path(row.target_path) for row in (eleven, twelve)]

        outcome = await correct_series(
            session,
            factory,
            EventHub(),
            eleven.id,
            to=Assignment(action=PlanAction.IMPORT, season=1, episode_start=23),
            actor=ACTOR,
        )

        await session.refresh(series)
        assert (series.season, series.episode_offset) == (1, 12)
        assert (outcome.season, outcome.episode_offset, outcome.moved) == (1, 12, 1)
        rows = await ledger(session)
        assert [(row.season, row.episode_start) for row in rows] == [(1, 23), (1, 24)]
        assert all(Path(row.target_path).exists() for row in rows)
        assert not any(path.exists() for path in old_paths)
        # 人改的那一集是人決定的；跟著重算的那一集還沒有人看過，留在第一批裡等「全部確認」。
        assert [row.audit for row in rows] == [False, True]
        assert series.confirmed is False

    async def test_a_held_job_of_the_series_is_planned_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """撤銷過、停在 review 的那一筆走重新規劃：讀到新的值，照常入庫。"""
        _, factory = await delivered(session, roots, snapshot=split_cour())
        eleven, twelve = await ledger(session)
        await undo_audit(session, twelve.id, actor=ACTOR)
        held = await session.get(Job, twelve.job_hash)
        assert held is not None
        assert held.state is JobState.REVIEW

        outcome = await correct_series(
            session,
            factory,
            EventHub(),
            eleven.id,
            to=Assignment(action=PlanAction.IMPORT, season=1, episode_start=23),
            actor=ACTOR,
        )

        assert outcome.replanned == 1
        await session.refresh(held)
        plan = await session.scalar(select(Plan).where(Plan.job_hash == held.hash))
        assert plan is not None
        assert (plan.status, plan.season_hint, plan.episode_offset) == (PlanStatus.AUTO, 1, 12)
        await sweep_imports(session, factory, EventHub(), now=NOW)
        rows = await ledger(session)
        assert sorted((row.season, row.episode_start) for row in rows) == [(1, 23), (1, 24)]

    async def test_a_held_plan_a_person_edited_is_not_planned_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """停在 review、管理員逐列改過的那一份（`engine = user`）是人的決定：
        重新規劃會把它整份換掉，所以不動它。"""
        _, factory = await delivered(session, roots, snapshot=split_cour())
        eleven, twelve = await ledger(session)
        await undo_audit(session, twelve.id, actor=ACTOR)
        plan = await session.scalar(select(Plan).where(Plan.job_hash == twelve.job_hash))
        assert plan is not None
        row = await session.scalar(
            select(PlanItem).where(PlanItem.plan_id == plan.id, PlanItem.action == "review")
        )
        assert row is not None
        await edit_items(
            session,
            plan.id,
            [ItemEdit(id=row.id, action=PlanAction.IMPORT, season=1, episode_start=20)],
            actor=ACTOR,
        )

        outcome = await correct_series(
            session,
            factory,
            EventHub(),
            eleven.id,
            to=Assignment(action=PlanAction.IMPORT, season=1, episode_start=23),
            actor=ACTOR,
        )

        assert outcome.replanned == 0
        edited = await session.get(PlanItem, row.id, populate_existing=True)
        assert edited is not None
        assert (edited.season, edited.episode_start) == (1, 20)

    async def test_confirmed_rows_are_left_alone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「還沒確認的集數」才重算：確認過的那一集是人說對的。"""
        series, factory = await delivered(session, roots, snapshot=split_cour())
        eleven, twelve = await ledger(session)
        await confirm_series(session, series.id, [twelve.id], actor=ACTOR)

        outcome = await correct_series(
            session,
            factory,
            EventHub(),
            eleven.id,
            to=Assignment(action=PlanAction.IMPORT, season=1, episode_start=23),
            actor=ACTOR,
        )

        assert outcome.moved == 0
        rows = await ledger(session)
        assert [(row.season, row.episode_start) for row in rows] == [(1, 23), (1, 12)]

    async def test_a_slot_held_by_a_sibling_that_also_moves_is_waited_for(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """offset 小於這一批的集數時，人要的那一格正被同一批的另一集佔著（01–12 放錯、正解 07–18，
        改第 1 集 → E07 時 E07 上是還沒搬的第 7 集）。它也要搬走，所以等它先走，不是拒絕。"""
        series, factory = await delivered(session, roots, snapshot=split_cour())
        eleven, _ = await ledger(session)

        outcome = await correct_series(
            session,
            factory,
            EventHub(),
            eleven.id,
            to=Assignment(action=PlanAction.IMPORT, season=1, episode_start=12),
            actor=ACTOR,
        )

        assert (outcome.episode_offset, outcome.moved, outcome.left) == (1, 1, 0)
        assert outcome.rematched is not None
        rows = await ledger(session)
        assert [(row.season, row.episode_start) for row in rows] == [(1, 12), (1, 13)]
        assert all(Path(row.target_path).exists() for row in rows)
        await session.refresh(series)
        assert series.episode_offset == 1

    async def test_a_slot_held_by_a_confirmed_episode_is_refused_before_anything(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """擋路的是確認過的那一集：它不會搬，人說的與它互相矛盾——什麼都不動，交給人。"""
        series, factory = await delivered(session, roots, snapshot=split_cour())
        eleven, twelve = await ledger(session)
        await confirm_series(session, series.id, [twelve.id], actor=ACTOR)

        with pytest.raises(RematchRejectedError) as refused:
            await correct_series(
                session,
                factory,
                EventHub(),
                eleven.id,
                to=Assignment(action=PlanAction.IMPORT, season=1, episode_start=12),
                actor=ACTOR,
            )

        assert refused.value.reason is RematchRefusal.TARGET_TAKEN
        await session.refresh(series)
        assert (series.season, series.episode_offset) == (None, None)
        rows = await ledger(session)
        assert [(row.season, row.episode_start) for row in rows] == [(1, 11), (1, 12)]

    async def test_a_file_not_sent_by_a_series_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, factory = await delivered(session, roots, snapshot=split_cour())
        eleven, _ = await ledger(session)
        job = await session.get(Job, eleven.job_hash)
        assert job is not None
        job.trigger_ref = "0"
        await session.commit()

        with pytest.raises(RematchRejectedError) as refused:
            await correct_series(
                session,
                factory,
                EventHub(),
                eleven.id,
                to=Assignment(action=PlanAction.IMPORT, season=1, episode_start=23),
                actor=ACTOR,
            )

        assert refused.value.reason is RematchRefusal.NOT_FROM_SERIES
        await session.refresh(series)
        assert (series.season, series.episode_offset) == (None, None)
