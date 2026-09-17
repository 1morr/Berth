"""一位使用者在 Jellyfin 看到哪了：媒體庫牆上那一行（M1.5 票 05、brief §12）。

**判定照 jellyfin-web 的卡片**（v10.11.11 `components/indicators/indicators.js`）：

- **已看**：`Played`，或 `PlayedPercentage` ≥ 100。
- **看到一半**：只有影片（電影、集）。jellyfin-web 的進度條只給 `MediaType=Video`，劇集沒有。
- **剩幾集沒看**：只有資料夾（劇集）。**沒開始看的劇也算**——jellyfin-web 的計數徽章只看
  `UnplayedItemCount`。資料夾才有這一格（研究 library-browsing.md §1.2），所以看它在不在就分得出
  劇集與影片，寫入的回應（只有 `UserData`、沒有型別）也推得出來。

一行只說一件事：已看優先。觀看紀錄存在 Jellyfin，Berth 不存。
"""

from __future__ import annotations

from dataclasses import dataclass

from berth.adapters.jellyfin import JellyfinUserData


@dataclass(frozen=True, slots=True)
class WatchState:
    """牆上那一格的觀看狀態。三格至多一格有話說；都沒有就是這個人還沒看過。"""

    played: bool
    #: 看到一半的影片看到幾 %（1–99）。劇集、看過的、沒在看的是 `None`。
    progress: int | None
    #: 還沒看完的劇集剩幾集沒看。影片與看完的劇集是 `None`。
    unplayed_episodes: int | None


def watch_state(data: JellyfinUserData) -> WatchState:
    played = data.played or data.played_percentage >= 100
    if played:
        return WatchState(played=True, progress=None, unplayed_episodes=None)
    if data.unplayed_item_count is not None:
        return WatchState(
            played=False, progress=None, unplayed_episodes=data.unplayed_item_count or None
        )
    under_way = data.played_percentage > 0
    return WatchState(
        played=False,
        # 「看到 0%」「看到 100%」卻沒看完都是假話，所以夾在 1–99。
        progress=min(99, max(1, round(data.played_percentage))) if under_way else None,
        unplayed_episodes=None,
    )
