"""M4 票 70：把 qBittorrent 的 preseed 腳本寫進 compose 檔（頂層 `configs` 的 `content`）。

部署要只剩 compose 檔加 `.env`，所以 `deploy/preseed/qbittorrent/10-berth.sh` 不能再是旁邊的
檔案。候選做法：頂層 `configs.<名>.content` 放腳本全文（`$` 寫成 `$$`，`content` 會做變數展開），
服務以長語法放到 `/custom-cont-init.d/10-berth.sh`。

linuxserver 的 `init-custom-files` 只執行 `-x` 的檔案（`[[ -x ]]`，否則印「is not an executable
file」），而 Docker 文件說 `content` 放進去預設是 0444。所以要量的是非 swarm 下 `mode` 有沒有效，
加上：

- 容器裡那個檔案的擁有者、權限、內容（與原檔逐位元組比 sha256，看 `$$` 有沒有展開回 `$`）；
- init 的 log 有沒有執行它、有沒有 docker-mods 的 tamper 警告（非 root 擁有、others 可寫）；
- `qBittorrent.conf` 裡兩個白名單鍵各恰好一行；
- `/api/v2/app/version` 從三處打：宿主經 published port、compose 網路上的 `BERTH_IP`、同網路的
  另一個位址。只有 `BERTH_IP` 該拿到 200；
- `restart` 與 `up -d --force-recreate`（拉新 image 時就是這條）之後再量一次：腳本說
  「already configured」、鍵沒有變成兩行。

變體（`--variant`，預設三個都跑）：

- `mode`：長語法加 `mode: 0555`，這是要選的寫法；
- `no-mode`：不寫 `mode`，對照組——證明 `mode` 是必要的，不是剛好可有可無；
- `profile-off`：同 `mode` 的 compose，但 `COMPOSE_PROFILES` 是空的（使用者選了既有 qBittorrent）：
  頂層 `configs` 沒有服務用時 `up -d` 會不會報錯，另一個服務照不照常起來。

compose 照部署檔的形狀：qbittorrent 在 `profiles: [qbittorrent]` 底下，另有一個沒有 profile、
永遠會起的 `idle`（代替 `berth`，同 image、只跑 `tail -f /dev/null`）。

image 用 `lscr.io/linuxserver/qbittorrent:latest`（與部署檔同 tag）。**不主動 pull**：VM 上另一套
Berth 也用這個 tag，pull 會改到它下次 recreate 拿到的版本；本機沒有時 compose 會自己拉。
實際版本記在報告裡。

compose project 與 network 叫 `berth-t70`、容器 `berth-t70-qbittorrent` 與 `berth-t70-idle`（協調者
為了與票 42 並行指定的名字），子網 10.70.0.0/16，WebUI port 7080；工作目錄（compose 檔與全新的
CONFIG_ROOT）在 `.local/experiments/inline-preseed/<變體>/`。
結束時 `down` 並刪掉工作目錄（CONFIG_ROOT 裡的檔案由容器內的 root 刪，rootless Docker 下宿主
使用者刪不掉 subuid 擁有的檔案）；`--keep` 留著除錯，只能配一個 `--variant`（變體共用同一個
project，後一個會重建掉前一個）。

只用標準庫、不 import `berth`：要原封不動搬到 Linux VM 上跑。搬的時候保留 repo 的相對位置
（這支、`lib.py`、`deploy/preseed/qbittorrent/10-berth.sh`）。

用法（報告寫到 .local/experiments/results/inline-preseed-<label>.json）：
    python scripts/experiments/inline_preseed.py --label desktop
    python scripts/experiments/inline_preseed.py --label compose-2.40.3 --compose-bin <執行檔>
    python3 scripts/experiments/inline_preseed.py --label vm-rootless    # 在 VM 上
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from lib import Report, poll, request

ROOT = Path(__file__).resolve().parents[2]
PRESEED = ROOT / "deploy" / "preseed" / "qbittorrent" / "10-berth.sh"
WORK = ROOT / ".local" / "experiments" / "inline-preseed"
RESULTS = ROOT / ".local" / "experiments" / "results"

PROJECT = "berth-t70"
IMAGE = "lscr.io/linuxserver/qbittorrent:latest"
SUBNET = "10.70.0.0/16"
IP_RANGE = "10.70.1.0/24"
BERTH_IP = "10.70.0.2"
#: 同網段、不在 ip_range 裡（不會被動態分配走），也不是 BERTH_IP。
OTHER_IP = "10.70.0.3"
WEBUI_PORT = 7080
TARGET = "/custom-cont-init.d/10-berth.sh"
KEYS = ("WebUI\\AuthSubnetWhitelistEnabled", "WebUI\\AuthSubnetWhitelist")
READY = "[ls.io-init] done."
#: 變體 → 服務 `configs` 長語法裡的 `mode` 那一行。
MODES = {
    "mode": "        mode: 0555\n",
    "no-mode": "",
}
PROFILE_OFF = "profile-off"
VARIANTS = (*MODES, PROFILE_OFF)

COMPOSE = """\
x-berth-ip: &berth-ip {berth_ip}

networks:
  default:
    name: {project}
    ipam:
      config:
        - subnet: {subnet}
          ip_range: {ip_range}

configs:
  qbittorrent-preseed:
    content: |
{content}
services:
  idle:
    image: {image}
    container_name: {project}-idle
    entrypoint: [tail, -f, /dev/null]
    stop_signal: SIGKILL

  qbittorrent:
    image: {image}
    container_name: {project}-qbittorrent
    profiles: [qbittorrent]
    environment:
      PUID: "1000"
      PGID: "1000"
      UMASK: "022"
      TZ: Etc/UTC
      WEBUI_PORT: "{port}"
      BERTH_IP: *berth-ip
    volumes:
      - ./config:/config
    ports:
      - {port}:{port}
    configs:
      - source: qbittorrent-preseed
        target: {target}
{mode}"""


def embed(script: str) -> str:
    """腳本全文 → `content: |` 底下的區塊：`$` 寫成 `$$`，每行縮排 6 格（空行不縮）。"""
    return "".join(
        f"      {line}\n" if line else "\n" for line in script.replace("$", "$$").splitlines()
    )


def compose_text(script: str, mode: str) -> str:
    return COMPOSE.format(
        berth_ip=BERTH_IP,
        project=PROJECT,
        subnet=SUBNET,
        ip_range=IP_RANGE,
        content=embed(script),
        image=IMAGE,
        port=WEBUI_PORT,
        target=TARGET,
        mode=MODES[mode],
    )


def run(
    cmd: list[str], *, check: bool = True, profiles: str = "qbittorrent"
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "COMPOSE_PROJECT_NAME": PROJECT, "COMPOSE_PROFILES": profiles},
    )


class Stack:
    def __init__(self, compose_cmd: list[str], workdir: Path) -> None:
        self.compose_cmd = compose_cmd
        self.workdir = workdir
        self.file = workdir / "compose.yml"
        self.container = f"{PROJECT}-qbittorrent"

    def compose(
        self, *args: str, check: bool = True, profiles: str = "qbittorrent"
    ) -> subprocess.CompletedProcess[str]:
        cmd = [*self.compose_cmd, "-f", str(self.file), *args]
        return run(cmd, check=check, profiles=profiles)

    def exec(self, *args: str) -> str:
        return run(["docker", "exec", self.container, *args], check=False).stdout

    def logs(self) -> list[str]:
        out = run(["docker", "logs", self.container], check=False)
        return (out.stdout + out.stderr).splitlines()

    def wait_ready(self, starts: int) -> None:
        """等第 `starts` 次 init 跑完，且 WebUI 在容器內回 200。"""
        poll(
            lambda: sum(READY in line for line in self.logs()) >= starts,
            what=f"第 {starts} 次 {READY}",
        )
        poll(
            lambda: (
                self.exec(
                    "curl",
                    "-s",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{http_code}",
                    f"http://localhost:{WEBUI_PORT}/",
                )
                == "200"
            ),
            what="WebUI 回 200",
        )

    def probe(self, ip: str) -> int:
        """從 compose 網路上的固定位址打 API，回狀態碼。"""
        out = run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                PROJECT,
                "--ip",
                ip,
                "--entrypoint",
                "curl",
                IMAGE,
                "-s",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                f"http://qbittorrent:{WEBUI_PORT}/api/v2/app/version",
            ],
            check=False,
        ).stdout.strip()
        return int(out) if out.isdigit() else 0

    def observe(self, expected_sha: str, log_from: int) -> dict[str, Any]:
        stat_fmt = "%U:%G %u:%g %a %F"
        file_stat = self.exec("stat", "-c", stat_fmt, TARGET).strip()
        dir_stat = self.exec("stat", "-c", stat_fmt, "/custom-cont-init.d").strip()
        mounted_sha = self.exec("sha256sum", TARGET).split(" ")[0]
        conf = self.exec("cat", "/config/qBittorrent/qBittorrent.conf").splitlines()
        lines = self.logs()[log_from:]
        mounts = json.loads(
            run(["docker", "inspect", "--format", "{{json .Mounts}}", self.container]).stdout
        )
        host = request(f"http://localhost:{WEBUI_PORT}/api/v2/app/version", timeout=10).status
        return {
            "file_stat": file_stat,
            "dir_stat": dir_stat,
            "content_identical": mounted_sha == expected_sha,
            "mounted_sha256": mounted_sha,
            "init_log": [
                line
                for line in lines
                if "custom-init" in line
                or "berth-preseed" in line
                or "security risk" in line
                or "not owned by root" in line
                or "write permissions for others" in line
            ],
            "tamper_warning": any("security risk" in line for line in lines),
            "key_lines": {key: [c for c in conf if c.startswith(f"{key}=")] for key in KEYS},
            "mounts": [{"type": m["Type"], "destination": m["Destination"]} for m in mounts],
            "api_status": {
                "host_published_port": host,
                f"berth_ip {BERTH_IP}": self.probe(BERTH_IP),
                f"other_ip {OTHER_IP}": self.probe(OTHER_IP),
            },
        }

    def cleanup(self) -> None:
        self.compose("down", "--volumes", "--remove-orphans", check=False)
        config = self.workdir / "config"
        if config.exists():
            # rootless Docker 下 CONFIG_ROOT 裡的檔案是 subuid 擁有，宿主使用者刪不掉。
            run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{config.resolve()}:/x",
                    "--entrypoint",
                    "sh",
                    IMAGE,
                    "-c",
                    "rm -rf /x/* /x/.[!.]*",
                ],
                check=False,
            )
        shutil.rmtree(self.workdir, ignore_errors=True)


def checks(stage: dict[str, Any], *, again: bool) -> dict[str, bool]:
    """選定的寫法在一個階段要成立的條件。`again`：重啟或重建後，腳本該說已設定過。"""
    log = "\n".join(stage["init_log"])
    status = stage["api_status"]
    return {
        "executable": len(perm := stage["file_stat"].split(" ")) > 2
        and int(perm[2], 8) & 0o111 != 0,
        "content_identical": stage["content_identical"],
        "init_ran_ok": "10-berth.sh: exited 0" in log,
        "preseed_said": ("already configured" if again else "added to") in log,
        "no_tamper_warning": not stage["tamper_warning"],
        "each_key_once": all(len(v) == 1 for v in stage["key_lines"].values()),
        "berth_ip_200": status[f"berth_ip {BERTH_IP}"] == 200,
        "others_403": status["host_published_port"] == 403
        and status[f"other_ip {OTHER_IP}"] == 403,
    }


def fresh_stack(compose_cmd: list[str], variant: str, mode: str) -> Stack:
    stack = Stack(compose_cmd, WORK / variant)
    stack.cleanup()
    stack.workdir.mkdir(parents=True)
    script = PRESEED.read_text(encoding="utf-8")
    stack.file.write_text(compose_text(script, mode), encoding="utf-8", newline="\n")
    return stack


def finish(report: Report, stack: Stack, variant: str, result: Any, keep: bool) -> None:
    report.record(variant, result)
    if keep:
        report.note(f"--keep：{stack.workdir} 與 {PROJECT} 留著")
    else:
        stack.cleanup()


def run_profile_off(report: Report, compose_cmd: list[str], keep: bool) -> bool:
    """`COMPOSE_PROFILES` 空的：頂層 `configs` 沒人用，`up -d` 照常、只起 `idle`。"""
    stack = fresh_stack(compose_cmd, PROFILE_OFF, "mode")
    report.heading(f"變體 {PROFILE_OFF}")
    result: dict[str, Any] = {}
    ok = False
    try:
        up = stack.compose("up", "-d", check=False, profiles="")
        ps = run(
            [
                "docker",
                "ps",
                "-a",
                "--format",
                "{{.Names}} {{.State}}",
                "--filter",
                f"label=com.docker.compose.project={PROJECT}",
            ]
        )
        result = {
            "returncode": up.returncode,
            "stderr_tail": up.stderr.strip().splitlines()[-5:],
            "containers": sorted(line for line in ps.stdout.splitlines() if line),
        }
        ok = up.returncode == 0 and result["containers"] == [f"{PROJECT}-idle running"]
        report.note(f"up -d → {up.returncode}；容器 {result['containers']}")
        report.note(f"    {'全部成立' if ok else '不成立'}")
    finally:
        finish(report, stack, PROFILE_OFF, result, keep)
    return ok


def run_variant(report: Report, compose_cmd: list[str], variant: str, keep: bool) -> bool:
    expected_sha = hashlib.sha256(PRESEED.read_bytes()).hexdigest()
    stack = fresh_stack(compose_cmd, variant, variant)

    report.heading(f"變體 {variant}")
    result: dict[str, Any] = {}
    ok = True
    try:
        stack.compose("up", "-d")
        stack.wait_ready(1)
        stages = [("first_start", False)]
        result["first_start"] = stack.observe(expected_sha, 0)

        before = len(stack.logs())
        stack.compose("restart", "qbittorrent")
        stack.wait_ready(2)
        stages.append(("restart", True))
        result["restart"] = stack.observe(expected_sha, before)

        stack.compose("up", "-d", "--force-recreate")
        stack.wait_ready(1)
        stages.append(("recreate", True))
        result["recreate"] = stack.observe(expected_sha, 0)

        for name, again in stages:
            stage = result[name]
            stage["checks"] = checks(stage, again=again)
            failed = [k for k, v in stage["checks"].items() if not v]
            ok = ok and not failed
            report.note(f"{name}: {stage['file_stat']}  api={stage['api_status']}")
            for line in stage["init_log"]:
                report.note(f"    {line}")
            report.note(f"    {'全部成立' if not failed else '不成立：' + ', '.join(failed)}")
    finally:
        finish(report, stack, variant, result, keep)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", required=True, help="報告檔名的後綴，例如 desktop")
    parser.add_argument(
        "--compose-bin", help="獨立的 docker-compose 執行檔；不給就用 `docker compose`"
    )
    parser.add_argument("--variant", choices=VARIANTS, action="append")
    parser.add_argument("--keep", action="store_true", help="留著容器與目錄；只能配一個 --variant")
    args = parser.parse_args()
    variants = args.variant or list(VARIANTS)
    if args.keep and len(variants) != 1:
        parser.error("--keep 只能配一個 --variant：變體共用同一個 project，後一個會重建掉前一個")

    compose_cmd = [args.compose_bin] if args.compose_bin else ["docker", "compose"]
    report = Report(f"inline-preseed-{args.label}", RESULTS)
    report.record(
        "environment",
        {
            "compose": run([*compose_cmd, "version"]).stdout.strip(),
            "docker": run(["docker", "version", "--format", "{{.Server.Version}}"]).stdout.strip(),
            "security_options": run(
                ["docker", "info", "--format", "{{json .SecurityOptions}}"]
            ).stdout.strip(),
            "image": run(
                [
                    "docker",
                    "image",
                    "inspect",
                    IMAGE,
                    "--format",
                    '{{index .Config.Labels "build_version"}}',
                ],
                check=False,
            ).stdout.strip(),
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        },
    )
    for key, value in report.sections["environment"].items():
        report.note(f"{key}: {value}")

    verdict = {}
    for variant in variants:
        if variant == PROFILE_OFF:
            verdict[variant] = run_profile_off(report, compose_cmd, args.keep)
        else:
            verdict[variant] = run_variant(report, compose_cmd, variant, args.keep)
    report.record("verdict", verdict)
    report.heading("結論")
    for variant, ok in verdict.items():
        report.note(f"{variant}: {'全部成立' if ok else '有不成立的條件'}")
    report.write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
