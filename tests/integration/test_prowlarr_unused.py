"""「不用 Prowlarr」（M4 票 61，審計 E3、P1-2）：沒有索引站是一個正常狀態，而且改得回來。

與精靈頁 4 的「之後再說」是同一個狀態（`setup.indexer.skipped`，`indexer.skip_indexers`）。
驗的是雙向：選了不用之後健康不阻擋、搜尋說沒有接索引站、完成再驗算這一格完成；改回來之後
三件事都照 Prowlarr 的實況。
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.domain import HealthStatus, IndexerProblem, ServiceKind, ServiceOrigin
from berth.models import SetupSettings
from berth.services.health import (
    CHECK_INTERVAL,
    RECHECK_INTERVAL,
    ServiceHealthView,
    check_health,
    overall_status,
    read_health,
    recheck_due,
)
from berth.services.indexer import skip_indexers
from berth.services.search import search_torrents
from berth.services.settings import update_settings
from berth.services.setup import complete_setup
from berth.services.sources import SourceCache
from tests.integration.arrange import NOW, chosen
from tests.integration.factories import FakeClientFactory
from tests.integration.test_health_service import ready
from tests.integration.test_search import SPY, arrange_media

pytestmark = pytest.mark.asyncio

DOWN = ServiceUnavailableError("GET /api/v1/indexer: host does not resolve")


async def prowlarr(session: AsyncSession) -> ServiceHealthView:
    report = await read_health(session)
    return next(row for row in report.services if row.kind is ServiceKind.PROWLARR)


async def stopped(session: AsyncSession, roots: dict[str, Path]) -> FakeClientFactory:
    """精靈跑完、健康檢查跑過一輪之後，Prowlarr 的容器被停掉（審計 S4 的重現步驟）。"""
    factory = await ready(session, roots)
    await complete_setup(session, now=NOW - CHECK_INTERVAL)
    factory.prowlarr_.ping_error = DOWN
    factory.indexer_search_.error = DOWN
    await check_health(session, factory, now=NOW)
    return factory


class TestHealth:
    async def test_a_stopped_prowlarr_blocks_until_it_is_set_aside(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await stopped(session, roots)
        assert (await prowlarr(session)).status is HealthStatus.FAILED
        assert await overall_status(session) == "degraded"

        await skip_indexers(session, factory, skipped=True)

        # 選下去的那一刻就不阻擋：不必等下一輪檢查把那一格的紅燈蓋掉。
        row = await prowlarr(session)
        assert row.unused is True
        assert (await read_health(session)).degraded is False
        assert await overall_status(session) == "ok"

    async def test_the_loop_leaves_an_unused_prowlarr_alone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await stopped(session, roots)
        await skip_indexers(session, factory, skipped=True)
        pings = 0

        async def ping() -> None:
            nonlocal pings
            pings += 1

        factory.prowlarr_.ping = ping  # type: ignore[method-assign]  # 記下有沒有人去連它

        await check_health(session, factory, now=NOW + CHECK_INTERVAL)

        assert pings == 0, "不用它就不連它"
        row = await prowlarr(session)
        assert row.unused is True
        assert row.status is not HealthStatus.FAILED
        assert row.failures == 0

    async def test_using_it_again_brings_back_what_prowlarr_says(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await stopped(session, roots)
        await skip_indexers(session, factory, skipped=True)
        await check_health(session, factory, now=NOW + CHECK_INTERVAL)

        await skip_indexers(session, factory, skipped=False)
        await check_health(session, factory, now=NOW + 2 * CHECK_INTERVAL)
        assert (await prowlarr(session)).status is HealthStatus.FAILED
        assert (await prowlarr(session)).unused is False

        factory.prowlarr_.ping_error = None
        await check_health(session, factory, now=NOW + 3 * CHECK_INTERVAL)
        assert (await prowlarr(session)).status is HealthStatus.OK

    async def test_an_existing_prowlarr_comes_back_the_same_way(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """既有的那一台也一樣：不用時不阻擋、不連它，改回來照它的實況（code-review 補的另一種
        來源）。"""
        factory = await stopped(session, roots)

        def existing(latest: SetupSettings) -> None:
            latest.choices = {
                **latest.choices,
                ServiceKind.PROWLARR: chosen(ServiceOrigin.EXISTING, "http://prowlarr:9696"),
            }

        await update_settings(session, SetupSettings, existing)
        await skip_indexers(session, factory, skipped=True)
        await check_health(session, factory, now=NOW + CHECK_INTERVAL)
        assert (await prowlarr(session)).unused is True
        assert await overall_status(session) == "ok"
        await complete_setup(session, now=NOW + CHECK_INTERVAL)

        factory.prowlarr_.ping_error = None
        await skip_indexers(session, factory, skipped=False)
        await check_health(session, factory, now=NOW + 2 * CHECK_INTERVAL)
        row = await prowlarr(session)
        assert row.unused is False
        assert row.status is HealthStatus.OK
        await complete_setup(session, now=NOW + 2 * CHECK_INTERVAL)


class TestSearch:
    async def test_an_unused_prowlarr_is_not_configured_rather_than_unreachable(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await stopped(session, roots)
        await arrange_media(session)
        before = await search_torrents(session, factory, SourceCache(), media_id=SPY)
        assert before.problem is IndexerProblem.UNREACHABLE

        await skip_indexers(session, factory, skipped=True)
        unused = await search_torrents(session, factory, SourceCache(), media_id=SPY)

        assert unused.problem is IndexerProblem.NOT_CONFIGURED
        assert unused.detail == ""

    async def test_using_it_again_searches_prowlarr_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await stopped(session, roots)
        await arrange_media(session)
        await skip_indexers(session, factory, skipped=True)

        factory.indexer_search_.error = None
        await skip_indexers(session, factory, skipped=False)
        view = await search_torrents(session, factory, SourceCache(), media_id=SPY)

        assert view.problem is None


class TestCompletion:
    async def test_the_prowlarr_page_counts_as_done_when_it_is_not_used(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """完成照頁序再驗（M4 票 31）：沒有站的 Prowlarr 擋得住完成，選了不用就算這一格完成。"""
        factory = await ready(session, roots)

        def no_sites(latest: SetupSettings) -> None:
            latest.indexer.steps = []

        await update_settings(session, SetupSettings, no_sites)
        with pytest.raises(ValueError, match="finish page 4"):
            await complete_setup(session, now=NOW)

        await skip_indexers(session, factory, skipped=True)
        await complete_setup(session, now=NOW)

        await skip_indexers(session, factory, skipped=False)
        with pytest.raises(ValueError, match="finish page 4"):
            await complete_setup(session, now=NOW)


class TestEarlyRecheck:
    """連不上 Prowlarr 時下一輪提早重測（審計 P1-2：回來之後要等滿 5 分鐘）。"""

    async def test_a_red_prowlarr_is_rechecked_before_the_interval(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await stopped(session, roots)

        assert (
            await recheck_due(session, now=NOW + RECHECK_INTERVAL - timedelta(seconds=1)) is False
        )
        assert await recheck_due(session, now=NOW + RECHECK_INTERVAL) is True
        assert RECHECK_INTERVAL < CHECK_INTERVAL

    async def test_a_green_or_unused_prowlarr_waits_for_the_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        await check_health(session, factory, now=NOW)
        assert await recheck_due(session, now=NOW + RECHECK_INTERVAL) is False

        factory = await stopped(session, roots)
        await skip_indexers(session, factory, skipped=True)
        assert await recheck_due(session, now=NOW + RECHECK_INTERVAL) is False

    async def test_a_red_qbittorrent_or_jellyfin_waits_for_the_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """只有 Prowlarr 提早（理由在票 61 的 Comments）：另外兩台牽動 Route 那一項，
        qBittorrent 重試登入還會把封鎖時間重算（brief §20.2）。"""
        factory = await ready(session, roots)
        factory.qbittorrent_.error = DOWN
        factory.jellyfin_.error = DOWN
        await check_health(session, factory, now=NOW)

        assert await recheck_due(session, now=NOW + RECHECK_INTERVAL) is False
