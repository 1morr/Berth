"""M4 票 36：選了「既有」之後，怎麼停掉已經在跑的套件內那一台（brief §20.14）。

README 原本只說「把它從 `COMPOSE_PROFILES` 拿掉再 `docker compose up -d`」。
2026-10-06 的審計（S2）看到 `up -d` 之後套件內那兩台照樣在跑。
這裡把每一種候選的指令都量一次，使用者文件與精靈照量到的寫：

| 步驟 | 指令 | 量什麼 |
| --- | --- | --- |
| `all_up` | 三個 profile 都開，`up -d` | 起點：四個容器都在跑 |
| `profile_removed` | `COMPOSE_PROFILES=prowlarr`，`up -d` | 拿掉之後，那兩台還在不在跑 |
| `remove_orphans` | 同上，`up -d --remove-orphans` | 不在啟用 profile 裡的服務算不算 orphan |
| `stop` | `stop jellyfin qbittorrent` | 指名不在啟用 profile 裡的服務，stop 收不收 |
| `up_again` | `up -d` | 停掉的那兩台會不會被下一次 `up -d` 叫起來 |
| `down_plain` | `down` | 不帶 `--profile '*'` 的 `down` 收不收停掉的那兩台（清理用） |

**隔離**：compose 檔取自 `deploy/`，專案名與網路名改成 `berth-exp-profiles`，
子網改成 `10.232.0.0/16`（Docker 自動配發的範圍外），容器名前面加 `bexp-`，port 用 4xxxx，
設定與資料放在 `.local/experiments/compose-profiles/`。同一台機器上正在跑的部署一個都不碰。
image 都用本地已有的（`--berth-image`），不 pull、不 build。
結束時 `--profile '*' down -v`、刪目錄，印出殘留。

用法（報告寫到 .local/experiments/results/compose-profile-removal.json）：
    python scripts/experiments/compose_profile_removal.py --berth-image berth:e2e
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from lib import Report

REPO = Path(__file__).resolve().parents[2]
DEPLOY = REPO / "deploy"
WORK = REPO / ".local" / "experiments" / "compose-profiles"
RESULTS = REPO / ".local" / "experiments" / "results"

PROJECT = "berth-exp-profiles"
PREFIX = "bexp-"
PORTS = {
    "BERTH_PORT": "48384",
    "JELLYFIN_PORT": "48097",
    "QBITTORRENT_WEBUI_PORT": "48081",
    "QBITTORRENT_BT_PORT": "46882",
    "PROWLARR_PORT": "49697",
}
ALL_PROFILES = "jellyfin,qbittorrent,prowlarr"
#: 使用者選了既有 Jellyfin 與既有 qBittorrent 之後那一行（審計 S2 的組合）。
EXISTING_CHOSEN = "prowlarr"
STOPPED = ("jellyfin", "qbittorrent")
#: `up -d` 回來之後等這麼久再看狀態，容器的 start 失敗才來得及出現。
SETTLE = 5
#: shell 裡 export 的這些會蓋過 `.env`（2026-09-26 在 berth-lab 踩過），子程序一律拿掉。
SHADOWING = ("CONFIG_ROOT", "DATA_ROOT", "COMPOSE_PROFILES", "COMPOSE_PROJECT_NAME", *PORTS)


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key not in SHADOWING}
    return subprocess.run(
        ["docker", *args], check=check, capture_output=True, text=True, encoding="utf-8", env=env
    )


def compose(*args: str) -> subprocess.CompletedProcess[str]:
    return docker(
        "compose",
        "--project-directory",
        str(WORK),
        "-f",
        str(WORK / "docker-compose.yml"),
        *args,
        check=False,
    )


def substitute(text: str, old: str, new: str) -> str:
    """每一處替換都要真的換到東西：deploy/ 的 compose 改了寫法時要在這裡停下，而不是默默量錯。"""
    if old not in text:
        raise SystemExit(f"deploy/docker-compose.yml no longer contains {old!r}")
    return text.replace(old, new)


def isolated_compose(berth_image: str) -> str:
    text = (DEPLOY / "docker-compose.yml").read_text(encoding="utf-8")
    text = substitute(text, "\nname: berth\n", f"\nname: {PROJECT}\n")
    text = substitute(text, "    name: berth\n", f"    name: {PROJECT}\n")
    text = substitute(text, "172.28.", "10.232.")
    text = substitute(text, "ghcr.io/1morr/berth:latest", berth_image)
    text = substitute(text, "container_name: berth\n", f"container_name: {PREFIX}berth\n")
    for service in ("jellyfin", "qbittorrent", "prowlarr"):
        text = substitute(
            text,
            f"container_name: berth-{service}\n",
            f"container_name: {PREFIX}berth-{service}\n",
        )
    return text


def write_env(profiles: str) -> None:
    lines = [
        "CONFIG_ROOT=./config",
        "DATA_ROOT=./data",
        *(f"{key}={value}" for key, value in PORTS.items()),
        f"COMPOSE_PROFILES={profiles}",
    ]
    (WORK / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def prepare(berth_image: str) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "docker-compose.yml").write_text(
        isolated_compose(berth_image), encoding="utf-8", newline="\n"
    )
    shutil.copytree(DEPLOY / "preseed", WORK / "preseed", dirs_exist_ok=True)
    write_env(ALL_PROFILES)


def states() -> dict[str, str]:
    """這個專案的每個容器與狀態（`running` / `exited` / ...）。"""
    out = docker(
        "ps",
        "-a",
        "--filter",
        f"label=com.docker.compose.project={PROJECT}",
        "--format",
        "{{.Names}}\t{{.State}}",
    ).stdout
    rows = (line.split("\t") for line in out.splitlines() if line.strip())
    return dict(sorted((name, state) for name, state in rows))


def step(report: Report, key: str, *args: str) -> dict[str, Any]:
    report.heading(key)
    done = compose(*args)
    time.sleep(SETTLE)
    outcome: dict[str, Any] = {
        "command": "docker compose " + " ".join(args),
        "exit_code": done.returncode,
        "stderr": [line for line in done.stderr.splitlines() if line.strip()][-8:],
        "containers": states(),
    }
    report.record(key, outcome)
    report.note(f"`{outcome['command']}` exit {done.returncode}")
    for line in outcome["stderr"]:
        report.note(f"  stderr: {line}")
    for name, state in outcome["containers"].items():
        report.note(f"  {name}: {state}")
    return outcome


def wipe() -> None:
    """linuxserver 的檔案是 uid 1000 建的，宿主不一定刪得動：用容器刪，再刪目錄。"""
    if WORK.exists():
        compose("--profile", "*", "down", "-v", "--remove-orphans")
        docker(
            "run",
            "--rm",
            "-v",
            f"{WORK}:/w",
            "python:3.13-alpine",
            "sh",
            "-c",
            "rm -rf /w/config /w/data",
            check=False,
        )
        shutil.rmtree(WORK, ignore_errors=True)


def leftovers() -> str:
    containers = docker("ps", "-a", "--filter", f"name={PREFIX}", "--format", "{{.Names}}")
    networks = docker("network", "ls", "--filter", f"name={PROJECT}", "--format", "{{.Name}}")
    return (containers.stdout + networks.stdout).strip() or "(none)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--berth-image", required=True, help="本地已有的 Berth image")
    parser.add_argument("--keep", action="store_true", help="結束時不清掉，留著除錯")
    args = parser.parse_args()

    report = Report("compose-profile-removal", RESULTS)
    report.record(
        "versions",
        {
            "engine": docker("version", "--format", "{{.Server.Version}}").stdout.strip(),
            "compose": docker("compose", "version", "--short").stdout.strip(),
            "os": docker(
                "info", "--format", "{{.OperatingSystem}} {{.KernelVersion}}"
            ).stdout.strip(),
        },
    )
    report.note(f"versions: {report.sections['versions']}")

    try:
        wipe()
        prepare(args.berth_image)
        # `--pull never`：只用本地的 image，不移動別的部署共用的 tag（M4 票 34）。
        step(report, "all_up", "up", "-d", "--pull", "never")
        write_env(EXISTING_CHOSEN)
        step(report, "profile_removed", "up", "-d", "--pull", "never")
        step(report, "remove_orphans", "up", "-d", "--pull", "never", "--remove-orphans")
        step(report, "stop", "stop", *STOPPED)
        step(report, "up_again", "up", "-d", "--pull", "never")
        step(report, "down_plain", "down")
    finally:
        if not args.keep:
            wipe()
        report.heading("leftovers")
        report.note(leftovers())
        report.write()


if __name__ == "__main__":
    main()
