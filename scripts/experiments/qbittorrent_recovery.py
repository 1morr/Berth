"""`missing_files` / `client_error` 那兩顆按鈕要打的端點，對真的 qBittorrent 錄一輪（M2 票 09c；
brief §20.2）。

回答三件事：

1. `torrents/recheck` 與「重新開始」（4.x 的 `torrents/resume`、5.x 的 `torrents/start`）回什麼：
   狀態碼與 body、不認得的 hash、5.x 上打舊名字、用 GET 打。
2. 資料被刪掉、容器重啟之後那個 torrent 的 `state` 是什麼（它就是 poller 認的 `missingFiles`）。
3. **兩支的順序**。原始碼說 5.x 的 `forceRecheck` 對停住的 torrent 會掛一個「校驗完再停下來」
   的條件，而 `start` 在校驗中不一定清得掉它——所以 recheck → start 與 start → recheck 可能停在
   不同的地方。資料回來了與資料還不在兩種處境各比一次。

四包都是先把資料寫進容器、qBittorrent 校驗完就是做種中；接著刪掉資料、重啟容器，四包一起變成
`missingFiles`。A、B 把資料放回去，C、D 不放；A、C 走 recheck → start，B、D 走 start → recheck。

用法：
    python scripts/experiments/qbittorrent_recovery.py --base-url http://localhost:18080 \
        --label 4.4.5 --container berth-exp-qbittorrent-44
"""

from __future__ import annotations

import argparse
import http.cookiejar
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from lib import Report, make_torrent, poll, request
from qbittorrent_poller import CATEGORY, CATEGORY_PATH, FILES, KEYS, QBittorrent, plant, settle

#: 不在這台上的 hash：「不認得」回什麼。
UNKNOWN = "0" * 40
#: 校驗完之後再等多久才讀最後的 state：`FilesChecked` 那個停止條件是在校驗結束那一刻才生效的。
AFTER_CHECK = 8


def fresh_opener() -> None:
    """重啟之後舊的 SID 就失效了。白名單上不必登入，但 cookie 要換一組乾淨的。"""
    jar = http.cookiejar.CookieJar()
    urllib.request.install_opener(
        urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    )


def wait_for_webui(qb: QBittorrent, port: str) -> str:
    def usable_host() -> str | None:
        for candidate in (f"localhost:{port}", "qbittorrent:8080", "qbittorrent"):
            probe = request(f"{qb.base}/api/v2/app/version", headers={"Host": candidate}, timeout=5)
            if probe.ok:
                return candidate
        return None

    host: str = poll(usable_host, what="qBittorrent WebUI 起來", timeout=300)
    return host


def row_of(qb: QBittorrent, info_hash: str) -> dict[str, Any]:
    rows = qb.json("torrents/info", params={"hashes": info_hash})
    return {key: rows[0].get(key) for key in KEYS} if rows else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--container", required=True)
    parser.add_argument("--webui-port", default="8080")
    parser.add_argument("--out", type=Path, default=Path(".local/experiments/results"))
    parser.add_argument("--fixtures", type=Path, default=Path("tests/fixtures/http/qbittorrent"))
    args = parser.parse_args()

    report = Report(name=f"qbittorrent-recovery-{args.label}", out_dir=args.out)
    qb = QBittorrent(args.base_url, f"localhost:{args.webui_port}")
    report.heading(f"qBittorrent {args.label} recheck / start（{args.base_url}）")
    fresh_opener()
    qb.host = wait_for_webui(qb, args.webui_port)
    webapi = qb.api("app/webapiVersion").text.strip()
    new_names = tuple(int(p) for p in webapi.split(".")[:2]) >= (2, 11)
    start, old_start = (
        ("torrents/start", "torrents/resume") if new_names else ("torrents/resume", "")
    )
    pause_key = "stopped" if new_names else "paused"
    report.note(f"webapi={webapi} start={start!r}")

    if CATEGORY not in set(qb.json("torrents/categories")):
        qb.api(
            "torrents/createCategory",
            method="POST",
            form={"category": CATEGORY, "savePath": CATEGORY_PATH},
        )
    fields = {
        "category": CATEGORY,
        "tags": "berth",
        "contentLayout": "Original",
        "autoTMM": "true",
        pause_key: "false",
    }

    # --- 四包做種中的 torrent --------------------------------------------------
    names = {key: f"Berth.Recovery.{key}.{args.label}" for key in "ABCD"}
    torrents = {key: make_torrent(name, FILES, salt=name) for key, name in names.items()}
    for key, torrent in torrents.items():
        plant(args.container, names[key], FILES)
        qb.add_file(torrent, fields)
    seeding = {key: settle(qb, torrent.info_hash) for key, torrent in torrents.items()}
    report.record("seeding", seeding)
    report.note("做種中：" + ", ".join(f"{k}={v.get('state')}" for k, v in seeding.items()))

    # --- 刪資料、重啟：missingFiles ---------------------------------------------
    for name in names.values():
        subprocess.run(
            ["docker", "exec", args.container, "rm", "-rf", f"{CATEGORY_PATH}/{name}"], check=True
        )
    subprocess.run(["docker", "restart", args.container], check=True, capture_output=True)
    fresh_opener()
    qb.host = wait_for_webui(qb, args.webui_port)
    missing = {key: settle(qb, torrent.info_hash) for key, torrent in torrents.items()}
    report.record("after_restart", missing)
    report.note("重啟之後：" + ", ".join(f"{k}={v.get('state')}" for k, v in missing.items()))

    # --- 端點本身的形狀 --------------------------------------------------------
    args.fixtures.mkdir(parents=True, exist_ok=True)
    shapes: dict[str, Any] = {}

    def shape(key: str, resp: Any, fixture: str = "") -> None:
        shapes[key] = {"status": resp.status, "body": resp.text[:200]}
        report.note(f"{key}: {resp.status} {resp.text[:80]!r}")
        if fixture:
            (args.fixtures / fixture).write_bytes(resp.body)

    shape(
        "recheck_unknown",
        qb.api("torrents/recheck", method="POST", form={"hashes": UNKNOWN}),
        f"torrents-recheck.unknown.{args.label}.txt",
    )
    shape("recheck_get", qb.api("torrents/recheck", params={"hashes": UNKNOWN}))
    shape("start_unknown", qb.api(start, method="POST", form={"hashes": UNKNOWN}))
    if old_start:
        shape(
            "old_name",
            qb.api(old_start, method="POST", form={"hashes": UNKNOWN}),
            f"torrents-resume.not-found.{args.label}.txt",
        )
    shape("recheck_missing_param", qb.api("torrents/recheck", method="POST", form={}))

    # --- 救回來：資料放回 A、B；A、C recheck → start，B、D start → recheck ----------
    for key in "AB":
        plant(args.container, names[key], FILES)
    endpoint = start.split("/")[1]
    for key in "AC":
        info_hash = torrents[key].info_hash
        first = qb.api("torrents/recheck", method="POST", form={"hashes": info_hash})
        second = qb.api(start, method="POST", form={"hashes": info_hash})
        if key == "A":
            shape("recheck", first, f"torrents-recheck.ok.{args.label}.txt")
            shape(endpoint, second, f"torrents-{endpoint}.ok.{args.label}.txt")
    for key in "BD":
        info_hash = torrents[key].info_hash
        qb.api(start, method="POST", form={"hashes": info_hash})
        qb.api("torrents/recheck", method="POST", form={"hashes": info_hash})
    report.record("shapes", shapes)

    for torrent in torrents.values():
        settle(qb, torrent.info_hash)
    time.sleep(AFTER_CHECK)
    final = {key: row_of(qb, torrent.info_hash) for key, torrent in torrents.items()}
    report.record("recovered", final)
    for key, order in (("A", "recheck→start"), ("B", "start→recheck")):
        report.note(
            f"資料回來 {order}: {final[key].get('state')} progress={final[key].get('progress')}"
        )
    for key, order in (("C", "recheck→start"), ("D", "start→recheck")):
        report.note(
            f"資料不在 {order}: {final[key].get('state')} progress={final[key].get('progress')}"
        )

    for torrent in torrents.values():
        qb.api(
            "torrents/delete",
            method="POST",
            form={"hashes": torrent.info_hash, "deleteFiles": "true"},
        )
    report.write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
