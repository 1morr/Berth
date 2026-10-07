"""M4 票 46：頁 2 的探針能不能「看得到但校驗不完」，不觸發「完成時執行外部程式」（brief §20.2）。

票 19 的探針（`qbittorrent_visibility_probe.py`）校驗到 100%，每次都觸發使用者設的「torrent 完成時
執行外部程式」。頁 2 測連線時就要問 qBittorrent 看不看得到 `/data`，所以換一個做法：探測檔兩片，
torrent 的第二片雜湊算在反相的內容上（`berth.adapters.torrent.probe_torrent(unfinished=True)`，
就是 Berth 會送的那一份）。看得到的那一台校驗完應該停在 50%、看不到的 0%、讀不了的 `error`。

每個版本量這幾件（每個情境一包新的 torrent）：

| 鍵 | 前置 | 回答 |
| --- | --- | --- |
| `unfinished_seen` | 檔在、加入後 recheck | 看得到時是不是停在 0.5、state 是什麼、要多久 |
| `unfinished_missing` | 目錄與檔都不在 | 還是 0 |
| `unfinished_unreadable` | 檔在但 `chmod 000` root 所有 | 還是 `error` |
| `whole_seen` | 票 19 的單片探針、檔在、recheck | 對照組：100%，會觸發完成時執行 |

開著「torrent 完成時執行外部程式」與（5.x 才有的）「torrent 加入時執行外部程式」，兩個寫不同的
檔，跑完看各被哪幾包觸發。

沿用 `qbittorrent_visibility_probe.py` 的一次性 network、volume 與容器（同一組名字，前綴
`berth-exp-visibility`），結束時刪掉並印出過濾結果；`--keep` 留著除錯。

用法（報告寫到 .local/experiments/results/qbittorrent-unfinished-probe-<版本>.json）：
    uv run python scripts/experiments/qbittorrent_unfinished_probe.py
    uv run python scripts/experiments/qbittorrent_unfinished_probe.py --image \
        lscr.io/linuxserver/qbittorrent:4.4.5
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from lib import Report, Torrent
from qbittorrent_stopped_recheck import Client, keep_cookies, wait_for_webui
from qbittorrent_visibility_probe import (
    CATEGORY_PATH,
    CONTAINER,
    build,
    cleanup,
    leftovers,
    plant,
    settle,
    shell,
)

from berth.adapters.torrent import UNFINISHED_PROBE_PAYLOAD, info_hash_of, probe_torrent

#: (鍵, 檔在, 權限不足, 校驗不完)
SCENARIOS: tuple[tuple[str, bool, bool, bool], ...] = (
    ("unfinished_seen", True, False, True),
    ("unfinished_missing", False, False, True),
    ("unfinished_unreadable", True, True, True),
    ("whole_seen", True, False, False),
)


def run_scenario(
    client: Client, key: str, has_file: bool, unreadable: bool, unfinished: bool, *, hold: float
) -> dict[str, Any]:
    name = f".berth-probe-{key}"
    payload = UNFINISHED_PROBE_PAYLOAD if unfinished else b"berth"
    raw = probe_torrent(name, payload, unfinished=unfinished)
    torrent = Torrent(name=name, raw=raw, info_hash=info_hash_of(raw))
    shell(f"rm -rf '{CATEGORY_PATH}' && mkdir -p '{CATEGORY_PATH}'")
    shell(f"chown 1000:1000 '{CATEGORY_PATH}'")
    if has_file:
        plant(name, payload, unreadable=unreadable)

    fields = {"savepath": CATEGORY_PATH, "autoTMM": "false", client.stop_key: "true"}
    added = client.add_file(torrent, fields)
    result: dict[str, Any] = {"add": f"{added.status} {added.text[:80]}"}
    # 與 Berth 同一個順序：先等它列得出來、離開 checkingResumeData，才 recheck（brief §20.2）。
    settle(client, torrent.info_hash, hold=0.5)
    client.post("torrents/recheck", {"hashes": torrent.info_hash})
    result.update(settle(client, torrent.info_hash, hold=hold))

    client.post("torrents/delete", {"hashes": torrent.info_hash, "deleteFiles": "false"})
    time.sleep(0.5)
    result["file_after_delete"] = shell(f"ls -la '{CATEGORY_PATH}' 2>&1")
    result["still_listed"] = bool(client.row(torrent.info_hash))
    result["payload_sha1"] = hashlib.sha1(payload).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="lscr.io/linuxserver/qbittorrent:5.2.3")
    parser.add_argument("--port", type=int, default=18096)
    parser.add_argument("--hold", type=float, default=2.0, help="state 不變多少秒才算走完")
    parser.add_argument("--out", type=Path, default=Path(".local/experiments/results"))
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    cleanup()
    report = Report(name="qbittorrent-unfinished-probe", out_dir=args.out)
    try:
        build(args.image, args.port)
        keep_cookies()
        client = Client(args.port)
        version, webapi = wait_for_webui(client)
        report.name = f"qbittorrent-unfinished-probe-{version.lstrip('v')}"
        report.heading(f"qBittorrent {version}（Web API {webapi}，{args.image}）")
        report.record("version", {"image": args.image, "app": version, "webapi": webapi})
        # %N 是 torrent 名。4.4.5 不認得 `autorun_on_torrent_added_*`，送了也不報錯。
        client.post(
            "app/setPreferences",
            {
                "json": (
                    '{"autorun_enabled": true, "autorun_program": "touch /config/done-%N",'
                    ' "autorun_on_torrent_added_enabled": true,'
                    ' "autorun_on_torrent_added_program": "touch /config/added-%N"}'
                )
            },
        )
        results: dict[str, Any] = {}
        for key, *rest in SCENARIOS:
            result = run_scenario(client, key, *rest, hold=args.hold)
            results[key] = result
            report.note(
                f"{key}：{' → '.join(result['states'])}，progress={result['progress']}，"
                f"{result['seconds']} s，刪除後還在清單={result['still_listed']}"
            )
            report.record("scenarios", results)
        time.sleep(2)
        fired = shell("ls -a /config 2>&1 | grep -E '^(done|added)-' || true").splitlines()
        report.note(f"執行外部程式被觸發：{fired or '沒有'}")
        report.record("autorun", fired)
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
