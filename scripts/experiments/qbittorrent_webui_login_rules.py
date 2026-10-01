"""M4 票 26：qBittorrent 收什麼樣的 WebUI 帳密。

量的是 `app/setPreferences` 的 `web_ui_username` / `web_ui_password`。

精靈全新安裝實測（`docs/research/wizard-qa-2026-10-01.md` 第 3 條）：沿用 4 字元的
Jellyfin 密碼時套件內 qBittorrent 回 400，而帳號已經寫進去、密碼沒有。原始碼
（`src/webui/api/appcontroller.cpp`）顯示 5.2.0 起 `setPreferences` 才驗：帳號至少 3 字元、
不能有冒號，密碼至少 6 字元，**帳號先驗先寫、密碼後驗**；4.4–5.1 一律照收。
這支對真的容器量：

- 每個情境送一次 `setPreferences`，記狀態碼、回應原文，再讀回 `web_ui_username`；
- 送出成功的再以那一組打 `auth/login`，看 qBittorrent 認不認（4.4.5 回 `200 Ok.`；5.2.3
  成功是 `204` 沒有 body，帳密錯是 `401`——票 26 另外從白名單外的宿主實測）；
- 每個情境之前把帳號設回 `admin`（4.4 收任何值，5.2 收 `admin`），情境之間互不影響。

情境的鍵寫在 `CASES`。字數是 QString 的長度（UTF-16 code unit），與瀏覽器
`String.length` 同一種算法，所以另外量一組六個中文字的密碼。

自己起停一次性的 network（固定 172.24.0.0/16，避開使用者其他環境的網段）、volume
與容器（前綴 `berth-exp-webuilogin`），結束時刪掉並印出過濾結果；`--keep` 留著除錯。

用法（報告寫到 .local/experiments/results/qbittorrent-webui-login-rules-<版本>.json）：
    python scripts/experiments/qbittorrent_webui_login_rules.py
    python scripts/experiments/qbittorrent_webui_login_rules.py --image <image>

`--image` 預設是 `lscr.io/linuxserver/qbittorrent:5.2.3`；票 26 另外跑了 `:4.4.5`。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from lib import Report
from qbittorrent_stopped_recheck import Client, docker, keep_cookies, wait_for_webui

PREFIX = "berth-exp-webuilogin"
CONTAINER = PREFIX
NETWORK = PREFIX
CONFIG = f"{PREFIX}-config"
SUBNET = "172.24.0.0/16"
CONF = """[LegalNotice]
Accepted=true

[Preferences]
Connection\\UPnP=false
WebUI\\Address=*
WebUI\\ServerDomains=*
WebUI\\AuthSubnetWhitelistEnabled=true
WebUI\\AuthSubnetWhitelist={subnet}
WebUI\\MaxAuthenticationFailCount=0
"""
#: (鍵, 送出去的偏好)。帳號在前、密碼在後只是寫法：qBittorrent 照原始碼的順序處理，
#: 不看 JSON 的鍵序，`password_first_in_json` 驗的就是這件事。
CASES: tuple[tuple[str, dict[str, str]], ...] = (
    ("password_5", {"web_ui_password": "abcde"}),
    ("password_6", {"web_ui_password": "abcdef"}),
    ("password_6_cjk", {"web_ui_password": "密碼密碼密碼"}),
    ("username_2", {"web_ui_username": "ab"}),
    ("username_3", {"web_ui_username": "abc"}),
    ("username_colon", {"web_ui_username": "ab:cd"}),
    ("pair_short_password", {"web_ui_username": "skipper", "web_ui_password": "abcd"}),
    ("password_first_in_json", {"web_ui_password": "abcd", "web_ui_username": "skipper"}),
    ("pair_short_username", {"web_ui_username": "ab", "web_ui_password": "abcdef"}),
    ("pair_ok", {"web_ui_username": "skipper", "web_ui_password": "Harbour-1"}),
)


def cleanup() -> None:
    docker("rm", "-f", "-v", CONTAINER, check=False)
    docker("volume", "rm", CONFIG, check=False)
    docker("network", "rm", NETWORK, check=False)


def leftovers() -> str:
    found = []
    for kind, fmt in (("ps", "{{.Names}}"), ("volume", "{{.Name}}"), ("network", "{{.Name}}")):
        args = ("ps", "-a") if kind == "ps" else (kind, "ls")
        out = docker(*args, "--filter", f"name={PREFIX}", "--format", fmt).stdout.strip()
        found.append(f"docker {' '.join(args)} --filter name={PREFIX}: [{out}]")
    return "\n".join(found)


def build(image: str, port: int) -> None:
    docker("network", "create", "--subnet", SUBNET, NETWORK)
    docker("volume", "create", CONFIG)
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
        stdin=CONF.format(subnet=SUBNET),
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
        image,
    )


def username(client: Client) -> str:
    return str(client.json("app/preferences").get("web_ui_username", ""))


def set_preferences(client: Client, values: dict[str, str]) -> tuple[int, str]:
    resp = client.api(
        "app/setPreferences", method="POST", form={"json": json.dumps(values, ensure_ascii=False)}
    )
    return resp.status, resp.text.strip()


def login_answer(client: Client, user: str, password: str) -> str:
    resp = client.api("auth/login", method="POST", form={"username": user, "password": password})
    return f"{resp.status} {resp.text.strip()}"


def run_case(client: Client, values: dict[str, str]) -> dict[str, Any]:
    reset = set_preferences(client, {"web_ui_username": "admin"})
    before = username(client)
    status, body = set_preferences(client, values)
    after = username(client)
    row: dict[str, Any] = {
        "sent": values,
        "reset": reset[0],
        "status": status,
        "body": body,
        "username_before": before,
        "username_after": after,
        "username_written": after != before,
    }
    if status == 200 and "web_ui_password" in values:
        row["login_with_it"] = login_answer(client, after, values["web_ui_password"])
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="lscr.io/linuxserver/qbittorrent:5.2.3")
    parser.add_argument("--port", type=int, default=28480)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--out", type=Path, default=Path(".local/experiments/results"))
    args = parser.parse_args()

    tag = args.image.rsplit(":", 1)[-1]
    report = Report(name=f"qbittorrent-webui-login-rules-{tag}", out_dir=args.out)
    cleanup()
    keep_cookies()
    try:
        build(args.image, args.port)
        client = Client(args.port)
        version, webapi = wait_for_webui(client)
        report.record("server", {"image": args.image, "version": version, "webapi": webapi})
        report.heading(f"{args.image}（{version}，Web API {webapi}）")
        cases = {}
        for key, values in CASES:
            row = cases[key] = run_case(client, values)
            report.note(
                f"{key:24} {row['status']} username_written={row['username_written']!s:5} "
                f"{row['body'][:70]!r} {row.get('login_with_it', '')}"
            )
        report.record("cases", cases)
    finally:
        if not args.keep:
            cleanup()
        report.record("leftovers", leftovers())
        print(leftovers())
        report.write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
