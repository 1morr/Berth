"""Jellyfin 的集帶不帶 TMDB 集 id 與首播日（M5 票 28 之後的比對規則）。

Berth 不信 Jellyfin 自己的季集號（Jellyfin 可能依 TVDB 編號）。使用者原本要先以集的
`ProviderIds.Tmdb`（TMDB 的**集** id）比對、沒有再以 `PremiereDate`（±1 天）比 TMDB 的 `air_date`；
**2026-10-30 量到 12.1.0 的集沒有 `Tmdb`**（只有 Tvdb、Imdb），所以 Berth 只照播出日比
（brief §20.8）。
`jellyfin_permissions.py` 第 7 節那棵樹關掉網路 metadata，集沒有 TMDB id；這支腳本用
**開啟網路 metadata**（預設 fetcher，即實際部署的樣子）的媒體庫補量：

1. `GET /Shows/{id}/Episodes?userId=&isMissing=false&fields=ProviderIds`：集帶哪些 provider id、
   `Tmdb` 是不是 TMDB 的集 id（對 `GET /3/tv/{id}/season/{n}` 的 `episodes[].id`）
2. 同一支不帶 `fields`：`ProviderIds` 還在嗎、`PremiereDate` 還在嗎、格式與 `air_date` 是否一致
3. TMDB 對不上、只靠檔名建出來的集長什麼樣子

起一台一次性 Jellyfin（image 取自 `deploy/docker-compose.yml`），跑完刪掉容器與工作目錄。
需要網路；TMDB 的 key 讀 `TMDB_API_KEY`（環境變數，或 `--env-file`），不會印出也不會寫進報告。

用法（報告寫到 .local/experiments/results/）：
    python scripts/experiments/jellyfin_episode_providers.py --env-file /path/to/.env
    python scripts/experiments/jellyfin_episode_providers.py --env-file … --record
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from jellyfin_naming import Jellyfin
from jellyfin_permissions import FFMPEG, FIXTURES, ROOT, compose_image, docker
from lib import Report, poll, request

CONTAINER = "berth-exp-jellyfin-episode-providers"
RESULTS = ROOT / ".local" / "experiments" / "results"
FIXTURE = "shows-episodes.series.providers.json"

SHOW_TMDB = 120089
SHOW = f"SPY x FAMILY (2022) [tmdbid-{SHOW_TMDB}]"
#: (季, 集)。第 2 季只放一集：Jellyfin 的 S02E01 要對上 TMDB 的第 2 季第 1 集。
SHOW_EPISODES = ((1, 1), (1, 2), (1, 3), (2, 1))
#: TMDB 對不上的作品（make_media.py 的 PROBE）：集只靠檔名。
PROBE = "Qwxzyv Berth Probe (2099)"
PROBE_EPISODES = ((1, 1), (1, 2))
EPISODE_KEYS = ("IndexNumber", "ParentIndexNumber", "ProviderIds", "PremiereDate", "Name")


def tmdb_key(env_file: Path | None) -> str:
    key = os.environ.get("TMDB_API_KEY", "")
    if not key and env_file:
        for line in env_file.read_text("utf-8").splitlines():
            if line.startswith("TMDB_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
    if not key:
        raise SystemExit("沒有 TMDB_API_KEY（環境變數或 --env-file）")
    return key


def tmdb_get(key: str, path: str) -> Any:
    """GET api.themoviedb.org/3/<path>。v4 read token 用 Bearer，否則用 api_key。"""
    bearer = key.startswith("eyJ")
    headers = {"Authorization": f"Bearer {key}"} if bearer else {}
    resp = request(
        f"https://api.themoviedb.org/3/{path}",
        headers=headers,
        params=None if bearer else {"api_key": key},
    )
    if not resp.ok:
        raise SystemExit(f"TMDB {path} -> {resp.status}")
    return resp.json()


def tmdb_season(key: str, season: int) -> dict[int, dict[str, Any]]:
    """TMDB 的某一季：集號 -> {id, air_date}。v4 read token 用 Bearer，否則用 api_key。"""
    url = f"https://api.themoviedb.org/3/tv/{SHOW_TMDB}/season/{season}"
    bearer = key.startswith("eyJ")
    headers = {"Authorization": f"Bearer {key}"} if bearer else {}
    resp = request(url, headers=headers, params=None if bearer else {"api_key": key})
    if not resp.ok:
        raise SystemExit(f"TMDB {url} -> {resp.status}")
    return {e["episode_number"]: e for e in resp.json()["episodes"]}


def make_tree(workdir: Path, image: str) -> None:
    seeds = workdir / "seeds"
    seeds.mkdir(parents=True)
    mount = f"type=bind,source={seeds},target=/out"
    black = ["-i", "color=c=black:s=64x64:r=1", "-t", "10"]
    encode = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "/out/seed.mkv"]
    quiet = ["-hide_banner", "-loglevel", "error", "-f", "lavfi"]
    docker("run", "--rm", "--mount", mount, "--entrypoint", FFMPEG, image, *quiet, *black, *encode)
    tv = workdir / "media" / "tv"
    for folder, title, episodes in (
        (SHOW, "SPY x FAMILY (2022)", SHOW_EPISODES),
        (f"{PROBE}", PROBE, PROBE_EPISODES),
    ):
        for season, episode in episodes:
            target = (
                tv / folder / f"Season {season:02d}" / f"{title} - S{season:02d}E{episode:02d}.mkv"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(seeds / "seed.mkv", target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18197)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--record", action="store_true", help="另外寫 fixture")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    key = tmdb_key(args.env_file)
    image = compose_image()
    report = Report("jellyfin_episode_providers", RESULTS)
    workdir = Path(tempfile.mkdtemp(prefix="berth-exp-episode-providers-"))
    docker("rm", "-f", "-v", CONTAINER, check=False)
    try:
        make_tree(workdir, image)
        (workdir / "config").mkdir()
        mounts = [
            "--mount", f"type=bind,source={workdir / 'config'},target=/config",
            "--mount", f"type=bind,source={workdir / 'media'},target=/media,readonly",
        ]  # fmt: skip
        env = ["-e", "PUID=1000", "-e", "PGID=1000", "-e", "TZ=Etc/UTC"]
        docker(
            "run",
            "-d",
            "--name",
            CONTAINER,
            "-p",
            f"127.0.0.1:{args.port}:8096",
            *env,
            *mounts,
            image,
        )
        report.note(f"一次性容器 {CONTAINER}（{image}），工作目錄 {workdir}")

        jf = Jellyfin(f"http://127.0.0.1:{args.port}", "episode-providers")
        jf.run_startup(report)
        # 網路 metadata 開著（TypeOptions 留空 = 預設 fetcher），這是與第 7 節唯一的差別。
        jf.create_library("TV", "tvshows", "/media/tv")
        jf.call("/Library/Refresh", method="POST")
        version = jf.call("/System/Info")["Version"]
        report.note(f"伺服器版本 {version}")

        def series_id(term: str) -> str | None:
            rows = jf.items(
                parentId=jf.library_id("TV"), includeItemTypes="Series", searchTerm=term
            )
            return str(rows[0]["Id"]) if rows else None

        def episodes(series: str, **extra: str) -> Any:
            return jf.call(
                f"/Shows/{series}/Episodes",
                params={"userId": jf.user_id, "isMissing": "false", **extra},
            )

        spy = poll(lambda: series_id("SPY"), what="SPY x FAMILY 出現", timeout=300)
        probe = poll(lambda: series_id("Qwxzyv"), what="Probe 出現", timeout=300)

        def settled(series: str, count: int) -> bool:
            """集齊且每一集都有首播日（metadata 抓完；Probe 那組永遠沒有，只等集數）。"""
            rows = episodes(series, fields="ProviderIds")["Items"]
            return len(rows) >= count and (
                series == probe or all(r.get("PremiereDate") for r in rows)
            )

        poll(
            lambda: settled(spy, len(SHOW_EPISODES)),
            what="SPY 的集 metadata",
            timeout=600,
            interval=5,
        )
        poll(
            lambda: settled(probe, len(PROBE_EPISODES)), what="Probe 的集", timeout=300, interval=5
        )
        time.sleep(10)  # 再給 Jellyfin 一點時間把剩下的欄位寫完

        results: dict[str, Any] = {"version": version}
        tmdb = {s: tmdb_season(key, s) for s in sorted({s for s, _ in SHOW_EPISODES})}
        for label, series, extra in (
            ("spy_fields", spy, {"fields": "ProviderIds"}),
            ("spy_plain", spy, {}),
            ("probe_fields", probe, {"fields": "ProviderIds"}),
            ("probe_plain", probe, {}),
        ):
            query = "&".join(
                f"{k}={v}" for k, v in {"userId": "U", "isMissing": "false", **extra}.items()
            )
            resp = request(
                f"{jf.base}/Shows/{series}/Episodes",
                headers={"Authorization": jf.auth_header()},
                params={"userId": jf.user_id, "isMissing": "false", **extra},
            )
            report.note(f"{label}: GET /Shows/{{id}}/Episodes?{query} -> {resp.status}")
            rows = resp.json()["Items"]
            table = []
            for r in rows:
                entry = {k: r.get(k) for k in EPISODE_KEYS}
                if label.startswith("spy"):
                    ref = tmdb.get(r["ParentIndexNumber"], {}).get(r["IndexNumber"], {})
                    entry["tmdb_episode_id"] = ref.get("id")
                    entry["tmdb_air_date"] = ref.get("air_date")
                table.append(entry)
                report.note(f"  {json.dumps(entry, ensure_ascii=False)}")
            results[label] = {"status": resp.status, "episodes": table}
            if label == "spy_fields" and args.record:
                if not version.startswith("12.1"):
                    raise SystemExit(f"伺服器是 {version}，不是 12.1.x，不錄 fixture")
                path = FIXTURES / FIXTURE
                text = json.dumps(resp.json(), indent=2, ensure_ascii=False, sort_keys=True)
                path.write_text(text + "\n", "utf-8", newline="\n")
                report.note(
                    f"寫入 {path.relative_to(ROOT)}（HTTP {resp.status}，{len(resp.body)} bytes）"
                )
        series_row = jf.call(f"/Users/{jf.user_id}/Items/{spy}")
        results["spy_series_provider_ids"] = series_row.get("ProviderIds")
        report.note(f"Series 的 ProviderIds：{series_row.get('ProviderIds')}")
        # Jellyfin 的 Tvdb / Imdb 是不是 TMDB 那集的 external_ids？（TMDB fetcher 只寫這兩個的證據）
        external: dict[str, Any] = {}
        for season, number in SHOW_EPISODES:
            ep_id = tmdb[season][number]["id"]
            ext = tmdb_get(key, f"tv/{SHOW_TMDB}/season/{season}/episode/{number}/external_ids")
            tag = f"S{season:02d}E{number:02d}"
            external[tag] = {
                "tmdb_episode_id": ep_id,
                "tvdb_id": ext.get("tvdb_id"),
                "imdb_id": ext.get("imdb_id"),
            }
            report.note(f"TMDB external_ids {tag}: {external[tag]}")
        results["tmdb_external_ids"] = external
        report.record("episode_providers", results)
        report.write()
    finally:
        if args.keep:
            report.note(f"--keep：保留容器 {CONTAINER} 與 {workdir}")
        else:
            docker("rm", "-f", "-v", CONTAINER, check=False)
            shutil.rmtree(workdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
