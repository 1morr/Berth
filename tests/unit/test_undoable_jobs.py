"""送單撤得回來的狀態（`jobs.UNDOABLE`，M5 票 12）：送出去了、還沒下載完，撤銷（移除 torrent、
刪下載的檔、清紀錄）不會碰到媒體庫或 complete 裡看得了的檔案。下載完之後規劃器隨時會接手入庫，
要刪得去 Job 頁看清楚範圍。"""

from __future__ import annotations

from berth.domain import JobState
from berth.services.jobs import UNDOABLE

#: 下載完之後（含入庫中、入庫了、被移走的），與送單本身還在打 qBittorrent 的那一刻。
NOT_UNDOABLE = {
    JobState.REQUESTED,
    JobState.COMPLETED,
    JobState.PLANNING,
    JobState.REVIEW,
    JobState.IMPORTING,
    JobState.IMPORTED,
    JobState.IMPORT_FAILED,
    JobState.REMOVED,
}


def test_only_downloads_that_have_not_finished_can_be_undone() -> None:
    assert UNDOABLE.isdisjoint(NOT_UNDOABLE)
    # 新加的狀態要決定歸哪一邊：兩邊加起來是全部。
    assert set(JobState) == UNDOABLE | NOT_UNDOABLE
