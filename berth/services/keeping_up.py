"""追更（Keeping up）：訂閱的作品有沒有按時入庫（M5.5 票 12，spec〈範圍〉「追更頁」、
`.scratch/m5.5/tracking-shape.md`）。頁面在 `/schedule/tracking`；它不是 Tracked Media
（`services.tracking`）。

**對象與遲到提醒同一群**（`watched_works`）：現在還訂著、帶著 Item 的綁好的 RSS Series 的作品，以及
預先綁定作品、字幕組一集都還沒發的 Feed 的作品（票 12b）。
頁面與每日巡檢開的 `episodes_overdue` 說的是同一群作品、同一套判定（`parser.overdue.watch_overdue`，
`watch_work` 是兩邊共用的那一支），所以頁上「晚 N 天」的那幾部就是 Issue 上的那幾部。

一部作品一列：
- **狀態**是基準之後已播、還沒入庫的那幾集的 `domain.conclude`，整部取 `overall`；那一段沒有集時是
  已入庫（跟上了），一集都還沒播是還沒播。**下載停滯**另外說（`domain.stalled`）：`WhyNot` 把它併進
  「在路上」。
- **晚 N 天**：判定有晚的集時，最早那一集從播出日到今天（容器時區）的天數（使用者 2026-11-04 定）。
- **分段**（`KeepingUpSection`）：過了 60 天視窗的收進「斷更很久」；有晚的集、或卡在不會自己好的
  地方的是「要你動手」；其餘「準時」。

時間表的卡片也讀這一套（`late_by_work`）：卡片那一集晚了就是「晚 N 天」。

只讀資料庫，不問 TMDB：快照由每日巡檢前的刷新（`sweep.refresh_watched`）與作品頁更新。
"""

from __future__ import annotations

import asyncio
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    KeepingUpSection,
    MediaSnapshot,
    OverdueReason,
    PlanAction,
    WhyNot,
    overall,
)
from berth.models import Job, LedgerEntry, Media, RssFeed, RssItem, RssSeries, RssSettings
from berth.parser import parse_release
from berth.parser.overdue import LateEpisode, OverdueJob, Watch, watch_overdue
from berth.services.commands import Effect, Flag, command
from berth.services.inventory import episodes_of
from berth.services.issues import covered_jobs
from berth.services.rss import subscribed_media
from berth.services.settings import read_settings
from berth.services.why_not import account_missing, claims_by_episode

#: 不會自己好的結論：還沒過門檻也排進「要你動手」（下載停滯另外看 `stalled`）。
_NEEDS_YOU = frozenset(
    {WhyNot.IMPORT_FAILED, WhyNot.DOWNLOAD_FAILED, WhyNot.AWAITING_REVIEW, WhyNot.UNBOUND}
)


@dataclass(frozen=True, slots=True)
class EpisodeMark:
    """「已播到」「已入庫到」那一格：一集與它的播出日（TMDB 沒寫是 `None`）。"""

    season: int
    episode: int
    air_date: date | None


@dataclass(frozen=True, slots=True)
class TrackedWork:
    """追更頁的一列。"""

    media_id: str
    #: Display Round（`GLOSSARY.md`）。
    title: str
    title_en: str
    #: 作品上每一條訂閱的字幕組，不重複：先 Series、再還沒長出 Series 的 Feed，各照建立的順序
    #: （`Subscriptions.groups`）。
    groups: tuple[str, ...]
    #: TMDB 上最新播出的一集（第 0 季不看）；一集都還沒播，或沒有快照，是 `None`。
    aired: EpisodeMark | None
    #: 帳本裡最新的一集（第 0 季不看）；一集都沒有是 `None`。
    imported: EpisodeMark | None
    #: 沒有 TMDB 快照時是 `None`：說不出哪一集播了。
    conclusion: WhyNot | None
    #: 基準之後缺的集裡有一集是下載停滯。
    stalled: bool
    section: KeepingUpSection
    #: 有晚的集（而且不在「斷更很久」）時才有；`next_run` 是「可能是下一輪」。
    reason: OverdueReason | None
    #: 最早那一集晚的集從播出日到今天的天數；沒有晚的集是 `None`。
    late_days: int | None
    #: 晚的集與卡在哪（同 `episodes_overdue` 的 `detail_json.episodes`）。
    late: tuple[LateEpisode, ...]


@dataclass(frozen=True, slots=True)
class KeepingUpView:
    """追更頁。作品照段（`KeepingUpSection` 的順序）排好，段內的順序見 `_order`。"""

    #: 容器時區的今天：「晚 N 天」照它算。
    today: date
    works: tuple[TrackedWork, ...]


def local_now() -> datetime:
    """容器時區的現在（測試換掉它）。日界與巡檢一樣照牆上的日期。"""
    return datetime.now().astimezone()


# 讀資料庫，不問任何服務。字幕組與 Feed 是管理員的事（`api/gate.py` 的 `/schedule/tracking`）。
@command(
    Effect.READ,
    about=(
        "Whether each subscribed work is keeping up: per work its release groups, the latest "
        "aired and imported episode, the why_not_explain conclusion for what is missing after "
        "the last imported episode (stalled downloads called out), and how many days late the "
        "overdue episodes are (counted from the air date). section is action, on_time or "
        "dormant (missing for more than 60 days, no longer reminded). Reads Berth's records only."
    ),
)
async def read_keeping_up(session: AsyncSession) -> KeepingUpView:
    """追更頁的每一列。"""
    now = local_now()
    fallback = (await read_settings(session, RssSettings)).overdue_days
    works: list[TrackedWork] = []
    for media_id, subscriptions in (await watched_works(session)).items():
        media = await session.get(Media, media_id)
        if media is None:
            continue
        works.append(await _track(session, media, subscriptions, now=now, fallback=fallback))
        # 一部作品要猜好幾個發佈名的季集（`account_missing`），一部讓出一次迴圈。
        await asyncio.sleep(0)
    return KeepingUpView(today=now.date(), works=_order(works))


async def _track(
    session: AsyncSession,
    media: Media,
    subscriptions: Subscriptions,
    *,
    now: datetime,
    fallback: int,
) -> TrackedWork:
    snapshot = media.stored_snapshot()
    display = media.snapshot()
    imported = await imported_episodes(session, media.id)
    groups = subscriptions.groups()
    newest = max((pair for pair in imported if pair[0] > 0), default=None)
    if snapshot is None:
        return TrackedWork(
            media_id=media.id,
            title=display.title,
            title_en=display.title_en,
            groups=groups,
            aired=None,
            imported=None if newest is None else EpisodeMark(*newest, None),
            conclusion=None,
            stalled=False,
            section=KeepingUpSection.ON_TIME,
            reason=None,
            late_days=None,
            late=(),
        )

    dates = _air_dates(snapshot)
    today = now.date()
    on_air = [pair for pair, day in dates.items() if day is not None and day <= today]
    accounts = await account_missing(
        session, media, [pair for pair in on_air if pair not in imported]
    )
    watch = await watch_work(
        session,
        snapshot,
        subscriptions,
        imported=imported,
        claimed={pair: account.jobs for pair, account in accounts.items()},
        now=now,
        fallback=fallback,
    )
    missing = [accounts[pair] for pair in watch.missing if pair in accounts]
    latest = max(on_air, default=None)
    if missing:
        conclusion = overall(account.conclusion for account in missing)
    else:
        # 基準之後沒有缺：跟上了（季中訂閱、之後還沒有新的一集也是）；一集都還沒播才是還沒播。
        conclusion = WhyNot.IMPORTED if latest is not None else WhyNot.UNAIRED
    stalled = any(account.stalled for account in missing)
    late = () if watch.dormant else watch.late
    if watch.dormant:
        section = KeepingUpSection.DORMANT
    elif late or stalled or conclusion in _NEEDS_YOU:
        section = KeepingUpSection.ACTION
    else:
        section = KeepingUpSection.ON_TIME
    return TrackedWork(
        media_id=media.id,
        title=display.title,
        title_en=display.title_en,
        groups=groups,
        aired=None if latest is None else EpisodeMark(*latest, dates[latest]),
        imported=None if newest is None else EpisodeMark(*newest, dates.get(newest)),
        conclusion=conclusion,
        stalled=stalled,
        section=section,
        reason=watch.reason if late else None,
        late_days=(today - min(one.air_date for one in late)).days if late else None,
        late=late,
    )


def _order(works: list[TrackedWork]) -> tuple[TrackedWork, ...]:
    """段照 `KeepingUpSection` 的順序。「要你動手」晚越久越前面（沒晚的排後，再照結論的優先序）；
    其餘段照最新播出的那一集新的在前；沒有快照的排在段尾。"""
    sections = list(KeepingUpSection)
    conclusions = list(WhyNot)

    def key(work: TrackedWork) -> tuple[object, ...]:
        aired = work.aired.air_date if work.aired and work.aired.air_date else None
        recency = -aired.toordinal() if aired else 0
        urgency = (0, 0)
        if work.section is KeepingUpSection.ACTION:
            urgency = (
                -(work.late_days if work.late_days is not None else -1),
                conclusions.index(work.conclusion) if work.conclusion else len(conclusions),
            )
        return (sections.index(work.section), *urgency, aired is None, recency, work.title)

    return tuple(sorted(works, key=key))


def _air_dates(snapshot: MediaSnapshot) -> dict[tuple[int, int], date | None]:
    """正片每一集的播出日（第 0 季不看）。"""
    return {
        (season.season_number, row.episode_number): row.air_date
        for season in snapshot.seasons
        if season.season_number > 0
        for row in season.episodes
    }


# --- 與巡檢共用 ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Subscriptions:
    """遲到看的一部作品的訂閱（`GLOSSARY.md`〈訂閱〉）。"""

    #: 綁到它、還帶著 Item 的 RSS Series，照建立的順序。
    series: tuple[RssSeries, ...]
    #: 預先綁定它的 Feed（票 12b），照建立的順序；字幕組一集都還沒發的也在。
    feeds: tuple[RssFeed, ...]
    #: `feeds` 裡已經長出綁到它的 RSS Series 的那幾條：門檻與字幕組由那條 Series 代表。
    grown: frozenset[int]

    def starts(self) -> list[datetime]:
        """每一條訂閱開始的那一刻：Series 建立、Feed 綁定（Feed 只在建立時綁，`subscribe_search`）。
        長出 Series 的 Feed 也算：起算取較早的，字幕組晚發第一筆不把起算日往後推。"""
        return [row.created_at for row in self.series] + [feed.created_at for feed in self.feeds]

    def threshold(self, fallback: int) -> int:
        """作品的門檻：每一條訂閱的門檻取最大值；沒覆寫的 Series 與還沒長出 Series 的 Feed 用全域
        `fallback`。"""
        days = [fallback if row.overdue_days is None else row.overdue_days for row in self.series]
        if self._without_series():
            days.append(fallback)
        return max(days, default=fallback)

    def groups(self) -> tuple[str, ...]:
        """字幕組名，不重複、讀不出來的不列。Series 同巡檢的 `_about`（Mikan 的 subgroup，沒有就從
        長出它的發佈名讀）；還沒長出 Series 的 Feed 是它只收的字幕組，沒有就是 Feed 名。"""
        names = [
            row.mikan_subgroup_name or parse_release(row.title_raw).group for row in self.series
        ]
        names += [feed.subgroup or feed.name for feed in self._without_series()]
        return tuple(dict.fromkeys(name for name in names if name))

    def _without_series(self) -> list[RssFeed]:
        """還沒長出綁到這部作品的 RSS Series 的 Feed（字幕組一集都還沒發）。"""
        return [feed for feed in self.feeds if feed.id not in self.grown]


# 巡檢（`services.sweep`）與時間表讀它：回 ORM 列，不進登錄表。
@command(Effect.READ, flags={Flag.INTERNAL})
async def watched_works(session: AsyncSession) -> dict[str, Subscriptions]:
    """遲到看的對象，照作品分好（作品 id 排序）：作品現在有訂閱（`rss.subscribed_media`，與作品頁的
    訂閱清單同一套判定），訂閱是綁好、還帶著 Item 的 RSS Series，或預先綁定作品的 Feed（字幕組
    一集都還沒發也算，票 12b）。刪掉 Feed 只刪 Feed，Series 與綁定留著（`delete_feed`），退訂了
    就不看（協調者追加，票 10 的缺陷）。"""
    bound = list(
        await session.scalars(
            select(RssSeries)
            .where(RssSeries.media_id.is_not(None))
            .order_by(RssSeries.created_at, RssSeries.id)
        )
    )
    prebound = list(
        await session.scalars(
            select(RssFeed)
            .where(RssFeed.media_id.is_not(None))
            .order_by(RssFeed.created_at, RssFeed.id)
        )
    )
    live = await subscribed_media(session, [row.media_id for row in bound if row.media_id])
    # 作品還訂著時，Feed 被刪的那幾條也不算（門檻、換輪、起算日都不看它）：刪 Feed 連 Item 一起刪，
    # 還掛著 Item 的才是還在送的那一條。
    carried = (
        await session.execute(
            select(RssItem.feed_id, RssSeries.id, RssSeries.media_id)
            .join(RssSeries, RssSeries.id == RssItem.series_id)
            .distinct()
        )
    ).tuples()
    carrying: set[int] = set()
    #: (Feed, 作品)：這條 Feed 帶著綁到這部作品的 Series。
    grew: set[tuple[int, str | None]] = set()
    for feed_id, series_id, media_id in carried:
        carrying.add(series_id)
        grew.add((feed_id, media_id))
    series: dict[str, list[RssSeries]] = {}
    for row in bound:
        if row.media_id in live and row.id in carrying:
            series.setdefault(row.media_id, []).append(row)
    # 預先綁定作品的 Feed 本身就是一條訂閱（`subscribed_media` 的前一半）。
    feeds: dict[str, list[RssFeed]] = {}
    for feed in prebound:
        if feed.media_id is not None:
            feeds.setdefault(feed.media_id, []).append(feed)
    return {
        media_id: Subscriptions(
            series=tuple(series.get(media_id, ())),
            feeds=tuple(feeds.get(media_id, ())),
            grown=frozenset(
                feed.id for feed in feeds.get(media_id, ()) if (feed.id, media_id) in grew
            ),
        )
        for media_id in sorted(series.keys() | feeds.keys())
    }


@command(Effect.READ, flags={Flag.INTERNAL})
async def imported_episodes(
    session: AsyncSession, media_id: str
) -> dict[tuple[int, int], datetime]:
    """這部作品帳本有正片蓋到的季集，不分誰送的，各自最早入庫的那一刻（換輪比它）。"""
    rows = await session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.media_id == media_id, LedgerEntry.action == PlanAction.IMPORT
        )
    )
    landed: dict[tuple[int, int], datetime] = {}
    for row in rows:
        for pair in episodes_of(row):
            if pair not in landed or row.created_at < landed[pair]:
                landed[pair] = row.created_at
    return landed


@command(Effect.READ, flags={Flag.INTERNAL})
async def watch_work(
    session: AsyncSession,
    snapshot: MediaSnapshot,
    subscriptions: Subscriptions,
    *,
    imported: Mapping[tuple[int, int], datetime],
    claimed: Mapping[tuple[int, int], Sequence[Job]],
    now: datetime,
    fallback: int,
) -> Watch:
    """一部作品的遲到判定（巡檢、追更頁、時間表共用）。`claimed` 是每一集蓋到的 Job
    （`why_not.claims_by_episode` 那一份）；Job 已經有 Issue 說著它現在這個狀態的算在等人
    （`issues.covered_jobs`）。`now` 是容器時區的現在。"""
    covered = await covered_jobs(
        session, list({job.hash: job for jobs in claimed.values() for job in jobs}.values())
    )
    return watch_overdue(
        snapshot,
        imported=imported,
        claims={
            pair: [
                OverdueJob(hash=job.hash, state=job.state, waiting=job.hash in covered)
                for job in jobs
            ]
            for pair, jobs in claimed.items()
        },
        subscribed=subscriptions.starts(),
        now=now,
        threshold_days=subscriptions.threshold(fallback),
    )


# 巡檢（`services.sweep`）與時間表讀它：收 ORM 列，不進登錄表。
@command(Effect.READ, flags={Flag.INTERNAL})
async def watch_of(
    session: AsyncSession,
    media: Media,
    subscriptions: Subscriptions,
    *,
    now: datetime,
    fallback: int,
) -> Watch | None:
    """`watch_work` 加上它要的材料（帳本與 `why_not.claims_by_episode`）；沒有 TMDB 快照的作品說不出
    哪一集播了，是 `None`。追更頁另外要每一集的結論，自己湊材料（`_track`）。"""
    snapshot = media.stored_snapshot()
    if snapshot is None:
        return None
    return await watch_work(
        session,
        snapshot,
        subscriptions,
        imported=await imported_episodes(session, media.id),
        claimed=await claims_by_episode(session, media),
        now=now,
        fallback=fallback,
    )


# 時間表（`services.schedule`）讀它。
@command(Effect.READ, flags={Flag.INTERNAL})
async def late_by_work(
    session: AsyncSession, media_ids: Collection[str], *, now: datetime
) -> dict[str, dict[tuple[int, int], date]]:
    """`media_ids` 裡訂閱著的作品各有哪幾集晚了（季集 → 播出日），同追更頁的「晚 N 天」：過了
    60 天視窗的不算。沒有晚的集的作品不在裡面。`now` 是呼叫端的容器時區現在（時間表的那一支
    時鐘）。"""
    wanted = set(media_ids)
    if not wanted:
        return {}
    fallback = (await read_settings(session, RssSettings)).overdue_days
    found: dict[str, dict[tuple[int, int], date]] = {}
    for media_id, subscriptions in (await watched_works(session)).items():
        media = await session.get(Media, media_id) if media_id in wanted else None
        if media is None:
            continue
        seen = await watch_of(session, media, subscriptions, now=now, fallback=fallback)
        if seen is not None and seen.late and not seen.dormant:
            found[media_id] = {(one.season, one.episode): one.air_date for one in seen.late}
        # 一部要猜好幾個發佈名的季集，一部讓出一次迴圈（同 `read_keeping_up`）。
        await asyncio.sleep(0)
    return found
