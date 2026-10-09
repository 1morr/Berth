"""送單來源記在伺服器上，瀏覽器只拿一個不透明的 id（M4 票 79）。

搜尋結果的下載連結是 Prowlarr 的代理網址，帶著 `?apikey=<Prowlarr key>`（brief §20.7）。
`/search` 一般使用者也打得到，所以連結不能出伺服器：搜尋與一次性連結把每一筆記在這裡、
回一個 id，`POST /jobs` 收 id、在這裡換回那一筆。送單因此也送不進任意網址。

**照 Sonarr / Radarr 的 interactive search**：搜尋時把每一筆結果放進程序內的快取（30 分鐘），
送單只帶 `guid` 加 `indexerId`，快取裡找不到就 404「再搜一次」。兩處不同：

- **id 是隨機的**，不是 `guid`：`guid` 是索引站給的，可能就是那個站的下載網址，而一般使用者
  不該拿得到別人的 id 去送單——猜不到比較省事。同一個發佈在兩輪搜尋裡各記一筆
  （兩條代理連結本來就不一樣）。
- **記兩小時**：一次搜尋 35–85 秒、還要吃請求預算（M3 票 20），結果表常常開著比較好一陣子；
  過期的代價是再搜一次。一筆不到 1 KB、一次搜尋最多 200 筆，記的時候順手清掉過期的。

**不落地**（票 08 的「搜尋結果不落地」仍成立）：Berth 重啟之後每一個 id 都不認得，與過期同一個說法。
一個程序一份（`create_app` 放進 `app.state`），Berth 只跑一個程序（同 `EventHub`）。
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable

from berth.domain import JobRefusal
from berth.services.jobs import JobRejectedError, JobSource

#: 一個 id 記多久。理由見模組說明。
SOURCE_TTL_SECONDS = 2 * 60 * 60


class SourceCache:
    """id → 那一筆送單要的東西（連結、發佈名、info hash、發佈時間、大小）。"""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        #: 插入順序就是過期順序（TTL 只有一種），所以清的時候從頭清到第一個沒過期的就停。
        self._entries: dict[str, tuple[float, JobSource]] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def remember(self, source: JobSource) -> str:
        now = self._clock()
        self._evict(now)
        source_id = secrets.token_urlsafe(16)
        self._entries[source_id] = (now + SOURCE_TTL_SECONDS, source)
        return source_id

    def recall(self, source_id: str) -> JobSource:
        """換回那一筆。不認得與過期是同一個拒絕：Berth 分不出來，下一步都是再搜一次。

        `detail` 是空的：它會原樣印在畫面上，而送來的那串字沒有東西好說。
        """
        entry = self._entries.get(source_id)
        if entry is None or self._clock() >= entry[0]:
            raise JobRejectedError(JobRefusal.SOURCE_EXPIRED)
        return entry[1]

    def _evict(self, now: float) -> None:
        for source_id, (expires, _) in list(self._entries.items()):
            if expires > now:
                break
            del self._entries[source_id]
