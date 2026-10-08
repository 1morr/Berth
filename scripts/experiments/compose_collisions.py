"""M4 票 16：套件容器撞名或撞 port 時，`docker compose up -d` 怎麼收場（brief §20.14）。

使用者接既有服務卻忘了從 `COMPOSE_PROFILES` 拿掉套件內那一台，宿主上就同時有兩個想叫同一個名字、
佔同一個 port 的容器。社群的說法是撞到的那一台起不來、其他照常起；這裡實際量，並量 `berth` 的
`extra_hosts: host.docker.internal:host-gateway` 在這台 Docker 上解到哪、連不連得到宿主。

情境（每一個都先 `down`，再放一個「使用者原本的」佔位容器，再 `up -d`）：

| 鍵 | 套件容器名 | 佔位容器 | 量什麼 |
| --- | --- | --- | --- |
| `name_old` | 票 16 之前的 `jellyfin` | 叫 `jellyfin` | 撞名：結束碼、錯誤訊息、其他容器起了沒 |
| `name_new` | 現在的 `berth-jellyfin` | 叫 `jellyfin` | 改名之後撞名消失 |
| `port` | `berth-jellyfin` | 叫 `jellyfin`、佔 `JELLYFIN_PORT` | 撞 port：同上三件 |
| `no_profiles` | — | 無 | `COMPOSE_PROFILES=`（三個都接既有）只起 `berth` |

`port` 那一輪 `berth` 起來之後，在它裡面 `getent hosts host.docker.internal`、讀 `/etc/hosts`，並以
`http://host.docker.internal:<JELLYFIN_PORT>/` 連佔位容器發佈在宿主上的 port（它是 `http.server`）；
另以拋棄式容器比較加不加 `--add-host host.docker.internal:host-gateway` 時解到的位址——Docker Desktop
本來就有這個名字，明寫一條不能把它蓋成連不到的位址。

**隔離**：compose 檔取自 `deploy/`，但專案名、網路名改成 `berth-exp-collide`，子網改成
`172.26.0.0/16`，每個容器名前面加 `bexp-`（佔位容器也是），port 用 4xxxx，設定與資料放在
`.local/experiments/compose-collisions/`。同一台機器上正在跑的正式部署一個都不碰。`berth` 的 image
用本地已有的（`--berth-image`），不 build。結束時 `down -v`、刪佔位容器與目錄，印出殘留。

用法（報告寫到 .local/experiments/results/compose-collisions.json）：
    python scripts/experiments/compose_collisions.py --berth-image berth:e2e
"""

from __future__ import annotations

import argparse
import json
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
WORK = REPO / ".local" / "experiments" / "compose-collisions"
RESULTS = REPO / ".local" / "experiments" / "results"

PROJECT = "berth-exp-collide"
PREFIX = "bexp-"
SQUATTER = f"{PREFIX}jellyfin"
SQUATTER_IMAGE = "python:3.13-alpine"
PORTS = {
    "BERTH_PORT": "48383",
    "JELLYFIN_PORT": "48096",
    "QBITTORRENT_WEBUI_PORT": "48080",
    "QBITTORRENT_BT_PORT": "46881",
    "PROWLARR_PORT": "49696",
}
ALL_PROFILES = "jellyfin,qbittorrent,prowlarr"
#: `up -d` 回來之後等這麼久再看狀態：撞 port 的錯要等容器真的 start 才出現。
SETTLE = 10
#: shell 裡 export 的這些會蓋過 `.env`（2026-09-26 在 berth-lab 踩過），子程序一律拿掉。
SHADOWING = ("CONFIG_ROOT", "DATA_ROOT", "COMPOSE_PROFILES", "COMPOSE_PROJECT_NAME", *PORTS)


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key not in SHADOWING}
    return subprocess.run(
        ["docker", *args], check=check, capture_output=True, text=True, encoding="utf-8", env=env
    )


def compose(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return docker(
        "compose",
        "--project-directory",
        str(WORK),
        "-f",
        str(WORK / "docker-compose.yml"),
        *args,
        check=check,
    )


def substitute(text: str, old: str, new: str) -> str:
    """每一處替換都要真的換到東西：deploy/ 的 compose 改了寫法時要在這裡停下，而不是默默量錯。"""
    if old not in text:
        raise SystemExit(f"deploy/docker-compose.yml no longer contains {old!r}")
    return text.replace(old, new)


def isolated_compose(berth_image: str, *, old_names: bool) -> str:
    text = (DEPLOY / "docker-compose.yml").read_text(encoding="utf-8")
    text = substitute(text, "\nname: berth\n", f"\nname: {PROJECT}\n")
    text = substitute(text, "    name: berth\n", f"    name: {PROJECT}\n")
    text = substitute(text, "172.28.", "172.26.")
    text = substitute(text, "ghcr.io/1morr/berth:latest", berth_image)
    text = substitute(text, "container_name: berth\n", f"container_name: {PREFIX}berth\n")
    for service in ("jellyfin", "qbittorrent", "prowlarr"):
        name = service if old_names else f"berth-{service}"
        text = substitute(
            text, f"container_name: berth-{service}\n", f"container_name: {PREFIX}{name}\n"
        )
    return text


def prepare(berth_image: str, *, old_names: bool, profiles: str) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "docker-compose.yml").write_text(
        isolated_compose(berth_image, old_names=old_names), encoding="utf-8", newline="\n"
    )
    lines = [
        "CONFIG_ROOT=./config",
        "DATA_ROOT=./data",
        *(f"{key}={value}" for key, value in PORTS.items()),
        f"COMPOSE_PROFILES={profiles}",
    ]
    (WORK / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def squat(*, publish: bool) -> None:
    """「使用者原本的 Jellyfin」：一個叫 jellyfin 的容器，`publish` 時佔住 JELLYFIN_PORT。"""
    docker("rm", "-f", SQUATTER, check=False)
    ports = ["-p", f"{PORTS['JELLYFIN_PORT']}:8000"] if publish else []
    docker(
        "run",
        "-d",
        "--name",
        SQUATTER,
        *ports,
        SQUATTER_IMAGE,
        "python",
        "-m",
        "http.server",
        "8000",
    )


def states() -> dict[str, dict[str, Any]]:
    """這個專案的每個容器：狀態、結束碼、錯誤（撞 port 的錯記在容器的 State.Error）。"""
    ids = docker("ps", "-aq", "--filter", f"label=com.docker.compose.project={PROJECT}").stdout
    result: dict[str, dict[str, Any]] = {}
    for container in ids.split():
        info = json.loads(docker("inspect", container).stdout)[0]
        result[info["Name"].lstrip("/")] = {
            "status": info["State"]["Status"],
            "exit_code": info["State"]["ExitCode"],
            "error": info["State"]["Error"],
        }
    return dict(sorted(result.items()))


def run_up(report: Report, key: str) -> dict[str, Any]:
    up = compose("up", "-d")
    time.sleep(SETTLE)
    outcome: dict[str, Any] = {
        "exit_code": up.returncode,
        "stderr": [line for line in up.stderr.splitlines() if line.strip()][-8:],
        "containers": states(),
    }
    report.record(key, outcome)
    report.note(f"`up -d` exit {up.returncode}")
    for line in outcome["stderr"]:
        report.note(f"  stderr: {line}")
    for name, state in outcome["containers"].items():
        error = f" — {state['error']}" if state["error"] else ""
        report.note(f"  {name}: {state['status']}{error}")
    return outcome


def host_gateway(report: Report) -> None:
    berth = f"{PREFIX}berth"
    port = PORTS["JELLYFIN_PORT"]
    resolved = docker("exec", berth, "getent", "hosts", "host.docker.internal", check=False)
    hosts = docker("exec", berth, "cat", "/etc/hosts", check=False)
    fetch = docker(
        "exec",
        berth,
        "python",
        "-c",
        "import urllib.request; r = urllib.request.urlopen("
        f"'http://host.docker.internal:{port}/', timeout=5); print(r.status)",
        check=False,
    )
    plain = docker(
        "run", "--rm", SQUATTER_IMAGE, "getent", "hosts", "host.docker.internal", check=False
    )
    added = docker(
        "run",
        "--rm",
        "--add-host",
        "host.docker.internal:host-gateway",
        SQUATTER_IMAGE,
        "getent",
        "hosts",
        "host.docker.internal",
        check=False,
    )
    outcome: dict[str, Any] = {
        "berth_getent": resolved.stdout.strip() or resolved.stderr.strip(),
        "berth_etc_hosts": [line for line in hosts.stdout.splitlines() if "host.docker" in line],
        "berth_fetch_host_port": fetch.stdout.strip() or fetch.stderr.strip()[-300:],
        "plain_container_getent": plain.stdout.strip() or f"(exit {plain.returncode})",
        "add_host_container_getent": added.stdout.strip() or f"(exit {added.returncode})",
    }
    report.record("host_gateway", outcome)
    for what, value in outcome.items():
        report.note(f"{what}: {value}")


def wipe() -> None:
    """linuxserver 的檔案是 uid 1000 建的，宿主不一定刪得動：用容器刪，再刪目錄。"""
    compose("down", "-v", "--remove-orphans")
    docker("rm", "-f", SQUATTER, check=False)
    if WORK.exists():
        docker(
            "run",
            "--rm",
            "-v",
            f"{WORK}:/w",
            SQUATTER_IMAGE,
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

    report = Report("compose-collisions", RESULTS)
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

    # (鍵, 用票 16 之前的容器名, 佔位容器：None / 只佔名字 / 也佔 port,
    #  COMPOSE_PROFILES, 量 host-gateway)
    scenarios = (
        ("name_old", True, "name", ALL_PROFILES, False),
        ("name_new", False, "name", ALL_PROFILES, False),
        ("port", False, "port", ALL_PROFILES, True),
        ("no_profiles", False, None, "", False),
    )
    try:
        wipe()
        for key, old_names, squatter, profiles, probe_host in scenarios:
            report.heading(key)
            compose("down", "--remove-orphans")
            docker("rm", "-f", SQUATTER, check=False)
            prepare(args.berth_image, old_names=old_names, profiles=profiles)
            if squatter is not None:
                squat(publish=squatter == "port")
            run_up(report, key)
            if probe_host:
                report.heading("host_gateway")
                host_gateway(report)
    finally:
        if not args.keep:
            wipe()
        report.heading("leftovers")
        report.note(leftovers())
        report.write()


if __name__ == "__main__":
    main()
