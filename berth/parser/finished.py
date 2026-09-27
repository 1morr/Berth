"""RSS Series 完結了沒（brief §15「以作品呈現」、plan §2.4、M4 票 13）。

完結的收進 RSS 頁的「已完結」（預設收起），**紀錄不刪**：去重與同一個番組 × 字幕組重新出現時
的綁定都要它。所以這不是一個存下來的狀態，而是每次讀清單時照現況算——有新 Item 出現時條件自己
不成立，它就回到清單。
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime, timedelta

from berth.domain import MediaSnapshot

#: 最近一筆發佈之後多久沒有新的就算完結（2026-09-27 shape 拍板）。試跑 10 個 Series、146 筆，同一個
#: Series 相鄰兩筆最長隔 22 天（字幕組晚發），其餘 ≤ 14 天；多一週的餘裕。收錯了也只是收起來，新的
#: 一筆來就回到清單。
QUIET_AFTER = timedelta(days=30)

#: TMDB 說完結而且都入庫了的，最近一筆發佈之後還要再等多久才收起來：一週一集的節奏。新的一筆——不論
#: 送了沒（排除、重複、v2 都算）——出現時就回到清單，這一週裡看得到它（2026-09-27 code-review）。
SETTLED_AFTER = timedelta(days=7)


def series_finished(
    *,
    latest: datetime,
    now: datetime,
    media: MediaSnapshot | None,
    seasons: Collection[int],
    held: Collection[tuple[int, int]],
    open_items: int,
) -> bool:
    """兩條路任一條成立就完結：

    1. **安靜太久**：`latest`（最近一筆的發佈時間；沒有就是長出來那一刻）到 `now` 超過
       `QUIET_AFTER`。
    2. **TMDB 說完結而且都入庫了**：`media.ended`，這個 Series 入庫過的那幾季（`seasons`）TMDB
       上的每一集都在帳本裡（`held` 是這部作品在庫的 `(季, 集)`），而且沒有還在等或還在路上的
       Item（`open_items`），最近一筆也發佈超過 `SETTLED_AFTER` 了。後兩條讓新出現的一筆把它帶回
       清單。
    """
    if now - latest > QUIET_AFTER:
        return True
    if media is None or not media.ended or open_items or not seasons:
        return False
    if now - latest <= SETTLED_AFTER:
        return False
    wanted = {
        (block.season_number, episode.episode_number)
        for block in media.seasons
        if block.season_number in seasons
        for episode in block.episodes
    }
    return bool(wanted) and wanted <= set(held)
