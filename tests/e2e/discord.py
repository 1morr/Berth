"""e2e 的假 Discord API（M4 票 133）：Berth 由 `DISCORD_API_URL` 指過來，這一台把每一則私訊記下來。

只做 Berth 會打的三支（`adapters/notify/discord.py`，形狀是 M4 票 121 錄下來的）：

- `GET /applications/@me`：存 bot token 時問「這是哪一個 bot」。
- `POST /users/@me/channels`：開 DM channel。channel id 就是 `dm-` 加收件人，所以送訊息那一步
  不必記狀態也知道送給誰——容器被 `docker stop` 再起來之後照樣認得。
- `POST /channels/{id}/messages`：記一列進 `MESSAGES`（JSON Lines：收件人、Berth 送的 body）。

**兩種壞法**：`MODE` 檔寫 `5xx` 時每一支都回 `503`（Discord 事故的樣子）；整個關掉是測試對這個容器
`docker stop`（名字解析不到，Berth 那一邊是連不上）。紀錄寫在自己的 volume，關掉再起來還在。

token 只看有沒有 `Bot ` 前綴，不記：Berth 記不記 token 不是這一台要驗的。

**只用標準庫**（同 `sites.py`）：容器是 `python:3.13-alpine`。宿主上的測試 import 這一支只為了常量。
"""

from __future__ import annotations

import http.server
import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

#: 容器裡的紀錄目錄（`compose.yml` 掛一個 named volume 在這裡）。
STATE = PurePosixPath("/var/lib/discord")
#: 每一則私訊一列。
MESSAGES = STATE / "messages.jsonl"
#: 測試寫、這一台每個請求讀一次：`BROKEN` 是壞掉，其他（或沒有這個檔）是正常。
MODE = STATE / "mode"
BROKEN = "5xx"
HEALTHY = "ok"
PORT = 8000
#: Berth 的 base URL 帶版本（`DEFAULT_DISCORD_API_URL` 的形狀）。
API = "/api/v10"
#: bot 的身分。名字會出現在 Berth 的通知設定頁。
APPLICATION = {"id": "100000000000000099", "name": "Berth e2e"}
CHANNEL_PREFIX = "dm-"


def broken() -> bool:
    try:
        with Path(MODE).open(encoding="utf-8") as mode:
            return mode.read().strip() == BROKEN
    except FileNotFoundError:
        return False


def record(recipient: str, body: object) -> int:
    """記一則，回它是第幾則（從 1 起）。"""
    line = {"recipient": recipient, "body": body, "at": datetime.now(UTC).isoformat()}
    with Path(MESSAGES).open("a", encoding="utf-8") as messages:
        messages.write(json.dumps(line, ensure_ascii=False) + "\n")
    with Path(MESSAGES).open(encoding="utf-8") as messages:
        return sum(1 for _ in messages)


def answer(method: str, path: str, authorization: str, body: object) -> tuple[int, object]:
    if path == "/healthz":
        return 200, {"ok": True}
    if broken():
        return 503, {"message": "e2e: Discord is having a bad day", "code": 0}
    if not authorization.startswith("Bot "):
        return 401, {"message": "401: Unauthorized", "code": 0}
    if method == "GET" and path == f"{API}/applications/@me":
        return 200, APPLICATION
    if method == "POST" and path == f"{API}/users/@me/channels":
        recipient = body.get("recipient_id") if isinstance(body, dict) else None
        if not isinstance(recipient, str) or not recipient:
            return 400, {"message": "Invalid Form Body", "code": 50035}
        return 200, {"id": f"{CHANNEL_PREFIX}{recipient}", "type": 1}
    prefix, suffix = f"{API}/channels/{CHANNEL_PREFIX}", "/messages"
    if method == "POST" and path.startswith(prefix) and path.endswith(suffix):
        recipient = path.removeprefix(prefix).removesuffix(suffix)
        number = record(recipient, body)
        return 200, {"id": str(number), "channel_id": f"{CHANNEL_PREFIX}{recipient}"}
    return 404, {"message": "404: Not Found", "code": 0}


class Handler(http.server.BaseHTTPRequestHandler):
    def _reply(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = None
        status, out = answer(method, self.path, self.headers.get("Authorization") or "", body)
        payload = json.dumps(out).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self._reply("GET")

    def do_POST(self) -> None:
        self._reply("POST")


if __name__ == "__main__":
    print(f"discord: listening on {PORT}", flush=True)
    http.server.ThreadingHTTPServer(("", PORT), Handler).serve_forever()
