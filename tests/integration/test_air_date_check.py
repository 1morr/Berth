"""播出日比對走到 `/review`（M3 票 14、plan §11.4 的「三道程式檢查」①、M3 驗收第六條）。

起點同 `test_rss.py`：票 07 錄下來的 Mikan 聚合 feed，《与你相恋》喵萌奶茶屋&LoliHouse 的
11、12 兩集（發佈於 2026-09-23、09-24）。快照換成三種播出日：

- `kimi_snapshot()`：七月開播、每週一集，11、12 在 09-10、09-17 播出——對得上，照常入庫；
- 還沒播到：同一部晚兩個月開播，發佈早於換算出的那一集的播出日（規則一）；
- 連載中的 split-cour：TMDB 併成一季，第二 cour 正在播，字幕組從 01 重數而 offset 沒設（規則二）。

手動送單走同一個 torrent，只是發佈時間來自索引站的 `publishDate`（`JobSource.published_at`）。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.rss.fake import FakeFeedFetcher
from berth.domain import (
    EpisodeSnapshot,
    EventType,
    JobState,
    JobTrigger,
    MediaSnapshot,
    PlanAction,
    ReasonCode,
    ReviewReason,
    why,
)
from berth.models import Event, Job, LedgerEntry, PlanItem
from berth.services.jobs import JobSource, add_download
from berth.services.review import PlanRow, review_queue
from berth.services.rss import add_feed, bind_series, poll_feed
from tests.integration.arrange import arrange, factory_for
from tests.integration.test_rss import (
    FEED,
    FEED_URL,
    KIMI,
    KIMI_KEY,
    NOW,
    anime_route,
    episode_pages,
    harbour,
    kimi,
    kimi_snapshot,
    run_pipeline,
    series_by_key,
    torrents,
)

pytestmark = pytest.mark.asyncio


def aired_from(first: date, *, episodes: int = 12) -> MediaSnapshot:
    """同一部作品，第一集改在 `first` 播、每週一集。"""
    season = kimi_snapshot().seasons[0]
    return kimi_snapshot().model_copy(
        update={
            "first_air_date": first,
            "seasons": (
                season.model_copy(
                    update={
                        "air_date": first,
                        "episode_count": episodes,
                        "episodes": tuple(
                            EpisodeSnapshot(
                                episode_number=number,
                                name=f"Episode {number}",
                                air_date=first + timedelta(days=7 * (number - 1)),
                            )
                            for number in range(1, episodes + 1)
                        ),
                    }
                ),
            ),
        }
    )


def airing_split_cour() -> MediaSnapshot:
    """TMDB 併成一季 24 集；第二 cour 七月開播、feed 發佈時正在播第 12 集（S01E24 在 09-17）。"""
    first, second = date(2026, 1, 8), date(2026, 7, 2)
    season = kimi_snapshot().seasons[0]
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
    return kimi_snapshot().model_copy(
        update={
            "first_air_date": first,
            "seasons": (
                season.model_copy(
                    update={"air_date": first, "episode_count": 24, "episodes": episodes}
                ),
            ),
        }
    )


async def delivered_by_rss(
    session: AsyncSession, roots: dict[str, Path], snapshot: MediaSnapshot
) -> None:
    """feed 輪一次 → 綁定（第一季、確認過，排除第一批的 audit）→ 兩集下載完、規劃、入庫。"""
    await arrange(session, roots)
    media = await kimi(session, snapshot=snapshot)
    route = await anime_route(session, roots)
    factory = factory_for(roots)
    factory.rss_ = FakeFeedFetcher({FEED_URL: FEED, **episode_pages()})
    factory.torrent_ = torrents()
    feed = await add_feed(session, url=FEED_URL, name="Mikan")
    await poll_feed(session, factory, feed.id, now=NOW)
    series = await series_by_key(session, KIMI_KEY)
    series.season = 1
    series.confirmed = True
    await session.commit()
    await bind_series(session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1)
    await run_pipeline(session, factory, roots)


async def jobs(session: AsyncSession) -> list[Job]:
    return list(await session.scalars(select(Job).order_by(Job.name)))


async def held_reasons(session: AsyncSession) -> list[list[dict[str, object]]]:
    rows = await session.scalars(
        select(PlanItem).where(PlanItem.action == PlanAction.REVIEW).order_by(PlanItem.rel_path)
    )
    return [list(row.reasons_json or []) for row in rows]


def published(episode: int) -> datetime:
    """feed 上那一集的發佈時間（UTC）。"""
    found = next(item for item in KIMI if f" - {episode:02d} " in item.title)
    assert found.published_at is not None
    return found.published_at


class TestRss:
    async def test_a_matching_air_date_imports_as_usual(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await delivered_by_rss(session, roots, kimi_snapshot())

        assert {job.state for job in await jobs(session)} == {JobState.IMPORTED}
        assert await held_reasons(session) == []
        # 發佈時間跟著 Job 存下來了：是 Feed Item 的那一個，不是送單的時刻。
        assert {job.published_at for job in await jobs(session)} == {published(11), published(12)}

    async def test_a_release_before_the_air_date_waits_in_review_with_both_dates(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """晚兩個月開播的話，11、12 要到十一月才播：九月的發佈不可能是它們（規則一）。"""
        snapshot = aired_from(date(2026, 9, 3))
        await delivered_by_rss(session, roots, snapshot)

        assert {job.state for job in await jobs(session)} == {JobState.REVIEW}
        assert await session.scalar(select(LedgerEntry.id)) is None
        eleven = snapshot.seasons[0].episodes[10].air_date
        assert eleven is not None
        assert (
            why(
                ReasonCode.RELEASED_BEFORE_AIRING,
                published=published(11).date().isoformat(),
                episode="S01E11",
                aired=eleven.isoformat(),
            ).model_dump(mode="json")
            in (await held_reasons(session))[0]
        )

        queue = await review_queue(session)
        plans = [row for row in queue.rows if isinstance(row, PlanRow)]
        assert {row.reason for row in plans} == {ReviewReason.AIR_DATE_CONFLICT}
        events = await session.scalars(
            select(Event).where(Event.type == EventType.REVIEW_REQUIRED.value)
        )
        assert {(event.payload_json or {})["reason"] for event in events} == {"air_date_conflict"}

    async def test_a_split_cour_restart_on_an_airing_series_waits_in_review(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """第二 cour 正在播，字幕組的 11、12 其實是 S01E23、E24。

        offset 沒設就對到三月的 S01E11（規則二）。
        """
        await delivered_by_rss(session, roots, airing_split_cour())

        assert {job.state for job in await jobs(session)} == {JobState.REVIEW}
        first = (await held_reasons(session))[0][-1]
        assert first == why(
            ReasonCode.BEHIND_LATEST_EPISODE,
            episode="S01E11",
            aired="2026-03-19",
            latest="S01E24",
            latest_aired="2026-09-17",
        ).model_dump(mode="json")


async def submit_manually(
    session: AsyncSession,
    roots: dict[str, Path],
    snapshot: MediaSnapshot,
    published_at: datetime | None,
) -> Job:
    """詳情頁手動送 12 那一集，發佈時間來自索引站。之後下載完、規劃、入庫。"""
    media, route, factory = await harbour(session, roots)
    row = await session.get(type(media), media.id)
    assert row is not None
    row.tmdb_snapshot_json = snapshot.model_dump(mode="json")
    await session.commit()
    item = next(item for item in KIMI if " - 12 " in item.title)
    outcome = await add_download(
        session,
        factory,
        source=JobSource(
            url=item.torrent_url,
            title=item.title,
            info_hash=item.info_hash,
            published_at=published_at,
        ),
        media_id=media.id,
        route_id=route.id,
        user_id=None,
    )
    await run_pipeline(session, factory, roots)
    job = await session.get(Job, outcome.job.hash)
    assert job is not None
    await session.refresh(job)
    assert job.trigger is JobTrigger.MANUAL
    return job


class TestManual:
    async def test_a_publish_date_before_the_air_date_waits_in_review(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job = await submit_manually(session, roots, aired_from(date(2026, 9, 3)), published(12))

        assert job.state is JobState.REVIEW
        assert job.published_at == published(12)
        [reasons] = await held_reasons(session)
        assert reasons[-1]["code"] == ReasonCode.RELEASED_BEFORE_AIRING.value

    async def test_a_matching_publish_date_imports(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job = await submit_manually(session, roots, kimi_snapshot(), published(12))

        assert job.state is JobState.IMPORTED

    async def test_no_publish_date_does_not_hold_it_and_says_so(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """索引站沒給的，跳過並記一筆——就算換算出的那一集還沒播，也沒有證據說它錯。"""
        job = await submit_manually(session, roots, aired_from(date(2026, 9, 3)), None)

        assert job.state is JobState.IMPORTED
        item = await session.scalar(select(PlanItem).where(PlanItem.action == PlanAction.IMPORT))
        assert item is not None
        assert why(ReasonCode.PUBLISHED_MISSING).model_dump(mode="json") in (
            item.reasons_json or []
        )

    async def test_rule_two_is_only_for_rss(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """手動搜的常常本來就是舊集：對到三月的 S01E12 也照常入庫。"""
        job = await submit_manually(session, roots, airing_split_cour(), published(12))

        assert job.state is JobState.IMPORTED
