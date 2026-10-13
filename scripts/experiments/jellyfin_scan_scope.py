"""M4 票 62：Jellyfin 能不能只刷新一個媒體庫，對空的媒體庫有沒有效（brief §20.1）。

起一台**一次性**的 Jellyfin（image 取 `deploy/docker-compose.yml` 釘的那一個），四個媒體庫：

- `Shows`、`Other`：各有一部劇，第一次掃描就有內容；
- `Empty`（電影）：第一次掃描時是空的（套件內的媒體庫一開始都是這樣）；
- `Split`：兩個路徑，`split-a` 有內容、`split-b` 是空的（既有 Jellyfin 的媒體庫加上 Berth 的
  路徑就是這個形狀，brief §16.4）。

第一次全庫掃描之後只往磁碟放檔、不通知，再量：

1. OpenAPI 上和「刷新、掃描」有關的端點，與 `POST /Items/{id}/Refresh` 收什麼參數；
2. 對 `Shows` 的媒體庫 item 打 `POST /Items/{id}/Refresh`（模式照網頁「掃描媒體庫」送的
   `Default`）：`Shows` 的新檔多久出現、`Other` 同時放的新檔有沒有被一起掃到；
3. 同一支對 `Empty`：等 90 秒；再送路徑通知 `POST /Library/Media/Updated`，再等 90 秒；
4. 同一支對 `Split`：`split-a` 與 `split-b` 各放一部，哪一部出現；
5. 內建排程任務 `RefreshLibrary`：多久收下、多久跑完，`Empty`、`split-b`、`Other` 都掃到了沒；
   任務還在跑時再送一次的狀態碼；
6. `Empty` 有過內容之後，再對它刷新一次，新放的那一部出不出現。

媒體庫關掉所有網路 fetcher，結果不隨 TMDB 變動。跑完刪掉容器與工作目錄（`--keep` 保留）。

用法（報告寫到 .local/experiments/results/jellyfin-scan-scope.json）：
    python scripts/experiments/jellyfin_scan_scope.py
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from jellyfin_naming import Jellyfin
from jellyfin_permissions import FFMPEG, Credential, Server, compose_image, create_library, docker
from lib import Report

ROOT = Path(__file__).resolve().parents[2]
CONTAINER = "berth-exp-jellyfin-scan-scope"
#: 網頁「掃描媒體庫」（refreshdialog 的 `scan` 模式）送的就是這兩個 `Default`。
SCAN_MODES = {"metadataRefreshMode": "Default", "imageRefreshMode": "Default"}
#: 「沒出現」要等多久才算數。路徑通知有 `LibraryMonitorDelay`（預設 60 秒），多給 30 秒。
QUIET = 90


def episode(root: Path, show: str, number: int) -> Path:
    return root / show / "Season 01" / f"{show} - S01E{number:02d}.mkv"


def movie(root: Path, name: str) -> Path:
    return root / name / f"{name}.mkv"


@contextmanager
def disposable_jellyfin(workdir: Path, image: str, port: int, keep: bool) -> Iterator[str]:
    docker("rm", "-f", "-v", CONTAINER, check=False)
    workdir.mkdir(parents=True, exist_ok=True)
    if any(workdir.iterdir()):
        raise SystemExit(f"{workdir} 不是空目錄；這支腳本跑完會整個刪掉它")
    try:
        (workdir / "seed").mkdir()
        (workdir / "media").mkdir()
        (workdir / "config").mkdir()
        seed_mount = f"type=bind,source={workdir / 'seed'},target=/out"
        docker(
            "run",
            "--rm",
            "--mount",
            seed_mount,
            "--entrypoint",
            FFMPEG,
            image,
            *("-hide_banner", "-loglevel", "error", "-f", "lavfi"),
            *("-i", "color=c=black:s=64x64:r=1", "-t", "60"),
            *("-c:v", "libx264", "-pix_fmt", "yuv420p", "/out/seed.mkv"),
        )
        mounts = [
            "--mount",
            f"type=bind,source={workdir / 'config'},target=/config",
            "--mount",
            f"type=bind,source={workdir / 'media'},target=/media,readonly",
        ]
        env = ["-e", "PUID=1000", "-e", "PGID=1000", "-e", "TZ=Etc/UTC"]
        docker(
            "run", "-d", "--name", CONTAINER, "-p", f"127.0.0.1:{port}:8096", *env, *mounts, image
        )
        yield f"http://127.0.0.1:{port}"
    finally:
        if not keep:
            docker("rm", "-f", "-v", CONTAINER, check=False)
            shutil.rmtree(workdir, ignore_errors=True)


class Probe:
    def __init__(self, jf: Jellyfin, srv: Server, admin: Credential, media: Path, seed: Path):
        self.jf = jf
        self.srv = srv
        self.admin = admin
        self.media = media
        self.seed = seed

    def place(self, path: Path) -> str:
        """往磁碟放一個檔，回傳容器裡看到的路徑。不通知 Jellyfin。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.seed, path)
        return "/media/" + path.relative_to(self.media).as_posix()

    def paths(self, library: str) -> set[str]:
        rows = self.jf.items(
            parentId=self.jf.library_id(library),
            recursive="true",
            includeItemTypes="Episode,Movie",
            fields="Path",
        )
        return {str(row.get("Path", "")) for row in rows}

    def refresh(self, library: str) -> dict[str, Any]:
        started = time.monotonic()
        resp = self.srv.send(
            self.admin,
            f"/Items/{self.jf.library_id(library)}/Refresh",
            method="POST",
            params=SCAN_MODES,
        )
        return {"status": resp.status, "seconds": round(time.monotonic() - started, 2)}

    def appears(self, library: str, path: str, timeout: float) -> float | None:
        """`path` 在 `timeout` 秒內出現在 `library` 的話，回傳等了幾秒。"""
        return self.until(lambda: path in self.paths(library), timeout)

    @staticmethod
    def until(check: Callable[[], bool], timeout: float) -> float | None:
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            if check():
                return round(time.monotonic() - started, 1)
            time.sleep(2)
        return None


def openapi(srv: Server, admin: Credential, report: Report) -> None:
    report.heading("1. OpenAPI")
    spec = srv.json(admin, "/api-docs/openapi.json")
    related = sorted(
        f"{method.upper()} {path}"
        for path, ops in spec.get("paths", {}).items()
        for method in ops
        if any(word in path.lower() for word in ("refresh", "scan", "media/updated"))
    )
    refresh = spec["paths"]["/Items/{itemId}/Refresh"]["post"]
    params = [param["name"] for param in refresh.get("parameters", [])]
    report.record("openapi", {"version": spec["info"]["version"], "related": related})
    report.record("refresh_item_parameters", params)
    report.note(f"OpenAPI {spec['info']['version']}；相關端點：{', '.join(related)}")
    report.note(f"POST /Items/{{itemId}}/Refresh 的參數：{', '.join(params)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18496)
    parser.add_argument(
        "--workdir", type=Path, default=ROOT / ".local" / "experiments" / "scan-scope"
    )
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    image = compose_image()
    report = Report("jellyfin-scan-scope", ROOT / ".local" / "experiments" / "results")
    report.record("image", image)
    workdir: Path = args.workdir.resolve()
    media = workdir / "media"
    with disposable_jellyfin(workdir, image, args.port, args.keep) as base:
        jf = Jellyfin(base, "scan-scope")
        jf.run_startup(report)
        srv = Server(base)
        admin = Credential("admin", jf.token, "berth-exp-scan-scope")
        probe = Probe(jf, srv, admin, media, workdir / "seed" / "seed.mkv")
        report.record("version", jf.public_info().get("Version"))

        report.heading("0. 第一次掃描")
        probe.place(episode(media / "shows", "Alpha", 1))
        probe.place(episode(media / "other", "Beta", 1))
        probe.place(episode(media / "split-a", "Gamma", 1))
        for folder in ("empty", "split-b"):
            (media / folder).mkdir()
        create_library(srv, admin, "Shows", "tvshows", "/media/shows")
        create_library(srv, admin, "Other", "tvshows", "/media/other")
        create_library(srv, admin, "Empty", "movies", "/media/empty")
        create_library(srv, admin, "Split", "tvshows", "/media/split-a")
        srv.json(
            admin,
            "/Library/VirtualFolders/Paths",
            method="POST",
            params={"refreshLibrary": "false"},
            json_body={"Name": "Split", "PathInfo": {"Path": "/media/split-b"}},
        )
        jf.run_task_and_wait("RefreshLibrary")
        first = {name: sorted(probe.paths(name)) for name in ("Shows", "Other", "Empty", "Split")}
        report.record("first_scan", first)
        report.note(f"第一次掃描後：{ {name: len(rows) for name, rows in first.items()} }")

        openapi(srv, admin, report)

        report.heading("2. 只刷新 Shows")
        alpha2 = probe.place(episode(media / "shows", "Alpha", 2))
        delta = probe.place(episode(media / "shows", "Delta", 1))
        beta2 = probe.place(episode(media / "other", "Beta", 2))
        sent = probe.refresh("Shows")
        alpha_after = probe.appears("Shows", alpha2, 120)
        delta_after = probe.appears("Shows", delta, 30)
        time.sleep(15)
        other_seen = beta2 in probe.paths("Other")
        report.record(
            "refresh_shows",
            {
                "request": sent,
                "existing_show_new_episode_after": alpha_after,
                "new_show_after": delta_after,
                "other_library_picked_up": other_seen,
            },
        )
        report.note(
            f"POST 回 {sent['status']}（{sent['seconds']} 秒）；Shows 的新集 {alpha_after} 秒、"
            f"新劇 {delta_after} 秒出現；Other 同時放的新集被掃到：{other_seen}"
        )

        report.heading("3. 空的媒體庫")
        epsilon = probe.place(movie(media / "empty", "Epsilon"))
        sent = probe.refresh("Empty")
        by_refresh = probe.appears("Empty", epsilon, QUIET)
        updated = srv.send(
            admin,
            "/Library/Media/Updated",
            method="POST",
            json_body={"Updates": [{"Path": epsilon, "UpdateType": "Created"}]},
        )
        by_notify = probe.appears("Empty", epsilon, QUIET)
        report.record(
            "refresh_empty",
            {
                "request": sent,
                "appeared_after_refresh": by_refresh,
                "notify_status": updated.status,
                "appeared_after_notify": by_notify,
            },
        )
        report.note(
            f"刷新 Empty（{sent['status']}）後 {QUIET} 秒內出現：{by_refresh}；"
            f"再送路徑通知（{updated.status}）後 {QUIET} 秒內出現：{by_notify}"
        )

        report.heading("4. 兩個路徑、一個空的")
        gamma2 = probe.place(episode(media / "split-a", "Gamma", 2))
        zeta = probe.place(episode(media / "split-b", "Zeta", 1))
        sent = probe.refresh("Split")
        gamma_after = probe.appears("Split", gamma2, 120)
        zeta_after = probe.appears("Split", zeta, 30)
        report.record(
            "refresh_split",
            {
                "request": sent,
                "seen_location_after": gamma_after,
                "empty_location_after": zeta_after,
            },
        )
        report.note(f"split-a 的新集 {gamma_after} 秒出現；split-b 的新劇 {zeta_after}")

        report.heading("5. 全庫掃描（RefreshLibrary 排程任務）")
        task = jf.task("RefreshLibrary")
        started = time.monotonic()
        first_post = srv.send(admin, f"/ScheduledTasks/Running/{task['Id']}", method="POST")
        accepted = round(time.monotonic() - started, 2)
        second_post = srv.send(admin, f"/ScheduledTasks/Running/{task['Id']}", method="POST")
        idle = Probe.until(lambda: (jf.task("RefreshLibrary") or {}).get("State") == "Idle", 300)
        seen = {
            "empty": epsilon in probe.paths("Empty"),
            "split_b": zeta in probe.paths("Split"),
            "other": beta2 in probe.paths("Other"),
        }
        report.record(
            "full_scan",
            {
                "status": first_post.status,
                "accepted_seconds": accepted,
                "second_post_while_running": second_post.status,
                "idle_after": idle,
                "picked_up": seen,
                "last_result": (jf.task("RefreshLibrary") or {}).get("LastExecutionResult"),
            },
        )
        report.note(
            f"POST 回 {first_post.status}（{accepted} 秒），跑完 {idle} 秒；"
            f"還在跑時再送一次回 {second_post.status}；掃到：{seen}"
        )

        report.heading("6. Empty 有過內容之後")
        eta = probe.place(movie(media / "empty", "Eta"))
        sent = probe.refresh("Empty")
        eta_after = probe.appears("Empty", eta, 120)
        report.record("refresh_empty_after_content", {"request": sent, "appeared_after": eta_after})
        report.note(f"刷新 Empty（{sent['status']}）後新的一部 {eta_after} 秒出現")

    report.write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
