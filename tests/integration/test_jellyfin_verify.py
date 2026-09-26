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
from berth.services.resolve_schedule import RESOLVE_DELAYS
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


async def until_given_up(
    session: AsyncSession, factory: FakeClientFactory, entry: LedgerEntry
) -> None:
    """照那一列自己的排程一直問，問到它不再排程（找到或用完 6 次）。"""
    await session.refresh(entry)
    while entry.resolve_after is not None:
        await sweep_resolutions(session, factory, now=entry.resolve_after)
        await session.refresh(entry)


def still_identifying(item: JellyfinItem) -> JellyfinItem:
    """2026-09-26 試跑記下的那一份：Jellyfin 還沒認完剛掃進來的檔案——Name 是作品名、季集
    `None`。Series 那一邊沒有 Tmdb 由 `unidentified_series` 擺。"""
    return replace(item, name="SPY x FAMILY", season=None, episode_start=None, episode_end=None)


def unidentified_series(item: JellyfinItem) -> JellyfinItem:
    return replace(item, tmdb_id="")


class TestStillIdentifying:
    """「還沒認出」不是「認得不一樣」（M4 票 02）：不寫 verdict，照還沒找到的節奏再問。"""

    async def test_the_trial_reading_opens_nothing_and_is_asked_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory, first = await looked_up(session, roots)
        jellyfin_reads(factory, f"episode-{first.episode_start}", still_identifying)
        jellyfin_reads(factory, "series-1", unidentified_series)

        outcome = await sweep_resolutions(session, factory, now=NOW + FIRST)

        assert await issues_of(session) == []
        assert outcome.resolved == 0
        await session.refresh(first)
        assert first.resolve_after == NOW + FIRST + RESOLVE_DELAYS[1]
        # 還沒認完的不算找到：畫面照實說「還在掃描」，對帳的 Jellyfin 那一方也不去比它。
        assert first.jellyfin_item_id == ""

    async def test_once_jellyfin_is_done_it_agrees_without_ever_opening(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """試跑的另一半：幾分鐘後讀回 `S01E10`，Issue 被收掉、下一輪又重開。現在一件都不開。"""
        route, factory, first = await looked_up(session, roots)
        jellyfin_reads(factory, f"episode-{first.episode_start}", still_identifying)
        jellyfin_reads(factory, "series-1", unidentified_series)
        await sweep_resolutions(session, factory, now=NOW + FIRST)

        await scanned(session, route, factory)
        await until_given_up(session, factory, first)

        assert [row for row in await issues_of(session) if row.type is MISMATCH] == []
        await session.refresh(first)
        assert first.jellyfin_item_id == f"episode-{first.episode_start}"

    async def test_it_is_asked_again_within_ten_minutes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Jellyfin 已經列出檔案、只差認完：不必等到一小時（同請它掃描之後，`SCAN_SETTLE`）。"""
        _, factory, first = await looked_up(session, roots)
        jellyfin_reads(factory, f"episode-{first.episode_start}", still_identifying)
        waits: list[timedelta] = []
        at = NOW + FIRST
        while True:
            await sweep_resolutions(session, factory, now=at)
            await session.refresh(first)
            if first.resolve_after is None:
                break
            waits.append(first.resolve_after - at)
            at = first.resolve_after

        assert waits == [RESOLVE_DELAYS[1], *[timedelta(minutes=10)] * 4]

    async def test_a_relook_that_catches_a_rescan_opens_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """試跑真正的迴圈：找到、一致，之後被排回反查（新版本入庫、重新反查），正好撞上
        新檔案觸發的重掃，讀到的是空的。那一次不開，認完之後也沒有收掉又重開。"""
        route, factory, first = await looked_up(session, roots)
        await sweep_resolutions(session, factory, now=NOW + FIRST)
        jellyfin_reads(factory, f"episode-{first.episode_start}", still_identifying)
        jellyfin_reads(factory, "series-1", unidentified_series)

        await look_again(session, factory, FIRST * 2)
        await scanned(session, route, factory)
        await until_given_up(session, factory, first)

        assert [row for row in await issues_of(session) if row.type is MISMATCH] == []

    async def test_a_reading_of_another_season_still_opens_at_once(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """雙向：認得出、而且認成別的季，不必等。"""
        _, factory, first = await looked_up(session, roots)
        jellyfin_reads(factory, f"episode-{first.episode_start}", season_two)

        await sweep_resolutions(session, factory, now=NOW + FIRST)

        (issue,) = await open_mismatches(session)
        assert issue.ledger_id == first.id

    async def test_six_readings_that_never_identify_open_a_mismatch(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """用完 6 次還認不出編號：落到 `jellyfin_item_mismatch`，它並排兩邊，說得出 Jellyfin
        讀成了空的。不是 `jellyfin_item_unresolved`——Jellyfin 列出了這個檔案。"""
        _, factory, first = await looked_up(session, roots)
        jellyfin_reads(factory, f"episode-{first.episode_start}", still_identifying)

        await until_given_up(session, factory, first)

        (issue,) = await open_mismatches(session)
        assert issue.ledger_id == first.id
        detail = issue.detail_json or {}
        assert detail["differs"] == ["season", "episode"]
        assert detail["jellyfin"]["season"] is None
        assert [row for row in await issues_of(session) if row.type is not MISMATCH] == []
        await session.refresh(first)
        assert first.resolve_attempts == len(RESOLVE_DELAYS)
        assert first.jellyfin_item_id == f"episode-{first.episode_start}"


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

    async def test_an_episode_whose_series_never_gets_a_work_opens_an_issue_at_the_end(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """集指著一個查不到的 Series（或 Series 沒有 `ProviderIds.Tmdb`）：說不出是哪一部作品。
        剛掃進來時那是 Jellyfin 還在認（M4 票 02），所以先照「還沒找到」的節奏再問；六次都
        還是這樣，才是作品沒被認出來，開一件。"""
        _, factory, first = await looked_up(session, roots)
        jellyfin_reads(
            factory, f"episode-{first.episode_start}", lambda item: replace(item, series_id="gone")
        )

        await sweep_resolutions(session, factory, now=NOW + FIRST)
        assert await open_mismatches(session) == []

        await until_given_up(session, factory, first)

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

    async def test_jellyfin_still_identifying_opens_and_closes_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """對帳那一刻 Jellyfin 正在重認（有人按了重新掃描）：與找不到同一個待遇，不動。"""
        _, factory, first = await looked_up(session, roots)
        jellyfin_reads(factory, f"episode-{first.episode_start}", season_two)
        await sweep_resolutions(session, factory, now=NOW + FIRST)

        jellyfin_reads(factory, "series-1", unidentified_series)
        await reconcile_once(session, factory, now=NOW + timedelta(days=1))

        (issue,) = await open_mismatches(session)
        assert issue.ledger_id == first.id
        assert issue.detected_at == NOW + FIRST

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
