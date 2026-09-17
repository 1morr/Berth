"""Jellyfin 圖片經 Berth 代理的量測（M1.5 票 04；研究 library-browsing.md §6）。

回答「Berth 要不要自己另存一份縮好的圖」，量三件事：

1. 縮圖參數真的照做嗎：2:3 的原圖帶 `fillWidth=342&fillHeight=513` 回多大、什麼格式、幾個位元組
   （`quality` 90 / 96；`format=Webp`，以及不帶 `format` 時 `Accept` 怎麼協商）
2. Jellyfin 自己有沒有存一份縮好的圖：同一張第一次（冷）與第二次（熱）的延遲，
   `/config/cache` 底下的檔案
3. 經過 Berth 多花多少：瀏覽器式的 6 條並行，直連 Jellyfin 與經過 Berth
   （`berth serve` 子程序：門禁、session、每張圖一個 httpx client）各量冷熱

起一台一次性 Jellyfin（image 取自 `deploy/docker-compose.yml`），一個電影媒體庫 100 部，
每部一張 1000×1500、帶雜訊的 JPEG 海報（雜訊讓它不像純色圖那樣好壓）。跑完刪容器與工作目錄。

它量的是 Berth 自己的代理，所以 import `berth`、要用 `uv run` 跑（同 `absolute_rule_cost.py`）。

用法（報告寫到 .local/experiments/results/）：
    uv run python scripts/experiments/jellyfin_images.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import statistics
import struct
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from jellyfin_naming import ADMIN, PASSWORD, Jellyfin
from jellyfin_permissions import FFMPEG, Credential, Server, compose_image, create_library, docker
from lib import Report, Response, poll, request

from berth.config import load_config
from berth.db import create_engine, create_session_factory, upgrade_to_head
from berth.models import JellyfinSettings, SetupSettings
from berth.services.settings import read_settings, write_settings

CONTAINER = "berth-exp-jellyfin-images"
MOVIES = 100
#: 瀏覽器對同一個 HTTP/1.1 主機的並行連線數。
BROWSER_CONNECTIONS = 6
#: Chromium 送圖片請求時的 `Accept`。
BROWSER_ACCEPT = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
#: 票 04 選的規格（`services/jellyfin_images.py`）。
POSTER = {"fillWidth": "342", "fillHeight": "513", "quality": "90", "format": "Webp"}


def make_media(workdir: Path, image: str) -> None:
    """100 部電影：每部一支 1 秒的黑畫面與一張各不相同的海報。

    用 Jellyfin image 自己的 ffmpeg 產生，宿主不必裝 ffmpeg。
    """
    seeds = workdir / "seeds"
    seeds.mkdir(parents=True)
    mount = f"type=bind,source={seeds},target=/out"
    ffmpeg = ["run", "--rm", "--mount", mount, "--entrypoint", FFMPEG, image]
    quiet = ["-hide_banner", "-loglevel", "error", "-f", "lavfi"]
    black = ["-i", "color=c=black:s=64x64:r=1", "-t", "1", "-c:v", "libx264", "/out/seed.mkv"]
    docker(*ffmpeg, *quiet, *black)
    # testsrc2 每一格都不同；雜訊讓 JPEG 大小接近真的海報，而不是幾 KB 的色塊。
    posters = ["-i", "testsrc2=size=1000x1500:rate=1", "-vf", "noise=alls=24:allf=t+u"]
    frames = ["-frames:v", str(MOVIES), "-q:v", "3", "/out/poster-%03d.jpg"]
    docker(*ffmpeg, *quiet, *posters, *frames)

    media = workdir / "media" / "movies"
    for index in range(1, MOVIES + 1):
        folder = media / f"Poster Probe {index:03d} (2020)"
        folder.mkdir(parents=True)
        shutil.copyfile(seeds / "seed.mkv", folder / f"Poster Probe {index:03d} (2020).mkv")
        shutil.copyfile(seeds / f"poster-{index:03d}.jpg", folder / "poster.jpg")


@contextmanager
def disposable_jellyfin(workdir: Path, image: str, port: int, keep: bool) -> Iterator[str]:
    docker("rm", "-f", "-v", CONTAINER, check=False)
    try:
        make_media(workdir, image)
        (workdir / "config").mkdir()
        config = f"type=bind,source={workdir / 'config'},target=/config"
        media = f"type=bind,source={workdir / 'media'},target=/media,readonly"
        env = ["-e", "PUID=1000", "-e", "PGID=1000", "-e", "TZ=Etc/UTC"]
        publish = ["-p", f"127.0.0.1:{port}:8096"]
        mounts = ["--mount", config, "--mount", media]
        docker("run", "-d", "--name", CONTAINER, *publish, *env, *mounts, image)
        yield f"http://127.0.0.1:{port}"
    finally:
        if not keep:
            docker("rm", "-f", "-v", CONTAINER, check=False)
            shutil.rmtree(workdir, ignore_errors=True)


# --- 量一張圖 ----------------------------------------------------------------


def dimensions(body: bytes) -> tuple[int, int] | None:
    """WebP（VP8 / VP8L / VP8X）與 JPEG（SOF0–SOF2）的寬高。認不得回 None。"""
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        chunk = body[12:16]
        if chunk == b"VP8 ":
            width, height = struct.unpack("<HH", body[26:30])
            return width & 0x3FFF, height & 0x3FFF
        if chunk == b"VP8L":
            bits = int.from_bytes(body[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if chunk == b"VP8X":
            return int.from_bytes(body[24:27], "little") + 1, int.from_bytes(
                body[27:30], "little"
            ) + 1
        return None
    if body[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(body):
            if body[index] != 0xFF:
                return None
            marker = body[index + 1]
            length = int.from_bytes(body[index + 2 : index + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2):
                height, width = struct.unpack(">HH", body[index + 5 : index + 9])
                return width, height
            index += 2 + length
    return None


def timed(fn: Callable[[], Response]) -> tuple[float, Response]:
    started = time.perf_counter()
    resp = fn()
    return (time.perf_counter() - started) * 1000, resp


def batch(fetch: Callable[[str], Response], ids: list[str]) -> dict[str, Any]:
    """像瀏覽器一樣 6 條並行抓一批圖：總時間與每張的延遲分佈。"""
    started = time.perf_counter()
    with ThreadPoolExecutor(BROWSER_CONNECTIONS) as pool:
        results = list(pool.map(lambda item: timed(lambda: fetch(item)), ids))
    total = (time.perf_counter() - started) * 1000
    latencies = sorted(ms for ms, _ in results)
    statuses = sorted({resp.status for _, resp in results})
    return {
        "images": len(ids),
        "statuses": statuses,
        "total_ms": round(total),
        "median_ms": round(statistics.median(latencies), 1),
        "p90_ms": round(latencies[int(len(latencies) * 0.9) - 1], 1),
        "max_ms": round(latencies[-1], 1),
        "bytes_median": int(statistics.median(len(resp.body) for _, resp in results)),
    }


# --- Berth ---------------------------------------------------------------------


async def seed_berth(config_root: Path, jellyfin: str) -> None:
    """精靈跑完、Jellyfin 位址填好的一台 Berth。登入走真的 `POST /api/auth/login`。"""
    config = load_config({"CONFIG_ROOT": str(config_root), "DATA_ROOT": str(config_root / "data")})
    config.config_root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config)
    await upgrade_to_head(engine)
    async with create_session_factory(engine)() as session:
        await write_settings(session, JellyfinSettings(base_url=jellyfin))
        setup = await read_settings(session, SetupSettings)
        setup.completed = True
        await write_settings(session, setup)
        await session.commit()
    await engine.dispose()


@contextmanager
def berth_serve(config_root: Path, port: int) -> Iterator[str]:
    """`berth serve` 另起一個程序：量測用的執行緒不要與伺服器搶同一把 GIL。"""
    env = {
        **os.environ,
        "CONFIG_ROOT": str(config_root),
        "DATA_ROOT": str(config_root / "data"),
        "WEB_ROOT": str(config_root / "no-web"),
        "PORT": str(port),
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "berth.cli", "serve"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        poll(lambda: request(f"{base}/api/health", timeout=2).ok, what="Berth 起來", timeout=60)
        yield base
    finally:
        process.terminate()
        process.wait(timeout=30)


def sign_in(base: str) -> str:
    resp = request(
        f"{base}/api/auth/login",
        method="POST",
        headers={"X-Requested-With": "XMLHttpRequest"},
        json_body={"username": ADMIN, "password": PASSWORD},
    )
    if not resp.ok:
        raise RuntimeError(f"Berth 登入失敗：{resp.status} {resp.text[:200]}")
    cookie = next(v for k, v in resp.headers.items() if k.lower() == "set-cookie")
    return cookie.split(";", 1)[0]


# --- main ----------------------------------------------------------------------


def jellyfin_cache(report: Report) -> dict[str, str]:
    """Jellyfin 把縮好的圖存在哪、存了多少。linuxserver 的 image 把 cache 放在 `/config/cache`。"""
    script = (
        "for d in /config/cache/images/resized-images /config/data/images /cache/images; do "
        'if [ -d "$d" ]; then '
        'echo "$d $(find "$d" -type f | wc -l) $(du -sk "$d" | cut -f1)KB"; fi; '
        "done"
    )
    out = docker("exec", CONTAINER, "sh", "-c", script, check=False).stdout.strip()
    report.note(f"Jellyfin 的圖片快取（目錄 檔案數 大小）：{out or '找不到'}")
    return {"du": out}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18397)
    parser.add_argument("--berth-port", type=int, default=18484)
    parser.add_argument("--out", type=Path, default=Path(".local/experiments/results"))
    parser.add_argument("--keep", action="store_true", help="跑完不刪容器與工作目錄")
    args = parser.parse_args()

    image = compose_image()
    workdir = Path(tempfile.mkdtemp(prefix="berth-jellyfin-images-"))
    report = Report(name="jellyfin-images", out_dir=args.out)
    report.heading(f"Jellyfin 圖片代理量測（{image}，{MOVIES} 張 1000×1500 海報）")

    with disposable_jellyfin(workdir, image, args.port, args.keep) as base:
        startup = f"{base}/Startup/Configuration"
        poll(lambda: request(startup, timeout=5).ok, what="Jellyfin 載入完成", timeout=300)
        setup = Jellyfin(base, "images")
        setup.run_startup(report)
        srv = Server(base)
        admin = Credential("admin", setup.token)
        version = srv.json(admin, "/System/Info")["Version"]
        create_library(srv, admin, "Movies", "movies")
        report.note(f"Jellyfin {version}；掃描完成，共 {setup.wait_for_scan()} 個 item")
        rows = setup.items(recursive="true", includeItemTypes="Movie", sortBy="SortName")
        tags = {row["Id"]: (row.get("ImageTags") or {}).get("Primary", "") for row in rows}
        ids = [row["Id"] for row in rows]
        if len(ids) != MOVIES or not all(tags.values()):
            missing = sum(not tag for tag in tags.values())
            report.note(f"媒體樹沒有照預期掃進來：{len(ids)} 部，缺圖 {missing}")
            report.write()
            return 1
        source = workdir / "media" / "movies" / "Poster Probe 001 (2020)" / "poster.jpg"
        report.record("source_bytes", source.stat().st_size)
        report.note(f"原圖一張 {source.stat().st_size // 1024} KB")

        def direct(item: str, params: Mapping[str, str], accept: str = "*/*") -> Response:
            query = {**params, "tag": tags[item]}
            url = f"{base}/Items/{item}/Images/Primary"
            return request(url, params=query, headers={"Accept": accept}, timeout=60)

        # 1. 參數與格式：每種變體用自己的 5 張，冷的那一次才真的是冷的。
        no_format = {key: value for key, value in POSTER.items() if key != "format"}
        variants: list[tuple[str, dict[str, str], str]] = [
            ("quality=90 format=Webp", POSTER, "*/*"),
            ("quality=96 format=Webp", {**POSTER, "quality": "96"}, "*/*"),
            ("quality=90 不帶 format，Accept */*", no_format, "*/*"),
            ("quality=90 不帶 format，瀏覽器的 Accept", no_format, BROWSER_ACCEPT),
        ]
        formats: dict[str, Any] = {}
        for offset, (label, params, accept) in enumerate(variants):
            chunk = ids[offset * 5 : offset * 5 + 5]
            cold = [timed(partial(direct, item, params, accept)) for item in chunk]
            warm = [timed(partial(direct, item, params, accept)) for item in chunk]
            first = cold[0][1]
            headers = {k.lower(): v for k, v in first.headers.items()}
            formats[label] = {
                "status": first.status,
                "content_type": headers.get("content-type"),
                "dimensions": dimensions(first.body),
                "bytes_median": int(statistics.median(len(resp.body) for _, resp in cold)),
                "cold_median_ms": round(statistics.median(ms for ms, _ in cold), 1),
                "warm_median_ms": round(statistics.median(ms for ms, _ in warm), 1),
                "cache_control": headers.get("cache-control"),
            }
            report.note(f"{label}：{formats[label]}")
        report.record("formats", formats)

        # 2 與 3. 同一個規格，40 張直連、40 張經過 Berth，各自冷熱兩輪。
        direct_ids, berth_ids = ids[20:60], ids[60:100]
        timings: dict[str, Any] = {}
        timings["直連 Jellyfin，冷"] = batch(lambda item: direct(item, POSTER), direct_ids)
        timings["直連 Jellyfin，熱"] = batch(lambda item: direct(item, POSTER), direct_ids)

        config_root = workdir / "berth"
        asyncio.run(seed_berth(config_root, base))
        with berth_serve(config_root, args.berth_port) as berth:
            cookie = sign_in(berth)

            def proxied(item: str) -> Response:
                url = f"{berth}/api/jellyfin/items/{item}/images/Primary"
                query = {"size": "poster", "tag": tags[item]}
                return request(url, params=query, headers={"Cookie": cookie}, timeout=60)

            timings["經過 Berth，冷"] = batch(proxied, berth_ids)
            timings["經過 Berth，熱"] = batch(proxied, berth_ids)
            # Jellyfin 那一端已經熱了的同一批圖：扣掉 Jellyfin 的份，剩下的就是 Berth 自己的份。
            timings["經過 Berth，Jellyfin 已熱（直連那一批）"] = batch(proxied, direct_ids)
            headers = {k.lower(): v for k, v in proxied(berth_ids[0]).headers.items()}
            report.note(f"Berth 回的標頭：{headers}")
            timings["berth_headers"] = headers
        for label, row in timings.items():
            if label != "berth_headers":
                report.note(f"{label}：{row}")
        report.record("timings", timings)
        report.record("jellyfin_cache", jellyfin_cache(report))
    report.write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
