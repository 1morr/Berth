"""Jellyfin 回驗：反查到的 item，Jellyfin 認的季集與作品要與帳本一致（plan §11.4 ③、M3 票 17）。

三道程式檢查的第三道，**便宜的保險**：它抓的是 Jellyfin 那邊的意外——兩份涵蓋範圍不同的正片
被合成一集（brief §7.8、§20.9）、作品被認成別的——Berth 自己算錯的集數它抓不到（檔名就是
Berth 取的）。

起點是 `test_resolver` 那一份真的入庫完的帳本；替身 Jellyfin 擺出它「認成了什麼」。每一組
斷言都是雙向的：不一致開一件 `jellyfin_item_mismatch`，一致時一件都不開、開著的由系統收掉。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin import JellyfinItem, JellyfinSource
from berth.domain import IssueAction, IssueStatus, IssueType
from berth.models import Issue, LedgerEntry, Route
from berth.models.types import utcnow
from berth.services.issues import list_issues, resolve_issue
from berth.services.reconcile import reconcile_once
from berth.services.resolver import sweep_resolutions
from tests.integration.factories import FakeClientFactory
from tests.integration.test_plan import NOW
from tests.integration.test_reconcile import issues_of
from tests.integration.test_resolver import FIRST, features, imported, scanned

pytestmark = pytest.mark.asyncio

MISMATCH = IssueType.JELLYFIN_ITEM_MISMATCH


async def looked_up(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Route, FakeClientFactory, LedgerEntry]:
    """入庫完、Jellyfin 掃到了，第一集是接下來要被 Jellyfin 認錯的那一列。"""
    route, factory = await imported(session, roots)
    await scanned(session, route, factory)
    return route, factory, (await features(session))[0]


def jellyfin_reads(
    factory: FakeClientFactory, item_id: str, change: Callable[[JellyfinItem], JellyfinItem]
) -> None:
    """替身 Jellyfin 把某一個 item 認成別的樣子。"""
    factory.jellyfin_.items_ = [
        change(item) if item.id == item_id else item for item in factory.jellyfin_.items_
    ]


def season_two(item: JellyfinItem) -> JellyfinItem:
    return replace(item, season=2)


def another_work(item: JellyfinItem) -> JellyfinItem:
    return replace(item, tmdb_id="999")


async def open_mismatches(session: AsyncSession) -> list[Issue]:
    return [
        row
        for row in await issues_of(session)
        if row.type is MISMATCH and row.status is IssueStatus.OPEN
    ]


async def look_again(session: AsyncSession, factory: FakeClientFactory, at: timedelta) -> None:
    """同一列再反查一次。

    正式環境裡把一列排回反查的是 importer（重新入庫、rematch 換路徑時 `first_resolve_at`）與
    「重新反查」。後者按下去時那一件已經由使用者收掉了，所以**系統收**走的是前者與每日對帳
    （`TestTheReconcilerUsesTheSameCheck`）；這裡直接排，比的是同一份。
    """
    for entry in await features(session):
        entry.resolve_attempts = 0
        entry.resolve_after = NOW + at
    await session.commit()
    await sweep_resolutions(session, factory, now=NOW + at)


class TestTheResolverCompares:
    async def test_a_different_season_opens_one_issue(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory, first = await looked_up(session, roots)
        jellyfin_reads(factory, f"episode-{first.episode_start}", season_two)

        await sweep_resolutions(session, factory, now=NOW + FIRST)

        (issue,) = await open_mismatches(session)
        assert issue.ledger_id == first.id
        assert issue.subject == str(first.id)
        assert issue.path == first.target_path
        detail = issue.detail_json or {}
        assert detail["differs"] == ["season"]
        assert detail["ledger"]["season"] == first.season
        assert detail["jellyfin"]["season"] == 2

    async def test_a_different_episode_range_opens_one_issue(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """兩份涵蓋範圍不同的正片被併成一集：Jellyfin 的分組鍵只有季號與集號（brief §20.9）。"""
        _, factory, first = await looked_up(session, roots)
        start = first.episode_start or 0
        jellyfin_reads(
            factory,
            f"episode-{first.episode_start}",
            lambda item: replace(item, episode_start=start, episode_end=start + 1),
        )

        await sweep_resolutions(session, factory, now=NOW + FIRST)

        (issue,) = await open_mismatches(session)
        detail = issue.detail_json or {}
        assert detail["differs"] == ["episode"]
        assert detail["jellyfin"]["episode_end"] == start + 1

    async def test_a_series_with_another_tmdb_id_opens_an_issue_for_every_episode(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """作品被認成別的：那個 Series 底下的每一集都是一件（冪等鍵是帳本那一列）。"""
        _, factory, _ = await looked_up(session, roots)
        jellyfin_reads(factory, "series-1", another_work)

        await sweep_resolutions(session, factory, now=NOW + FIRST)

        issues = await open_mismatches(session)
        assert sorted(row.ledger_id or 0 for row in issues) == sorted(
            entry.id for entry in await features(session)
        )
        detail = issues[0].detail_json or {}
        assert detail["differs"] == ["tmdb"]
        assert (detail["ledger"]["tmdb"], detail["jellyfin"]["tmdb"]) == ("120089", "999")

    async def test_agreement_opens_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory, _ = await looked_up(session, roots)

        outcome = await sweep_resolutions(session, factory, now=NOW + FIRST)

        assert outcome.resolved == 3
        assert await open_mismatches(session) == []

    async def test_a_second_version_is_compared_against_the_item_that_holds_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """多版本合併之後，帳本那個檔案只是主條目底下的一個來源（brief §20.9）：比的是主條目的
        季集。`S01E01-E02` 的一份當了主條目，單集的 `S01E01` 那一列就不一致。"""
        _, factory, first = await looked_up(session, roots)
        primary = f"{first.target_path}.bd.mkv"
        jellyfin_reads(
            factory,
            f"episode-{first.episode_start}",
            lambda item: replace(
                item,
                id="episode-merged",
                path=primary,
                episode_end=(first.episode_start or 0) + 1,
                sources=(
                    JellyfinSource(path=primary, name="BD"),
                    JellyfinSource(path=first.target_path, name="WEB"),
                ),
            ),
        )

        await sweep_resolutions(session, factory, now=NOW + FIRST)

        (issue,) = await open_mismatches(session)
        assert issue.ledger_id == first.id
        assert (issue.detail_json or {})["jellyfin"]["item"] == "episode-merged"

    async def test_an_episode_whose_series_jellyfin_did_not_list_has_no_work(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """集指著一個查不到的 Series（或 Series 沒有 `ProviderIds.Tmdb`）：說不出是哪一部作品，
        算不一致——那正是作品沒被認出來的樣子。"""
        _, factory, first = await looked_up(session, roots)
        jellyfin_reads(
            factory, f"episode-{first.episode_start}", lambda item: replace(item, series_id="gone")
        )

        await sweep_resolutions(session, factory, now=NOW + FIRST)

        (issue,) = await open_mismatches(session)
        detail = issue.detail_json or {}
        assert (detail["differs"], detail["jellyfin"]["tmdb"]) == (["tmdb"], "")

    async def test_a_mismatch_is_still_resolved(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """找到了就是找到了：item 照記，重試排程停下——問題在 Jellyfin 認成什麼，不在找不找得到。"""
        _, factory, first = await looked_up(session, roots)
        jellyfin_reads(factory, f"episode-{first.episode_start}", season_two)

        await sweep_resolutions(session, factory, now=NOW + FIRST)

        await session.refresh(first)
        assert first.jellyfin_item_id == f"episode-{first.episode_start}"
        assert first.resolve_after is None


class TestIdempotence:
    async def test_looking_twice_keeps_one_open_issue(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory, first = await looked_up(session, roots)
        jellyfin_reads(factory, f"episode-{first.episode_start}", season_two)
        await sweep_resolutions(session, factory, now=NOW + FIRST)

        await look_again(session, factory, FIRST * 2)

        (issue,) = await open_mismatches(session)
        assert issue.detected_at == NOW + FIRST * 2


class TestTheSystemClosesIt:
    async def test_the_next_lookup_that_agrees_closes_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route, factory, first = await looked_up(session, roots)
        jellyfin_reads(factory, f"episode-{first.episode_start}", season_two)
        await sweep_resolutions(session, factory, now=NOW + FIRST)
        (issue,) = await open_mismatches(session)

        await scanned(session, route, factory)  # 使用者在 Jellyfin 修好了
        await look_again(session, factory, FIRST * 2)

        await session.refresh(issue)
        assert issue.status is IssueStatus.RESOLVED
        assert issue.resolved_by == "system"

    async def test_a_lookup_that_cannot_find_the_item_leaves_it_open(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """找不到不是「一致了」：可能是 Jellyfin 正在重掃。那一件等下一次真的比到。"""
        _, factory, first = await looked_up(session, roots)
        jellyfin_reads(factory, f"episode-{first.episode_start}", season_two)
        await sweep_resolutions(session, factory, now=NOW + FIRST)

        factory.jellyfin_.items_ = []
        await look_again(session, factory, FIRST * 2)

        assert len(await open_mismatches(session)) == 1


class TestTheReconcilerUsesTheSameCheck:
    """對帳的 Jellyfin 那一方重對主條目時比同一份（M2 票 09）：入庫之後才出的意外在這裡抓到。"""

    async def test_it_opens_and_later_closes_the_issue(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route, factory, _ = await looked_up(session, roots)
        await sweep_resolutions(session, factory, now=NOW + FIRST)
        assert await open_mismatches(session) == []

        jellyfin_reads(factory, "series-1", another_work)
        await reconcile_once(session, factory, now=NOW + timedelta(days=1))
        assert len(await open_mismatches(session)) == 3

        await scanned(session, route, factory)
        await reconcile_once(session, factory, now=NOW + timedelta(days=2))
        assert await open_mismatches(session) == []

    async def test_jellyfin_being_down_closes_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory, first = await looked_up(session, roots)
        jellyfin_reads(factory, f"episode-{first.episode_start}", season_two)
        await sweep_resolutions(session, factory, now=NOW + FIRST)

        factory.jellyfin_.error = ServiceUnavailableError("GET /Items: connection refused")
        await reconcile_once(session, factory, now=NOW + timedelta(days=1))

        assert len(await open_mismatches(session)) == 1


class TestTheButtons:
    async def test_relook_is_offered_and_puts_the_row_back_in_the_queue(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory, first = await looked_up(session, roots)
        jellyfin_reads(factory, f"episode-{first.episode_start}", season_two)
        await sweep_resolutions(session, factory, now=NOW + FIRST)

        (view,) = [row for row in await list_issues(session) if row.type is MISMATCH]
        assert view.actions == (IssueAction.RELOOK,)

        await resolve_issue(session, factory, view.id, IssueAction.RELOOK, actor="7")

        await session.refresh(first)
        assert first.resolve_after is not None
        assert first.resolve_after <= utcnow()
