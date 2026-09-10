"""`qbit_poller` 要讀的那三支端點，對真的 qBittorrent 錄一輪（票 10；plan §3.2、brief §20.2）。

回答四件事，每一件都是狀態機轉換直接依賴的：

1. `sync/maindata` 的 `rid` 增量長什麼樣（`full_update`、`torrents` 只帶變動欄位、
   `torrents_removed`）。
2. 一個 torrent 在「只有磁力連結」「有 metadata 但沒有種」「檔案已經在磁碟上」三種處境下，
   `state` / `progress` / `completion_on` / `content_path` 分別是什麼。
3. `torrents/files[].name` 相對誰（brief §20.7 說是 `save_path`，這裡再驗一次多檔的情形）。
4. **連續登入失敗之後那個 403 與帳密錯的 403 差在哪裡**（plan §8.1、T1.9 第四條）。
   第 4 項會把來源 IP 封掉，所以它一定跑在最後。

torrent 是腳本現造的：`metaDL` 那一個是隨機 hash 的磁力連結（永遠拿不到 metadata），
`stalledDL` 那一個是合法的 .torrent 但磁碟上沒有資料，完成的那一個則是先把
`make_torrent` 算 pieces 用的那份位元組寫進容器再加進去——qBittorrent 自己校驗完就是完成。

用法：
    python scripts/experiments/qbittorrent_poller.py --base-url http://localhost:18080 \
        --label 4.4.5 --container berth-exp-qbittorrent-44
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from lib import Report, Torrent, make_torrent, multipart, poll, request

CATEGORY = "berth-exp"
CATEGORY_PATH = "/downloads/berth-exp"
#: 完成的那一包。檔名照真實發佈的樣子，因為 `job_files.rel_path` 存的就是這一串。
RELEASE = "Berth.Poller.Test.S01.1080p.WEB-DL"
FILES: list[tuple[str, int]] = [
    ("Berth.Poller.Test.S01E01.1080p.WEB-DL.mkv", 40000),
    ("Subs/Berth.Poller.Test.S01E01.zh-Hant.srt", 120),
]
#: 第 4 項問的是「不在白名單上的來源」，所以先把免密關掉再打。
BAN_ATTEMPTS = 8

TRANSIENT = {"checkingResumeData", "checkingDL", "checkingUP", "allocating", "moving", "unknown"}

#: 逐 torrent 記進報告的欄位。缺席本身也是結果，所以用 `.get`。
KEYS = (
    "state",
    "progress",
    "completion_on",
    "save_path",
    "content_path",
    "size",
    "total_size",
    "amount_left",
    "category",
    "tags",
    "added_on",
    "name",
)


class QBittorrent:
    def __init__(self, base_url: str, host: str) -> None:
        self.base = base_url.rstrip("/")
        self.host = host

    @property
    def origin(self) -> str:
        return f"http://{self.host}"

    def api(self, path: str, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        headers.setdefault("Host", self.host)
        headers.setdefault("Referer", self.origin)
        headers.setdefault("Origin", self.origin)
        return request(f"{self.base}/api/v2/{path}", headers=headers, **kwargs)

    def json(self, path: str, **kwargs: Any) -> Any:
        resp = self.api(path, **kwargs)
        if not resp.ok:
            raise RuntimeError(f"{path} -> {resp.status} {resp.text[:200]}")
        return resp.json()

    def add_file(self, torrent: Torrent, fields: dict[str, str]) -> Any:
        body, ctype = multipart(fields, {"torrents": (f"{torrent.name}.torrent", torrent.raw)})
        return self.api("torrents/add", method="POST", body=body, content_type=ctype)


def content_of(files: list[tuple[str, int]]) -> dict[str, bytes]:
    """`make_torrent` 算 pieces 用的那份位元組，逐檔拆回來。"""
    return {path: bytes((i % 251) for i in range(size)) for path, size in files}


def plant(container: str, torrent_name: str, files: list[tuple[str, int]]) -> None:
    """把完成的那一包寫進容器的 category save path。

    `docker cp` 進去的是 root 所有、0644，qBittorrent（uid 1000）讀得到——做種只要讀。
    """
    blobs = content_of(files)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / torrent_name
        for rel, payload in blobs.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        subprocess.run(["docker", "exec", container, "mkdir", "-p", CATEGORY_PATH], check=True)
        subprocess.run(["docker", "cp", str(root), f"{container}:{CATEGORY_PATH}/"], check=True)


def settle(qb: QBittorrent, info_hash: str, timeout: float = 120) -> dict[str, Any]:
    def stable() -> Any:
        rows = qb.json("torrents/info", params={"hashes": info_hash})
        row = rows[0] if rows else None
        return row if row and row.get("state") not in TRANSIENT else None

    row: dict[str, Any] = poll(
        stable, what=f"{info_hash[:8]} 的 state 穩定", timeout=timeout, interval=1
    )
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--container", required=True)
    parser.add_argument("--webui-port", default="8080")
    parser.add_argument("--out", type=Path, default=Path(".local/experiments/results"))
    parser.add_argument("--fixtures", type=Path, default=Path("tests/fixtures/http/qbittorrent"))
    parser.add_argument("--skip-ban", action="store_true")
    args = parser.parse_args()

    report = Report(name=f"qbittorrent-poller-{args.label}", out_dir=args.out)
    qb = QBittorrent(args.base_url, f"localhost:{args.webui_port}")
    report.heading(f"qBittorrent {args.label} poller 端點（{args.base_url}）")

    # **cookie 一定要留著**：免密白名單上的請求 qBittorrent 照樣開一個 session 並發 SID，
    # 而 `sync/maindata` 的 rid 狀態是掛在那個 session 上的。不帶 cookie 的話每一次請求
    # 都是新 session，`rid` 永遠回不到增量（實測 4.4.5：每一輪都 `full_update: true`）。
    jar = http.cookiejar.CookieJar()
    urllib.request.install_opener(
        urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    )

    def usable_host() -> str | None:
        for candidate in (f"localhost:{args.webui_port}", "qbittorrent:8080", "qbittorrent"):
            probe = request(f"{qb.base}/api/v2/app/version", headers={"Host": candidate}, timeout=5)
            if probe.ok:
                return candidate
        return None

    qb.host = poll(usable_host, what="qBittorrent WebUI 起來", timeout=300)
    version = qb.api("app/version").text.strip()
    webapi = qb.api("app/webapiVersion").text.strip()
    report.record("version", {"app": version, "webapi": webapi})
    report.note(f"app/version={version} webapi={webapi} host={qb.host!r}")

    # category 決定 save path（autoTMM）。已經在就不動它。
    if CATEGORY not in set(qb.json("torrents/categories")):
        qb.api(
            "torrents/createCategory",
            method="POST",
            form={"category": CATEGORY, "savePath": CATEGORY_PATH},
        )

    pause_key = "stopped" if tuple(int(p) for p in webapi.split(".")[:2]) >= (2, 11) else "paused"
    base_fields = {
        "category": CATEGORY,
        "tags": "berth",
        "contentLayout": "Original",
        "autoTMM": "true",
        pause_key: "false",
    }

    # --- 1. 只有磁力連結：永遠停在 metaDL，`torrents/files` 是空的 ---------------
    magnet_hash = (uuid.uuid4().hex + uuid.uuid4().hex)[:40]
    qb.api(
        "torrents/add",
        method="POST",
        form={**base_fields, "urls": f"magnet:?xt=urn:btih:{magnet_hash}&dn=berth-metadl"},
    )

    # --- 2. 有 metadata、磁碟上沒有資料：stalledDL --------------------------------
    stalled = make_torrent(f"{RELEASE}.stalled", FILES, salt="stalled")
    qb.add_file(stalled, base_fields)

    # --- 3. 檔案已經在 save path 上：qBittorrent 校驗完就是完成 --------------------
    done = make_torrent(RELEASE, FILES, salt="")
    plant(args.container, RELEASE, FILES)
    qb.add_file(done, base_fields)

    done_row = settle(qb, done.info_hash)
    stalled_row = settle(qb, stalled.info_hash)
    magnet_row = poll(
        lambda: (qb.json("torrents/info", params={"hashes": magnet_hash}) or [None])[0],
        what="磁力連結那一筆出現",
        timeout=60,
        interval=1,
    )
    report.note(
        f"metaDL={magnet_row.get('state')!r} stalled={stalled_row.get('state')!r} "
        f"done={done_row.get('state')!r} progress={done_row.get('progress')} "
        f"completion_on={done_row.get('completion_on')}"
    )
    report.record(
        "torrents",
        {
            "magnet": {key: magnet_row.get(key) for key in KEYS},
            "stalled": {key: stalled_row.get(key) for key in KEYS},
            "done": {key: done_row.get(key) for key in KEYS},
        },
    )

    args.fixtures.mkdir(parents=True, exist_ok=True)

    # --- sync/maindata：rid=0 的整份，再拿它的 rid 換一次增量 ----------------------
    full = qb.api("sync/maindata", params={"rid": 0})
    write(args.fixtures / f"sync-maindata.full.{args.label}.json", full.body)
    payload = full.json()
    rid = payload.get("rid")
    report.note(
        f"maindata rid={rid} full_update={payload.get('full_update')} "
        f"keys={sorted(payload.keys())} torrents={len(payload.get('torrents') or {})}"
    )
    report.record(
        "maindata_full",
        {
            "rid": rid,
            "keys": sorted(payload.keys()),
            "torrent_keys": sorted(next(iter(payload["torrents"].values())).keys()),
        },
    )

    # 增量：再加一個磁力連結，下一輪只會帶那一筆（外加做種那幾筆的變動欄位）。
    extra_hash = (uuid.uuid4().hex + uuid.uuid4().hex)[:40]
    qb.api(
        "torrents/add",
        method="POST",
        form={**base_fields, "urls": f"magnet:?xt=urn:btih:{extra_hash}&dn=berth-partial"},
    )
    time.sleep(4)
    partial = qb.api("sync/maindata", params={"rid": rid})
    write(args.fixtures / f"sync-maindata.partial.{args.label}.json", partial.body)
    partial_payload = partial.json()
    report.record(
        "maindata_partial",
        {
            "rid": partial_payload.get("rid"),
            "full_update": partial_payload.get("full_update"),
            "keys": sorted(partial_payload.keys()),
            "torrents": {
                key: sorted(value.keys())
                for key, value in (partial_payload.get("torrents") or {}).items()
            },
        },
    )
    report.note(f"增量回：{partial.text[:300]}")

    # 移除：`torrents_removed` 是 `client_removed` 那條轉換唯一的訊號。
    qb.api("torrents/delete", method="POST", form={"hashes": extra_hash, "deleteFiles": "false"})
    time.sleep(4)
    removed = qb.api("sync/maindata", params={"rid": partial_payload.get("rid")})
    write(args.fixtures / f"sync-maindata.removed.{args.label}.json", removed.body)
    report.record("maindata_removed", removed.json())
    report.note(f"移除之後回：{removed.text[:300]}")

    # --- torrents/files：多檔那一包 ----------------------------------------------
    files = qb.api("torrents/files", params={"hash": done.info_hash})
    write(args.fixtures / f"torrents-files.multi.{args.label}.json", files.body)
    rows = files.json()
    report.record(
        "files",
        {
            "keys": sorted(rows[0].keys()),
            "names": [row.get("name") for row in rows],
            "save_path": done_row.get("save_path"),
            "content_path": done_row.get("content_path"),
        },
    )
    report.note(
        f"files[].name={[row.get('name') for row in rows]} save_path={done_row.get('save_path')!r}"
    )

    empty = qb.api("torrents/files", params={"hash": magnet_hash})
    report.record("files_metadl", {"status": empty.status, "body": empty.text[:200]})
    report.note(f"metaDL 的 torrents/files -> {empty.status} {empty.text[:80]!r}")

    # --- 4. 連續登入失敗 → 403（會封 IP，所以放最後） -----------------------------
    if not args.skip_ban:
        measure_ban(qb, report, args, jar)

    report.write()
    return 0


def measure_ban(
    qb: QBittorrent, report: Report, args: argparse.Namespace, jar: http.cookiejar.CookieJar
) -> None:
    """把免密白名單關掉，用錯的密碼打到被封，記下兩種 403 的原文。"""
    qb.api(
        "app/setPreferences",
        method="POST",
        form={
            "json": json.dumps(
                {"bypass_auth_subnet_whitelist_enabled": False, "bypass_local_auth": False}
            )
        },
    )
    # **session 要先丟掉**：`auth/login` 在 session 還活著時直接回 `Ok.`，連密碼都不看
    # （實測 4.4.5：帶著 SID 打八次錯密碼全部是 `Ok.`）。那條路徑量不到帳密檢查。
    jar.clear()
    attempts: list[dict[str, Any]] = []
    for index in range(BAN_ATTEMPTS):
        resp = qb.api(
            "auth/login", method="POST", form={"username": "admin", "password": "wrong-password"}
        )
        attempts.append({"n": index + 1, "status": resp.status, "body": resp.text.strip()[:200]})
        if resp.status == 403:
            break
    report.record("login_attempts", attempts)
    for row in attempts:
        report.note(f"  第 {row['n']} 次登入 -> {row['status']} {row['body']!r}")

    banned = attempts[-1]
    if banned["status"] == 403 and banned["body"]:
        write(args.fixtures / f"auth-login.banned.{args.label}.txt", f"{banned['body']}\n".encode())
    # 被封之後其他端點也是 403 嗎——poller 每 5 秒打一次，它踩到的是這一支。
    probe = qb.api("app/version")
    report.record("banned_other_endpoint", {"status": probe.status, "body": probe.text[:200]})
    report.note(f"  被封之後 app/version -> {probe.status} {probe.text.strip()[:120]!r}")
    if probe.status == 403 and probe.text.strip():
        write(
            args.fixtures / f"app-version.banned.{args.label}.txt",
            f"{probe.text.strip()}\n".encode(),
        )


def write(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)
    print(f"寫入 {path}（{len(payload)} bytes）")


if __name__ == "__main__":
    raise SystemExit(main())
