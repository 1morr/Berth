"""片長驗證：mediainfo 量到的片長對 TMDB 那一集的片長（M3 票 15、plan §11.4 的「三道程式檢查」②）。

抓的是**分類錯誤**：SP / OVA、兩集合併的檔案被當成一集正片——規則層照檔名讀出一個有把握的集號，
而那個檔案根本不是那一集。**抓不到同一季裡算錯的集號**：同一季的每一集差不多一樣長（那是播出日
比對的事，`parser.airing`）。短於五分鐘的「正片」由分類器自己降成 extra（`parser.classify`，
brief §6.2；2026-09-26 使用者拍板保留），所以這裡看到的是分類器看不出來的那些。

可疑的那一列送審核（`PlanAction.REVIEW`），季集與目標路徑留著：片長其實沒錯的（TMDB 的片長
寫錯、導演剪輯版）核准就照這一格入庫（`parser.promote`）。

**不寫死在規劃的路徑裡**：M5 的 AI 結果也要過同一條（brief §14「AI 說了不算」），所以它只吃
Plan Item、量到的片長與快照。
"""

from __future__ import annotations

from collections.abc import Sequence

from berth.domain import (
    FileEntry,
    MediaSnapshot,
    PlanItem,
    episode_label,
    why,
)
from berth.domain import ReasonCode as Code
from berth.parser.planner import episode_span, hold, note

#: 片長驗證把一列送審核時留下的理由。規劃器看到它就把整份 Plan 的理由說成
#: `ReviewReason.RUNTIME_CONFLICT`（`services/plan._verdict`）。
HELD_BY_RUNTIME: frozenset[Code] = frozenset({Code.RUNTIME_MISMATCH})

#: 兩個容忍取大的那一個：差超過 `RUNTIME_SLACK` 秒**而且**超過 TMDB 片長的 `RUNTIME_RATIO`
#: 才算差太多。量測（`scripts/experiments/runtime_gap.py`，AnimeTosho 的 mediainfo 對語料的
#: TMDB 快照，8 部動畫）：87 集對得上的正片比例 0.94–1.03、差 −84 到 +41 秒；兩集合併成一檔
#: 比例 1.86–2.04、差 +1288 秒起。
#: 兩個門檻都留了約兩倍餘裕。只有動畫的樣本：一小時的劇靠比例那一邊（±9 分鐘）。
#:
#: 絕對秒數：TMDB 的片長是整數分鐘、常是概數。短的一集靠它——只看比例的話五分鐘的短篇差幾十秒就被擋。
RUNTIME_SLACK = 180

#: 與 TMDB 片長成比例的容忍。長的一集靠它——只看秒數的話一小時的劇差幾分鐘就被擋。
RUNTIME_RATIO = 0.15


def check_runtime(
    items: Sequence[PlanItem], entries: Sequence[FileEntry], media: MediaSnapshot | None
) -> tuple[PlanItem, ...]:
    """逐列比對，差太多的送審核並說出兩個片長。純函式。

    只看**要入庫的正片**（`episode_span`）：其餘的列沒有一集可以比。`entries` 是交給解析器的
    那一份（`FileEntry.duration_s`）。TMDB 沒有那一集（或範圍裡任何一集）的片長時不擋、記一筆；
    mediainfo 沒量到（`None`：量不到或 pre-plan 還在下載；`0`：說不出多長）時不擋也不記——
    §8.7「失敗不阻擋」，而 pre-plan 那一輪每一列都是 `None`，逐列記一筆只是雜訊。
    """
    if media is None:
        return tuple(items)
    durations = {entry.rel_path: entry.duration_s for entry in entries}
    return tuple(_checked(item, durations.get(item.rel_path), media) for item in items)


def _checked(item: PlanItem, seconds: int | None, media: MediaSnapshot) -> PlanItem:
    span = episode_span(item)
    if span is None or not seconds:
        return item
    season, start, end = span
    label = episode_label(season, start, end if end != start else None)
    minutes = _minutes(media, season, start, end)
    if minutes is None:
        return note(item, why(Code.RUNTIME_MISSING, episode=label))
    if abs(seconds - minutes * 60) <= _tolerance(minutes):
        return item
    return hold(
        item,
        why(Code.RUNTIME_MISMATCH, episode=label, measured=_clock(seconds), minutes=minutes),
    )


def _tolerance(minutes: int) -> int:
    """容忍的秒數：絕對與比例取大的那一個。"""
    return max(RUNTIME_SLACK, round(minutes * 60 * RUNTIME_RATIO))


def _minutes(media: MediaSnapshot, season: int, start: int, end: int) -> int | None:
    """TMDB 說這一段有幾分鐘（範圍是各集相加）。任何一集不在、或沒填片長，都是 `None`。"""
    found = [media.episode(season, number) for number in range(start, end + 1)]
    runtimes = [row.runtime for row in found if row is not None and row.runtime]
    return sum(runtimes) if len(runtimes) == len(found) else None


def _clock(seconds: int) -> str:
    """`12:05` / `1:02:03`：播放器的寫法，不必翻譯。"""
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"
