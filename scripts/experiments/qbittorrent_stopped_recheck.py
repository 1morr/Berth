"""M3 票 03：**停住的** torrent 送 `recheck` 與「重新開始」之後，狀態怎麼走（brief §20.2）。

M2 票 09c 的 `qbittorrent_recovery.py` 量的四包都是 `missingFiles`（重啟前在跑的），沒有一包是
使用者或分享比率停住的。原始碼說兩版對停住的 torrent 做 recheck 時都會「校驗完再停下來」，
而清掉這個條件的方式不同：

- 4.4.5 `forceRecheck` 設 `stop_when_ready`，`resume()` 看到 `m_isStopped` 還是真就把它清掉。
- 5.2.3 `forceRecheck` **自己先呼叫 `start()`**（`m_isStopped` 變假），再設
  `StopCondition::FilesChecked`；之後的 `start()` 看到沒停就什麼都不做，條件留著，校驗完
  `handleTorrentChecked` 照樣 `stop()`（[`torrentimpl.cpp`](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.3/src/base/bittorrent/torrentimpl.cpp)）。

所以要量的是順序與時機：start 送到的時候校驗還沒做完。資料用**稀疏的全零檔**（`truncate`），
宿主不必寫幾 GB，piece 雜湊只要算一次；大小由 `--size-gib` 決定，要大到校驗跑好幾秒。

情境（每個都是一包新的 torrent，校驗完是做種中，接著照情境先停住或不停）：

| 鍵 | 前置 | 動作 |
| --- | --- | --- |
| `stopped_recheck` | 停住 | recheck |
| `stopped_recheck_start` | 停住 | recheck → start（Berth 09c 的順序） |
| `stopped_start_recheck` | 停住 | start → recheck |
| `missing_recheck` | 停住、刪掉一個檔 | recheck |
| `missing_recheck_start` | 停住、刪掉一個檔 | recheck → start |
| `missing_start_recheck` | 停住、刪掉一個檔 | start → recheck |
| `seeding_missing_recheck_start` | 做種中、刪掉一個檔 | recheck → start |
| `seeding_missing_start_recheck` | 做種中、刪掉一個檔 | start → recheck |

每個情境記下動作之後的 state 序列（只記變化，附相對秒數與 progress），直到 state 不在
校驗 / 搬移中並且 `--hold` 秒不變。

自己起停一次性的 network、兩個 volume 與容器（前綴 `berth-exp-recheck`），結束時刪掉並印出
`docker ps -a` / `docker volume ls` 的過濾結果；`--keep` 留著除錯。

用法（報告寫到 .local/experiments/results/qbittorrent-stopped-recheck-<版本>.json）：
    python scripts/experiments/qbittorrent_stopped_recheck.py
    python scripts/experiments/qbittorrent_stopped_recheck.py --image <image>

`--image` 預設是 `lscr.io/linuxserver/qbittorrent:5.2.3`；票 03 另外跑了 `:latest`（compose 的預設）
與 `:4.4.5`（對照組）。
"""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from lib import Report, Torrent, bencode, poll
from qbittorrent_poller import QBittorrent

PREFIX = "berth-exp-recheck"
CONTAINER = PREFIX
NETWORK = PREFIX
CONFIG = f"{PREFIX}-config"
DATA = f"{PREFIX}-data"
SAVE_PATH = "/data/complete"
PIECE = 1 << 22
#: 校驗與搬移中：序列還沒走完。
TRANSIENT = ("checking", "moving", "allocating", "metaDL", "unknown")
#: 與 `prepare_qbittorrent.py` 同一份底，只換存檔路徑與白名單網段。
CONF = """[LegalNotice]
Accepted=true

[Preferences]
Connection\\UPnP=false
Downloads\\SavePath={save}/
WebUI\\Address=*
WebUI\\ServerDomains=*
WebUI\\AuthSubnetWhitelistEnabled=true
WebUI\\AuthSubnetWhitelist={subnet}
"""
SCENARIOS: tuple[tuple[str, bool, bool, tuple[str, ...]], ...] = (
    # (鍵, 先停住, 刪掉第二個檔, 動作)
    ("stopped_recheck", True, False, ("recheck",)),
    ("stopped_recheck_start", True, False, ("recheck", "start")),
    ("stopped_start_recheck", True, False, ("start", "recheck")),
    ("missing_recheck", True, True, ("recheck",)),
    ("missing_recheck_start", True, True, ("recheck", "start")),
    ("missing_start_recheck", True, True, ("start", "recheck")),
    ("seeding_missing_recheck_start", False, True, ("recheck", "start")),
    ("seeding_missing_start_recheck", False, True, ("start", "recheck")),
)


def docker(
    *args: str, check: bool = True, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args], check=check, capture_output=True, text=True, input=stdin
    )


def cleanup() -> None:
    docker("rm", "-f", "-v", CONTAINER, check=False)
    docker("volume", "rm", CONFIG, DATA, check=False)
    docker("network", "rm", NETWORK, check=False)


def leftovers() -> str:
    containers = docker("ps", "-a", "--filter", f"name={PREFIX}", "--format", "{{.Names}}")
    volumes = docker("volume", "ls", "--filter", f"name={PREFIX}", "--format", "{{.Name}}")
    networks = docker("network", "ls", "--filter", f"name={PREFIX}", "--format", "{{.Name}}")
    return (
        f"docker ps -a --filter name={PREFIX}: [{containers.stdout.strip()}]\n"
        f"docker volume ls --filter name={PREFIX}: [{volumes.stdout.strip()}]\n"
        f"docker network ls --filter name={PREFIX}: [{networks.stdout.strip()}]"
    )


def zero_torrent(name: str, files: list[tuple[str, int]]) -> Torrent:
    """全零內容的多檔 torrent。每個大小都是 `PIECE` 的倍數，所以每一片的雜湊都相同。"""
    total = sum(size for _, size in files)
    assert total % PIECE == 0
    info: dict[str, Any] = {
        "name": name,
        "files": [{"length": size, "path": path.split("/")} for path, size in files],
        "piece length": PIECE,
        "pieces": hashlib.sha1(bytes(PIECE)).digest() * (total // PIECE),
        "berth-salt": name,
    }
    raw = bencode({"announce": "http://127.0.0.1:6969/announce", "info": info})
    return Torrent(name=name, raw=raw, info_hash=hashlib.sha1(bencode(info)).hexdigest())


def keep_cookies() -> None:
    """同一個 session 一路用到底（brief §20.2：免密白名單上照樣發 SID）。"""
    jar = http.cookiejar.CookieJar()
    urllib.request.install_opener(
        urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    )


class Client(QBittorrent):
    """`qbittorrent_poller.QBittorrent` 加上這一支要的：版本相關的端點名與兩個小工具。"""

    def __init__(self, port: int) -> None:
        # qBittorrent 比對 Host 的 port 與它自己聽的那一個（容器內 8080），不是宿主發佈的。
        super().__init__(f"http://127.0.0.1:{port}", "localhost:8080")
        self.start_name = "torrents/start"
        self.stop_name = "torrents/stop"
        self.stop_key = "stopped"

    def post(self, path: str, form: dict[str, str]) -> None:
        resp = self.api(path, method="POST", form=form)
        if not resp.ok:
            raise RuntimeError(f"{path} -> {resp.status} {resp.text[:200]}")

    def row(self, info_hash: str) -> dict[str, Any]:
        resp = self.api("torrents/info", params={"hashes": info_hash})
        rows = resp.json() if resp.ok else []
        return rows[0] if rows else {}


def wait_for_webui(client: Client) -> tuple[str, str]:
    def up() -> bool:
        return bool(client.api("app/version", timeout=5).ok)

    poll(up, what="qBittorrent WebUI 起來", timeout=300)
    version = client.api("app/version").text.strip()
    webapi = client.api("app/webapiVersion").text.strip()
    if tuple(int(p) for p in webapi.split(".")[:2]) < (2, 11):
        client.start_name, client.stop_name, client.stop_key = (
            "torrents/resume",
            "torrents/pause",
            "paused",
        )
    return version, webapi


def settled(client: Client, info_hash: str, *, hold: float, timeout: float = 600) -> dict[str, Any]:
    """等 state 離開校驗 / 搬移並且 `hold` 秒不變。"""
    deadline = time.monotonic() + timeout
    last_state, since = None, time.monotonic()
    while time.monotonic() < deadline:
        row = client.row(info_hash)
        state = row.get("state")
        if state != last_state:
            last_state, since = state, time.monotonic()
        elif state and not state.startswith(TRANSIENT) and time.monotonic() - since >= hold:
            return row
        time.sleep(0.2)
    raise TimeoutError(f"{info_hash[:8]} 在 {timeout} 秒內沒有穩定（最後是 {last_state}）")


def trace(
    client: Client, info_hash: str, *, hold: float, timeout: float = 600
) -> list[dict[str, Any]]:
    """動作之後的 state 序列：只記變化。結束條件同 `settled`。"""
    started = time.monotonic()
    steps: list[dict[str, Any]] = []
    since = started
    while time.monotonic() - started < timeout:
        row = client.row(info_hash)
        state = row.get("state")
        now = time.monotonic()
        if not steps or steps[-1]["state"] != state:
            steps.append(
                {"t": round(now - started, 2), "state": state, "progress": row.get("progress")}
            )
            since = now
        else:
            steps[-1]["progress_last"] = row.get("progress")
            if state and not state.startswith(TRANSIENT) and now - since >= hold:
                return steps
        time.sleep(0.2)
    steps.append({"t": round(time.monotonic() - started, 2), "state": "timeout"})
    return steps


def build(image: str, port: int) -> None:
    docker("network", "create", NETWORK)
    subnet = docker(
        "network", "inspect", NETWORK, "--format", "{{(index .IPAM.Config 0).Subnet}}"
    ).stdout.strip()
    docker("volume", "create", CONFIG)
    docker("volume", "create", DATA)
    conf = CONF.format(save=SAVE_PATH, subnet=subnet)
    docker(
        "run",
        "--rm",
        "-i",
        "--mount",
        f"type=volume,source={CONFIG},target=/config",
        "--entrypoint",
        "sh",
        image,
        "-c",
        "mkdir -p /config/qBittorrent && cat > /config/qBittorrent/qBittorrent.conf",
        stdin=conf,
    )
    docker(
        "run",
        "-d",
        "--name",
        CONTAINER,
        "--network",
        NETWORK,
        "-e",
        "PUID=1000",
        "-e",
        "PGID=1000",
        "-e",
        "WEBUI_PORT=8080",
        "-p",
        f"127.0.0.1:{port}:8080",
        "--mount",
        f"type=volume,source={CONFIG},target=/config",
        "--mount",
        f"type=volume,source={DATA},target=/data",
        image,
    )


def as_qbittorrent(*command: str) -> None:
    """以容器裡 qBittorrent 的使用者（uid 1000）動檔案：缺的那個檔它要寫得回去。"""
    docker("exec", "-u", "1000:1000", CONTAINER, *command)


def run_scenario(
    client: Client,
    key: str,
    stop_first: bool,
    remove_one: bool,
    actions: tuple[str, ...],
    *,
    size: int,
    hold: float,
) -> dict[str, Any]:
    name = f"Berth.Recheck.{key}"
    files = [(f"{name}.E01.mkv", size // 2), (f"{name}.E02.mkv", size // 2)]
    torrent = zero_torrent(name, files)
    folder = f"{SAVE_PATH}/{name}"
    as_qbittorrent("mkdir", "-p", folder)
    for path, length in files:
        as_qbittorrent("truncate", "-s", str(length), f"{folder}/{path}")

    fields = {
        "savepath": SAVE_PATH,
        "autoTMM": "false",
        "contentLayout": "Original",
        client.stop_key: "false",
    }
    added = client.add_file(torrent, fields)
    if not added.ok:
        raise RuntimeError(f"torrents/add -> {added.status} {added.text[:200]}")
    t0 = time.monotonic()
    seeding = settled(client, torrent.info_hash, hold=hold)
    # `settled` 在 state 穩定之後還多等了 `hold` 秒才回來，那一段不是校驗。
    first_check = round(time.monotonic() - t0 - hold, 1)
    before = seeding
    if stop_first:
        client.post(client.stop_name, {"hashes": torrent.info_hash})
        before = settled(client, torrent.info_hash, hold=hold)
    if remove_one:
        as_qbittorrent("rm", f"{folder}/{files[1][0]}")

    endpoints = {"recheck": "torrents/recheck", "start": client.start_name}
    sent_at = time.monotonic()
    for action in actions:
        client.post(endpoints[action], {"hashes": torrent.info_hash})
    gap = round(time.monotonic() - sent_at, 3)
    steps = trace(client, torrent.info_hash, hold=hold)

    client.post("torrents/delete", {"hashes": torrent.info_hash, "deleteFiles": "true"})
    docker("exec", CONTAINER, "rm", "-rf", folder)
    return {
        "actions": list(actions),
        "first_check_seconds": first_check,
        "seeding_state": seeding.get("state"),
        "before": {"state": before.get("state"), "progress": before.get("progress")},
        "requests_seconds": gap,
        "steps": steps,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="lscr.io/linuxserver/qbittorrent:5.2.3")
    parser.add_argument("--port", type=int, default=18093)
    parser.add_argument("--size-gib", type=int, default=8, help="每包兩個檔加起來的大小")
    parser.add_argument("--hold", type=float, default=6.0, help="state 不變多少秒才算走完")
    parser.add_argument("--only", default="", help="逗號分隔的情境鍵，只跑這幾個")
    parser.add_argument("--out", type=Path, default=Path(".local/experiments/results"))
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    cleanup()
    report = Report(name="qbittorrent-stopped-recheck", out_dir=args.out)
    try:
        build(args.image, args.port)
        keep_cookies()
        client = Client(args.port)
        version, webapi = wait_for_webui(client)
        report.name = f"qbittorrent-stopped-recheck-{version.lstrip('v')}"
        report.heading(f"qBittorrent {version}（Web API {webapi}，{args.image}）")
        report.record(
            "version",
            {"image": args.image, "app": version, "webapi": webapi, "size_gib": args.size_gib},
        )
        docker("exec", CONTAINER, "sh", "-c", f"mkdir -p {SAVE_PATH} && chown -R 1000:1000 /data")

        only = {key for key in args.only.split(",") if key}
        results: dict[str, Any] = {}
        for key, stop_first, remove_one, actions in SCENARIOS:
            if only and key not in only:
                continue
            result = run_scenario(
                client,
                key,
                stop_first,
                remove_one,
                actions,
                size=args.size_gib << 30,
                hold=args.hold,
            )
            results[key] = result
            sequence = " → ".join(
                f"{step['state']}({step.get('progress_last', step['progress'])})"
                for step in result["steps"]
            )
            report.note(
                f"{key}：{result['before']['state']} --{'→'.join(actions)}--> {sequence}"
                f"（首次校驗 {result['first_check_seconds']} s）"
            )
            report.record("scenarios", results)
    finally:
        if args.keep:
            print(f"--keep：容器 {CONTAINER} 與 volume 留著")
        else:
            cleanup()
        report.record("leftovers", leftovers())
        print(leftovers())
        report.write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
