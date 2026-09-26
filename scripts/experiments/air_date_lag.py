"""字幕組發佈相對 TMDB 播出日晚多久，對真的 RSS fixture 與真的 TMDB 量一次（M3 票 14 規則一、二）。

票 14 兩條規則都要一個門檻：規則一的兩天容忍（`RELEASE_TOLERANCE`）已經定案；規則二「對到的
那一集比最近播出的一集早很多」的「很多」（`berth.parser.airing.BEHIND_LATEST`）由這支腳本定：
6 週（2026-09-26 實跑，結果記在票 14 的 Comments）。這支腳本對三個來源（Mikan、acg.rip、Nyaa）的
真實 RSS fixture 逐筆量：

- **lag_days**：`發佈時間.date() - 換算出的那一集的 TMDB 播出日`（規則一要看的數）。
- **behind_days**：`（發佈當下最近播出的一集的播出日） - 換算出的那一集的播出日`（規則二要看的數；
  算法與 `berth.parser.airing._far_behind`/`_latest` 一致：只看 season_number >= 1、播出日不晚於
  發佈日 + 2 天容忍的那些集）。

Mikan 的作品認定重用 `services.rss._auto_bind` 的那一條（`_clues` 讀番組頁、`_candidates` 打
TMDB 搜尋、`parser.binding.judge` 判定）；acg.rip、Nyaa 沒有番組頁，`judge` 一律不給有把握的
`media`，這裡退而求其次：`judge` 的 `candidates`（標題比對後去重）只剩一個時當作那一部作品的量測
依據，不只一個或零個就跳過那個 Series 並算進「跳過」。每個 Series（Mikan 用番組×字幕組、其他用
`parser.binding.title_key`）只查一次 TMDB，量測本身逐筆 RSS Item 都跑。

另外對一部真的 split-cour 作品（葬送的芙莉蓮 TMDB tv:209867，TMDB 把兩輪播出合成一季）模擬一筆
「第二輪重新從 01 編號、且沒設 season/episode offset」的發佈，量出那個情境的 behind_days 有多大
——這是規則二真正要抓的案例（票 14：「新一季被當成第一季...規則一抓不到」）。

**real-rule check**：上面 behind_days 是這支腳本自己照規則二重算的近似值，沒有套「作品在發佈當下
還在連載」那第二個條件（`berth.parser.airing._far_behind`）。這段改對每一筆 mapped 的 item 直接呼叫
真正的 `berth.parser.airing.check_airing`（餵真的 `PlanItem`、`MediaSnapshot`、發佈時間），統計預設
門檻（`BEHIND_LATEST`）下 action 被改成 `review` 的筆數與最後一條 reason 的 code 分布；
再用 monkeypatch（改 `berth.parser.airing.BEHIND_LATEST` 這個模組屬性，不動原始碼）把門檻掃過
28／35／42／56 天，逐一列出每個門檻下被規則二擋下的那幾筆（字幕組、標題、對到的集、matched_air、
最近播出的一集、它的播出日、pub），供人工判斷是算錯還是正常的補檔／慢發。

TMDB 憑證讀環境變數 `TMDB_API_KEY`（v3 key 或 v4 token，`.env.example` 給實驗腳本的那一個），
不印出來；資料庫是暫時目錄裡的一份新的（跑完就丟），不碰任何 Berth 環境。會 import `berth`，
要用 `uv run` 跑：

    uv run --env-file .env python scripts/experiments/air_date_lag.py
"""

from __future__ import annotations

import asyncio
import math
import os
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from berth.adapters.http import ServiceError
from berth.adapters.rss import FeedFetcher, FeedItem, acgrip, mikan, nyaa
from berth.adapters.rss.client import HttpFeedFetcher
from berth.config import load_config
from berth.db import create_engine, create_session_factory, upgrade_to_head
from berth.domain import (
    EpisodeSnapshot,
    FileEntry,
    MediaKind,
    MediaSnapshot,
    ParseContext,
    PlanAction,
    PlanItem,
    ReasonCode,
)
from berth.models import RssSeries, TmdbSettings
from berth.models import media_id as build_media_id
from berth.parser import BEHIND_LATEST, airing, check_airing, episode_span, plan
from berth.parser.binding import judge, title_key
from berth.services.clients import HttpServiceClientFactory, ServiceClientFactory
from berth.services.media import read_snapshot
from berth.services.rss import _candidates, _clues, _LookupError
from berth.services.settings import write_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "http"
MIKAN_MULTI = FIXTURES / "mikan" / "rss-mybangumi.xml"
MIKAN_SINGLE = FIXTURES / "mikan" / "rss-bangumi.4009-370.xml"
ACGRIP_DIR = FIXTURES / "acgrip"
NYAA_DIR = FIXTURES / "nyaa"

#: 帳本那一層猜季集時那一個（中性的）檔案大小：夠大才不會被分類成 sample（`parser.classify`）。
_EPISODE_SIZE = 1 << 30

#: 規則二真正要抓的情境：TMDB 把兩輪播出合成一季，字幕組第二輪從 01 重數。
_SPLIT_COUR_CANDIDATES: tuple[tuple[MediaKind, int], ...] = (
    (MediaKind.TV, 209867),  # 葬送的芙莉蓮 Frieren: Beyond Journey's End
    (MediaKind.TV, 220542),  # 藥屋のひとりごと Kusuriya no Hitorigoto
)

#: 規則二的門檻候選（天）：BEHIND_LATEST 目前是佔位的 6 週 = 42 天（`berth.parser.airing`）。
_THRESHOLDS_DAYS = (14, 21, 28, 35, 42, 56)

#: real-rule check 那段：monkeypatch `berth.parser.airing.BEHIND_LATEST` 逐一掃過的門檻（天）。
_REAL_RULE_THRESHOLDS_DAYS = (28, 35, 42, 56)


@dataclass(frozen=True, slots=True)
class Measurement:
    source: str
    series_title: str
    release_title: str
    season: int
    episode: int
    pub: date
    matched_air: date | None
    lag_days: int | None
    latest_label: str
    behind_days: int | None
    #: real-rule check 那段要重跑 `check_airing`，得留住真的 PlanItem/快照/完整發佈時間。
    plan_item: PlanItem
    snapshot: MediaSnapshot
    published_at: datetime


def trunc(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _air_date(snapshot: MediaSnapshot, season: int, episode: int) -> date | None:
    found = next(
        (
            row
            for block in snapshot.seasons
            if block.season_number == season
            for row in block.episodes
            if row.episode_number == episode
        ),
        None,
    )
    return found.air_date if found is not None else None


def _latest_aired(snapshot: MediaSnapshot, pub: date) -> tuple[int, int, date] | None:
    """`pub` 當下最近播出的一集（regular season，播出日 <= pub + 2 天）。

    與 `berth.parser.airing._latest` 同規則（私有函式讀不到，這裡照規則重寫一份）。
    """
    cutoff = pub + timedelta(days=2)
    best: tuple[int, int, date] | None = None
    for block in snapshot.seasons:
        if block.season_number < 1:
            continue
        for row in block.episodes:
            if row.air_date is None or row.air_date > cutoff:
                continue
            if best is None or row.air_date > best[2]:
                best = (block.season_number, row.episode_number, row.air_date)
    return best


@dataclass(frozen=True, slots=True)
class _Evaluation:
    item: PlanItem
    is_batch: bool
    season: int
    episode: int
    matched_air: date | None
    lag_days: int | None
    latest_label: str
    behind_days: int | None


def _evaluate(
    snapshot: MediaSnapshot, release_title: str, pub: date, *, season_hint: int | None = None
) -> _Evaluation | None:
    """真的跑一次解析器，量出這一筆發佈對它換算出的那一集的 lag/behind。沒配對到集數是 `None`。"""
    entry = FileEntry(rel_path=release_title + ".mkv", size=_EPISODE_SIZE)
    context = ParseContext(media=snapshot, season_hint=season_hint)
    (item,) = plan(release_title, (entry,), context)
    span = episode_span(item)
    if span is None:
        return None
    season, start, end = span
    episode = end
    matched_air = _air_date(snapshot, season, episode)
    lag_days = (pub - matched_air).days if matched_air is not None else None
    latest = _latest_aired(snapshot, pub)
    latest_label = f"S{latest[0]:02d}E{latest[1]:02d}@{latest[2]}" if latest is not None else "n/a"
    behind_days = (
        (latest[2] - matched_air).days if latest is not None and matched_air is not None else None
    )
    return _Evaluation(
        item, start != end, season, episode, matched_air, lag_days, latest_label, behind_days
    )


def _record(
    snapshot: MediaSnapshot,
    source: str,
    series_title: str,
    release_title: str,
    published_at: datetime,
    counts: Counter[str],
    measurements: list[Measurement],
) -> None:
    pub = published_at.date()
    result = _evaluate(snapshot, release_title, pub)
    if result is None:
        counts["skipped: parser gave no match"] += 1
        return
    if result.is_batch:
        counts["skipped: batch/range (>1 episode)"] += 1
        return
    if result.matched_air is None:
        counts["no air date"] += 1
    counts["mapped"] += 1
    measurements.append(
        Measurement(
            source,
            series_title,
            release_title,
            result.season,
            result.episode,
            pub,
            result.matched_air,
            result.lag_days,
            result.latest_label,
            result.behind_days,
            result.item,
            snapshot,
            published_at,
        )
    )
    lag_label = f"{result.lag_days:+d}d" if result.lag_days is not None else "n/a"
    behind_label = f"{result.behind_days}d" if result.behind_days is not None else "n/a"
    print(
        f"   [{source}] {trunc(series_title, 22):22s} | {trunc(release_title, 58):58s} "
        f"| S{result.season:02d}E{result.episode:02d} pub={pub} air={result.matched_air} "
        f"lag={lag_label:>6s} latest={result.latest_label:<18s} behind={behind_label}"
    )


async def _process_mikan_feed(  # type: ignore[no-untyped-def]  # 一次性腳本，AsyncSession
    session,
    factory: ServiceClientFactory,
    fetcher: FeedFetcher,
    path: Path,
    series_cache: dict[tuple[int, int], MediaSnapshot | None],
    counts: Counter[str],
    measurements: list[Measurement],
) -> None:
    items = mikan.parse_feed(path.read_bytes())
    print(f"\n--- mikan feed: {path.name} ({len(items)} items) ---")
    for item in reversed(items):
        counts["total"] += 1
        if item.published_at is None:
            counts["skipped: no published_at"] += 1
            continue
        try:
            page = (await fetcher.fetch(item.link)).decode("utf-8", errors="replace")
        except ServiceError as exc:
            counts["skipped: mikan episode page fetch failed"] += 1
            print(f"   [skip] episode page fetch failed for {item.title!r}: {exc}")
            continue
        pair = mikan.series_key(page)
        if pair is None:
            counts["skipped: no series_key on episode page"] += 1
            continue
        if pair not in series_cache:
            series_cache[pair] = await _resolve_mikan_series(session, factory, fetcher, pair, item)
        snapshot = series_cache[pair]
        if snapshot is None:
            counts["skipped: series not resolved to tmdb"] += 1
            continue
        _record(
            snapshot,
            "mikan",
            snapshot.title_en or snapshot.title,
            item.title,
            item.published_at,
            counts,
            measurements,
        )


async def _resolve_mikan_series(  # type: ignore[no-untyped-def]  # 一次性腳本，AsyncSession
    session,
    factory: ServiceClientFactory,
    fetcher: FeedFetcher,
    pair: tuple[int, int],
    item: FeedItem,
) -> MediaSnapshot | None:
    series = RssSeries(
        key=f"mikan:{pair[0]}:{pair[1]}",
        mikan_bangumi_id=pair[0],
        mikan_subgroup_id=pair[1],
        title_raw=item.title,
    )
    try:
        clues = await _clues(fetcher, series)
        shots, _ = await _candidates(session, factory, clues)
    except _LookupError as failed:
        print(f"   [series lookup failed] {pair}: {failed}")
        return None
    verdict = judge(clues, shots)
    if verdict.media is not None:
        print(f"   [series bound] {pair} {clues.title!r} -> {verdict.media.title_en!r}")
        return verdict.media
    if len(verdict.candidates) == 1:
        only = verdict.candidates[0]
        print(f"   [series single candidate] {pair} {clues.title!r} -> {only.title_en!r}")
        return only
    print(f"   [series unresolved] {pair} {clues.title!r}: {len(verdict.candidates)} candidates")
    return None


async def _process_release_feed(  # type: ignore[no-untyped-def]  # 一次性腳本，AsyncSession
    session,
    factory: ServiceClientFactory,
    fetcher: FeedFetcher,
    source: str,
    path: Path,
    parse_feed: Callable[[bytes], tuple[FeedItem, ...]],
    series_cache: dict[str, MediaSnapshot | None],
    counts: Counter[str],
    measurements: list[Measurement],
) -> None:
    items = parse_feed(path.read_bytes())
    print(f"\n--- {source} feed: {path.name} ({len(items)} items) ---")
    for item in reversed(items):
        counts["total"] += 1
        if item.published_at is None:
            counts["skipped: no published_at"] += 1
            continue
        key = title_key(item.title)
        if key is None:
            counts["skipped: no title_key"] += 1
            continue
        if key not in series_cache:
            series_cache[key] = await _resolve_title_series(session, factory, fetcher, key, item)
        snapshot = series_cache[key]
        if snapshot is None:
            counts["skipped: series not resolved to tmdb (no show page)"] += 1
            continue
        _record(
            snapshot,
            source,
            snapshot.title_en or snapshot.title,
            item.title,
            item.published_at,
            counts,
            measurements,
        )


async def _resolve_title_series(  # type: ignore[no-untyped-def]  # 一次性腳本，AsyncSession
    session,
    factory: ServiceClientFactory,
    fetcher: FeedFetcher,
    key: str,
    item: FeedItem,
) -> MediaSnapshot | None:
    """非 Mikan 沒有番組頁：`judge` 一律不給有把握的 `media`，剩一個候選才當量測依據。"""
    series = RssSeries(key=key, mikan_bangumi_id=None, mikan_subgroup_id=None, title_raw=item.title)
    clues = await _clues(fetcher, series)
    try:
        shots, _ = await _candidates(session, factory, clues)
    except _LookupError as failed:
        print(f"   [series lookup failed] {key}: {failed}")
        return None
    verdict = judge(clues, shots)
    if len(verdict.candidates) == 1:
        print(f"   [series single candidate] {key} -> {verdict.candidates[0].title_en!r}")
        return verdict.candidates[0]
    if not verdict.candidates:
        print(f"   [series unresolved] {key}: no title match")
    else:
        print(f"   [series unresolved] {key}: {len(verdict.candidates)} ambiguous title matches")
    return None


def _percentile(values: Sequence[int], pct: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * pct / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[int(position)])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _print_distribution(label: str, values: Sequence[int]) -> None:
    if not values:
        print(f"{label}: (no data)")
        return
    print(
        f"{label}: n={len(values)} min={min(values)} p50={_percentile(values, 50):.1f} "
        f"p90={_percentile(values, 90):.1f} p95={_percentile(values, 95):.1f} max={max(values)}"
    )


def _print_summary(counts: Counter[str], measurements: list[Measurement]) -> None:
    print("\n\n=== summary ===")
    print(f"items total: {counts['total']}")
    print(f"mapped (has season/episode, not batch): {counts['mapped']}")
    print(f"no air date among mapped: {counts['no air date']}")
    print("skipped, by reason:")
    for reason, n in sorted(
        ((k, v) for k, v in counts.items() if k.startswith("skipped")), key=lambda kv: -kv[1]
    ):
        print(f"   {reason}: {n}")

    lag_values = [m.lag_days for m in measurements if m.lag_days is not None]
    behind_values = [m.behind_days for m in measurements if m.behind_days is not None]

    print("\n--- lag_days (規則一：pub - matched_air) ---")
    _print_distribution("lag_days", lag_values)
    outliers = [
        m for m in measurements if m.lag_days is not None and (m.lag_days < -2 or m.lag_days > 21)
    ]
    print(f"items with lag_days < -2 or > 21: {len(outliers)}")
    for m in outliers:
        print(
            f"   [{m.source}] {trunc(m.series_title, 22)} | {trunc(m.release_title, 58)} "
            f"S{m.season:02d}E{m.episode:02d} pub={m.pub} air={m.matched_air} lag={m.lag_days:+d}d"
        )

    print("\n--- behind_days (規則二：latest_aired - matched_air) ---")
    _print_distribution("behind_days", behind_values)
    for threshold in _THRESHOLDS_DAYS:
        n = sum(1 for v in behind_values if v > threshold)
        print(f"   flagged at behind_days > {threshold}d: {n}")


def _reason_code(item: PlanItem) -> str:
    """`item.reasons` 最後一條的 code：`check_airing` 這次呼叫如果有加新理由一定在最後一個。"""
    return str(item.reasons[-1].code) if item.reasons else "(none)"


def _print_real_rule_check(measurements: list[Measurement]) -> None:
    """對每一筆 mapped 的 item 直接呼叫真正的 `berth.parser.airing.check_airing`（非近似版）。"""
    print("\n\n=== real-rule check（直接呼叫 berth.parser.airing.check_airing） ===")
    print(f"BEHIND_LATEST（預設、未 patch）: {BEHIND_LATEST}")
    reviewed = 0
    reason_counts: Counter[str] = Counter()
    for m in measurements:
        (checked,) = check_airing((m.plan_item,), m.snapshot, m.published_at, from_series=True)
        if checked.action != PlanAction.REVIEW:
            continue
        reviewed += 1
        reason_counts[_reason_code(checked)] += 1
    print(f"mapped items fed into check_airing: {len(measurements)}")
    print(f"action -> review: {reviewed}")
    for code, n in reason_counts.most_common():
        print(f"   {code}: {n}")

    print(
        "\n--- BEHIND_LATEST 門檻掃描（規則二；monkeypatch berth.parser.airing.BEHIND_LATEST） ---"
    )
    # 門檻自 M3 票 16 起住在 `parser.publishing`；`check_airing` 讀的是 airing 自己
    # import 進來的那個名字，所以換 airing 模組裡的那一個（`vars()`：它不是公開屬性）。
    original = BEHIND_LATEST
    try:
        for days in _REAL_RULE_THRESHOLDS_DAYS:
            vars(airing)["BEHIND_LATEST"] = timedelta(days=days)
            flagged: list[tuple[Measurement, PlanItem]] = []
            for m in measurements:
                (checked,) = check_airing(
                    (m.plan_item,), m.snapshot, m.published_at, from_series=True
                )
                held_by_rule2 = (
                    checked.action == PlanAction.REVIEW
                    and checked.reasons
                    and checked.reasons[-1].code == ReasonCode.BEHIND_LATEST_EPISODE
                )
                if held_by_rule2:
                    flagged.append((m, checked))
            print(f"\n   BEHIND_LATEST={days}d: flagged by rule 2 = {len(flagged)}")
            for m, checked in flagged:
                params = checked.reasons[-1].params
                group = m.plan_item.tags.group or "(no group)"
                print(
                    f"      [{m.source}] group={group:14s} {trunc(m.release_title, 50):50s} "
                    f"matched={params.get('episode')} matched_air={params.get('aired')} "
                    f"latest={params.get('latest')} latest_aired={params.get('latest_aired')} "
                    f"pub={m.pub}"
                )
    finally:
        vars(airing)["BEHIND_LATEST"] = original


def _cour_boundary(episodes: Sequence[EpisodeSnapshot]) -> tuple[int, int] | None:
    """季內相鄰兩集播出日差距最大、且超過 30 天的那個切點：回傳（第二輪第一集的 index, 差幾天）。"""
    best: tuple[int, int] | None = None
    for i in range(1, len(episodes)):
        prev, curr = episodes[i - 1].air_date, episodes[i].air_date
        if prev is None or curr is None:
            continue
        gap = (curr - prev).days
        if gap > 30 and (best is None or gap > best[1]):
            best = (i, gap)
    return best


async def _split_cour(  # type: ignore[no-untyped-def]  # 一次性腳本，AsyncSession
    session,
    factory: ServiceClientFactory,
) -> None:
    print("\n\n=== split-cour simulation（規則二真正要抓的情境） ===")
    for kind, tmdb_id in _SPLIT_COUR_CANDIDATES:
        target_id = build_media_id(kind, tmdb_id)
        snapshot = await read_snapshot(session, factory, target_id)
        if snapshot is None:
            print(f"   {target_id}: 讀不到，換下一個候選")
            continue
        print(
            f"   verified snapshot: tmdb {kind.value}:{tmdb_id} "
            f"title={snapshot.title_en!r} ({snapshot.title!r})"
        )
        season1 = next((s for s in snapshot.seasons if s.season_number == 1), None)
        if season1 is None or len(season1.episodes) < 2:
            print(f"   {target_id}: season 1 缺或集數太少，換下一個候選")
            continue
        episodes = sorted(season1.episodes, key=lambda e: e.episode_number)
        boundary = _cour_boundary(episodes)
        if boundary is None:
            print(f"   {target_id}: season 1 裡沒有 >30 天的缺口，換下一個候選")
            continue
        index, gap_days = boundary
        cour2_first = episodes[index]
        if cour2_first.air_date is None:
            print(f"   {target_id}: 缺口那一集沒有播出日，換下一個候選")
            continue
        _run_split_cour(snapshot, episodes[0], cour2_first, gap_days, cour2_first.air_date)
        return
    print("   沒有一個候選可用，split-cour 這段量不出來")


def _run_split_cour(
    snapshot: MediaSnapshot,
    cour1_first: EpisodeSnapshot,
    cour2_first: EpisodeSnapshot,
    gap_days: int,
    pub: date,
) -> None:
    print(f"   cour1 starts S01E{cour1_first.episode_number:02d} air={cour1_first.air_date}")
    print(
        f"   cour2 starts S01E{cour2_first.episode_number:02d} "
        f"air={cour2_first.air_date}  (gap={gap_days}d)"
    )

    release_title = f"[Experiment] {snapshot.title_en} - 01 [1080p][simulated cour-2 restart]"
    result = _evaluate(snapshot, release_title, pub, season_hint=1)
    print(f"   release title: {release_title!r}")
    print(f"   simulated pub date (= cour2 ep1 真實播出日): {pub}")
    if result is None:
        print("   解析器沒有配對到任何集數，模擬失敗")
        return
    print(
        f"   parser mapped to: S{result.season:02d}E{result.episode:02d}  (batch={result.is_batch})"
    )
    print(f"   matched episode 真實 air_date: {result.matched_air}")
    print(f"   lag_days: {result.lag_days}")
    print(f"   latest aired by pub+2d: {result.latest_label}")
    print(f"   behind_days: {result.behind_days}")


async def measure(session) -> None:  # type: ignore[no-untyped-def]  # 一次性腳本，AsyncSession
    factory = HttpServiceClientFactory()
    fetcher = HttpFeedFetcher()
    counts: Counter[str] = Counter()
    measurements: list[Measurement] = []
    mikan_cache: dict[tuple[int, int], MediaSnapshot | None] = {}
    title_cache: dict[str, MediaSnapshot | None] = {}
    try:
        await _process_mikan_feed(
            session, factory, fetcher, MIKAN_MULTI, mikan_cache, counts, measurements
        )
        await _process_mikan_feed(
            session, factory, fetcher, MIKAN_SINGLE, mikan_cache, counts, measurements
        )
        for path in sorted(ACGRIP_DIR.glob("*.xml")):
            await _process_release_feed(
                session,
                factory,
                fetcher,
                "acgrip",
                path,
                acgrip.parse_feed,
                title_cache,
                counts,
                measurements,
            )
        for path in sorted(NYAA_DIR.glob("*.xml")):
            await _process_release_feed(
                session,
                factory,
                fetcher,
                "nyaa",
                path,
                nyaa.parse_feed,
                title_cache,
                counts,
                measurements,
            )
    finally:
        await fetcher.aclose()
    _print_summary(counts, measurements)
    _print_real_rule_check(measurements)
    await _split_cour(session, factory)


async def main() -> int:
    key = os.environ.get("TMDB_API_KEY", "")
    if not key:
        print("set TMDB_API_KEY to a TMDB v3 key or v4 token", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as root:
        config = load_config({"CONFIG_ROOT": f"{root}/config", "DATA_ROOT": f"{root}/data"})
        config.config_root.mkdir(parents=True)
        engine = create_engine(config)
        await upgrade_to_head(engine)
        try:
            async with create_session_factory(engine)() as session:
                await write_settings(session, TmdbSettings(api_key=key))
                await measure(session)
        finally:
            await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
