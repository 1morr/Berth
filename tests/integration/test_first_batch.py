"""第一批證據夠強時系統確認 RSS Series（M4 票 11、`services.first_batch`）。

起點同 `test_series_review.py`：《与你相恋》喵萌奶茶屋&LoliHouse 的 11、12 兩集從 Mikan 聚合 feed
一路走到帳本。預設的快照上兩集都在發佈前一兩天播出、只寫集號、單季——證據夠強，Series 由系統確認、
沒有一列掛 audit。其餘每一條測試拿掉一樣證據，整批照舊等人。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.rss.mikan import parse_feed
from berth.domain import EventType, FirstBatchBasis, JobState, MediaSnapshot, ReasonCode
from berth.models import Event, Job, PlanItem, RssSeries
from berth.services.downloads import poll_downloads
from berth.services.events import EventHub
from berth.services.first_batch import Span, asks
from berth.services.hints import JobHints
from berth.services.importer import sweep_imports
from berth.services.plan import sweep_plans
from tests.integration import test_rss, test_series_review
from tests.integration.factories import FakeClientFactory
from tests.integration.test_air_date_check import airing_split_cour
from tests.integration.test_rss import FEED, NOW, finish_downloads, kimi_snapshot
from tests.integration.test_series_review import audits, delivered, ledger, split_cour, undated

pytestmark = pytest.mark.asyncio


def one_undated(episode: int) -> MediaSnapshot:
    """只有第 `episode` 集 TMDB 還沒填播出日。"""
    season = kimi_snapshot().seasons[0]
    episodes = tuple(
        row.model_copy(update={"air_date": None}) if row.episode_number == episode else row
        for row in season.episodes
    )
    return kimi_snapshot().model_copy(
        update={"seasons": (season.model_copy(update={"episodes": episodes}),)}
    )


async def confirmed(session: AsyncSession, series_id: int) -> bool | None:
    """Series 現在確認了沒（每次都重問資料庫，同一個物件前後兩次的值型別檢查器會當成不變）。"""
    row = await session.get(RssSeries, series_id, populate_existing=True)
    return row.confirmed if row is not None else None


async def confirmations(session: AsyncSession) -> list[Event]:
    return list(
        await session.scalars(
            select(Event).where(Event.type == EventType.SERIES_CONFIRMED.value).order_by(Event.id)
        )
    )


class TestSureFirstBatch:
    async def test_the_series_is_confirmed_and_nothing_waits(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, _ = await delivered(session, roots)

        await session.refresh(series)
        assert series.confirmed is True
        assert await audits(session) == []
        assert {row.audit for row in await ledger(session)} == {False}

    async def test_every_job_of_the_batch_says_why(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """兩集同一輪規劃：先算的那一份看到另一筆還沒落地，照舊掛 audit；後算的那一份落地時整批
        一起擔保、清掉前一份的旗標。兩筆的時間線都記下依據。"""
        series, _ = await delivered(session, roots)

        events = await confirmations(session)
        jobs = await session.scalars(select(Job.hash).where(Job.trigger_ref == str(series.id)))
        assert {event.job_hash for event in events} == set(jobs)
        assert {event.actor for event in events} == {"system"}
        assert events[0].payload_json == {
            "series": series.id,
            "name": series.title_raw,
            "episodes": ["S01E11", "S01E12"],
        }


def aired_on(snapshot: MediaSnapshot, season: int, days: dict[int, date]) -> MediaSnapshot:
    """`snapshot` 的第 `season` 季裡，`days` 列出的集改成那一天播。"""
    seasons = tuple(
        row.model_copy(
            update={
                "episodes": tuple(
                    ep.model_copy(update={"air_date": days.get(ep.episode_number, ep.air_date)})
                    for ep in row.episodes
                )
            }
        )
        if row.season_number == season
        else row
        for row in snapshot.seasons
    )
    return snapshot.model_copy(update={"seasons": seasons})


def two_seasons() -> MediaSnapshot:
    """TMDB 上有兩季、各 12 集：第一季去年播完；第二季第 11 集在發佈（09-22）前一天播，第 12 集
    在發佈（09-24）後一天播（有換算的列容忍兩天），所以第 11 集發佈時下一集還沒播。"""
    shot = kimi_snapshot()
    (first,) = shot.seasons
    last_year = tuple(
        ep.model_copy(update={"air_date": ep.air_date - timedelta(days=364)})
        for ep in first.episodes
        if ep.air_date is not None
    )
    previous = first.model_copy(update={"episodes": last_year, "air_date": last_year[0].air_date})
    current = first.model_copy(
        update={"season_number": 2, "name": "Season 2", "names": ("Season 2",)}
    )
    shot = shot.model_copy(update={"seasons": (previous, current)})
    return aired_on(shot, 2, {11: date(2026, 9, 21), 12: date(2026, 9, 25)})


@pytest.fixture
def cumulative_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    """同一個 feed，喵萌奶茶屋那兩集改寫成季號寫明的累計編號（S2 - 23、S2 - 24），檔名也是。"""
    feed = FEED
    for episode in (11, 12):
        feed = feed.replace(
            f"Koi wo Shitai - {episode} ".encode(), f"Koi wo Shitai S2 - {episode + 12} ".encode()
        )
    items = parse_feed(feed)
    assert sum(" S2 - " in item.title for item in items) == 2

    def release_file(item_title: str) -> str:
        episode = item_title.split(" - ")[1].split(" ")[0]
        return f"[LoliHouse] Kimi ga Shinu made Koi wo Shitai S2 - {episode} [1080p].mkv"

    monkeypatch.setattr(test_rss, "ITEMS", items)
    monkeypatch.setattr(test_rss, "release_file", release_file)
    monkeypatch.setattr(test_series_review, "FEED", feed)


class TestSimulcastAndCumulativeReadingsConfirm:
    """M5.5 加的兩種讀法經 services 走到 Series 確認（票 04、05、05b）。

    解析器層的條件逐條在 `tests/unit/test_parser_first_batch.py`；這裡守的是規劃、入庫到確認的接線。
    """

    async def test_a_literal_row_ahead_of_airing_is_confirmed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """地上波先行：兩集都比 TMDB 的播出日早 7 天發，照字面、在 9 天內，Series 由系統確認。"""
        early = aired_on(kimi_snapshot(), 1, {11: date(2026, 9, 29), 12: date(2026, 10, 1)})
        series, _ = await delivered(session, roots, snapshot=early)

        await session.refresh(series)
        assert series.confirmed is True
        assert await audits(session) == []
        reasons = {
            reason["code"]
            for row in await session.scalars(select(PlanItem.reasons_json))
            for reason in row or []
        }
        assert ReasonCode.RELEASED_AHEAD_OF_AIRING.value in reasons

    @pytest.mark.usefixtures("cumulative_feed")
    async def test_a_written_season_counted_from_the_first_is_confirmed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """累計編號：S2 - 23、24 是前面 12 集加 S02E11、E12，剛播、下一集發佈時還沒播。"""
        series, _ = await delivered(session, roots, snapshot=two_seasons())

        await session.refresh(series)
        assert series.confirmed is True
        assert await audits(session) == []
        (event, *_) = await confirmations(session)
        assert (event.payload_json or {}).get("episodes") == ["S02E11", "S02E12"]

    @pytest.mark.usefixtures("cumulative_feed")
    async def test_a_cumulative_batch_whose_next_episode_already_aired_waits(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """對照組（票 05b）：第 11 集的下一集在它發佈前就播了，整批等人。"""
        aired = aired_on(two_seasons(), 2, {12: date(2026, 9, 21)})
        series, _ = await delivered(session, roots, snapshot=aired)

        await session.refresh(series)
        assert series.confirmed is False
        assert await confirmations(session) == []


class TestTheBatchStillWaits:
    @pytest.mark.parametrize("episode", [11, 12])
    async def test_one_episode_without_an_air_date(
        self, session: AsyncSession, roots: dict[str, Path], episode: int
    ) -> None:
        """一集拿不到播出日，另一集的證據再強也不算：整批等人。先算、後算的是它都一樣。"""
        series, _ = await delivered(session, roots, snapshot=one_undated(episode))

        await session.refresh(series)
        assert series.confirmed is False
        assert len(await audits(session)) == 2
        assert await confirmations(session) == []

    async def test_a_series_with_a_season(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, _ = await delivered(session, roots, season=1)

        await session.refresh(series)
        assert series.confirmed is False
        assert len(await audits(session)) == 2

    async def test_a_series_with_only_an_offset(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """offset 0 也是人說過話：照字面是人說的，不是證據。"""
        series, _ = await delivered(session, roots, offset=0)

        await session.refresh(series)
        assert series.confirmed is False
        assert len(await audits(session)) == 2

    async def test_released_long_after_it_aired(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """TMDB 把兩個 cour 併成一季、feed 在播完一年後才帶到（照字面入庫錯的那一種）：不是剛播。"""
        series, _ = await delivered(session, roots, snapshot=split_cour())

        await session.refresh(series)
        assert series.confirmed is False
        assert len(await audits(session)) == 2

    async def test_a_split_cour_while_airing_is_held(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """M3 驗收那一條：連載中的 split-cour 從 01 重數，播出日比對整批擋在審核，Series 不確認。"""
        series, _ = await delivered(session, roots, snapshot=airing_split_cour())

        await session.refresh(series)
        assert series.confirmed is False
        states = set(
            await session.scalars(select(Job.state).where(Job.trigger_ref == str(series.id)))
        )
        assert states == {JobState.REVIEW}
        assert await confirmations(session) == []

    async def test_a_sibling_still_downloading(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """另一集還在下載：整批還沒到齊，這一集先掛 audit；另一集落地時才整批擔保。"""
        series, factory = await delivered(session, roots, pipeline=False)
        finish_downloads(factory, roots)
        client = factory.qbittorrent_
        done, running = client.torrents
        client.torrents = (done, replace(running, progress=0.5, state="downloading"))
        await _round(session, factory)

        assert await confirmed(session, series.id) is False
        assert len(await audits(session)) == 1

        finish_downloads(factory, roots)
        await _round(session, factory)

        assert await confirmed(session, series.id) is True
        assert await audits(session) == []


class TestWhatItAsks:
    async def test_the_waiting_episodes_and_how_they_were_read(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, _ = await delivered(session, roots, snapshot=undated())

        found = await asks(session, [series.id])

        assert found[series.id].spans == (Span(season=1, start=11, end=12),)
        assert found[series.id].basis is FirstBatchBasis.LITERAL

    async def test_values_on_the_series(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, _ = await delivered(session, roots, snapshot=split_cour(), season=1, offset=12)

        found = await asks(session, [series.id])

        assert found[series.id].spans == (Span(season=1, start=23, end=24),)
        assert found[series.id].basis is FirstBatchBasis.SERIES

    async def test_a_batch_held_in_review_is_asked_about_too(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """連載中的 split-cour 整批停在審核、一集都沒入庫：作品頁照樣說得出在問哪幾集。"""
        series, _ = await delivered(session, roots, snapshot=airing_split_cour())

        found = await asks(session, [series.id])

        assert found[series.id].spans == (Span(season=1, start=11, end=12),)
        assert found[series.id].basis is FirstBatchBasis.LITERAL

    async def test_nothing_waiting_asks_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, _ = await delivered(session, roots)

        assert await asks(session, [series.id]) == {}


async def _round(session: AsyncSession, factory: FakeClientFactory) -> None:
    """poller → 規劃 → 入庫各一輪（`test_rss.run_pipeline` 少了「全部下載完」那一步）。"""
    hub = EventHub()
    await poll_downloads(session, factory.qbittorrent_, hub, JobHints(), now=NOW)
    await sweep_plans(session, factory, hub, now=NOW)
    await sweep_imports(session, factory, hub, now=NOW)
