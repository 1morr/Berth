"""實驗腳本共用的最小工具：HTTP、輪詢、bencode、報告輸出。

只用標準庫。這些腳本要能在沒有 Berth 虛擬環境的機器（NAS、別人的 Linux 宿主）上
直接以 `python3` 執行，所以不 import `berth`，也不裝任何依賴。
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

JSON_CT = "application/json"
FORM_CT = "application/x-www-form-urlencoded"


class PollTimeoutError(RuntimeError):
    """輪詢在期限內沒等到條件成立。"""


@dataclass(frozen=True)
class Response:
    """把 urllib 的成功與 HTTPError 兩條路徑收斂成同一個型別。"""

    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def json(self) -> Any:
        return json.loads(self.body) if self.body else None

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


def request(
    url: str,
    *,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, Any] | None = None,
    form: Mapping[str, Any] | None = None,
    json_body: Any = None,
    body: bytes | None = None,
    content_type: str | None = None,
    timeout: float = 60.0,
) -> Response:
    """發一個請求。4xx / 5xx 不丟例外，實驗要記錄的正是狀態碼本身。"""
    if params:
        url = f"{url}?{urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})}"
    sent = dict(headers or {})
    if json_body is not None:
        body = json.dumps(json_body).encode()
        sent.setdefault("Content-Type", JSON_CT)
    elif form is not None:
        body = urllib.parse.urlencode(form).encode()
        sent.setdefault("Content-Type", FORM_CT)
    if content_type:
        sent["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, method=method, headers=sent)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return Response(resp.status, resp.read(), dict(resp.headers.items()))
    except urllib.error.HTTPError as exc:
        return Response(exc.code, exc.read(), dict(exc.headers.items()))


def multipart(
    fields: Mapping[str, str], files: Mapping[str, tuple[str, bytes]]
) -> tuple[bytes, str]:
    """組 multipart/form-data；qBittorrent 的 torrents/add 上傳 .torrent 要用。"""
    boundary = f"----berth{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        head = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
        parts.append(f"{head}{value}\r\n".encode())
    for name, (filename, payload) in files.items():
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        file_head = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
            f'filename="{filename}"\r\nContent-Type: {ctype}\r\n\r\n'
        ).encode()
        parts.append(file_head + payload + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def poll(
    fn: Callable[[], Any],
    *,
    what: str,
    timeout: float = 180.0,
    interval: float = 2.0,
) -> Any:
    """重複呼叫 fn 直到它回傳真值；超時丟 PollTimeout。fn 內的例外視為「還沒好」。"""
    deadline = time.monotonic() + timeout
    last: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            value = fn()
        except Exception as exc:
            last = exc
        else:
            if value:
                return value
        time.sleep(interval)
    raise PollTimeoutError(
        f"等 {what} 超過 {timeout} 秒" + (f"（最後一個錯誤：{last!r}）" if last else "")
    )


# --- bencode / .torrent ------------------------------------------------------


def bencode(value: Any) -> bytes:
    """最小 bencode 編碼器，只支援 .torrent 用得到的四種型別。"""
    if isinstance(value, bool):
        raise TypeError("bencode 沒有布林型別")
    if isinstance(value, int):
        return b"i%de" % value
    if isinstance(value, bytes):
        return b"%d:%s" % (len(value), value)
    if isinstance(value, str):
        return bencode(value.encode())
    if isinstance(value, Sequence):
        return b"l" + b"".join(bencode(item) for item in value) + b"e"
    if isinstance(value, Mapping):
        items = sorted(value.items(), key=lambda kv: str(kv[0]).encode())
        return b"d" + b"".join(bencode(k) + bencode(v) for k, v in items) + b"e"
    raise TypeError(f"bencode 不支援 {type(value)!r}")


@dataclass(frozen=True)
class Torrent:
    """一個合法但沒有實際資料的 .torrent；用來問 qBittorrent 「你怎麼解讀它」。"""

    name: str
    raw: bytes
    info_hash: str


def make_torrent(
    name: str,
    files: Sequence[tuple[str, int]] | None = None,
    *,
    single_length: int | None = None,
    salt: str = "",
) -> Torrent:
    """造一個 torrent。files 給多檔（路徑, 大小），single_length 給單檔。

    pieces 是對「假造但確定」的內容算的真 SHA-1，所以檔案結構合法；
    磁碟上沒有對應資料，加進 qBittorrent 後永遠不會完成，這正是我們要的。
    """
    piece_length = 16384
    if single_length is not None:
        blobs = [bytes((i % 251) for i in range(single_length))]
        info: dict[str, Any] = {"name": name, "length": single_length}
    else:
        assert files is not None
        blobs = [bytes((i % 251) for i in range(size)) for _, size in files]
        info = {
            "name": name,
            "files": [{"length": size, "path": path.split("/")} for path, size in files],
        }
    data = b"".join(blobs)
    pieces = b"".join(
        hashlib.sha1(data[i : i + piece_length]).digest()
        for i in range(0, max(len(data), 1), piece_length)
    )
    info["piece length"] = piece_length
    info["pieces"] = pieces
    if salt:
        info["berth-salt"] = salt
    encoded_info = bencode(info)
    raw = bencode({"announce": "http://127.0.0.1:6969/announce", "info": info})
    return Torrent(name=name, raw=raw, info_hash=hashlib.sha1(encoded_info).hexdigest())


# --- 報告 --------------------------------------------------------------------


@dataclass
class Report:
    """收集實驗結果：JSON 給機器，stdout 的 markdown 給人。"""

    name: str
    out_dir: Path
    sections: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def record(self, key: str, value: Any) -> None:
        self.sections[key] = value

    def note(self, line: str) -> None:
        self.notes.append(line)
        print(f"  {line}", flush=True)

    def heading(self, line: str) -> None:
        print(f"\n## {line}", flush=True)

    def write(self) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / f"{self.name}.json"
        payload = {"name": self.name, "notes": self.notes, "sections": self.sections}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n報告：{path}", flush=True)
        return path
