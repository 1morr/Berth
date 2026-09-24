"""帳本：一條「來源檔案 → 目標硬鏈接」的紀錄（plan §2.3、brief §7.9、CONTEXT.md 的 Ledger Entry）。

**帳本是 Berth 的核心資產**（brief §7.9）：沒有它就回答不了「這個媒體庫檔案來自哪個
torrent」「這個 torrent 入庫到哪」「哪些鏈接斷了」。所以這一列的形狀主要是關於**它自己
站得住**，不靠別的表活著：

- **`job_hash` 是弱引用**（與 `events` 相同）：刪除範圍的四個旗標裡「清除帳本」是獨立的
  一個（brief §9.2），刪掉 Job 不可以順手把帳本帶走。`berth rebuild-ledger` 與「認領進帳本」
  長回來的列，來源不屬於任何 Job 時是 `None`（重新入庫自 M2 票 10 起有自己的 Job）。
- **`action`、季集與 Tags 抄一份進來**，不是只記 `plan_item_id`：review 之後重新規劃會把
  `plan_items` 整份換掉（`models/plan.py`），而帳本記的是**當時真的鏈接了什麼**。
  `plan_item_id` 因此是 `SET NULL`，只是一條「從哪一份決定來的」線索。
- **inode 與 device 存成 TEXT**。Windows 的 `st_dev` 是 64 位元無號的磁碟區序號，實測
  `11550084160259632778`（票 09）超過 SQLite INTEGER 的有號上限，存進去就是 `OverflowError`；
  而這兩欄只拿來比相等，不做算術。
- **`resolve_after` 是 `jellyfin_resolver` 的排程**（plan §3.2）：`None` 代表沒有要反查的事
  ——找到了、重試用完了，或這一筆本來就不是一個 Jellyfin item（字幕與特典）。重試幾次、下一次
  什麼時候都要活過重啟，所以落在這一列而不是迴圈的記憶體裡。

`target_path` 是**容器裡的 POSIX 路徑**，也就是 Jellyfin 回報 `Path` 的那個形狀——反查比的
就是這一串字（brief §20.1）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import LedgerStatus, PlanAction
from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, enum_column, utcnow

#: 唯一的鏈接方式。硬鏈接失敗不退回複製（brief §4.4），欄位留著是 plan §2.3 的形狀。
HARDLINK = "hardlink"


class LedgerEntry(Base):
    __tablename__ = "ledger"
    __table_args__ = (
        # 一條媒體庫路徑只會有一個來源（plan §3.3）：同一個目標寫第二筆就是冪等出了錯。
        Index("ix_ledger_target_path", "target_path", unique=True),
        Index("ix_ledger_job_hash", "job_hash"),
        Index("ix_ledger_resolve_after", "resolve_after"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_hash: Mapped[str | None] = mapped_column(Text, default=None)
    #: 相對 `jobs.save_path`，含 torrent 自己的根目錄那一層（與 `job_files.rel_path` 同形）。
    source_rel_path: Mapped[str] = mapped_column(Text)
    source_abs_path: Mapped[str] = mapped_column(Text)
    source_inode: Mapped[str] = mapped_column(Text)
    source_dev: Mapped[str] = mapped_column(Text)
    target_path: Mapped[str] = mapped_column(Text)
    #: 鏈接完量到的目標 inode。與 `source_inode` 相等就是硬鏈接成立的定義。
    target_inode: Mapped[str] = mapped_column(Text)
    media_id: Mapped[str | None] = mapped_column(
        ForeignKey("media.id", ondelete="SET NULL"), default=None
    )
    season: Mapped[int | None] = mapped_column(default=None)
    episode_start: Mapped[int | None] = mapped_column(default=None)
    episode_end: Mapped[int | None] = mapped_column(default=None)
    tags_json: Mapped[dict[str, Any] | None] = mapped_column(JsonText, default=None)
    plan_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_items.id", ondelete="SET NULL"), default=None
    )
    #: `import` / `extra` / `subtitle`。只有 `import` 在 Jellyfin 裡是一個查得到的 item。
    action: Mapped[PlanAction] = mapped_column(enum_column(PlanAction))
    jellyfin_item_id: Mapped[str] = mapped_column(Text, default="")
    #: 正片是劇集的一集時，它所屬的 Series item（票 13）。媒體庫的深連結開的是作品，
    #: 不是某一集；反查那一刻 `/Items` 的 Episode 自己帶著它，所以與 item id 一起寫下。
    #: `server_default` 是 migration 原生 `ADD COLUMN` 留下來的（不重建表，理由在 `7c3e5a9b2d41`）。
    jellyfin_series_id: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: Jellyfin 版本選單上這個檔案的名字（`MediaSources[].Name`，票 14b）。反查到的那一刻寫下；
    #: 還沒收錄就是空字串，畫面照實說「Jellyfin 還沒收錄」而不是自己重算一個（brief §7.7、§20.9）。
    jellyfin_version_name: Mapped[str] = mapped_column(Text, default="", server_default="")
    resolve_attempts: Mapped[int] = mapped_column(default=0)
    resolve_after: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    link_mode: Mapped[str] = mapped_column(Text, default=HARDLINK)
    status: Mapped[LedgerStatus] = mapped_column(enum_column(LedgerStatus), default=LedgerStatus.OK)
    #: medium 自動入庫的旗標，抄自那一列 Plan Item（CONTEXT.md 的 Audit）。
    audit: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    #: Reconciler 上一次比對它的時間（M2）。
    checked_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
