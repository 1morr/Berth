"""M4 票 19：Berth 怎麼證明「qBittorrent 看得到分類的 save path」（brief §20.2）。

`download_path` 只在 Berth 容器裡 `stat` 分類路徑，而那個目錄是 Berth 自己剛 `mkdir` 的，
既有 qBittorrent 只掛 `/downloads` 時照樣綠。要從 qBittorrent 那一側問，而它的 Web API 沒有
「這條路徑你看不看得到」（`app/getDirectoryContent` 5.0 才有，4.4 沒有；而且它只說目錄在不在，
qBittorrent 自己的檔案層裡也可能有一個同名的空目錄）。候選做法：

1. 在分類路徑寫一個小檔（這裡用 `docker cp` 代替 Berth 寫），做成單檔 .torrent；
2. 以停住、`savepath=<分類路徑>`、`autoTMM=false`、不掛分類加進 qBittorrent，送 `torrents/recheck`；
3. 校驗走完看 `progress`：1 就是它讀得到 Berth 寫的那個檔；0 就是看不到；
4. `torrents/delete` 帶 `deleteFiles=false`，小檔由寫它的那一方刪。

每個版本量這幾件（每個情境一包新的 torrent）：

| 鍵 | 前置 | 回答 |
| --- | --- | --- |
| `seen_added_stopped` | 檔在、只加不 recheck | 停住加入時會不會自己校驗 |
| `seen_recheck` | 檔在、加入後 recheck | 看得到時 progress 是不是 1、要多久 |
| `missing_recheck` | 目錄與檔都不在 | 看不到時 progress 0、state 是什麼、它有沒有替我們建目錄 |
| `empty_dir_recheck` | 目錄在、檔不在 | qBittorrent 自己的檔案層裡剛好有同名空目錄時也是 0 |
| `unreadable_recheck` | 檔在但 `chmod 000` root 所有 | 權限不足時長什麼樣子（與看不到分不分得開） |
| `temp_seen_recheck` | 開了全域 temp path、檔在 | 未完成目錄會不會讓它去 temp path 找而誤判 |
| `temp_seen_no_download_path` | 同上、加入時 `useDownloadPath=false` | 那個參數擋不擋得住 |

另外開著「torrent 完成時執行外部程式」跑完全部情境，看探針校驗到 100% 會不會觸發它。

自己起停一次性的 network、兩個 volume 與容器（前綴 `berth-exp-visibility`），結束時刪掉並印出
`docker ps -a` / `docker volume ls` 的過濾結果；`--keep` 留著除錯。

用法（報告寫到 .local/experiments/results/qbittorrent-visibility-<版本>.json）：
    python scripts/experiments/qbittorrent_visibility_probe.py
    python scripts/experiments/qbittorrent_visibility_probe.py --image <image>

`--image` 預設是 `lscr.io/linuxserver/qbittorrent:5.2.3`；票 19 另外跑了 `:4.4.5`（支援下限）。
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from lib import Report, make_torrent
from qbittorrent_stopped_recheck import TRANSIENT, Client, docker, keep_cookies, wait_for_webui

PREFIX = "berth-exp-visibility"
CONTAINER = PREFIX
NETWORK = PREFIX
CONFIG = f"{PREFIX}-config"
DATA = f"{PREFIX}-data"
CATEGORY_PATH = "/data/complete/movies"
TEMP_PATH = "/data/incomplete"
SIZE = 4096
CONF = """[LegalNotice]
Accepted=true

[Preferences]
Connection\\UPnP=false
Downloads\\SavePath=/data/downloads/
WebUI\\Address=*
WebUI\\ServerDomains=*
WebUI\\AuthSubnetWhitelistEnabled=true
WebUI\\AuthSubnetWhitelist={subnet}
"""
#: (鍵, 目錄在, 檔在, 權限不足, 開 temp path, 加入參數, 送 recheck)
SCENARIOS: tuple[tuple[str, bool, bool, bool, bool, dict[str, str], bool], ...] = (
    ("seen_added_stopped", True, True, False, False, {}, False),
    ("seen_recheck", True, True, False, False, {}, True),
    ("missing_recheck", False, False, False, False, {}, True),
    ("empty_dir_recheck", True, False, False, False, {}, True),
    ("unreadable_recheck", True, True, True, False, {}, True),
    ("temp_seen_recheck", True, True, False, True, {}, True),
    ("temp_seen_no_download_path", True, True, False, True, {"useDownloadPath": "false"}, True),
)


def cleanup() -> None:
    docker("rm", "-f", "-v", CONTAINER, check=False)
    docker("volume", "rm", CONFIG, DATA, check=False)
    docker("network", "rm", NETWORK, check=False)


def leftovers() -> str:
    found = []
    for kind, fmt in (("ps", "{{.Names}}"), ("volume", "{{.Name}}"), ("network", "{{.Name}}")):
        args = ["ps", "-a"] if kind == "ps" else [kind, "ls"]
        out = docker(*args, "--filter", f"name={PREFIX}", "--format", fmt).stdout.strip()
        found.append(f"docker {' '.join(args)} --filter name={PREFIX}: [{out}]")
    return "\n".join(found)


def build(image: str, port: int) -> None:
    docker("network", "create", NETWORK)
    subnet = docker(
        "network", "inspect", NETWORK, "--format", "{{(index .IPAM.Config 0).Subnet}}"
    ).stdout.strip()
    docker("volume", "create", CONFIG)
    docker("volume", "create", DATA)
    docker(
        "run", "--rm", "-i",
        "--mount", f"type=volume,source={CONFIG},target=/config",
        "--entrypoint", "sh", image,
        "-c", "mkdir -p /config/qBittorrent && cat > /config/qBittorrent/qBittorrent.conf",
        stdin=CONF.format(subnet=subnet),
    )  # fmt: skip
    docker(
        "run", "-d", "--name", CONTAINER, "--network", NETWORK,
        "-e", "PUID=1000", "-e", "PGID=1000", "-e", "WEBUI_PORT=8080",
        "-p", f"127.0.0.1:{port}:8080",
        "--mount", f"type=volume,source={CONFIG},target=/config",
        "--mount", f"type=volume,source={DATA},target=/data",
        image,
    )  # fmt: skip


def shell(command: str) -> str:
    return docker("exec", CONTAINER, "sh", "-c", command, check=False).stdout.strip()


def plant(name: str, payload: bytes, *, unreadable: bool) -> None:
    """代替 Berth 在分類路徑寫探測檔。`docker cp` 進去的是 root 所有、0644。"""
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / name
        source.write_bytes(payload)
        docker("cp", str(source), f"{CONTAINER}:{CATEGORY_PATH}/{name}")
    if unreadable:
        shell(f"chmod 000 '{CATEGORY_PATH}/{name}'")


def settle(client: Client, info_hash: str, *, hold: float, timeout: float = 60) -> dict[str, Any]:
    """state 離開校驗並且 `hold` 秒不變；回最後一列與經過的秒數。"""
    started = time.monotonic()
    last, since, row = None, started, {}
    states: list[str] = []
    while time.monotonic() - started < timeout:
        row = client.row(info_hash)
        state = row.get("state")
        if state != last:
            last, since = state, time.monotonic()
            states.append(str(state))
        elif state and not str(state).startswith(TRANSIENT) and time.monotonic() - since >= hold:
            break
        time.sleep(0.1)
    return {
        "states": states,
        "state": row.get("state"),
        "progress": row.get("progress"),
        "save_path": row.get("save_path"),
        "download_path": row.get("download_path"),
        "seconds": round(time.monotonic() - started - hold, 2),
    }


def run_scenario(
    client: Client,
    key: str,
    has_dir: bool,
    has_file: bool,
    unreadable: bool,
    temp: bool,
    extra: dict[str, str],
    recheck: bool,
    *,
    hold: float,
) -> dict[str, Any]:
    name = f"berth-probe-{key}.bin"
    torrent = make_torrent(name, single_length=SIZE, salt=key)
    payload = bytes((i % 251) for i in range(SIZE))
    shell(f"rm -rf '{CATEGORY_PATH}' && mkdir -p /data/complete")
    if has_dir:
        shell(f"mkdir -p '{CATEGORY_PATH}' && chown 1000:1000 '{CATEGORY_PATH}'")
    if has_file:
        plant(name, payload, unreadable=unreadable)
    client.post(
        "app/setPreferences",
        {"json": f'{{"temp_path_enabled": {str(temp).lower()}, "temp_path": "{TEMP_PATH}"}}'},
    )

    fields = {"savepath": CATEGORY_PATH, "autoTMM": "false", client.stop_key: "true", **extra}
    added = client.add_file(torrent, fields)
    result: dict[str, Any] = {"add": f"{added.status} {added.text[:80]}"}
    if recheck:
        client.post("torrents/recheck", {"hashes": torrent.info_hash})
    result.update(settle(client, torrent.info_hash, hold=hold))

    client.post("torrents/delete", {"hashes": torrent.info_hash, "deleteFiles": "false"})
    time.sleep(0.5)
    result["after_delete"] = shell(f"ls -la '{CATEGORY_PATH}' 2>&1; ls -la '{TEMP_PATH}' 2>&1")
    result["still_listed"] = bool(client.row(torrent.info_hash))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="lscr.io/linuxserver/qbittorrent:5.2.3")
    parser.add_argument("--port", type=int, default=18095)
    parser.add_argument("--hold", type=float, default=2.0, help="state 不變多少秒才算走完")
    parser.add_argument("--out", type=Path, default=Path(".local/experiments/results"))
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    cleanup()
    report = Report(name="qbittorrent-visibility", out_dir=args.out)
    try:
        build(args.image, args.port)
        keep_cookies()
        client = Client(args.port)
        version, webapi = wait_for_webui(client)
        report.name = f"qbittorrent-visibility-{version.lstrip('v')}"
        report.heading(f"qBittorrent {version}（Web API {webapi}，{args.image}）")
        report.record("version", {"image": args.image, "app": version, "webapi": webapi})
        # 設了「torrent 完成時執行外部程式」時，探針校驗到 100% 會不會觸發它（code-review）。
        # 兩個版本的偏好鍵都是 `autorun_enabled` / `autorun_program`；%N 是 torrent 名。
        client.post(
            "app/setPreferences",
            {"json": '{"autorun_enabled": true, "autorun_program": "touch /config/autorun-%N"}'},
        )
        results: dict[str, Any] = {}
        for key, *rest in SCENARIOS:
            result = run_scenario(client, key, *rest, hold=args.hold)  # type: ignore[arg-type]  # 元組拆開傳，型別逐欄對得上
            results[key] = result
            report.note(
                f"{key}：{' → '.join(result['states'])}，progress={result['progress']}，"
                f"{result['seconds']} s，download_path={result['download_path']!r}，"
                f"刪除後還在清單={result['still_listed']}"
            )
            report.record("scenarios", results)
        time.sleep(2)
        fired = shell("ls /config 2>&1 | grep autorun- || true")
        report.note(f"完成時執行外部程式被觸發：{fired.splitlines() or '沒有'}")
        report.record("autorun", fired.splitlines())
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
