"""第一批的「證據夠強」（M4 票 11、`berth.parser.first_batch`）對真資料量一次：擔保了幾筆、
有沒有擔保錯。

三段：

1. **語料**（離線）：`tests/fixtures/parser/{anime,tv}/*.json` 與凍結的 TMDB 快照。每一筆當成某個
   RSS Series 的第一批、Series 沒有季號與 offset。發佈時間用語料自己的；沒有的（舊語料）模擬成
   「期望的最後一集播出後一天」——字幕組照常發佈的樣子。擔保了的逐列對期望比：**擔保錯的必須是 0**。
   模擬的發佈時間照定義就是剛播，所以這一輪量不到「剛播」那一條；另跑一輪**對抗**的：發佈時間改成
   「Berth 自己讀成的那一集播出後一天」——解析器讀錯時，那一集在規則眼裡也是剛播，擋得下的只剩
   照字面與白名單。
2. **split-cour 模擬**（連 TMDB）：TMDB 把兩輪播出合成一季的作品（芙莉蓮、藥師少女），第二輪從 01
   重數、在第二輪第一集播出後一天發佈——不能擔保；第一輪第 3 集剛播時發佈——要擔保。
3. **真的 RSS fixture**（連 TMDB、Mikan）：`air_date_lag.py` 那一套三站 fixture，逐筆照發佈時間
   規劃再問擔不擔保，列出不擔保的那幾筆與它們的理由。沒有標準答案：看的是「一般的每週發佈」有多少
   被擔保、沒被擔保的是不是該問人的那種。

    uv run --env-file .env python scripts/experiments/first_batch_rule.py [--online]

`--online` 才跑第 2、3 段（要 `TMDB_API_KEY`，資料庫是暫時目錄裡的一份新的，跑完就丟）。
"""

from __future__ import annotations

import asyncio
import importlib.util
import itertools
import os
import sys
import tempfile
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import ModuleType

from berth.domain import (
    CollectionType,
    FileEntry,
    MediaSnapshot,
    ParseContext,
    PlanAction,
    PlanItem,
)
from berth.parser import check_airing, episode_span, plan, vouch_first_batch
from berth.services.bench import Fixture, load_corpus, load_snapshot, paths

REPO_ROOT = Path(__file__).resolve().parents[2]


def _vouch(
    name: str, entries: tuple[FileEntry, ...], snapshot: MediaSnapshot, at: datetime
) -> tuple[tuple[PlanItem, ...], tuple[tuple[int, int, int], ...] | None]:
    """規劃時的那一份（解析器 + 播出日比對，RSS Series 送的），再問它擔不擔保。"""
    context = ParseContext(
        media=snapshot, route_collection_type=CollectionType.TVSHOWS, published_at=at
    )
    items = check_airing(plan(name, entries, context), snapshot, at, from_series=True)
    vouched = vouch_first_batch(name, items, snapshot, at, season_hint=None, episode_offset=None)
    return items, vouched


def _codes(items: tuple[PlanItem, ...]) -> str:
    return "; ".join(
        f"{item.action.value}/{item.confidence.value}:"
        + ",".join(reason.code.value for reason in item.reasons)
        for item in items
        if item.action is not PlanAction.SKIP
    )


# --- 1. 語料 --------------------------------------------------------------------------


def _simulated(fixture: Fixture, snapshot: MediaSnapshot) -> datetime | None:
    """期望的最後一集播出後一天。期望裡沒有正片、或 TMDB 沒有那一集的播出日時是 `None`。"""
    last = max(
        (
            (row.season, row.episode_end or row.episode)
            for row in fixture.expected
            if row.action is PlanAction.IMPORT and row.season is not None and row.episode
        ),
        default=None,
    )
    if last is None:
        return None
    found = snapshot.episode(*last)
    if found is None or found.air_date is None:
        return None
    return datetime.combine(found.air_date + timedelta(days=1), datetime.min.time(), UTC)


def _as_read(fixture: Fixture, snapshot: MediaSnapshot) -> datetime | None:
    """Berth 不看發佈時間讀成的最後一集播出後一天（對抗的那一輪）。"""
    context = ParseContext(media=snapshot, route_collection_type=CollectionType.TVSHOWS)
    spans = [
        span
        for item in plan(fixture.torrent_name, fixture.files, context)
        if (span := episode_span(item)) is not None
    ]
    if not spans:
        return None
    season, _, end = max(spans)
    found = snapshot.episode(season, end)
    if found is None or found.air_date is None:
        return None
    return datetime.combine(found.air_date + timedelta(days=1), datetime.min.time(), UTC)


def corpus(*, adversarial: bool = False) -> Counter[str]:
    corpus_root, snapshot_root, _ = paths(REPO_ROOT)
    counts: Counter[str] = Counter()
    for fixture in load_corpus(corpus_root):
        if fixture.category == "movie" or fixture.season_hint or fixture.episode_offset:
            continue
        snapshot = load_snapshot(snapshot_root, fixture.tmdb)
        if adversarial:
            at, kind = _as_read(fixture, snapshot), "as read"
        else:
            at = fixture.published_at or _simulated(fixture, snapshot)
            kind = "real" if fixture.published_at else "simulated"
        if at is None:
            counts["skipped: no episode to date"] += 1
            continue
        items, vouched = _vouch(fixture.torrent_name, fixture.files, snapshot, at)
        if vouched is None:
            counts[f"{kind}: not vouched"] += 1
            print(f"   [no]  {fixture.id}: {_codes(items)[:160]}")
            continue
        expected = {row.path: row for row in fixture.expected}
        wrong = [
            item.rel_path
            for item in items
            if (span := episode_span(item)) is not None
            and (
                (row := expected.get(item.rel_path)) is None
                or span != (row.season, row.episode, row.episode_end or row.episode)
            )
        ]
        counts[f"{kind}: vouched {'WRONG' if wrong else 'correct'}"] += 1
        print(f"   [{'WRONG' if wrong else 'yes'}] {fixture.id}: {vouched} {wrong or ''}")
    return counts


# --- 2. split-cour 模擬 --------------------------------------------------------------


def _day(on: date) -> datetime:
    return datetime.combine(on + timedelta(days=1), datetime.min.time(), UTC)


async def split_cour(session, lag: ModuleType) -> Counter[str]:  # type: ignore[no-untyped-def]  # 一次性腳本，AsyncSession
    counts: Counter[str] = Counter()
    factory = lag.HttpServiceClientFactory()
    for kind, tmdb in lag._SPLIT_COUR_CANDIDATES:
        snapshot = await lag.read_snapshot(session, factory, lag.build_media_id(kind, tmdb))
        season = next(block for block in snapshot.seasons if block.season_number == 1)
        rows = [row for row in season.episodes if row.air_date is not None]
        restart = next(
            (
                later
                for earlier, later in itertools.pairwise(rows)
                if (later.air_date - earlier.air_date).days > 60
            ),
            None,
        )
        name = snapshot.title_en or snapshot.title
        if restart is None or rows[2].air_date is None:
            print(f"   {name}: no second cour on TMDB")
            continue
        entry = (FileEntry(rel_path=f"[Experiment] {name} - 01.mkv", size=1 << 30),)
        _, second = _vouch(f"[Experiment] {name} - 01", entry, snapshot, _day(restart.air_date))
        third = (FileEntry(rel_path=f"[Experiment] {name} - 03.mkv", size=1 << 30),)
        _, first = _vouch(f"[Experiment] {name} - 03", third, snapshot, _day(rows[2].air_date))
        counts["cour-2 restart vouched (must be 0)"] += int(second is not None)
        counts["cour-1 episode vouched"] += int(first is not None)
        print(f"   {name}: cour-2 '- 01' -> {second}; cour-1 '- 03' -> {first}")
    return counts


# --- 3. 真的 RSS fixture --------------------------------------------------------------


async def rss(session, lag: ModuleType) -> Counter[str]:  # type: ignore[no-untyped-def]  # 一次性腳本，AsyncSession
    """`air_date_lag` 那一套認作品與逐筆量測，換成逐筆問擔不擔保。"""
    measurements: list[object] = []
    seen: Counter[str] = Counter()
    factory = lag.HttpServiceClientFactory()
    fetcher = lag.HttpFeedFetcher()
    try:
        for path in (lag.MIKAN_MULTI, lag.MIKAN_SINGLE):
            await lag._process_mikan_feed(session, factory, fetcher, path, {}, seen, measurements)
        titles: dict[str, object] = {}
        for source, folder, parse in (
            ("acgrip", lag.ACGRIP_DIR, lag.acgrip.parse_feed),
            ("nyaa", lag.NYAA_DIR, lag.nyaa.parse_feed),
        ):
            for path in sorted(folder.glob("*.xml")):
                await lag._process_release_feed(
                    session, factory, fetcher, source, path, parse, titles, seen, measurements
                )
    finally:
        await fetcher.aclose()
    counts: Counter[str] = Counter()
    for found in measurements:
        name = found.release_title  # type: ignore[attr-defined]  # air_date_lag.Measurement
        entry = (FileEntry(rel_path=f"{name}.mkv", size=1 << 30),)
        items, vouched = _vouch(name, entry, found.snapshot, found.published_at)  # type: ignore[attr-defined]  # 同上
        counts["vouched" if vouched else "not vouched"] += 1
        if vouched is None:
            print(f"   [no] {name[:70]} pub={found.pub}: {_codes(items)[:140]}")  # type: ignore[attr-defined]  # 同上
    return counts


def _load_lag() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "air_date_lag", REPO_ROOT / "scripts" / "experiments" / "air_date_lag.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclass 找得到自己的模組才建得起來。
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


async def online() -> None:
    from berth.config import load_config
    from berth.db import create_engine, create_session_factory, upgrade_to_head
    from berth.models import TmdbSettings
    from berth.services.settings import write_settings

    key = os.environ.get("TMDB_API_KEY", "")
    if not key:
        print("set TMDB_API_KEY to a TMDB v3 key or v4 token", file=sys.stderr)
        return
    lag = _load_lag()
    with tempfile.TemporaryDirectory() as root:
        config = load_config({"CONFIG_ROOT": f"{root}/config", "DATA_ROOT": f"{root}/data"})
        config.config_root.mkdir(parents=True)
        engine = create_engine(config)
        await upgrade_to_head(engine)
        try:
            async with create_session_factory(engine)() as session:
                await write_settings(session, TmdbSettings(api_key=key))
                print("\n== 2. split-cour ==")
                print(dict(await split_cour(session, lag)))
                print("\n== 3. real RSS fixtures ==")
                print(dict(await rss(session, lag)))
        finally:
            await engine.dispose()


def main() -> int:
    print("== 1. corpus ==")
    print(dict(corpus()))
    print("== 1b. corpus, published right after the episode Berth read ==")
    print(dict(corpus(adversarial=True)))
    if "--online" in sys.argv:
        asyncio.run(online())
    return 0


if __name__ == "__main__":
    sys.exit(main())
