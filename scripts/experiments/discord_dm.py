"""M4 票 121：Discord bot 私訊對真的 Discord 實際回什麼。

量的是票 123 的 adapter 與票 128 的故障處理要照著寫的幾件事：從沒連過 gateway 的 bot 能不能私訊、
超過長度上限的錯誤形狀、沒有共同伺服器與收件人關了私訊各回什麼、token 錯的 401、第一個 429 的
body 與 header，以及只私訊時邀請連結要哪些 scope 與 permissions。

只打 REST（API v10），只用標準庫（`lib.py`），不 import berth。唯一的例外是 `gateway-once`：
連一次 gateway 再斷開，用來對照「連過 gateway 有沒有差」，要 Berth 虛擬環境裡的 `websockets`。
憑證只從環境變數讀，不寫進任何檔案：

    DISCORD_BOT_TOKEN   Developer Portal → Bot → Reset Token 拿到的那一串
    DISCORD_USER_ID     收件人的 user ID（開發者模式 → 右鍵自己 → 複製使用者 ID）

步驟（每一步各自一次 run；使用者在 Discord 上動手的步驟夾在中間，
順序見 docs/development.md，坑見 scripts/experiments/README.md）：

    uv run python scripts/experiments/discord_dm.py invite          # 最小權限的邀請連結
    uv run python scripts/experiments/discord_dm.py send <label>    # 開 DM 送一則（可 --length）
    uv run python scripts/experiments/discord_dm.py baseline        # 文字、embed、超長、401
    uv run python scripts/experiments/discord_dm.py ratelimit       # 連續送到第一個 429 就停
    uv run python scripts/experiments/discord_dm.py gateway-once    # 連一次 gateway（對照用）
    uv run python scripts/experiments/discord_dm.py fixtures        # 遮掉 id 與名字，寫進 fixture
    uv run python scripts/experiments/discord_dm.py embed-url       # 票 124：embed url 收哪些主機

原始回應（含真的 id，不含 token）落在 .local/experiments/results/discord_dm/，不進版控。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from lib import Response, request

API = "https://discord.com/api/v10"
# Discord 要求 bot 的 User-Agent 是這個形狀；urllib 預設的 UA 可能被 Cloudflare 擋。
USER_AGENT = "DiscordBot (https://github.com/1morr/Berth, 0.2.9)"
# 只私訊：bot 要在共同伺服器裡才私訊得到，但不需要任何伺服器權限。
INVITE_SCOPE = "bot"
INVITE_PERMISSIONS = "0"

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / ".local" / "experiments" / "results" / "discord_dm"
FIXTURES = REPO / "tests" / "fixtures" / "http" / "discord"

CONTENT_MAX = 2000
EMBED_TEXT_MAX = 6000
EMBED_DESCRIPTION_MAX = 4096
# 票 123 的契約測試用的那幾份；其餘結果（`send` 的排查與對照）只留在 .local。
FIXTURE_NAMES = (
    "users-me-channels.created",
    "users-me-channels.unauthorized",
    "channels-messages.created",
    "channels-messages.embed",
    "channels-messages.content-too-long",
    "channels-messages.embeds-too-long",
    "channels-messages.dm-closed",
    "channels-messages.no-mutual-guild",
    "channels-messages.rate-limited",
)
# Cloudflare 的 cookie 與瀏覽器回報設定（CSP 裡帶 Sentry 的 key）不是 Discord API 的契約，
# 不進 repo。
DROPPED_HEADERS = {
    "set-cookie",
    "content-security-policy",
    "report-to",
    "reporting-endpoints",
    "nel",
}
RATELIMIT_CAP = 30  # 送到第一個 429 就停；超過這個數還沒遇到也停，不刻意打爆

SNOWFLAKE = re.compile(r"\b\d{17,20}\b")
# 使用者物件裡會帶出真人身分的欄位。字串換成假值、物件逐葉遮掉，null 照留（形狀不變）。
PERSONAL = {
    "username",
    "global_name",
    "avatar",
    "banner",
    "banner_color",
    "accent_color",
    "avatar_decoration_data",
    "clan",
    "primary_guild",
    "collectibles",
    "display_name_styles",
    "discriminator",
}


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"缺環境變數 {name}（見檔頭說明）")
    return value


def call(method: str, path: str, *, token: str, body: Any = None) -> Response:
    headers = {"Authorization": f"Bot {token}", "User-Agent": USER_AGENT}
    return request(f"{API}{path}", method=method, headers=headers, json_body=body, timeout=30)


def save(name: str, method: str, path: str, resp: Response, *, note: str = "") -> None:
    """存一份原始回應，並印出狀態碼、`code` 與 `message`。"""
    RESULTS.mkdir(parents=True, exist_ok=True)
    try:
        body = resp.json()
    except ValueError:  # Cloudflare 擋下時回的是 HTML
        body = resp.text
    record = {
        "request": {"method": method, "path": path, "note": note},
        "status": resp.status,
        "headers": resp.headers,
        "body": body,
    }
    out = RESULTS / f"{name}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    code = body.get("code") if isinstance(body, dict) else None
    message = body.get("message") if isinstance(body, dict) else None
    print(f"{name}: {resp.status} code={code} message={message!r} → {out.relative_to(REPO)}")


def open_dm(name: str, token: str, user_id: str) -> str | None:
    path = "/users/@me/channels"
    resp = call("POST", path, token=token, body={"recipient_id": user_id})
    save(name, "POST", path, resp)
    body = resp.json() if resp.ok else None
    return str(body["id"]) if isinstance(body, dict) else None


def send(name: str, token: str, channel_id: str, payload: dict[str, Any], note: str) -> Response:
    path = f"/channels/{channel_id}/messages"
    resp = call("POST", path, token=token, body=payload)
    save(name, "POST", "/channels/{channel.id}/messages", resp, note=note)
    return resp


def cmd_invite(token: str) -> None:
    resp = call("GET", "/applications/@me", token=token)
    if not resp.ok:
        sys.exit(f"GET /applications/@me → {resp.status} {resp.text}")
    app = resp.json()
    # 不存這份回應：裡面有應用程式擁有者的帳號。
    print(f"bot_public={app.get('bot_public')}")
    print(f"bot_require_code_grant={app.get('bot_require_code_grant')}")
    print(
        "https://discord.com/oauth2/authorize"
        f"?client_id={app['id']}&scope={INVITE_SCOPE}&permissions={INVITE_PERMISSIONS}"
    )


def cmd_send(label: str, token: str, user_id: str, length: int | None) -> None:
    """開 DM、送一則純文字；給了 `length` 就送那麼長的 `content`（看長度檢查與別的檢查誰先）。"""
    channel = open_dm(f"users-me-channels.{label}", token, user_id)
    if channel is None:
        print("開 DM channel 就被拒，不再送訊息")
        return
    text = "x" * length if length else f"Berth 票 121 實驗（{label}）：純文字私訊。"
    note = f"{label}, content {len(text)} chars"
    send(f"channels-messages.{label}", token, channel, {"content": text}, note=note)


def cmd_baseline(token: str, user_id: str) -> None:
    channel = open_dm("users-me-channels.created", token, user_id)
    if channel is None:
        sys.exit("開 DM channel 失敗，停在這裡")
    send(
        "channels-messages.created",
        token,
        channel,
        {"content": "Berth 票 121 實驗：純文字私訊。"},
        note="plain content",
    )
    send(
        "channels-messages.embed",
        token,
        channel,
        {
            "embeds": [
                {
                    "title": "Berth 票 121 實驗：embed",
                    "description": "葬送的芙莉蓮 S02E05 已入庫。",
                    "color": 0xE0A526,
                    "fields": [
                        {"name": "Route", "value": "Anime", "inline": True},
                        {"name": "大小", "value": "1.4 GB", "inline": True},
                    ],
                    "footer": {"text": "Berth"},
                }
            ],
            "allowed_mentions": {"parse": []},
        },
        note="one embed with fields",
    )
    send(
        "channels-messages.content-too-long",
        token,
        channel,
        {"content": "x" * (CONTENT_MAX + 1)},
        note=f"content {CONTENT_MAX + 1} chars",
    )
    rest = EMBED_TEXT_MAX + 1 - EMBED_DESCRIPTION_MAX
    send(
        "channels-messages.embeds-too-long",
        token,
        channel,
        {
            "embeds": [
                {"description": "a" * EMBED_DESCRIPTION_MAX},
                {"description": "b" * rest},
            ]
        },
        note=f"two embeds, descriptions {EMBED_DESCRIPTION_MAX} + {rest} = {EMBED_TEXT_MAX + 1}",
    )
    path = "/users/@me/channels"
    bad = call("POST", path, token="invalid.berth.token", body={"recipient_id": user_id})
    save("users-me-channels.unauthorized", "POST", path, bad, note="wrong bot token")


def cmd_ratelimit(token: str, user_id: str) -> None:
    channel = open_dm("users-me-channels.ratelimit", token, user_id)
    if channel is None:
        sys.exit("開 DM channel 失敗，停在這裡")
    path = f"/channels/{channel}/messages"
    trail: list[dict[str, Any]] = []
    for n in range(1, RATELIMIT_CAP + 1):
        resp = call("POST", path, token=token, body={"content": f"Berth 票 121 速率實驗 #{n}"})
        limits = {k: v for k, v in resp.headers.items() if k.lower().startswith("x-ratelimit")}
        trail.append({"n": n, "status": resp.status, "ratelimit": limits})
        print(f"#{n}: {resp.status} {limits}")
        if resp.status == 429:
            save(
                "channels-messages.rate-limited",
                "POST",
                "/channels/{channel.id}/messages",
                resp,
                note=f"message #{n} in a burst without sleeping",
            )
            break
    else:
        print(f"送了 {RATELIMIT_CAP} 則都沒有 429，停下")
    RESULTS.mkdir(parents=True, exist_ok=True)
    summary = RESULTS / "ratelimit-trail.json"
    summary.write_text(
        json.dumps(trail, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n"
    )
    print(f"→ {summary.relative_to(REPO)}")


#: 票 124：自架的 Berth 從外面看可能是這幾種形狀。Discord 對 embed `url` 的檢查文件沒寫。
EMBED_URLS = (
    ("domain", "https://berth.example.com/media/tv:120089"),
    ("subpath", "https://example.com/berth/media/tv:120089"),
    ("tailscale", "https://berth.tail1234.ts.net/media/tv:120089"),
    ("mdns", "http://nas.local:8000/media/tv:120089"),
    ("lan-ip", "http://192.168.1.10:8000/media/tv:120089"),
    ("loopback-ip", "http://127.0.0.1:8000/media/tv:120089"),
    ("localhost", "http://localhost:8000/media/tv:120089"),
    ("single-label", "http://berth:8000/media/tv:120089"),
    ("ipv6", "http://[::1]:8000/media/tv:120089"),
)
#: 一則一則補回額度（約 1 秒一則，brief §20.23），間隔大於它就不會碰到 429。
EMBED_URL_GAP = 1.5


def cmd_embed_url(token: str, user_id: str) -> None:
    """每一種網址各送兩則：放在 embed 的 `url`（標題變成連結），與寫成 description 裡的 Markdown
    連結（`[text](url)`）。印出哪幾種被拒、拒在哪個欄位。"""
    channel = open_dm("users-me-channels.embed-url", token, user_id)
    if channel is None:
        sys.exit("開 DM channel 失敗，停在這裡")
    rows: list[dict[str, Any]] = []
    for label, url in EMBED_URLS:
        for place, embed in (
            ("url", {"title": f"票 124 embed url：{label}", "url": url}),
            ("markdown", {"title": f"票 124 markdown：{label}", "description": f"[打開]({url})"}),
        ):
            payload = {"embeds": [embed], "allowed_mentions": {"parse": []}}
            resp = send(f"embed-url.{label}.{place}", token, channel, payload, note=url)
            body = resp.json() if resp.status != 200 else None
            rows.append(
                {
                    "label": label,
                    "place": place,
                    "url": url,
                    "status": resp.status,
                    "errors": body.get("errors") if isinstance(body, dict) else None,
                }
            )
            time.sleep(EMBED_URL_GAP)
    RESULTS.mkdir(parents=True, exist_ok=True)
    summary = RESULTS / "embed-url-summary.json"
    summary.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n"
    )
    print(f"→ {summary.relative_to(REPO)}")
    for row in rows:
        print(f"{row['status']} {row['place']:8} {row['label']:12} {json.dumps(row['errors'])}")


GATEWAY = "wss://gateway.discord.gg/?v=10&encoding=json"


def cmd_gateway_once(token: str) -> None:
    """連 gateway 一次：Hello → Identify（intents 0）→ 等到 READY 就斷開，不 heartbeat。

    只有這一步要 `websockets`（Berth 的虛擬環境經 uvicorn[standard] 帶著），所以延遲 import。
    """
    from websockets.sync.client import connect

    identify = {
        "op": 2,
        "d": {
            "token": token,
            "intents": 0,
            "properties": {"os": sys.platform, "browser": "berth-exp", "device": "berth-exp"},
        },
    }
    with connect(GATEWAY, user_agent_header=USER_AGENT) as ws:
        hello = json.loads(ws.recv(timeout=30))
        print(f"op={hello['op']} heartbeat_interval={hello['d']['heartbeat_interval']}")
        ws.send(json.dumps(identify))
        while True:
            event = json.loads(ws.recv(timeout=30))
            print(f"op={event['op']} t={event.get('t')}")
            if event.get("t") == "READY":
                guilds = event["d"].get("guilds", [])
                print(f"READY: {len(guilds)} guild(s), v={event['d'].get('v')}")
                return


# --- fixtures ----------------------------------------------------------------


class Scrubber:
    """把真的 snowflake 換成假的（同一個 id 在所有檔案裡換成同一個假值）、遮掉個人欄位。"""

    def __init__(self) -> None:
        self.ids: dict[str, str] = {}
        self.names: set[str] = set()

    def fake_id(self, real: str) -> str:
        if real not in self.ids:
            self.ids[real] = f"{len(self.ids) + 1:018d}"
        return self.ids[real]

    def text(self, value: str) -> str:
        return SNOWFLAKE.sub(lambda m: self.fake_id(m.group()), value)

    def scrub_personal(self, key: str, value: Any, is_bot: bool) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            if not is_bot:  # bot 的名字是使用者自己取的，不是誰的身分
                self.names.add(value)
            if key in {"username", "global_name"}:
                return "berth-test-bot" if is_bot else "berth-test-user"
            return "0" * len(value)
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return 0
        if isinstance(value, dict):
            return {k: self.scrub_personal(k, v, is_bot) for k, v in value.items()}
        if isinstance(value, list):
            return [self.scrub_personal(key, v, is_bot) for v in value]
        return value

    def walk(self, value: Any) -> Any:
        if isinstance(value, dict):
            is_bot = value.get("bot") is True
            return {
                k: self.scrub_personal(k, v, is_bot) if k in PERSONAL else self.walk(v)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [self.walk(v) for v in value]
        if isinstance(value, str):
            return self.text(value)
        return value


def cmd_fixtures(token: str, user_id: str) -> None:
    sources = [RESULTS / f"{name}.json" for name in FIXTURE_NAMES]
    missing = [p.name for p in sources if not p.exists()]
    if missing:
        sys.exit(f"{RESULTS.relative_to(REPO)} 缺 {', '.join(missing)}，先跑前面幾步")
    scrub = Scrubber()
    scrub.fake_id(user_id)  # 收件人固定是 000…001
    FIXTURES.mkdir(parents=True, exist_ok=True)
    written: list[tuple[Path, str]] = []
    for src in sources:
        record = json.loads(src.read_text(encoding="utf-8"))
        headers = {k: v for k, v in record["headers"].items() if k.lower() not in DROPPED_HEADERS}
        fixture = {
            "status": record["status"],
            "headers": scrub.walk(headers),
            "body": scrub.walk(record["body"]),
        }
        out = FIXTURES / src.name
        written.append((out, json.dumps(fixture, indent=2, ensure_ascii=False, sort_keys=True)))
    leaks = [token, *scrub.ids, *(n for n in scrub.names if len(n) >= 3)]
    for out, text in written:
        found = [leak for leak in leaks if leak in text]
        if found:
            sys.exit(f"{out.name} 還有沒遮掉的值（{len(found)} 個），一個檔都不寫")
    for out, text in written:
        out.write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"→ {out.relative_to(REPO)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="step", required=True)
    sub.add_parser("invite")
    sub.add_parser("gateway-once")
    send_parser = sub.add_parser("send")
    send_parser.add_argument("label", help="結果檔名的後綴，例如 dm-closed")
    send_parser.add_argument("--length", type=int, help="改送這麼多字元的 content")
    sub.add_parser("baseline")
    sub.add_parser("ratelimit")
    sub.add_parser("fixtures")
    sub.add_parser("embed-url")
    args = parser.parse_args()

    token = env("DISCORD_BOT_TOKEN")
    if args.step == "invite":
        cmd_invite(token)
        return
    if args.step == "gateway-once":
        cmd_gateway_once(token)
        return
    user_id = env("DISCORD_USER_ID")
    if args.step == "send":
        cmd_send(args.label, token, user_id, args.length)
    elif args.step == "baseline":
        cmd_baseline(token, user_id)
    elif args.step == "ratelimit":
        cmd_ratelimit(token, user_id)
    elif args.step == "embed-url":
        cmd_embed_url(token, user_id)
    else:
        cmd_fixtures(token, user_id)


if __name__ == "__main__":
    main()
