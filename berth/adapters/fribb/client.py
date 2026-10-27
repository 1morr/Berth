"""下載、更新與查 Fribb 的表（回應錄在 `tests/fixtures/http/fribb/`，是真表裁出的幾筆）。

- 檔案在 `CONFIG_ROOT/cache/fribb/anime-list-full.json`。比 `MAX_AGE_SECONDS` 舊就重抓：上游每週
  自動更新一次（週二，brief §20.3），每週抓一次就跟得上。
- **下載到的要先解得開才換掉舊檔**：寫到旁邊的暫存檔、驗過再換名。實測一次 `curl` 只拿到
  7.5 MB 裡的 6.6 MB，連線就斷了。
- 更新不了（GitHub 不通、拿到半張表）而舊檔還在：用舊的，一小時內不再試，免得每次查都等一次下載。
- 解好的索引全程序一份，以檔案的修改時間認是不是同一份。讀檔與解析在執行緒裡做（整張表約 0.2 秒）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from berth.adapters.fribb import LIST_URL, FribbEntry, parse_list
from berth.adapters.http import (
    HttpSession,
    ProtocolMismatchError,
    ServiceError,
    ServiceUnavailableError,
)

logger = logging.getLogger(__name__)

#: 表比這舊就重抓。
MAX_AGE_SECONDS = 7 * 24 * 60 * 60
#: 更新失敗之後多久再試。
RETRY_SECONDS = 60 * 60

#: 7.5 MB；慢的連線也要下載得完。
_TIMEOUT_SECONDS = 120.0

#: 路徑 → （檔案修改時間, 索引）。
_INDEXES: dict[Path, tuple[float, dict[int, FribbEntry]]] = {}
#: 路徑 → 上一次更新失敗的時間。
_FAILED: dict[Path, float] = {}


def list_path(config_root: Path) -> Path:
    return config_root / "cache" / "fribb" / "anime-list-full.json"


class HttpFribb:
    def __init__(
        self, path: Path, *, url: str = LIST_URL, clock: Callable[[], float] = time.time
    ) -> None:
        self._path = path
        self._url = url
        self._clock = clock

    async def lookup(self, anilist_ids: Sequence[int]) -> dict[int, FribbEntry]:
        index = await self._index()
        return {i: index[i] for i in anilist_ids if i in index}

    async def _index(self) -> dict[int, FribbEntry]:
        await self._refresh()
        mtime = self._path.stat().st_mtime
        cached = _INDEXES.get(self._path)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        index = await asyncio.to_thread(_read, self._path)
        _INDEXES[self._path] = (mtime, index)
        return index

    async def _refresh(self) -> None:
        now = self._clock()
        exists = self._path.exists()
        if exists and now - self._path.stat().st_mtime < MAX_AGE_SECONDS:
            return
        if exists and now - _FAILED.get(self._path, 0.0) < RETRY_SECONDS:
            return
        try:
            await self._download()
        except ServiceError as exc:
            if not exists:
                raise
            _FAILED[self._path] = now
            logger.warning("fribb list not updated, using the old copy", extra={"error": str(exc)})
            return
        _FAILED.pop(self._path, None)

    async def _download(self) -> None:
        parts = urlsplit(self._url)
        async with HttpSession(
            f"{parts.scheme}://{parts.netloc}", timeout=_TIMEOUT_SECONDS
        ) as http:
            response = await http.get(parts.path)
        await asyncio.to_thread(_replace, self._path, response.content)


def _replace(path: Path, content: bytes) -> None:
    """解得開、是一串條目才換掉舊檔。"""
    try:
        answer: Any = json.loads(content)
    except ValueError as exc:
        raise ServiceUnavailableError(
            f"fribb list: not complete JSON ({len(content)} bytes)"
        ) from exc
    if not isinstance(answer, list) or not answer:
        raise ProtocolMismatchError("fribb list: not a list of entries")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    partial.write_bytes(content)
    partial.replace(path)


def _read(path: Path) -> dict[int, FribbEntry]:
    try:
        answer: Any = json.loads(path.read_bytes())
    except ValueError as exc:
        raise ProtocolMismatchError(f"fribb list at {path}: not JSON") from exc
    if not isinstance(answer, list):
        raise ProtocolMismatchError(f"fribb list at {path}: not a list of entries")
    return parse_list(answer)
