"""M2 票 11：1,000 部的媒體庫上量 Berth（plan §11.3 決定 2 的門檻）。宿主那一半。

門檻寫死在票上：**1,000 部的媒體庫上 `GET /inventory/{id}` p95 > 1 s，或 reconciler 走完一輪
> 10 分鐘，就做分段取；否則不做快取。** 另外量票上列的五件（研究 library-browsing.md §2、§3、§6）。

這一支起停整個一次性環境，量測本身在 `large_library_berth.py`（Berth 的 image 裡跑）：

1. `docker build --target backend`：只有 Berth 的 venv，不建前端
2. 一個 docker network、三個 volume（媒體、Jellyfin 設定、qBittorrent 設定）
3. Jellyfin 的 ffmpeg 產一支 1 秒的種子影片，`tree` 子命令照它造 1,000 部 × 12 集
4. qBittorrent 5.2.3 與 Jellyfin（`deploy/` 釘的那一個）掛同一個 `/data`，與正式部署同形
5. 精靈、API key、TV 媒體庫（網路 fetcher 全關，TMDB id 從資料夾名的 `[tmdbid-N]` 來）、等掃描
6. `measure` 子命令：灌觀看紀錄、torrent 與 Berth 的資料庫，量完寫報告
7. 刪容器、volume、network、image，印出 `docker ps -a` 與 `docker volume ls` 的過濾結果

用法（報告寫到 .local/experiments/results/large-library.json）：
    python scripts/experiments/large_library.py
    python scripts/experiments/large_library.py --series 30   # 先小規模跑通
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from jellyfin_naming import Jellyfin
from jellyfin_permissions import FFMPEG, Credential, Server, compose_image, create_library, docker
from lib import Report, poll, request

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "berth-exp-large"
NETWORK = PREFIX
IMAGE = f"{PREFIX}:local"
JELLYFIN = f"{PREFIX}-jellyfin"
QBITTORRENT = f"{PREFIX}-qbittorrent"
DATA = f"{PREFIX}-data"
JELLYFIN_CONFIG = f"{PREFIX}-jellyfin-config"
QBITTORRENT_CONFIG = f"{PREFIX}-qbittorrent-config"
VOLUMES = (DATA, JELLYFIN_CONFIG, QBITTORRENT_CONFIG)
#: 與 `scripts/experiments/compose.yml` 的 5.x 同一個（票 09c 驗過的版本）。
QBITTORRENT_IMAGE = "lscr.io/linuxserver/qbittorrent:5.2.3"
API_KEY_APP = "Berth-Large-Library"
IDS = ["-e", "PUID=1000", "-e", "PGID=1000", "-e", "TZ=Etc/UTC"]


def cleanup(*, image: bool) -> None:
    docker("rm", "-f", "-v", JELLYFIN, QBITTORRENT, check=False)
    docker("volume", "rm", *VOLUMES, check=False)
    docker("network", "rm", NETWORK, check=False)
    if image:
        docker("image", "rm", IMAGE, check=False)


def leftovers() -> str:
    containers = docker("ps", "-a", "--filter", f"name={PREFIX}", "--format", "{{.Names}}")
    volumes = docker("volume", "ls", "--filter", f"name={PREFIX}", "--format", "{{.Name}}")
    return (
        f"docker ps -a --filter name={PREFIX}: [{containers.stdout.strip()}]\n"
        f"docker volume ls --filter name={PREFIX}: [{volumes.stdout.strip()}]"
    )


def run(*args: str) -> None:
    """輸出直接接到終端機：build 與量測都要跑好幾分鐘，要看得到它在動。"""
    subprocess.run(["docker", *args], check=True)


def berth_container(command: str, *options: str, network: bool = False) -> list[str]:
    """在 Berth 的 image 裡跑 `large_library_berth.py <command>`，`/data` 是媒體 volume。"""
    mounts = [
        "--mount",
        f"type=volume,source={DATA},target=/data",
        "--mount",
        f"type=bind,source={ROOT / 'scripts' / 'experiments'},target=/exp,readonly",
    ]
    net = ["--network", NETWORK] if network else []
    # `-X faulthandler`：程序崩潰時印出 Python 堆疊（這台機器上看過 segfault，研究 §0）。
    python = ["/app/.venv/bin/python", "-X", "faulthandler", "/exp/large_library_berth.py"]
    return ["run", "--rm", *net, *mounts, *options, IMAGE, *python, *command.split()]


def wait_for_scan(setup: Jellyfin, series: int, episodes: int) -> float:
    """掃描任務回 Idle 不代表 item 都建好了：等劇與集的數量都到齊。"""
    started = time.monotonic()
    setup.call("/Library/Refresh", method="POST")

    def counted() -> bool:
        found = {}
        for kind in ("Series", "Episode"):
            page = setup.call(
                "/Items",
                params={
                    "recursive": "true",
                    "includeItemTypes": kind,
                    "limit": "0",
                    "userId": setup.user_id,
                },
            )
            found[kind] = int(page.get("TotalRecordCount", 0))
        print(f"  掃描中：{found}", flush=True)
        return found == {"Series": series, "Episode": series * episodes}

    poll(counted, what="媒體庫掃描完成", timeout=7200, interval=20)
    return time.monotonic() - started


def build_environment(args: argparse.Namespace, jellyfin_image: str) -> None:
    """network、volume、種子影片、媒體樹、兩個服務的容器。"""
    docker("network", "create", NETWORK)
    subnet = docker(
        "network", "inspect", NETWORK, "--format", "{{(index .IPAM.Config 0).Subnet}}"
    ).stdout.strip()
    for volume in VOLUMES:
        docker("volume", "create", volume)

    seed = [
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=64x64:r=1",
        "-t",
        "1",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-y",
        "/data/seed.mkv",
    ]
    docker(
        "run",
        "--rm",
        "--mount",
        f"type=volume,source={DATA},target=/data",
        "--entrypoint",
        FFMPEG,
        jellyfin_image,
        "-hide_banner",
        "-loglevel",
        "error",
        *seed,
    )
    qb_config = ["--mount", f"type=volume,source={QBITTORRENT_CONFIG},target=/qbconfig"]
    tree = f"tree --series {args.series} --episodes {args.episodes} --subnet {subnet}"
    run(*berth_container(tree, *qb_config))

    data = ["--mount", f"type=volume,source={DATA},target=/data"]
    docker(
        "run",
        "-d",
        "--name",
        QBITTORRENT,
        "--network",
        NETWORK,
        *IDS,
        "-e",
        "WEBUI_PORT=8080",
        *data,
        "--mount",
        f"type=volume,source={QBITTORRENT_CONFIG},target=/config",
        QBITTORRENT_IMAGE,
    )
    docker(
        "run",
        "-d",
        "--name",
        JELLYFIN,
        "--network",
        NETWORK,
        *IDS,
        "-p",
        f"127.0.0.1:{args.port}:8096",
        "--mount",
        f"type=volume,source={DATA},target=/data,readonly",
        "--mount",
        f"type=volume,source={JELLYFIN_CONFIG},target=/config",
        jellyfin_image,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", type=int, default=1000)
    parser.add_argument("--episodes", type=int, default=12)
    parser.add_argument("--port", type=int, default=18398)
    parser.add_argument("--out", type=Path, default=ROOT / ".local" / "experiments" / "results")
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--keep", action="store_true", help="跑完不刪容器、volume 與 image")
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="沿用上一輪 --keep 留下的環境：只重 build image 與重量，不重造媒體樹、不重掃",
    )
    parser.add_argument(
        "--stages",
        default="jellyfin,inventory,reconcile",
        help="只量這幾段（逗號分隔）；配 --reuse 補量崩掉的那一段",
    )
    args = parser.parse_args()
    args.out = args.out.resolve()

    jellyfin_image = compose_image()
    report = Report(name="large-library-setup", out_dir=args.out)
    report.heading(f"大媒體庫的一次性環境（{jellyfin_image}、{QBITTORRENT_IMAGE}）")
    if not args.reuse:
        cleanup(image=False)
    args.out.mkdir(parents=True, exist_ok=True)
    try:
        # 改過 Berth 的程式碼要重量時，image 一定要重 build（快取的那幾層不會重做）。
        run(
            "build",
            "--target",
            "backend",
            "-f",
            str(ROOT / "deploy" / "Dockerfile"),
            "-t",
            IMAGE,
            str(ROOT),
        )
        if not args.reuse:
            build_environment(args, jellyfin_image)

        base = f"http://127.0.0.1:{args.port}"
        # 精靈的端點在精靈跑完之後就要驗證了（`--reuse`），所以那時改等公開的系統資訊。
        ready = f"{base}/System/Info/Public" if args.reuse else f"{base}/Startup/Configuration"
        poll(lambda: request(ready, timeout=5).ok, what="Jellyfin 載入完成", timeout=300)
        setup = Jellyfin(base, "large-library")
        setup.run_startup(report)
        srv = Server(base)
        admin = Credential("admin", setup.token)
        keys = srv.json(admin, "/Auth/Keys")["Items"]
        if not any(k.get("AppName") == API_KEY_APP for k in keys):
            srv.json(admin, "/Auth/Keys", method="POST", params={"app": API_KEY_APP})
            keys = srv.json(admin, "/Auth/Keys")["Items"]
        key = next(k["AccessToken"] for k in keys if k.get("AppName") == API_KEY_APP)
        if not args.reuse:
            create_library(srv, admin, "TV", "tvshows", "/data/library/tv")
            scan = wait_for_scan(setup, args.series, args.episodes)
            report.note(f"掃描 {args.series} 部 × {args.episodes} 集：{scan:.0f} 秒")
            report.record("scan_seconds", round(scan))
            report.write()
        library_id = setup.library_id("TV")

        measure = (
            f"measure --series {args.series} --episodes {args.episodes} "
            f"--jellyfin http://{JELLYFIN}:8096 --api-key {key} --library-id {library_id} "
            f"--qbittorrent http://{QBITTORRENT}:8080 --repeats {args.repeats} "
            f"--stages {args.stages}"
        )
        out = ["--mount", f"type=bind,source={args.out},target=/out"]
        run(*berth_container(measure, *out, network=True))
    finally:
        # Jellyfin 的程序可能無聲地重啟而容器照樣 Up（s6 會把它拉起來）：數它起來了幾次。
        logs = subprocess.run(
            ["docker", "logs", JELLYFIN], capture_output=True, encoding="utf-8", errors="replace"
        )
        startups = f"{logs.stdout}{logs.stderr}".count("Main: Startup complete")
        report.note(f"Jellyfin 這個容器裡啟動了 {startups} 次（1 次 = 沒有重啟過）")
        report.record("jellyfin_startups", startups)
        report.write()
        if args.keep:
            print(f"--keep：保留 {JELLYFIN}、{QBITTORRENT}、{VOLUMES}、{IMAGE}", flush=True)
        else:
            cleanup(image=True)
        print(leftovers(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
