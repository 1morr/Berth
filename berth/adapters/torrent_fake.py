"""測試與前端演練用的 torrent 來源替身（`adapters/torrent.py` 的 `TorrentFetcher`）。

住在 `adapters/` 底下的獨立模組而不是 `torrent/fake.py`，是因為 `torrent.py` 是一個檔案
不是套件——其他 adapter 之所以是套件，是它們各有 client 與協定型別要分開放。
"""

from __future__ import annotations

from berth.adapters.torrent import TorrentSource, magnet_info_hash

#: 沒有特別指定時回的那一份。hash 是 40 字十六進位，形狀與真的一樣。
DEFAULT_HASH = "1111111111111111111111111111111111111111"


class FakeTorrentFetcher:
    """一張「網址 → 來源」的查表，加一個可以讓它整個垮掉的旗標。

    預設行為是**照網址推**：磁力連結讀它自己的 hash，其餘一律回 `DEFAULT_HASH`。
    多數測試只在意「有沒有拿到一個 hash」，逐筆安排一份 torrent 只會讓安排蓋過斷言。
    """

    def __init__(
        self,
        *,
        sources: dict[str, TorrentSource] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._sources = dict(sources or {})
        self.error = error
        #: 被要過的每一條網址，用來斷言「重複送單時一次都沒去要」。
        self.requested: list[str] = []

    async def fetch(self, url: str) -> TorrentSource:
        self.requested.append(url)
        if self.error is not None:
            raise self.error
        if url in self._sources:
            return self._sources[url]
        info_hash = magnet_info_hash(url)
        if info_hash:
            return TorrentSource(info_hash=info_hash, magnet=url)
        return TorrentSource(info_hash=DEFAULT_HASH, content=b"d4:infod4:name5:berthee")

    async def aclose(self) -> None:
        return None
