"""qBittorrent 版本相容矩陣（brief §20.6、§20.2；plan §8.1、§9.2）。

對同一個實例問四件 adapter 一定會踩到的事：

1. `paused` 與 `stopped` 哪個被接受，加入後的 state 叫什麼。
2. `contentLayout` 的三個值對 `content_path` 與 `torrents/files` 的影響。
3. `torrents/files` 的 `name` 是相對 `save_path` 還是 `content_path`。
4. `torrents/categories` 回傳 `savePath` 還是 `save_path`。

外加 Host 檢查（`WebUI\\ServerDomains` / `web_ui_domain_list`）與 CSRF 的實測，
回答 plan §9.2「要不要預置 ServerDomains」。

torrent 是腳本現造的，磁碟上沒有對應資料，所以永遠不會真的下載。

用法：
    python scripts/experiments/qbittorrent_matrix.py --base-url http://localhost:18080 --label 4.4.5
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from lib import Report, Torrent, make_torrent, multipart, poll, request

CATEGORY = "berth-exp"
CATEGORY_PATH = "/downloads/berth-exp"

# 剛加入的 torrent 會先經過這些暫態，brief §20.2 的完成判定也要排除它們。
TRANSIENT_STATES = {
    "checkingResumeData",
    "checkingDL",
    "checkingUP",
    "allocating",
    "metaDL",
    "moving",
    "unknown",
}

# adapter 會讀或會寫的偏好鍵（plan §8.1、§9.2）。缺席本身就是結果。
PREF_KEYS = [
    "save_path",
    "temp_path",
    "temp_path_enabled",
    "auto_tmm_enabled",
    "category_changed_tmm_enabled",
    "torrent_changed_tmm_enabled",
    "bypass_auth_subnet_whitelist",
    "bypass_auth_subnet_whitelist_enabled",
    "bypass_local_auth",
    "web_ui_host_header_validation_enabled",
    "web_ui_domain_list",
    "web_ui_csrf_protection_enabled",
    "web_ui_clickjacking_protection_enabled",
]


class QBittorrent:
    def __init__(self, base_url: str, host_header: str) -> None:
        self.base = base_url.rstrip("/")
        # Host 標頭一定要送，而且 port 要等於 WebUI 真正監聽的 port：qBittorrent 的
        # Host 檢查除了比對網域，還會比對 port，`ServerDomains=*` 不會放過 port 不符。
        # 發佈 port 有偏移時（-p 18080:8080），Host: localhost:18080 會被擋。
        self.host = host_header
        self.origin = f"http://{host_header}"

    def set_host(self, host_header: str) -> None:
        """Host 與 Referer/Origin 必須一起換，CSRF 檢查會比對兩者。"""
        self.host = host_header
        self.origin = f"http://{host_header}"

    def api(self, path: str, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        headers.setdefault("Host", self.host)
        # 免密走子網白名單，但 CSRF 仍要求 Referer / Origin 與 Host 一致（brief §20.2）。
        headers.setdefault("Referer", self.origin)
        headers.setdefault("Origin", self.origin)
        return request(f"{self.base}/api/v2/{path}", headers=headers, **kwargs)

    def json(self, path: str, **kwargs: Any) -> Any:
        resp = self.api(path, **kwargs)
        if not resp.ok:
            raise RuntimeError(f"{path} -> {resp.status} {resp.text[:200]}")
        return resp.json()

    def add(self, torrent: Torrent, fields: dict[str, str]) -> Any:
        body, ctype = multipart(fields, {"torrents": (f"{torrent.name}.torrent", torrent.raw)})
        return self.api("torrents/add", method="POST", body=body, content_type=ctype)

    def info(self, info_hash: str) -> Any:
        rows = self.json("torrents/info", params={"hashes": info_hash})
        return rows[0] if rows else None


def probe_add(
    qb: QBittorrent, report: Report, case: str, torrent: Torrent, fields: dict[str, str]
) -> dict[str, Any]:
    """加一個 torrent，回報 qBittorrent 對它的解讀。"""
    resp = qb.add(torrent, {**fields, "category": CATEGORY})
    entry: dict[str, Any] = {
        "case": case,
        "sent": fields,
        "add_status": resp.status,
        "add_body": resp.text.strip()[:120],
        "info_hash": torrent.info_hash,
    }

    def settled() -> Any:
        # 剛加入時會短暫停在 checkingResumeData / allocating，那不是 paused / stopped 的答案。
        row = qb.info(torrent.info_hash)
        return row if row and row.get("state") not in TRANSIENT_STATES else None

    try:
        row = poll(settled, what=f"{case} 的 state 穩定", timeout=90, interval=1)
    except Exception as exc:  # 加入失敗也是結果，不要中斷整批實驗
        entry["error"] = repr(exc)
        report.note(f"{case}: 加入後查不到（{resp.status} {resp.text.strip()[:80]}）")
        return entry
    files = qb.json("torrents/files", params={"hash": torrent.info_hash})
    entry.update(
        {
            "state": row.get("state"),
            "save_path": row.get("save_path"),
            "content_path": row.get("content_path"),
            "download_path": row.get("download_path"),
            "auto_tmm": row.get("auto_tmm"),
            "category": row.get("category"),
            "file_keys": sorted(files[0].keys()) if files else [],
            "file_names": [f.get("name") for f in files],
        }
    )
    root = torrent.name + "/"
    names = entry["file_names"]
    entry["name_includes_torrent_root"] = bool(names) and all(n.startswith(root) for n in names)
    report.note(
        f"{case}: state={entry['state']!r} content_path={entry['content_path']!r} files={names}"
    )
    return entry


def host_header_matrix(qb: QBittorrent, report: Report, hosts: list[str]) -> dict[str, int]:
    """同一個 TCP 目標、不同 Host 標頭，看 qBittorrent 放行哪些。"""
    result = {}
    for host in hosts:
        resp = request(f"{qb.base}/api/v2/app/version", headers={"Host": host}, timeout=10)
        result[host] = resp.status
    report.note("  ".join(f"Host={h} -> {s}" for h, s in result.items()))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--container-host", default="qbittorrent")
    parser.add_argument("--webui-port", default="8080", help="WebUI 在容器內監聽的 port")
    parser.add_argument("--out", type=Path, default=Path(".local/experiments/results"))
    args = parser.parse_args()

    report = Report(name=f"qbittorrent-{args.label}", out_dir=args.out)
    qb = QBittorrent(args.base_url, f"localhost:{args.webui_port}")

    report.heading(f"qBittorrent {args.label}（{args.base_url}）")

    def usable_host() -> str | None:
        # 上一輪若在收窄 domain list 之後中斷，localhost 會進不去；逐個試，讓腳本能重跑。
        for candidate in (
            f"localhost:{args.webui_port}",
            f"{args.container_host}:{args.webui_port}",
            args.container_host,
        ):
            probe = request(f"{qb.base}/api/v2/app/version", headers={"Host": candidate}, timeout=5)
            if probe.ok:
                return candidate
        return None

    qb.set_host(poll(usable_host, what="qBittorrent WebUI 起來", timeout=300))
    report.note(f"用得通的 Host 標頭：{qb.host!r}")
    version = qb.api("app/version").text.strip()
    webapi = qb.api("app/webapiVersion").text.strip()
    report.record("version", {"app": version, "webapi": webapi})
    report.note(f"app/version={version} app/webapiVersion={webapi}")

    prefs = qb.json("app/preferences")
    present = {k: prefs.get(k) for k in PREF_KEYS if k in prefs}
    missing = [k for k in PREF_KEYS if k not in prefs]
    report.record("preferences", {"present": present, "missing": missing, "total_keys": len(prefs)})
    report.note(f"偏好鍵共 {len(prefs)} 個；本專案用得到但不存在的：{missing or '無'}")

    # 上一輪若在收窄 domain list 之後中斷，先還原成出廠狀態，第一組矩陣才量得準。
    qb.api(
        "app/setPreferences",
        method="POST",
        form={"json": '{"web_ui_domain_list": "*", "web_ui_host_header_validation_enabled": true}'},
    )
    time.sleep(1)
    qb.set_host(f"localhost:{args.webui_port}")

    # 上一輪留下的 torrent 會讓 torrents/add 回「Fails.」，先清掉才能重跑。
    stale = qb.json("torrents/info", params={"category": CATEGORY})
    if stale:
        qb.api(
            "torrents/delete",
            method="POST",
            form={"hashes": "|".join(t["hash"] for t in stale), "deleteFiles": "true"},
        )
        time.sleep(2)
        report.note(f"清掉上一輪的 {len(stale)} 個 torrent")

    # --- category 的鍵名 -------------------------------------------------
    report.heading("category 的鍵名（plan §8.1 的 savePath / save_path）")
    qb.api(
        "torrents/createCategory",
        method="POST",
        form={"category": CATEGORY, "savePath": CATEGORY_PATH},
    )
    categories = qb.json("torrents/categories")
    entry = categories.get(CATEGORY, {})
    report.record("categories", {"raw_entry": entry, "keys": sorted(entry.keys())})
    report.note(f"torrents/categories[{CATEGORY!r}] = {entry}")

    # --- paused / stopped 與 contentLayout -------------------------------
    report.heading("paused / stopped 與 contentLayout")
    multi = [("E01.mkv", 2048), ("Subs/E01.CHT.ass", 512)]
    cases = [
        (
            "paused=true",
            make_torrent("Berth.Test.Pack.A", multi, salt="a"),
            {"paused": "true", "contentLayout": "Original"},
        ),
        (
            "stopped=true",
            make_torrent("Berth.Test.Pack.B", multi, salt="b"),
            {"stopped": "true", "contentLayout": "Original"},
        ),
        (
            "no-pause-param",
            make_torrent("Berth.Test.Pack.C", multi, salt="c"),
            {"contentLayout": "Original"},
        ),
        (
            "layout=NoSubfolder",
            make_torrent("Berth.Test.Pack.D", multi, salt="d"),
            {"stopped": "true", "paused": "true", "contentLayout": "NoSubfolder"},
        ),
        (
            "single+Original",
            make_torrent("Berth.Test.Single.E.mkv", single_length=2048, salt="e"),
            {"stopped": "true", "paused": "true", "contentLayout": "Original"},
        ),
        (
            "single+Subfolder",
            make_torrent("Berth.Test.Single.F.mkv", single_length=2048, salt="f"),
            {"stopped": "true", "paused": "true", "contentLayout": "Subfolder"},
        ),
    ]
    adds = [probe_add(qb, report, name, torrent, fields) for name, torrent, fields in cases]
    report.record("adds", adds)

    # --- Host 檢查 --------------------------------------------------------
    report.heading("Host 檢查（plan §9.2 的 WebUI\\ServerDomains）")
    published = args.base_url.rsplit(":", 1)[-1]
    hosts = [
        f"{args.container_host}:{args.webui_port}",  # Berth 在 compose 內網用的位址
        args.container_host,  # 完全沒有 port 的 Host 標頭
        f"localhost:{args.webui_port}",
        f"localhost:{published}",  # 發佈 port 有偏移時瀏覽器會送的
        f"127.0.0.1:{args.webui_port}",
        f"evil.example:{args.webui_port}",
    ]
    host_results: dict[str, Any] = {}
    host_results["domain_list=*"] = host_header_matrix(qb, report, hosts)

    def set_prefs(payload: str) -> None:
        qb.api("app/setPreferences", method="POST", form={"json": payload})
        time.sleep(1)

    set_prefs('{"web_ui_domain_list": "' + args.container_host + '"}')
    # 白名單一旦收窄，腳本自己的 Host 也要跟著改，否則下一個請求就被自己擋掉。
    qb.set_host(f"{args.container_host}:{args.webui_port}")
    current = qb.json("app/preferences").get("web_ui_domain_list")
    report.note(f"改為 web_ui_domain_list={current!r}")
    host_results["domain_list=container-name"] = host_header_matrix(qb, report, hosts)

    set_prefs('{"web_ui_host_header_validation_enabled": false}')
    after = qb.json("app/preferences")
    supported = "web_ui_host_header_validation_enabled" in after
    report.note(
        f"web_ui_host_header_validation_enabled 可經 API 設定：{supported}"
        + ("" if supported else "（本版沒有這個鍵，只能改設定檔的 WebUI\\HostHeaderValidation）")
    )
    host_results["host_header_validation=false"] = host_header_matrix(qb, report, hosts)

    set_prefs('{"web_ui_host_header_validation_enabled": true, "web_ui_domain_list": "*"}')
    qb.set_host(f"localhost:{args.webui_port}")
    host_results["restored"] = host_header_matrix(qb, report, hosts)
    report.record("host_header", host_results)
    report.record("host_header_validation_pref_supported", supported)

    # --- CSRF ------------------------------------------------------------
    report.heading("CSRF（brief §20.2 的 Referer / Origin）")
    base_headers = {"Host": qb.host}
    csrf = {
        "with_referer": qb.api("app/setPreferences", method="POST", form={"json": "{}"}).status,
        "without_referer": request(
            f"{qb.base}/api/v2/app/setPreferences",
            method="POST",
            form={"json": "{}"},
            headers=base_headers,
            timeout=10,
        ).status,
        "wrong_origin": request(
            f"{qb.base}/api/v2/app/setPreferences",
            method="POST",
            form={"json": "{}"},
            headers={
                **base_headers,
                "Origin": "http://evil.example",
                "Referer": "http://evil.example/",
            },
            timeout=10,
        ).status,
    }
    report.record("csrf", csrf)
    report.note(str(csrf))

    report.write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
