"""索引站搜尋的介面（plan §8.4、票 08）。

`ProwlarrClient` 與 `TorznabClient` 是**精靈**用的：它們回答「這個端點還通不通」。這一支
回答的是另一個問題——「這部作品現在有哪些發佈可以下載」。分成兩個介面而不是替既有的
client 多加一個方法，是因為兩邊的實作只有位址是共通的：Prowlarr 走 REST（它刻意不提供
跨站聚合 Torznab，brief §20.7），任意 Torznab 端點走 XML。

**一次呼叫一個查詢**（推翻 plan §8.4 原本的 `search(queries, categories)`）：多標題展開、
合併去重、逐查詢逾時全部是領域決策——要看 `MediaSnapshot` 的標題集合與 Route 的 profile
才決定得了，而 adapter 不認得那兩個東西。留在這一層的話兩個實作各要抄一份同樣的邏輯。
搬去 `services/search.py` 之後這裡只剩「一個查詢 → 一次 HTTP → 一串結果」。
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from berth.domain import MediaKind


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """發給索引站的一次查詢。

    `text` 與 `tmdb_id` 不是二選一的旗標而是**同一個問題的兩種問法**：端點的 `t=caps` 說
    支援 tmdbid 時用 id 問（一次就夠、也不會被翻譯與別名絆倒），不支援時退回關鍵字。
    要用哪一種由 `capabilities()` 回答，呼叫端據此決定要發幾個查詢（票 08 驗收）。
    """

    text: str = ""
    #: 用 tmdbid 搜的那一種問法。`None` = 這個端點只認得關鍵字。
    tmdb_id: int | None = None
    #: 決定走 `t=tvsearch` 還是 `t=movie`。Prowlarr 的 REST 不分這個。
    kind: MediaKind = MediaKind.TV


@dataclass(frozen=True, slots=True)
class SearchCapability:
    """這個端點搜得動什麼（`t=caps`）。"""

    #: `<searching><search available>`。`False` 時整個搜尋沒有意義，畫面要說得出來。
    searchable: bool = True
    #: 哪幾種作品可以用 tmdbid 搜。**實測十個預設公開站一個都沒有**（票 08，brief §20.7），
    #: 所以 `q=` 那條退路才是常態，不是例外。
    tmdb_id: frozenset[MediaKind] = frozenset()


@dataclass(frozen=True, slots=True)
class IndexerResult:
    """索引站回的一筆發佈。結果表的一列（brief §13）。"""

    #: 發佈名。解析器讀的就是它（`parse_release`）。
    title: str
    #: 哪一個站。Prowlarr 聚合時逐筆不同，單一 Torznab 端點時整批一樣。
    indexer: str = ""
    #: 位元組。索引站沒說時是 0。
    size: int = 0
    #: `None` = 那個站沒報。與 0 不同：0 是「真的沒有人做種」。
    seeders: int | None = None
    leechers: int | None = None
    #: 送給 qBittorrent 的那一條（票 09）。Prowlarr 回的是它自己的代理網址，
    #: **每次請求都不一樣**（`link=` 的密文帶 nonce，2026-09-10 實測 1021 筆只有 1 筆重疊），
    #: 所以它不能拿來當身分。
    download_url: str = ""
    #: 站上的頁面。結果表的「來源」連過去。
    info_url: str = ""
    #: 小寫十六進位的 info hash，正規化過（`normalise_info_hash`）。沒有就是空字串。
    info_hash: str = ""
    #: 索引站給的穩定識別字串（磁力連結或集頁網址）。`info_hash` 缺席時的身分。
    guid: str = ""
    published_at: datetime | None = None
    #: Torznab 分類碼。**不拿來篩**（票 08）：各站的映射自訂，實測 dmhy 對 `cat=5000`、
    #: `cat=5070` 與不帶 `cat` 都回同樣 80 筆，它不是可靠的篩子。顯示用。
    categories: tuple[int, ...] = field(default_factory=tuple)

    @property
    def key(self) -> str:
        """合併去重的身分（票 08 驗收）。

        info hash 優先——同一個 torrent 在不同站上是同一個 hash，而 `guid` 各站各寫各的。
        沒有 hash 的站（實測 ACG.RIP）只剩 `guid`，那時同一個發佈在兩個站上會是兩列，
        而那也是誠實的：Berth 沒有證據說它們是同一個東西。
        """
        return self.info_hash or self.guid


class IndexerSearch(Protocol):
    """一個索引站端點。位址與憑證在建構時就決定了。"""

    @property
    def base_url(self) -> str: ...

    async def capabilities(self) -> SearchCapability:
        """這個端點搜得動什麼。連不上時丟 `ServiceError` 的子類。"""
        ...

    async def search(self, query: SearchQuery) -> tuple[IndexerResult, ...]:
        """一個查詢 → 一串結果。搜不到東西是空的 tuple，不是例外。"""
        ...

    async def aclose(self) -> None: ...


def normalise_info_hash(value: str) -> str:
    """把 info hash 收斂成小寫十六進位。

    **同一個 torrent 在不同站上寫法不同**：2026-09-10 實測同一個發佈在 Mikan 是
    `4bd0f6ef…`（40 字十六進位）、在 dmhy 是 `JPIPN34K…`（32 字 base32），而後者
    解碼出來就是前者。不正規化的話它們是兩列，而使用者看到的是同一個東西出現兩次
    （單一次查詢的 1200 筆裡有 47 筆是這樣重複的）。

    認不得的寫法原樣小寫回傳——猜錯一個 hash 比留著一個怪字串糟得多。
    """
    text = value.strip()
    if len(text) == 40:
        return text.lower()
    if len(text) == 32:
        try:
            return binascii.hexlify(base64.b32decode(text.upper())).decode()
        except (binascii.Error, ValueError):
            return text.lower()
    return text.lower()


def first_int(values: Sequence[str]) -> int | None:
    """一串候選字串裡第一個像整數的。都不像就是 `None`（「那個站沒報」）。"""
    for value in values:
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


__all__ = [
    "IndexerResult",
    "IndexerSearch",
    "SearchCapability",
    "SearchQuery",
    "first_int",
    "normalise_info_hash",
]
