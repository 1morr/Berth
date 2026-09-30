"""M4 票 22：分類自己的未完成目錄（`createCategory` 的 `downloadPath`）能不能取代全域 `temp_path`。

Berth 想只替自己的分類開未完成目錄，不動使用者的全域設定（brief §16.4）。brief §20.2 查到
`createCategory` 從 Web API 2.8.4 / 4.4.0 起收 `downloadPathEnabled` 與 `downloadPath`，但沒有人
實跑過「autoTMM 的 torrent 下載中真的落在那裡、完成後搬到 `savePath`」。這支量它：

- 一台做種的 qBittorrent（固定 5.2.3），用稀疏全零檔校驗成做種中；
- 一台受測版本（`--image`），全域 `dl_limit` 限速讓「下載中」看得到，`torrents/addPeers`
  直連做種端；
- 每個情境一包新的 torrent、一個新的分類，照 Berth 的送單形狀加入（`category`、`autoTMM=true`，
  不送 `savepath`）；下載中每 0.5 秒記一次檔案在哪個目錄、torrent 報的 `save_path` /
  `download_path`，完成後再記一次。

| 鍵 | 全域 temp path | 分類 |
| --- | --- | --- |
| `category_path_global_off` | 關 | `downloadPathEnabled=true` + `downloadPath` |
| `category_path_global_on` | 開（另一個目錄） | 同上：誰贏 |
| `category_disabled_global_on` | 開 | `downloadPathEnabled=false`：能不能讓分類不走全域的 |
| `plain_global_off` | 關 | 兩個欄位都不送（對照：直接寫進 savePath） |
| `plain_global_on` | 開 | 兩個欄位都不送（對照：跟著全域） |

另外記 `torrents/categories` 的原樣（讀回來的鍵名，Berth 比對衝突要讀它），以及對已存在的分類
再送一次 `createCategory` 的回應。

自己起停一次性的 network、volume 與兩個容器（前綴 `berth-exp-catpath`），結束時刪掉並印出
`docker ps -a` / `docker volume ls` 的過濾結果；`--keep` 留著除錯。

用法（報告寫到 .local/experiments/results/qbittorrent-category-download-path-<版本>.json）：
    python scripts/experiments/qbittorrent_category_download_path.py
    python scripts/experiments/qbittorrent_category_download_path.py --image <image>

`--image` 預設是 `lscr.io/linuxserver/qbittorrent:5.2.3`；票 22 另外跑了 `:4.4.5`（支援下限）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from lib import Report, Torrent, bencode
from qbittorrent_stopped_recheck import (
    PIECE,
    TRANSIENT,
    Client,
    docker,
    keep_cookies,
    wait_for_webui,
)

PREFIX = "berth-exp-catpath"
NETWORK = PREFIX
LEECHER = f"{PREFIX}-leecher"
SEEDER = f"{PREFIX}-seeder"
SEEDER_IMAGE = "lscr.io/linuxserver/qbittorrent:5.2.3"
VOLUMES = tuple(
    f"{PREFIX}-{role}-{kind}" for role in ("leecher", "seeder") for kind in ("config", "data")
)
GLOBAL_TEMP = "/data/global-incomplete"
SEED_PATH = "/data/seed"
SIZE = 16 * PIECE  # 64 MiB
LIMIT = 4 * 1024 * 1024  # 4 MiB/s：下載約 16 秒
CONF = """[LegalNotice]
Accepted=true

[BitTorrent]
Session\\Port={port}
Session\\DHTEnabled=false
Session\\LSDEnabled=false
Session\\PeXEnabled=false
Session\\BTProtocol=TCP

[Preferences]
Connection\\PortRangeMin={port}
Connection\\UPnP=false
Downloads\\SavePath=/data/downloads/
WebUI\\Address=*
WebUI\\ServerDomains=*
WebUI\\AuthSubnetWhitelistEnabled=true
WebUI\\AuthSubnetWhitelist={subnet}
"""
PEER_PORT = 46999
#: (鍵, 全域 temp path 開, 分類額外欄位)
SCENARIOS: tuple[tuple[str, bool, dict[str, str]], ...] = (
    (
        "category_path_global_off",
        False,
        {"downloadPathEnabled": "true", "downloadPath": "@incomplete"},
    ),
    (
        "category_path_global_on",
        True,
        {"downloadPathEnabled": "true", "downloadPath": "@incomplete"},
    ),
    ("category_disabled_global_on", True, {"downloadPathEnabled": "false"}),
    ("plain_global_off", False, {}),
    ("plain_global_on", True, {}),
)


def private_zero_torrent(name: str) -> Torrent:
    """單檔、全零、**private**：DHT / PeX / LSD 都不碰，只連 `addPeers` 給的那一個。"""
    info: dict[str, Any] = {
        "name": name,
        "files": [{"length": SIZE, "path": ["payload.bin"]}],
        "piece length": PIECE,
        "pieces": hashlib.sha1(bytes(PIECE)).digest() * (SIZE // PIECE),
        "private": 1,
        "berth-salt": f"{name}-{time.time_ns()}",
    }
    raw = bencode({"announce": "http://127.0.0.1:6969/announce", "info": info})
    return Torrent(name=name, raw=raw, info_hash=hashlib.sha1(bencode(info)).hexdigest())


def cleanup() -> None:
    docker("rm", "-f", "-v", LEECHER, SEEDER, check=False)
    docker("volume", "rm", *VOLUMES, check=False)
    docker("network", "rm", NETWORK, check=False)


def leftovers() -> str:
    found = []
    for kind, fmt in (("ps", "{{.Names}}"), ("volume", "{{.Name}}"), ("network", "{{.Name}}")):
        args = ["ps", "-a"] if kind == "ps" else [kind, "ls"]
        out = docker(*args, "--filter", f"name={PREFIX}", "--format", fmt).stdout.strip()
        found.append(f"docker {' '.join(args)} --filter name={PREFIX}: [{out}]")
    return "\n".join(found)


def start(name: str, role: str, image: str, port: int, subnet: str) -> None:
    config, data = f"{PREFIX}-{role}-config", f"{PREFIX}-{role}-data"
    for volume in (config, data):
        docker("volume", "create", volume)
    docker(
        "run", "--rm", "-i",
        "--mount", f"type=volume,source={config},target=/config",
        "--entrypoint", "sh", image,
        "-c", "mkdir -p /config/qBittorrent && cat > /config/qBittorrent/qBittorrent.conf",
        stdin=CONF.format(subnet=subnet, port=PEER_PORT),
    )  # fmt: skip
    docker(
        "run", "-d", "--name", name, "--network", NETWORK,
        "-e", "PUID=1000", "-e", "PGID=1000", "-e", "WEBUI_PORT=8080",
        "-p", f"127.0.0.1:{port}:8080",
        "--mount", f"type=volume,source={config},target=/config",
        "--mount", f"type=volume,source={data},target=/data",
        image,
    )  # fmt: skip
    # volume 的 /data 是 root 所有；qBittorrent 以 1000 跑，建不了分類目錄會整包 `error`。
    docker("exec", name, "sh", "-c", "chown 1000:1000 /data")


def shell(container: str, command: str) -> str:
    return docker("exec", container, "sh", "-c", command, check=False).stdout.strip()


def where(key: str, incomplete: str, save: str) -> dict[str, str]:
    """三個候選目錄底下各有什麼（大小與相對路徑）。

    4.4.5 的 image 是 busybox，沒有 `find -printf`。
    """
    out = {}
    for label, root in (
        ("category_incomplete", incomplete),
        ("global_temp", GLOBAL_TEMP),
        ("save", save),
    ):
        listing = shell(
            LEECHER,
            f"cd '{root}' 2>/dev/null && find . -type f -exec wc -c {{}} + | grep '{key}' || true",
        )
        out[label] = listing
    return out


def wait_seeding(client: Client, info_hash: str, timeout: float = 60) -> str:
    deadline = time.monotonic() + timeout
    state = ""
    while time.monotonic() < deadline:
        row = client.row(info_hash)
        state = str(row.get("state", ""))
        if row.get("progress") == 1 and not state.startswith(TRANSIENT):
            return state
        time.sleep(0.3)
    raise TimeoutError(f"seeder 沒進做種（最後是 {state}）")


def run_scenario(
    leecher: Client, seeder: Client, peer: str, key: str, temp: bool, extra: dict[str, str]
) -> dict[str, Any]:
    torrent = private_zero_torrent(f"catpath-{key}")
    # 做種端：稀疏全零檔、校驗成做種中。
    shell(
        SEEDER,
        f"mkdir -p '{SEED_PATH}/{torrent.name}' "
        f"&& truncate -s {SIZE} '{SEED_PATH}/{torrent.name}/payload.bin' "
        f"&& chown -R 1000:1000 '{SEED_PATH}'",
    )
    seeder.add_file(torrent, {"savepath": SEED_PATH, "autoTMM": "false", seeder.stop_key: "false"})
    time.sleep(1)
    seeder.post("torrents/recheck", {"hashes": torrent.info_hash})
    seeding = wait_seeding(seeder, torrent.info_hash)

    category = f"berth-{key}"
    save = f"/data/torrent/complete/{key}"
    incomplete = f"/data/torrent/incomplete/{key}"
    leecher.post(
        "app/setPreferences",
        {
            "json": json.dumps(
                {"temp_path_enabled": temp, "temp_path": GLOBAL_TEMP, "dl_limit": LIMIT}
            )
        },
    )
    form = {"category": category, "savePath": save}
    form.update({k: (incomplete if v == "@incomplete" else v) for k, v in extra.items()})
    leecher.post("torrents/createCategory", form)
    categories = leecher.json("torrents/categories")
    again = leecher.api("torrents/createCategory", method="POST", form=form)

    added = leecher.add_file(
        torrent, {"category": category, "autoTMM": "true", leecher.stop_key: "false"}
    )
    time.sleep(0.5)
    leecher.post("torrents/addPeers", {"hashes": torrent.info_hash, "peers": peer})

    samples: list[dict[str, Any]] = []
    started = time.monotonic()
    done_at = None
    while time.monotonic() - started < 180:
        row = leecher.row(torrent.info_hash)
        state = str(row.get("state", ""))
        progress = row.get("progress", 0)
        downloading = 0 < progress < 1 and state.startswith(
            ("downloading", "stalledDL", "forcedDL")
        )
        if downloading and (not samples or time.monotonic() - samples[-1]["t_abs"] >= 3):
            samples.append(
                {
                    "t_abs": time.monotonic(),
                    "t": round(time.monotonic() - started, 1),
                    "state": state,
                    "progress": round(progress, 3),
                    "save_path": row.get("save_path"),
                    "download_path": row.get("download_path"),
                    "content_path": row.get("content_path"),
                    "files": where(key, incomplete, save),
                }
            )
        if progress == 1 and not state.startswith(TRANSIENT):
            done_at = round(time.monotonic() - started, 1)
            break
        time.sleep(0.5)
    time.sleep(1)
    final = leecher.row(torrent.info_hash)
    result = {
        "category_form": form,
        "categories_readback": categories.get(category),
        "create_again": f"{again.status} {again.text[:80]}",
        "add": f"{added.status} {added.text[:80]}",
        "seeder_state": seeding,
        "during": [{k: v for k, v in s.items() if k != "t_abs"} for s in samples],
        "done_at": done_at,
        "final": {
            "state": final.get("state"),
            "progress": final.get("progress"),
            "save_path": final.get("save_path"),
            "download_path": final.get("download_path"),
            "content_path": final.get("content_path"),
            "files": where(key, incomplete, save),
        },
    }
    for client in (leecher, seeder):
        client.post("torrents/delete", {"hashes": torrent.info_hash, "deleteFiles": "true"})
    return result


def summarise(result: dict[str, Any]) -> str:
    during = result["during"]
    first = during[0] if during else {}
    landed = [label for label, listing in first.get("files", {}).items() if listing]
    final = [label for label, listing in result["final"]["files"].items() if listing]
    return (
        f"下載中 download_path={first.get('download_path')!r} 檔在 {landed or '（沒取到樣本）'}；"
        f"完成（{result['done_at']} s）後檔在 {final}，save_path={result['final']['save_path']!r}；"
        f"分類讀回 {result['categories_readback']}；重建 {result['create_again']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="lscr.io/linuxserver/qbittorrent:5.2.3")
    parser.add_argument("--port", type=int, default=18093)
    parser.add_argument("--seeder-port", type=int, default=18094)
    parser.add_argument("--out", type=Path, default=Path(".local/experiments/results"))
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    cleanup()
    report = Report(name="qbittorrent-category-download-path", out_dir=args.out)
    try:
        docker("network", "create", NETWORK)
        subnet = docker(
            "network", "inspect", NETWORK, "--format", "{{(index .IPAM.Config 0).Subnet}}"
        ).stdout.strip()
        start(SEEDER, "seeder", SEEDER_IMAGE, args.seeder_port, subnet)
        start(LEECHER, "leecher", args.image, args.port, subnet)
        keep_cookies()
        seeder, leecher = Client(args.seeder_port), Client(args.port)
        wait_for_webui(seeder)
        version, webapi = wait_for_webui(leecher)
        seeder_ip = docker(
            "inspect",
            SEEDER,
            "--format",
            f'{{{{(index .NetworkSettings.Networks "{NETWORK}").IPAddress}}}}',
        ).stdout.strip()
        peer = f"{seeder_ip}:{PEER_PORT}"
        report.name = f"qbittorrent-category-download-path-{version.lstrip('v')}"
        report.heading(f"qBittorrent {version}（Web API {webapi}，{args.image}）")
        report.record(
            "version", {"image": args.image, "app": version, "webapi": webapi, "peer": peer}
        )
        results: dict[str, Any] = {}
        for key, temp, extra in SCENARIOS:
            results[key] = run_scenario(leecher, seeder, peer, key, temp, extra)
            report.note(f"{key}：{summarise(results[key])}")
            report.record("scenarios", results)
    finally:
        if args.keep:
            print(f"--keep：容器與 volume（{PREFIX}-*）留著")
        else:
            cleanup()
        report.record("leftovers", leftovers())
        print(leftovers())
        report.write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
