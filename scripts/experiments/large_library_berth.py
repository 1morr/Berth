"""M2 票 11：1,000 部的媒體庫上量 Berth——跑在容器裡的那一半。

宿主那一半是 `large_library.py`（起停容器、Jellyfin 精靈、建媒體庫、等掃描）。這一支由它以
`docker run` 在 Berth 的 image 裡跑，與 Jellyfin、qBittorrent 在同一個 docker network、同一個
`/data` volume 上——**帳本的路徑要與 Jellyfin 回報的 `Path` 一字不差**（brief §20.1），所以
Berth 這一端不能跑在 Windows 宿主上。

兩個子命令：

- `tree`：造媒體樹。每部一包 complete 目錄（12 集各自一個 inode），硬鏈接進
  `/data/library/tv/<作品> (<年>) [tmdbid-N]/Season 01/`，與 Berth 入庫的形狀相同；順手寫好
  qBittorrent 的免密白名單。
- `measure`：灌資料（觀看紀錄、1,000 個 torrent、Berth 的資料庫）之後量票上的五件與兩條門檻，
  JSON 寫到 `/out/large-library.json`。

它量的是 Berth 自己，所以 import `berth`（同 `jellyfin_images.py`）。
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import cProfile
import io
import math
import os
import pstats
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from lib import Report, Response, make_torrent, multipart, poll, request

from berth.adapters.http import ServiceError
from berth.adapters.jellyfin.client import HttpJellyfinClient
from berth.config import load_config
from berth.db import create_engine, create_session_factory, upgrade_to_head
from berth.domain import (
    CollectionType,
    EpisodeSnapshot,
    JobState,
    JobTrigger,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    SeasonSnapshot,
)
from berth.models import (
    JellyfinSettings,
    Job,
    LedgerEntry,
    Media,
    PathSettings,
    QbittorrentSettings,
    Route,
    SetupSettings,
    media_id,
)
from berth.services import inventory as inventory_service
from berth.services.clients import HttpServiceClientFactory
from berth.services.jellyfin_access import (
    ACCESS_TTL_SECONDS,
    BrowsableLibrary,
    JellyfinAccess,
    WallQuery,
)
from berth.services.reconcile import Progress, SideReport, reconcile_once
from berth.services.resolver import sweep_resolutions
from berth.services.settings import read_settings, write_settings

DATA = Path("/data")
SEED = DATA / "seed.mkv"
COMPLETE = DATA / "complete"
LIBRARY = DATA / "library"
CATEGORY = "tv"
RELEASES = COMPLETE / CATEGORY
TV = LIBRARY / "tv"
#: 容器裡的一次性目錄，跑完容器就沒了。
CONFIG = Path("/tmp/berth-config")
BERTH_PORT = 8383
PASSWORD = "berth-experiment-2026"
VIEWER = "viewer"
GONE = "gone"
TICKS_PER_MINUTE = 60 * 10_000_000
#: 1,000 部、每部一季 12 集（一個動畫季度）。電影庫不另外造：每部一個 item，比劇集輕
#: （劇集的 `UnplayedItemCount` 要數底下的集、`MediaSources` 是 12 倍的列）。
SERIES = 1000
EPISODES = 12
#: 門檻（票 11、plan §11.3 決定 2）。
INVENTORY_P95_LIMIT_MS = 1000
RECONCILE_LIMIT_S = 600


# --- 媒體樹 --------------------------------------------------------------------


@dataclass(frozen=True)
class Work:
    number: int

    @property
    def title(self) -> str:
        return f"Harbor Series {self.number:04d}"

    @property
    def year(self) -> int:
        return 1990 + self.number % 35

    @property
    def tmdb(self) -> int:
        return 900_000 + self.number

    @property
    def folder(self) -> str:
        return f"{self.title} ({self.year}) [tmdbid-{self.tmdb}]"

    @property
    def release(self) -> str:
        return f"[Berth Exp] {self.title} S01 [1080p]"

    def source_name(self, episode: int) -> str:
        return f"[Berth Exp] {self.title} - {episode:02d} [1080p].mkv"

    def target(self, episode: int) -> Path:
        name = f"{self.title} ({self.year}) - S01E{episode:02d}.mkv"
        return TV / self.folder / "Season 01" / name

    def source(self, episode: int) -> Path:
        return RELEASES / self.release / self.source_name(episode)


def works(count: int) -> list[Work]:
    return [Work(number) for number in range(1, count + 1)]


QBITTORRENT_CONF = """[AutoRun]
enabled=false
program=

[LegalNotice]
Accepted=true

[Preferences]
Connection\\UPnP=false
Connection\\PortRangeMin=6881
Downloads\\SavePath=/data/complete/
Downloads\\TempPath=/data/incomplete/
WebUI\\Address=*
WebUI\\ServerDomains=*
WebUI\\AuthSubnetWhitelistEnabled=true
WebUI\\AuthSubnetWhitelist=__SUBNET__
"""


def build_tree(series: int, episodes: int, subnet: str) -> None:
    """每一集一個 inode（complete 那一份），媒體庫那一份是它的硬鏈接——Berth 入庫的樣子。"""
    if not SEED.is_file():
        raise SystemExit(f"{SEED} 不在：宿主那一半要先用 Jellyfin 的 ffmpeg 產生它")
    started = time.perf_counter()
    for work in works(series):
        (RELEASES / work.release).mkdir(parents=True, exist_ok=True)
        work.target(1).parent.mkdir(parents=True, exist_ok=True)
        for episode in range(1, episodes + 1):
            source = work.source(episode)
            if not source.exists():
                shutil.copyfile(SEED, source)
            target = work.target(episode)
            if not target.exists():
                os.link(source, target)
    conf = Path("/qbconfig/qBittorrent/qBittorrent.conf")
    conf.parent.mkdir(parents=True, exist_ok=True)
    conf.write_text(QBITTORRENT_CONF.replace("__SUBNET__", subnet), "utf-8")
    elapsed = time.perf_counter() - started
    print(f"媒體樹：{series} 部 × {episodes} 集，{elapsed:.1f} 秒", flush=True)


# --- 量測工具 ------------------------------------------------------------------


def percentile(values: list[float], q: float) -> float:
    """nearest-rank：第 ceil(q·n) 小的那一個。n=20 的 p95 是第 19 個。"""
    ranked = sorted(values)
    return ranked[max(0, math.ceil(q * len(ranked)) - 1)]


def summary(latencies: list[float]) -> dict[str, float]:
    return {
        "p50_ms": round(percentile(latencies, 0.5), 1),
        "p95_ms": round(percentile(latencies, 0.95), 1),
        "max_ms": round(max(latencies), 1),
    }


#: 量測中 Jellyfin 斷線的次數與原文。2026-09-23 在 Docker Desktop 上兩次看到 Jellyfin 12.1.0 的
#: 程序無聲地結束又被 s6 拉起來（核心沒有 OOM、Jellyfin 的 log 沒有錯誤，同一個請求單獨重打
#: 不重現）；那一次不計入延遲，重打一次，次數寫進報告。
DROPPED: list[str] = []


def attempt(fetch: Callable[[], Response]) -> Response:
    for tries in range(3):
        try:
            return fetch()
        except OSError as exc:
            DROPPED.append(f"{type(exc).__name__}: {exc}")
            if tries == 2:
                raise
            time.sleep(20)  # Jellyfin 重新起來約 5 秒；多等一點讓它把媒體庫載完
    raise AssertionError("unreachable")


def sample(fetch: Callable[[], Response], repeats: int) -> dict[str, Any]:
    """同一個請求依序打 `repeats` 次（先熱一次，不計）。筆數與位元組取最後一次。"""
    attempt(fetch)
    latencies: list[float] = []
    last: Response | None = None
    for _ in range(repeats):
        started = time.perf_counter()
        try:
            last = fetch()
        except OSError as exc:
            DROPPED.append(f"{type(exc).__name__}: {exc}")
            time.sleep(20)
            continue
        latencies.append((time.perf_counter() - started) * 1000)
    assert last is not None
    payload = last.json() if last.ok else None
    rows = payload.get("Items") if isinstance(payload, dict) else None
    return {
        "status": last.status,
        "count": len(rows) if isinstance(rows, list) else None,
        "total": payload.get("TotalRecordCount") if isinstance(payload, dict) else None,
        "bytes": len(last.body),
        "repeats": repeats,
        **summary(latencies),
    }


class Jellyfin:
    """API key 直打 Jellyfin。參數照 Berth 的 adapter 抄，量到的才是 Berth 會付的代價。"""

    def __init__(self, base: str, api_key: str) -> None:
        self.base = base.rstrip("/")
        parts = 'Client="Berth-Experiment", Device="script", DeviceId="berth-exp-large"'
        self.headers = {
            "Authorization": f'MediaBrowser {parts}, Version="0.1.0", Token="{api_key}"'
        }

    def get(self, path: str, params: dict[str, str] | None = None) -> Response:
        return request(f"{self.base}{path}", headers=self.headers, params=params, timeout=600)

    def send(
        self, method: str, path: str, *, params: dict[str, str] | None = None, body: Any = None
    ) -> Response:
        return request(
            f"{self.base}{path}",
            method=method,
            headers=self.headers,
            params=params,
            json_body=body,
            timeout=600,
        )

    def ok(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = self.send(method, path, **kwargs)
        if not resp.ok:
            raise RuntimeError(f"{method} {path} -> {resp.status} {resp.text[:300]}")
        return resp.json()


def library_index(user_id: str, library_id: str, *, user_data: bool) -> dict[str, str]:
    """`HttpJellyfinClient.library_index` 的參數；`user_data=True` 是票 14 想要的那一種。"""
    return {
        "userId": user_id,
        "parentId": library_id,
        "recursive": "true",
        "includeItemTypes": "Series",
        "fields": "ProviderIds",
        "imageTypeLimit": "1",
        "enableImageTypes": "Primary",
        "enableUserData": "true" if user_data else "false",
        "enableTotalRecordCount": "false",
    }


def library_page(user_id: str, library_id: str, start: int) -> dict[str, str]:
    """`HttpJellyfinClient.library_page`：牆的一頁，帶觀看紀錄（伺服器預設）。"""
    return {
        "userId": user_id,
        "parentId": library_id,
        "recursive": "true",
        "includeItemTypes": "Series",
        "sortBy": "SortName",
        "sortOrder": "Ascending",
        "fields": "PrimaryImageAspectRatio,ProviderIds,Path",
        "imageTypeLimit": "1",
        "enableImageTypes": "Primary,Backdrop,Thumb",
        "startIndex": str(start),
        "limit": "100",
    }


def with_sources(library_id: str, item_type: str) -> dict[str, str]:
    """`HttpJellyfinClient.items`：反查與對帳用的那一支，整份 `MediaSources`、不帶 `userId`。"""
    return {
        "parentId": library_id,
        "recursive": "true",
        "includeItemTypes": item_type,
        "fields": "Path,ProviderIds,MediaSources",
    }


# --- 灌資料 --------------------------------------------------------------------


def seed_watch(jf: Jellyfin, library_id: str, viewer: str) -> dict[str, int]:
    """觀看紀錄照真實的比例撒：四部裡一部看過前三集、十部裡一部整部看完、二十部裡一部看到一半。
    沒有紀錄的話 `UnplayedItemCount` 那一段算不出真的代價。"""
    rows = jf.ok(
        "GET",
        "/Items",
        params={
            "parentId": library_id,
            "recursive": "true",
            "includeItemTypes": "Episode",
            "fields": "",
            "enableImages": "false",
            "enableUserData": "false",
        },
    )["Items"]
    by_series: dict[str, dict[int, str]] = {}
    for row in rows:
        by_series.setdefault(row["SeriesId"], {})[int(row.get("IndexNumber") or 0)] = row["Id"]
    counts = {"episodes_played": 0, "series_played": 0, "in_progress": 0}
    user = {"userId": viewer}
    for index, series_id in enumerate(sorted(by_series)):
        episodes = by_series[series_id]
        if index % 4 == 0:
            for number in (1, 2, 3):
                jf.ok("POST", f"/UserPlayedItems/{episodes[number]}", params=user)
                counts["episodes_played"] += 1
        elif index % 10 == 1:
            jf.ok("POST", f"/UserPlayedItems/{series_id}", params=user)
            counts["series_played"] += 1
        elif index % 20 == 2:
            body = {"PlaybackPositionTicks": 7 * TICKS_PER_MINUTE}
            jf.ok("POST", f"/UserItems/{episodes[1]}/UserData", params=user, body=body)
            counts["in_progress"] += 1
    return counts


def seed_torrents(base: str, targets: list[Work], episodes: int) -> dict[str, str]:
    """每部一個 torrent，停著、跳過校驗：qBittorrent 認得 complete 裡的那一包，
    `orphan_complete` 與 `unknown_torrent` 才比得到真的東西。回傳 release → info hash。"""
    size = SEED.stat().st_size
    request(
        f"{base}/api/v2/torrents/createCategory",
        method="POST",
        form={"category": CATEGORY, "savePath": str(RELEASES)},
    )
    hashes: dict[str, str] = {}
    for work in targets:
        files = [(work.source_name(episode), size) for episode in range(1, episodes + 1)]
        torrent = make_torrent(work.release, files, salt=str(work.number))
        fields = {
            "savepath": str(RELEASES),
            "category": CATEGORY,
            "stopped": "true",
            "paused": "true",
            "skip_checking": "true",
        }
        body, content_type = multipart(
            fields, {"torrents": (f"{work.number}.torrent", torrent.raw)}
        )
        resp = request(
            f"{base}/api/v2/torrents/add",
            method="POST",
            body=body,
            content_type=content_type,
            timeout=60,
        )
        # 409：上一輪（`--reuse`）已經加過同一個 hash。
        if not resp.ok and resp.status != 409:
            raise RuntimeError(f"torrents/add {work.release}: {resp.status} {resp.text[:200]}")
        hashes[work.release] = torrent.info_hash
    return hashes


def snapshot(work: Work, episodes: int) -> dict[str, Any]:
    aired = date(2020, 1, 5)
    season = SeasonSnapshot(
        season_number=1,
        name="Season 1",
        names=("Season 1",),
        episode_count=episodes,
        air_date=aired,
        episodes=tuple(
            EpisodeSnapshot(
                episode_number=n, name=f"Episode {n}", air_date=aired + timedelta(n * 7)
            )
            for n in range(1, episodes + 1)
        ),
    )
    return MediaSnapshot(
        tmdb_id=work.tmdb,
        kind=MediaKind.TV,
        title=work.title,
        title_en=work.title,
        title_original=work.title,
        year=work.year,
        first_air_date=aired,
        titles=(work.title,),
        seasons=(season,),
    ).model_dump(mode="json")


def ledger_entry(work: Work, episode: int, job_hash: str, now: datetime) -> LedgerEntry:
    source, target = work.source(episode), work.target(episode)
    facts = source.stat()
    return LedgerEntry(
        job_hash=job_hash,
        source_rel_path=f"{work.release}/{source.name}",
        source_abs_path=str(source),
        source_inode=str(facts.st_ino),
        source_dev=str(facts.st_dev),
        target_path=str(target),
        target_inode=str(target.stat().st_ino),
        media_id=media_id(MediaKind.TV, work.tmdb),
        season=1,
        episode_start=episode,
        episode_end=episode,
        action=PlanAction.IMPORT,
        resolve_after=now,
    )


async def seed_berth(
    jellyfin: str,
    api_key: str,
    qbittorrent: str,
    library_id: str,
    hashes: dict[str, str],
    targets: list[Work],
    episodes: int,
) -> None:
    """精靈跑完、一條 Route、1,000 部作品各一筆已入庫的 Job 與 12 列帳本。

    帳本的 Jellyfin id 留空、`resolve_after` 是現在：之後跑一輪真的反查把它們填上
    （順便量反查在這個規模上的代價）。
    """
    shutil.rmtree(CONFIG, ignore_errors=True)
    config = load_config({"CONFIG_ROOT": str(CONFIG), "DATA_ROOT": str(DATA)})
    config.config_root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config)
    await upgrade_to_head(engine)
    now = datetime.now(UTC)
    async with create_session_factory(engine)() as session:
        await write_settings(session, JellyfinSettings(base_url=jellyfin, api_key=api_key))
        await write_settings(session, QbittorrentSettings(base_url=qbittorrent))
        await write_settings(
            session,
            PathSettings(
                complete_root=str(COMPLETE),
                incomplete_root=str(DATA / "incomplete"),
                library_root=str(LIBRARY),
            ),
        )
        setup = await read_settings(session, SetupSettings)
        setup.completed = True
        await write_settings(session, setup)
        route = Route(
            slug="tv",
            name="TV",
            jellyfin_library_id=library_id,
            jellyfin_library_name="TV",
            collection_type=CollectionType.TVSHOWS,
            target_path=str(TV),
            category=CATEGORY,
        )
        session.add(route)
        await session.flush()
        # 三批各自 flush：這幾個 model 之間沒有 relationship，SQLAlchemy 不保證插入順序，
        # 而 `jobs.media_id` 與帳本的 `media_id` 都有外鍵。
        session.add_all(
            Media(
                id=media_id(MediaKind.TV, work.tmdb),
                tmdb_id=work.tmdb,
                kind=MediaKind.TV,
                title_en=work.title,
                title_original=work.title,
                year=work.year,
                folder_name=work.folder,
                folder_frozen=True,
                tmdb_snapshot_json=snapshot(work, episodes),
                tmdb_fetched_at=now,
            )
            for work in targets
        )
        await session.flush()
        session.add_all(
            Job(
                hash=hashes[work.release],
                name=work.release,
                trigger=JobTrigger.MANUAL,
                media_id=media_id(MediaKind.TV, work.tmdb),
                route_id=route.id,
                state=JobState.IMPORTED,
                save_path=str(RELEASES),
                content_path=str(RELEASES / work.release),
                progress=1.0,
                completed_at=now,
                imported_at=now,
            )
            for work in targets
        )
        await session.flush()
        session.add_all(
            ledger_entry(work, episode, hashes[work.release], now)
            for work in targets
            for episode in range(1, episodes + 1)
        )
        await session.commit()
    await engine.dispose()


# --- Berth 的 HTTP 那一面 --------------------------------------------------------


@contextlib.contextmanager
def berth_serve() -> Iterator[str]:
    """`berth serve` 另起一個程序（同 `jellyfin_images.py`）：量測的迴圈不與伺服器搶 GIL。"""
    # 留在 `/out`：容器跑完就沒了，而 serve 中途倒下時要看得到原因。
    log = Path("/out/berth-serve.log")
    env = {
        **os.environ,
        "CONFIG_ROOT": str(CONFIG),
        "DATA_ROOT": str(DATA),
        "WEB_ROOT": str(CONFIG / "no-web"),
        "PORT": str(BERTH_PORT),
    }
    with log.open("wb") as sink:
        process = subprocess.Popen(
            [sys.executable, "-m", "berth.cli", "serve"], env=env, stdout=sink, stderr=sink
        )
        base = f"http://127.0.0.1:{BERTH_PORT}"
        try:
            poll(lambda: request(f"{base}/api/health", timeout=2).ok, what="Berth 起來", timeout=90)
            yield base
        finally:
            if process.poll() is not None:
                print(f"berth serve 已經結束（{process.returncode}），log：{log}", flush=True)
            process.terminate()
            process.wait(timeout=30)


def sign_in(base: str, username: str) -> str:
    resp = request(
        f"{base}/api/auth/login",
        method="POST",
        headers={"X-Requested-With": "XMLHttpRequest"},
        json_body={"username": username, "password": PASSWORD},
    )
    if not resp.ok:
        raise RuntimeError(f"Berth 登入失敗（{username}）：{resp.status} {resp.text[:200]}")
    cookie = next(v for k, v in resp.headers.items() if k.lower() == "set-cookie")
    return cookie.split(";", 1)[0]


def inventory(base: str, cookie: str, library_id: str, page: int) -> Response:
    return request(
        f"{base}/api/inventory/{library_id}",
        headers={"Cookie": cookie},
        params={"page": str(page)},
        timeout=120,
    )


def measure_inventory(base: str, cookie: str, library_id: str, repeats: int) -> dict[str, Any]:
    """`GET /inventory/{id}`，門檻的那一支。第一次是冷的（權限快取與 Jellyfin 都還沒熱）。"""
    started = time.perf_counter()
    first = inventory(base, cookie, library_id, 1)
    cold_ms = (time.perf_counter() - started) * 1000
    if not first.ok:
        raise RuntimeError(f"GET /inventory -> {first.status} {first.text[:300]}")
    body = first.json()
    out: dict[str, Any] = {
        "cold_ms": round(cold_ms, 1),
        "bytes": len(first.body),
        "titles": len(body["titles"]),
        "tracked": len(body["tracked"]),
        "total": body["total"],
        "watch_on_titles": sum(card["watch"] is not None for card in body["titles"]),
        "watch_on_tracked": sum(card["watch"] is not None for card in body["tracked"]),
    }
    for page in (1, 5):
        latencies: list[float] = []
        failures: list[str] = []
        for _ in range(repeats):
            started = time.perf_counter()
            try:
                resp = inventory(base, cookie, library_id, page)
            except OSError as exc:  # 斷線、逾時：記下來，不讓一次失敗吃掉整輪量測
                failures.append(f"{type(exc).__name__}: {exc}")
                continue
            if not resp.ok:
                failures.append(f"{resp.status} {resp.text[:120]}")
                continue
            latencies.append((time.perf_counter() - started) * 1000)
        row: dict[str, Any] = {"repeats": repeats, "failures": failures}
        if latencies:
            row |= summary(latencies)
        out[f"page_{page}"] = row
    return out


async def wall_breakdown(
    args: argparse.Namespace, library_id: str, viewer: str, repeats: int
) -> dict[str, Any]:
    """同一程序裡把 `read_wall` 拆開量：Berth 自己的清單（`_survey`）、Jellyfin 的那一頁、
    整份清單，與整支 `read_wall`。和經過 `berth serve` 的數字對照，差的就是 serve 那一層
    （門禁、背景迴圈）。"""
    config = load_config({"CONFIG_ROOT": str(CONFIG), "DATA_ROOT": str(DATA)})
    engine = create_engine(config)
    client = HttpJellyfinClient(args.jellyfin, token=args.api_key)
    library = BrowsableLibrary(id=library_id, name="TV", collection_type=CollectionType.TVSHOWS)
    access = JellyfinAccess(client, viewer, (library,))
    timings: dict[str, list[float]] = {"survey": [], "page": [], "index": [], "read_wall": []}
    try:
        for _ in range(repeats):
            async with create_session_factory(engine)() as session:
                routes = await inventory_service._routes(session)
                started = time.perf_counter()
                await inventory_service._survey(session, library, routes, today=date.today())
                timings["survey"].append((time.perf_counter() - started) * 1000)
            started = time.perf_counter()
            await access.page(
                library_id, start=0, limit=inventory_service.PAGE_SIZE, query=WallQuery()
            )
            timings["page"].append((time.perf_counter() - started) * 1000)
            started = time.perf_counter()
            await access.index(library_id)
            timings["index"].append((time.perf_counter() - started) * 1000)
            async with create_session_factory(engine)() as session:
                started = time.perf_counter()
                await inventory_service.read_wall(
                    session, access, library_id, page=1, query=WallQuery()
                )
                timings["read_wall"].append((time.perf_counter() - started) * 1000)
    finally:
        await client.aclose()
        await engine.dispose()
    return {key: summary(values) for key, values in timings.items()}


# --- 對帳 ----------------------------------------------------------------------


class TimedProgress(Progress):
    """每一方問完的時刻。`reconcile_once` 本來就逐方回報，量時間不必改它。"""

    def __init__(self) -> None:
        super().__init__()
        self.started = time.perf_counter()
        self.marks: list[tuple[str, float]] = []

    def side_done(self, report: SideReport) -> None:
        super().side_done(report)
        self.marks.append((report.side.value, time.perf_counter()))


async def reconcile_round(profile: cProfile.Profile | None = None) -> dict[str, Any]:
    config = load_config({"CONFIG_ROOT": str(CONFIG), "DATA_ROOT": str(DATA)})
    engine = create_engine(config)
    progress = TimedProgress()
    try:
        async with create_session_factory(engine)() as session:
            if profile is not None:
                profile.enable()
            report = await reconcile_once(session, HttpServiceClientFactory(), progress=progress)
            if profile is not None:
                profile.disable()
    finally:
        await engine.dispose()
    finished = time.perf_counter()
    sides: dict[str, float] = {}
    previous = progress.started
    for side, moment in progress.marks:
        sides[side] = round(moment - previous, 2)
        previous = moment
    return {
        "total_s": round(finished - progress.started, 2),
        "sides_s": sides,
        "checks_s": round(finished - previous, 2),
        "counted": {row.side.value: row.counted for row in report.sides},
        "unavailable": {row.side.value: row.unavailable for row in report.sides if row.unavailable},
        "opened": report.opened,
        "updated": report.updated,
    }


def top_functions(profile: cProfile.Profile, limit: int = 20) -> str:
    buffer = io.StringIO()
    pstats.Stats(profile, stream=buffer).sort_stats("cumulative").print_stats(limit)
    return buffer.getvalue()


async def resolve_all() -> dict[str, Any]:
    """一輪反查：12,000 列同時到期（第一次入庫完的樣子放大）。"""
    config = load_config({"CONFIG_ROOT": str(CONFIG), "DATA_ROOT": str(DATA)})
    engine = create_engine(config)
    try:
        async with create_session_factory(engine)() as session:
            started = time.perf_counter()
            outcome = await sweep_resolutions(session, HttpServiceClientFactory())
            elapsed = time.perf_counter() - started
    finally:
        await engine.dispose()
    return {
        "seconds": round(elapsed, 2),
        "resolved": outcome.resolved,
        "retried": outcome.retried,
        "exhausted": outcome.exhausted,
    }


# --- 被刪掉的帳號 --------------------------------------------------------------


def after_delete(jf: Jellyfin, user_id: str, episode_id: str) -> dict[str, Any]:
    """API key 代讀 / 代寫一位已刪除的使用者。M1.5 票 01 量過停用的那一種（研究 §2）。"""
    user = {"userId": user_id}
    calls: list[tuple[str, str, dict[str, str]]] = [
        ("GET", f"/Users/{user_id}", {}),
        ("GET", "/UserViews", user),
        (
            "GET",
            "/Items",
            {**user, "recursive": "true", "includeItemTypes": "Series", "limit": "1"},
        ),
        ("GET", "/UserItems/Resume", {**user, "mediaTypes": "Video"}),
        ("GET", "/Shows/NextUp", user),
        ("GET", f"/Items/{episode_id}", user),
        ("POST", f"/UserPlayedItems/{episode_id}", user),
    ]
    out: dict[str, Any] = {}
    for method, path, params in calls:
        resp = jf.send(method, path, params=params)
        label = f"{method} {path.replace(user_id, '{id}').replace(episode_id, '{episode}')}"
        out[label] = {"status": resp.status, "body": resp.text[:160]}
    return out


async def policy_of(jellyfin: str, api_key: str, user_id: str) -> str:
    """Berth 的 adapter 讀這位使用者的 `Policy` 時丟什麼。"""
    client = HttpJellyfinClient(jellyfin, token=api_key)
    try:
        policy = await client.user_policy(user_id)
    except ServiceError as exc:
        return f"{type(exc).__name__}: {exc}"
    finally:
        await client.aclose()
    return f"returned {policy!r}"


def fresh_user(jf: Jellyfin, name: str) -> str:
    """重跑時先刪掉上一輪留下的同名帳號（`--reuse`），再建一個新的。"""
    for row in jf.ok("GET", "/Users"):
        if row.get("Name") == name:
            jf.ok("DELETE", f"/Users/{row['Id']}")
    return str(jf.ok("POST", "/Users/New", body={"Name": name, "Password": PASSWORD})["Id"])


def deleted_account(
    report: Report,
    jf: Jellyfin,
    berth: str,
    library_id: str,
    episode_id: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    gone = fresh_user(jf, GONE)
    before = jf.send("GET", f"/Users/{gone}")
    cookie = sign_in(berth, GONE)
    first = inventory(berth, cookie, library_id, 1)
    deleted = jf.send("DELETE", f"/Users/{gone}")
    raw = after_delete(jf, gone, episode_id)
    adapter = asyncio.run(policy_of(args.jellyfin, args.api_key, gone))
    # 權限快取活 60 秒（`ACCESS_TTL_SECONDS`）：過期之後 Berth 才會再去讀 `Policy`。
    time.sleep(ACCESS_TTL_SECONDS + 2)
    later = inventory(berth, cookie, library_id, 1)
    again = inventory(berth, cookie, library_id, 1)
    relogin = request(
        f"{berth}/api/auth/login",
        method="POST",
        headers={"X-Requested-With": "XMLHttpRequest"},
        json_body={"username": GONE, "password": PASSWORD},
    )
    out = {
        "user_before_delete": before.status,
        "berth_inventory_before_delete": first.status,
        "delete_status": deleted.status,
        "jellyfin_after_delete": raw,
        "berth_adapter_user_policy": adapter,
        "berth_inventory_after_ttl": {"status": later.status, "body": later.text[:300]},
        "berth_inventory_again": {"status": again.status, "body": again.text[:300]},
        "berth_login_again": {"status": relogin.status, "body": relogin.text[:300]},
    }
    for key, value in out.items():
        report.note(f"刪除帳號 {key}：{value}")
    return out


# --- measure -------------------------------------------------------------------


STAGES = ("jellyfin", "inventory", "reconcile")


def measure(args: argparse.Namespace) -> int:
    """灌資料之後照 `--stages` 量。每一段量完就寫一次報告：這台機器上偶爾有程序無聲崩潰
    （研究 large-library.md §0），前面量到的不該跟著丟。只跑一部分時報告檔名帶段名。"""
    stages = tuple(args.stages.split(","))
    unknown = set(stages) - set(STAGES)
    if unknown:
        raise SystemExit(f"不認得的段落：{sorted(unknown)}；可用 {STAGES}")
    name = "large-library" if stages == STAGES else f"large-library-{'-'.join(stages)}"
    report = Report(name=name, out_dir=Path("/out"))
    report.heading(f"大媒體庫量測：{args.series} 部 × {args.episodes} 集")
    jf = Jellyfin(args.jellyfin, args.api_key)
    targets = works(args.series)
    library_id = args.library_id
    info = jf.ok("GET", "/System/Info")
    report.record("jellyfin_version", info["Version"])
    report.record("scale", {"series": args.series, "episodes_per_series": args.episodes})

    viewer = fresh_user(jf, VIEWER)
    report.record("watch_seeded", seed_watch(jf, library_id, viewer))
    report.note(f"觀看紀錄：{report.sections['watch_seeded']}")

    started = time.perf_counter()
    hashes = seed_torrents(args.qbittorrent, targets, args.episodes)
    report.note(f"qBittorrent：{len(hashes)} 個 torrent，{time.perf_counter() - started:.0f} 秒")
    asyncio.run(
        seed_berth(
            args.jellyfin,
            args.api_key,
            args.qbittorrent,
            library_id,
            hashes,
            targets,
            args.episodes,
        )
    )
    resolved = asyncio.run(resolve_all())
    report.record("resolver_sweep", resolved)
    report.note(f"一輪反查（全部到期）：{resolved}")
    report.write()
    verdict: dict[str, Any] = {}
    if "jellyfin" in stages:
        measure_jellyfin(report, jf, viewer, library_id, args.repeats)
    if "inventory" in stages:
        verdict |= measure_berth_wall(report, jf, viewer, library_id, args)
    if "reconcile" in stages:
        verdict |= measure_reconcile(report, args.reconcile_rounds)
    report.record("dropped_connections", DROPPED)
    report.note(f"量測中斷線：{len(DROPPED)} 次 {DROPPED}")
    report.note(f"判定：{verdict}")
    report.record("verdict", verdict)
    report.write()
    return 0


def measure_jellyfin(
    report: Report, jf: Jellyfin, viewer: str, library_id: str, repeats: int
) -> None:
    """票上的五件之一到四：直打 Jellyfin，參數照 adapter。"""
    raw: dict[str, Any] = {}
    raw["1 library_index（牆的整份清單，enableUserData=false）"] = sample(
        lambda: jf.get("/Items", library_index(viewer, library_id, user_data=False)), repeats
    )
    tmdb = {
        "userId": viewer,
        "recursive": "true",
        "includeItemTypes": "Series",
        "hasTmdbId": "true",
        "fields": "ProviderIds",
        "enableImages": "false",
        "enableUserData": "false",
    }
    raw["2 tmdb_index（不帶 parentId，Media 詳情的觀看區）"] = sample(
        lambda: jf.get("/Items", tmdb), repeats
    )
    # 整份 `MediaSources` 一次可能要十幾秒，少打幾次；p95 在 n=5 時就是最慢那一次。
    heavy = max(3, repeats // 4)
    raw["3a items(Series) 帶 MediaSources"] = sample(
        lambda: jf.get("/Items", with_sources(library_id, "Series")), heavy
    )
    raw["3b items(Episode) 帶 MediaSources（反查 / 對帳）"] = sample(
        lambda: jf.get("/Items", with_sources(library_id, "Episode")), heavy
    )
    no_sources = {**with_sources(library_id, "Episode"), "fields": "Path,ProviderIds"}
    raw["3c 對照：items(Episode) 不帶 MediaSources"] = sample(
        lambda: jf.get("/Items", no_sources), heavy
    )
    raw["4a 牆的一頁（100 部，帶觀看紀錄，現況）"] = sample(
        lambda: jf.get("/Items", library_page(viewer, library_id, 0)), repeats
    )
    raw["4b library_index 帶觀看紀錄（整份 1,000 部）"] = sample(
        lambda: jf.get("/Items", library_index(viewer, library_id, user_data=True)), repeats
    )
    series_ids = [row["Id"] for row in jf.ok("GET", "/Items", params=tmdb)["Items"]]
    for count in (50, 200):
        by_ids = {
            **library_index(viewer, library_id, user_data=True),
            "ids": ",".join(series_ids[:count]),
        }
        by_ids.pop("parentId")
        raw[f"4c 只取篩出來的 {count} 部（ids=，帶觀看紀錄）"] = sample(
            partial(jf.get, "/Items", by_ids), repeats
        )
    for label, row in raw.items():
        report.note(f"{label}：{row}")
    report.record("jellyfin", raw)

    # 分段取的代價先量起來：超門檻時要拿它比。
    paged: dict[str, Any] = {}
    for size in (500, 2000):
        latencies, pages, fetched = [], 0, 0
        started = time.perf_counter()
        while True:
            params = {
                **with_sources(library_id, "Episode"),
                "startIndex": str(fetched),
                "limit": str(size),
                "sortBy": "SortName",
            }
            t0 = time.perf_counter()
            resp = jf.get("/Items", params)
            latencies.append((time.perf_counter() - t0) * 1000)
            rows = resp.json()["Items"]
            pages += 1
            fetched += len(rows)
            if len(rows) < size:
                break
        paged[f"limit={size}"] = {
            "pages": pages,
            "items": fetched,
            "total_s": round(time.perf_counter() - started, 2),
            "slowest_page_ms": round(max(latencies), 1),
        }
    report.note(f"items(Episode) 帶 MediaSources 分段取：{paged}")
    report.record("jellyfin_paged_episodes", paged)
    report.write()


def measure_berth_wall(
    report: Report, jf: Jellyfin, viewer: str, library_id: str, args: argparse.Namespace
) -> dict[str, Any]:
    """門檻一 `GET /inventory/{id}`，與票上第五件（被刪掉的帳號）。"""
    episode_id = jf.ok(
        "GET",
        "/Items",
        params={
            "parentId": library_id,
            "recursive": "true",
            "includeItemTypes": "Episode",
            "limit": "1",
            "enableImages": "false",
        },
    )["Items"][0]["Id"]
    with berth_serve() as berth:
        cookie = sign_in(berth, VIEWER)
        wall = measure_inventory(berth, cookie, library_id, args.inventory_repeats)
        report.note(f"GET /inventory/{{id}}（viewer）：{wall}")
        report.record("inventory", wall)
        breakdown = asyncio.run(wall_breakdown(args, library_id, viewer, 10))
        report.note(f"read_wall 拆開量（同一程序、不經 serve）：{breakdown}")
        report.record("inventory_breakdown", breakdown)
        report.record(
            "deleted_account", deleted_account(report, jf, berth, library_id, episode_id, args)
        )
    report.write()
    # 有失敗的那一頁不算數：p95 以無限大計，判定一定是「超了」。
    inventory_p95 = max(
        math.inf if row["failures"] else row["p95_ms"] for row in (wall["page_1"], wall["page_5"])
    )
    return {
        "inventory_p95_ms": inventory_p95,
        "inventory_over": inventory_p95 > INVENTORY_P95_LIMIT_MS,
    }


def measure_reconcile(report: Report, repeats: int) -> dict[str, Any]:
    """門檻二：對帳走完一輪。最後多跑一輪 cProfile，看時間花在哪。"""
    rounds = [asyncio.run(reconcile_round()) for _ in range(repeats)]
    for index, row in enumerate(rounds, 1):
        report.note(f"對帳第 {index} 輪：{row}")
    report.record("reconcile", rounds)
    report.write()
    profile = cProfile.Profile()
    asyncio.run(reconcile_round(profile))
    hot = top_functions(profile)
    report.record("reconcile_profile", hot)
    print(hot, flush=True)
    reconcile_s = max(row["total_s"] for row in rounds)
    return {"reconcile_s": reconcile_s, "reconcile_over": reconcile_s > RECONCILE_LIMIT_S}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    tree = sub.add_parser("tree")
    tree.add_argument("--series", type=int, default=SERIES)
    tree.add_argument("--episodes", type=int, default=EPISODES)
    tree.add_argument(
        "--subnet", required=True, help="qBittorrent 免密白名單（docker network 的網段）"
    )
    run = sub.add_parser("measure")
    run.add_argument("--series", type=int, default=SERIES)
    run.add_argument("--episodes", type=int, default=EPISODES)
    run.add_argument("--jellyfin", required=True)
    run.add_argument("--api-key", required=True)
    run.add_argument("--library-id", required=True)
    run.add_argument("--qbittorrent", required=True)
    run.add_argument("--repeats", type=int, default=20)
    run.add_argument("--inventory-repeats", type=int, default=30)
    run.add_argument("--reconcile-rounds", type=int, default=3)
    run.add_argument("--stages", default=",".join(STAGES), help=f"逗號分隔，預設全部：{STAGES}")
    args = parser.parse_args()
    if args.command == "tree":
        build_tree(args.series, args.episodes, args.subnet)
        return 0
    return measure(args)


if __name__ == "__main__":
    raise SystemExit(main())
