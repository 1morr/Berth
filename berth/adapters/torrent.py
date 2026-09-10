"""把索引站的下載連結變成「一個 info hash + 一份交得出去的東西」（票 09）。

**為什麼這一步在 Berth 而不是 qBittorrent**：兩個理由。

1. `jobs.hash` 是主鍵（plan §2.3），而索引站不一定報 info hash——實測 ACG.RIP 就不報
   （brief §20.7）。沒有 hash 就沒有 Job，也就沒有 plan §3.3 的「同一個送兩次是同一列」。
2. `torrents/add` 收網址時是**背景抓取**：它一律回 200，抓失敗時 torrent 從此不會出現
   （brief §20.7 實測不認得的參數也不報錯）。那樣 plan §3.1 的 `submit_failed` 永遠觸發不到，
   而使用者會對著一個「已送出」的 Job 等一個永遠不會來的下載。自己抓的話「索引站不給」
   與「qBittorrent 不收」變成兩件當場分得出來的事。

換來的成本是一個 bencode 掃描器。它**不解碼**，只找出 `info` 那個值的位元組範圍再 SHA-1——
解出來再編回去只在原檔的鍵剛好照字典序時才等價，而 info hash 差一個位元組就是另一個 torrent。
"""

from __future__ import annotations

import binascii
import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

import httpx

from berth.adapters.http import (
    DEFAULT_TIMEOUT_SECONDS,
    AuthFailedError,
    ProtocolMismatchError,
    ServiceError,
    ServiceUnavailableError,
    is_dns_failure,
)
from berth.adapters.indexer import normalise_info_hash

#: 磁力連結的 scheme。索引站的代理網址常常 302 到它，httpx 跟不了（不是 HTTP），
#: 所以重導向要自己走。
MAGNET_SCHEME = "magnet"

#: 自己走重導向的上限。Prowlarr 的代理是一跳，多留幾跳給前置代理。
MAX_REDIRECTS = 5

#: 一份 `.torrent` 的合理上限。索引站回一個幾百 MB 的東西時那不是 torrent，
#: 而是有人把 Berth 當成下載器在用。
MAX_TORRENT_BYTES = 8 * 1024 * 1024

#: info hash 的十六進位長度。`jobs.hash` 存的就是這個形狀。
HEX_HASH_LENGTH = 40

#: bencode 巢狀的深度上限。真的 torrent 最多三層（`info` → `files` → `path`）。
MAX_NESTING = 32


class NotATorrentError(ServiceError):
    """拿回來的位元組不是一份 `.torrent`。

    最常見的真實樣子是**一頁 HTML 登入表單**（索引站的憑證過期、或 Prowlarr 的代理連結
    已經失效）。它與「連不上」的下一步不同：這個要人去看憑證，那個只能等。
    """


@dataclass(frozen=True, slots=True)
class TorrentSource:
    """要交給 qBittorrent 的一份東西，以及它的身分。

    `magnet` 與 `content` 剛好有一個：磁力站（TPB、dmhy）只給得出前者，其餘給 `.torrent`。
    兩種在 `torrents/add` 上是不同的欄位，所以形狀留著這個差別而不是抹平成一個 `bytes`。
    """

    #: 小寫十六進位，40 字。與 `adapters.indexer.normalise_info_hash` 同一種寫法。
    info_hash: str
    magnet: str = ""
    content: bytes = b""
    #: 上傳 `.torrent` 時的檔名。qBittorrent 只拿它當表單欄位名，不影響儲存的檔名。
    filename: str = "berth.torrent"


class TorrentFetcher(Protocol):
    """一條下載連結 → 一份 `TorrentSource`。"""

    async def fetch(self, url: str) -> TorrentSource:
        """連不上丟 `ServiceError` 的子類；拿回來的東西不是 torrent 丟 `NotATorrentError`。"""
        ...

    async def aclose(self) -> None: ...


class HttpTorrentFetcher:
    """對索引站（多半是 Prowlarr 的代理）要那一份 torrent。

    **重導向自己走**：Prowlarr 對磁力站回的是 302 到 `magnet:`，而 httpx 的
    `follow_redirects` 碰到非 HTTP 的 scheme 會丟 `UnsupportedProtocol`。自己走的話
    磁力連結就是一個正常的結果，不是一個例外。
    """

    def __init__(self, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)

    async def fetch(self, url: str) -> TorrentSource:
        if _is_magnet(url):
            return _from_magnet(url)

        current = url
        for _ in range(MAX_REDIRECTS):
            async with self._stream(current) as response:
                if response.is_redirect:
                    current = response.headers.get("location", "")
                    if not current:
                        raise ProtocolMismatchError(f"{url}: redirect without a location")
                    if _is_magnet(current):
                        return _from_magnet(current)
                    continue
                _classify(url, response)
                content = await self._read(url, response)
                return TorrentSource(
                    info_hash=info_hash_of(content), content=content, filename=_filename(url)
                )
        raise ProtocolMismatchError(f"{url}: too many redirects")

    @asynccontextmanager
    async def _stream(self, url: str) -> AsyncIterator[httpx.Response]:
        try:
            async with self._client.stream("GET", url) as response:
                yield response
        except httpx.ConnectError as exc:
            if is_dns_failure(exc):
                raise ServiceUnavailableError(f"{url}: host does not resolve") from exc
            raise ServiceUnavailableError(f"{url}: connection refused") from exc
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError(f"{url}: {type(exc).__name__}") from exc

    async def _read(self, url: str, response: httpx.Response) -> bytes:
        """**邊讀邊擋**，不是整份進記憶體之後才判大小。

        索引站回一個幾百 MB 的東西時那不是 torrent；等它下載完再說「太大了」等於
        那個上限只保護了 bencode 掃描器，沒保護這個程序。
        """
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > MAX_TORRENT_BYTES:
                raise NotATorrentError(f"{url}: larger than {MAX_TORRENT_BYTES} bytes")
            chunks.append(chunk)
        return b"".join(chunks)

    async def aclose(self) -> None:
        await self._client.aclose()


def _classify(url: str, response: httpx.Response) -> None:
    """錯誤映射與 `adapters/http.py` 同一套——這一支不走 `HttpSession`（它綁一個 base URL，
    而下載連結是索引站給的整條網址），但服務層認得的例外必須是同一組。"""
    if response.status_code in (401, 403):
        raise AuthFailedError(f"{url}: {response.status_code}")
    if response.status_code >= 400:
        raise ProtocolMismatchError(f"{url}: {response.status_code}")


def _from_magnet(uri: str) -> TorrentSource:
    info_hash = magnet_info_hash(uri)
    if not info_hash:
        raise NotATorrentError(f"{uri[:80]}: magnet link without a btih hash")
    return TorrentSource(info_hash=info_hash, magnet=uri)


def _is_magnet(url: str) -> bool:
    return url.strip().lower().startswith(f"{MAGNET_SCHEME}:")


def _filename(url: str) -> str:
    """上傳時的表單檔名。取網址最後一段只是為了讓 qBittorrent 的 log 讀得懂。"""
    tail = urlsplit(url).path.rsplit("/", 1)[-1]
    return tail if tail.endswith(".torrent") else "berth.torrent"


def magnet_info_hash(uri: str) -> str:
    """磁力連結裡的 `xt=urn:btih:`，正規化成小寫十六進位。

    認不得就回空字串——猜一個 hash 比沒有 hash 糟得多（呼叫端會把它當成另一個 torrent）。
    base32 與十六進位兩種寫法都收：同一個發佈在 dmhy 是 32 字 base32、在 Mikan 是 40 字
    十六進位（brief §20.7），不收攏的話同一個 torrent 會變成兩個 Job。
    """
    parts = urlsplit(uri.strip())
    if parts.scheme.lower() != MAGNET_SCHEME:
        return ""
    for value in parse_qs(parts.query).get("xt", []):
        prefix, _, raw = value.partition("urn:btih:")
        if prefix or not raw:
            continue
        return _strict_hash(raw)
    return ""


def _strict_hash(raw: str) -> str:
    """`normalise_info_hash` 的嚴格版：**認不得就回空字串**。

    轉換本身只有一份實作（`adapters.indexer`），這裡多的是那一層檢查——那一支是去重用的
    身分，認不得的寫法原樣小寫回去仍然是一個穩定的鍵；這一支要的是**真的 info hash**，
    而 `jobs.hash` 是主鍵，猜一個出來會讓兩個不同的 torrent 變成同一列。
    """
    text = normalise_info_hash(raw)
    if len(text) != HEX_HASH_LENGTH:
        return ""
    try:
        binascii.unhexlify(text)
    except (binascii.Error, ValueError):
        return ""
    return text


def info_hash_of(raw: bytes) -> str:
    """一份 `.torrent` 的 info hash：`info` 那個值的**原始位元組**的 SHA-1。

    SHA-1 是 BitTorrent 協定訂的識別方式，不是這裡在選一個雜湊——所以 `usedforsecurity=False`。
    """
    span = _info_span(raw)
    if span is None:
        raise NotATorrentError("not a .torrent: no info dictionary")
    start, end = span
    return hashlib.sha1(raw[start:end], usedforsecurity=False).hexdigest()


def _info_span(raw: bytes) -> tuple[int, int] | None:
    """最外層字典裡 `info` 那個值的位元組範圍。

    只掃最外層的鍵：巢狀結構裡也可能有叫 `info` 的鍵（實務上沒有，但掃描器不該賭）。
    """
    if not raw.startswith(b"d"):
        return None
    position = 1
    try:
        while position < len(raw) and raw[position : position + 1] != b"e":
            key, position = _read_string(raw, position)
            start = position
            position = _skip(raw, position)
            if key == b"info":
                return (start, position)
    except _MalformedError:
        return None
    return None


class _MalformedError(Exception):
    """掃到不是 bencode 的東西。對外一律翻成 `NotATorrentError`。"""


def _skip(raw: bytes, position: int, depth: int = 0) -> int:
    """跳過位於 `position` 的一個 bencode 值，回傳它結束後的位置。

    `depth` 擋的是刻意做深的巢狀：`RecursionError` **不是** `_MalformedError`，它會穿過
    `_info_span` 的 `except` 一路冒成 500，而那份位元組本來就只是「不是 torrent」。
    """
    if depth > MAX_NESTING:
        raise _MalformedError
    marker = raw[position : position + 1]
    if marker == b"i":
        end = raw.find(b"e", position)
        if end == -1:
            raise _MalformedError
        return end + 1
    if marker in (b"l", b"d"):
        position += 1
        while True:
            if position >= len(raw):
                raise _MalformedError
            if raw[position : position + 1] == b"e":
                return position + 1
            position = _skip(raw, position, depth + 1)
    if marker.isdigit():
        _, position = _read_string(raw, position)
        return position
    raise _MalformedError


def _read_string(raw: bytes, position: int) -> tuple[bytes, int]:
    """`4:info` → (`b"info"`, 結束位置)。"""
    colon = raw.find(b":", position)
    if colon == -1:
        raise _MalformedError
    try:
        length = int(raw[position:colon])
    except ValueError as exc:
        raise _MalformedError from exc
    end = colon + 1 + length
    if length < 0 or end > len(raw):
        raise _MalformedError
    return raw[colon + 1 : end], end


__all__ = [
    "MAX_TORRENT_BYTES",
    "HttpTorrentFetcher",
    "NotATorrentError",
    "TorrentFetcher",
    "TorrentSource",
    "info_hash_of",
    "magnet_info_hash",
]
