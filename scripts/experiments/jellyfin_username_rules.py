"""M4 票 29：Jellyfin 12 收什麼樣的帳號，以及 `/System/Configuration` 讀回的 metadata 語言。

精靈全新安裝實測（`docs/research/wizard-qa-2026-10-01.md` 第 18 條）：含 `< > & " / \\` 的帳號
被 `POST /Startup/User` 回 400，畫面只說「那一段沒做完」。原始碼（v12.1
`Jellyfin.Server.Implementations/Users/UserManager.cs`）的規則是 `ValidUsernameRegex`
`^(?!\\s)[\\w\\ \\-'._@+]+(?<!\\s)$`，另外不收 `.` 與 `..`；`StartupController.UpdateStartupUser`
先擋只有空白的密碼，再改名（`RenameUser` → `ThrowIfInvalidUsername`），最後才設密碼。
這支對真的容器量：

1. 初始精靈期間，每個不合法的帳號送一次 `POST /Startup/User`，記狀態碼與原文——改名在設密碼
   之前，所以被拒之後第一個使用者仍然沒有密碼，下一次照樣能試；
2. 只有空白的密碼；
3. 一個合法的中文帳號建立管理員，跑完 `/Startup/Configuration`（zh-TW / TW）與 `Complete`；
4. 以那個管理員的 token 用 `POST /Users/New` 試其餘的合法與不合法帳號（同一支
   `ThrowIfInvalidUsername`）；
5. `GET /System/Configuration`：metadata 語言與國家是不是第 3 步寫的那一組（媒體庫照它建，
   `JellyfinClient.metadata_defaults`）。`--fixture` 給了就把原文寫成契約測試的錄製回應。

自己起停一個一次性容器（`berth-exp-jfusername`，掛 Docker 的預設 bridge，不建 network），
結束時刪掉並印出過濾結果；`--keep` 留著除錯。

用法（報告寫到 .local/experiments/results/jellyfin-username-rules-<版本>.json）：
    python scripts/experiments/jellyfin_username_rules.py \\
        --fixture tests/fixtures/http/jellyfin/system-configuration.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from lib import Report, Response, request

PREFIX = "berth-exp-jfusername"
CONTAINER = PREFIX
CONFIG = f"{PREFIX}-config"
PASSWORD = "harbour-lights"
ADMIN = "船長 01"
#: 初始精靈期間送的（第 1 步）。實測 B2-05～07 的六個字元，加上規則外的其他符號。
STARTUP_REJECTS = ("a<b", "a>b", "a&b", 'a"b', "a/b", "a\\b", "a:b", "a#b", "tab\tin", ".", "..")
#: 管理員建好之後以 `POST /Users/New` 試的（第 4 步）。
NEW_USERS = ("skipper", "o'brien", "a.b@c+d-e_f", "José", "ナミ", "..x", "a<b", ".", " lead")
AUTH = 'MediaBrowser Client="berth-exp", Device="exp", DeviceId="berth-exp", Version="1"'


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], check=check, capture_output=True, text=True)


def cleanup() -> None:
    docker("rm", "-f", "-v", CONTAINER, check=False)
    docker("volume", "rm", CONFIG, check=False)


def leftovers() -> str:
    found = []
    for kind, fmt in (("ps", "{{.Names}}"), ("volume", "{{.Name}}")):
        args = ("ps", "-a") if kind == "ps" else (kind, "ls")
        out = docker(*args, "--filter", f"name={PREFIX}", "--format", fmt).stdout.strip()
        found.append(f"docker {' '.join(args)} --filter name={PREFIX}: [{out}]")
    return "\n".join(found)


def start(image: str, port: int) -> None:
    docker("volume", "create", CONFIG)
    docker(
        "run",
        "-d",
        "--name",
        CONTAINER,
        "-e",
        "PUID=1000",
        "-e",
        "PGID=1000",
        "-p",
        f"127.0.0.1:{port}:8096",
        "--mount",
        f"type=volume,source={CONFIG},target=/config",
        image,
    )


def wait_until_up(base: str, seconds: int = 180) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    while True:
        try:
            resp = request(f"{base}/System/Info/Public", timeout=5)
            payload = resp.json() if resp.ok else None
            if isinstance(payload, dict) and payload.get("Id"):
                return payload
        except (OSError, ValueError):
            pass
        if time.monotonic() > deadline:
            raise TimeoutError(f"{base} did not answer within {seconds}s")
        time.sleep(2)


def headers(token: str = "") -> dict[str, str]:
    return {"Authorization": f'{AUTH}, Token="{token}"' if token else AUTH}


def answer(resp: Response) -> str:
    return f"{resp.status} {resp.text.strip()[:160]}"


def startup_user(base: str, name: str, password: str = PASSWORD) -> Response:
    return request(
        f"{base}/Startup/User",
        method="POST",
        headers=headers(),
        json_body={"Name": name, "Password": password},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="lscr.io/linuxserver/jellyfin:version-12.1ubu2604")
    parser.add_argument("--port", type=int, default=28496)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--out", type=Path, default=Path(".local/experiments/results"))
    args = parser.parse_args()

    base = f"http://127.0.0.1:{args.port}"
    info: dict[str, Any] = {}
    cleanup()
    try:
        start(args.image, args.port)
        info = wait_until_up(base)
        report = Report(name=f"jellyfin-username-rules-{info.get('Version')}", out_dir=args.out)
        report.record("server", {"image": args.image, "version": info.get("Version")})
        report.heading(f"{args.image}（{info.get('Version')}）")

        # GET 會建立預設使用者，少了它 POST 回 500（brief §20.7）。
        request(f"{base}/Startup/User", headers=headers())
        report.heading("1–2. 初始精靈期間 POST /Startup/User")
        startup: dict[str, str] = {}
        for name in STARTUP_REJECTS:
            startup[name] = answer(startup_user(base, name))
            report.note(f"{name!r:12} {startup[name]}")
        startup["<blank password>"] = answer(startup_user(base, "skipper", "   "))
        report.note(f"{'blank pw':12} {startup['<blank password>']}")
        startup[ADMIN] = answer(startup_user(base, ADMIN))
        report.note(f"{ADMIN!r:12} {startup[ADMIN]}")
        report.record("startup_user", startup)

        configured = request(
            f"{base}/Startup/Configuration",
            method="POST",
            headers=headers(),
            json_body={
                "UICulture": "zh-TW",
                "MetadataCountryCode": "TW",
                "PreferredMetadataLanguage": "zh-TW",
            },
        )
        completed = request(f"{base}/Startup/Complete", method="POST", headers=headers())
        signed = request(
            f"{base}/Users/AuthenticateByName",
            method="POST",
            headers=headers(),
            json_body={"Username": ADMIN, "Pw": PASSWORD},
        )
        report.note(
            f"configuration {configured.status} · complete {completed.status} · "
            f"sign in as {ADMIN!r} {signed.status}"
        )
        token = str(signed.json()["AccessToken"])

        report.heading("4. POST /Users/New（管理員）")
        created: dict[str, str] = {}
        for name in NEW_USERS:
            created[name] = answer(
                request(
                    f"{base}/Users/New",
                    method="POST",
                    headers=headers(token),
                    json_body={"Name": name, "Password": PASSWORD},
                )
            )
            report.note(f"{name!r:14} {created[name][:60]}")
        report.record("users_new", created)

        report.heading("5. GET /System/Configuration")
        conf = request(f"{base}/System/Configuration", headers=headers(token))
        anonymous = request(f"{base}/System/Configuration", headers=headers())
        payload = conf.json()
        report.record(
            "system_configuration",
            {
                "status": conf.status,
                "anonymous": anonymous.status,
                "PreferredMetadataLanguage": payload.get("PreferredMetadataLanguage"),
                "MetadataCountryCode": payload.get("MetadataCountryCode"),
                "UICulture": payload.get("UICulture"),
            },
        )
        report.note(
            f"{conf.status} PreferredMetadataLanguage={payload.get('PreferredMetadataLanguage')} "
            f"MetadataCountryCode={payload.get('MetadataCountryCode')} "
            f"UICulture={payload.get('UICulture')} · anonymous {anonymous.status}"
        )
        if args.fixture:
            # 錄製回應不經 git 正規化（`.gitattributes`），Windows 上也寫 LF。
            args.fixture.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            report.note(f"fixture → {args.fixture}")
        report.record("leftovers", "")
        report.write()
    finally:
        if not args.keep:
            cleanup()
        print(leftovers())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
