"""Import Plan 與它逐檔的決定（plan §2.3、CONTEXT.md、票 11）。

**一個 Job 只有一列 `plans`**（`job_hash` unique），推翻不了的理由是這一列回答的問題：
「這個 Job 現在的計劃是什麼」。重跑 planning 會把它整份改寫，而不是再長一列——不然
`GET /api/plans/{id}` 要先回答「哪一個 id 才是現在那一份」，而 `plan_items` 會在每一次
重跑之後多一份重複的決定（票上「重跑不產生重複的 plan item」那一條驗收）。上一份計劃
在時間線上（`events`），它本來就是紀錄該待的地方。

`job_hash` 仍然可以是 `None`：M2 的重新入庫以 complete 底下的一個目錄為 Import Source
（`source_path`），那時候沒有 Job。SQLite 的 unique 容得下多個 NULL，所以同一個約束同時
成立於兩種來源。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import Confidence, PlanAction, PlanEngine, PlanStatus
from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, enum_column, utcnow


class Plan(Base):
    """一個 Import Source 的逐檔決定（CONTEXT.md 的 Import Plan）。"""

    __tablename__ = "plans"
    __table_args__ = (Index("ix_plans_job_hash", "job_hash", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    #: 哪一個 Job。M2 的重新入庫沒有 Job，那時是 `None` 而 `source_path` 有值。
    job_hash: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.hash", ondelete="CASCADE"), default=None
    )
    #: 重新入庫時的來源目錄（M2）。Job 帶來的那些用 `jobs.save_path` + 檔案的相對路徑。
    source_path: Mapped[str] = mapped_column(Text, default="")
    engine: Mapped[PlanEngine] = mapped_column(enum_column(PlanEngine), default=PlanEngine.RULES)
    #: 算出這一份的那一版 Berth。規則改了之後舊的 Plan 仍然說得出它是誰算的。
    engine_version: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[PlanStatus] = mapped_column(enum_column(PlanStatus))
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JsonText, default=None)
    #: **算出這一份的時間**。這一列永遠是「現在的計劃」，重跑會把它整份換掉，
    #: 所以時間也跟著換；上一份留在時間線上。
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    #: 誰核准或拒絕的（M2 的 Review Queue）。自動入庫的那些沒有人在場。
    decided_by: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)


class PlanItem(Base):
    """Plan 裡一個檔案的決定（CONTEXT.md 的 Plan Item）。

    欄位與 `domain.PlanItem` 幾乎一樣，但**不是同一個東西**：那一個是解析器的輸出
    （純資料、沒有身分），這一列是它落地之後的樣子——有 id、有 `media_id`（M2 可以逐列
    改指派）、有 `applied_at` 與 `error`（importer 逐檔回填，票 12）。
    """

    __tablename__ = "plan_items"
    __table_args__ = (Index("ix_plan_items_plan_id", "plan_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"))
    #: 對應的 `job_files` 那一列。重新入庫時沒有 Job，那時是 `None`。
    job_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_files.id", ondelete="SET NULL"), default=None
    )
    #: 相對於 Import Source 的內容根（與 `domain.FileEntry.rel_path` 同一個意思）。
    rel_path: Mapped[str] = mapped_column(Text)
    action: Mapped[PlanAction] = mapped_column(enum_column(PlanAction))
    #: 這個檔案屬於哪一部作品。Job 一路都帶著同一個，但 M2 可以逐列改。
    media_id: Mapped[str | None] = mapped_column(
        ForeignKey("media.id", ondelete="SET NULL"), default=None
    )
    season: Mapped[int | None] = mapped_column(default=None)
    episode_start: Mapped[int | None] = mapped_column(default=None)
    episode_end: Mapped[int | None] = mapped_column(default=None)
    #: `domain.Tags` 的結構化版本。檔名只是它的一種呈現（brief §6.8）。
    tags_json: Mapped[dict[str, Any] | None] = mapped_column(JsonText, default=None)
    #: 相對於 Route 目標路徑的位置。**只有真的會被寫出去的檔案有值**（plan §4.2）。
    target_path: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[Confidence] = mapped_column(enum_column(Confidence))
    #: 為什麼是這個決定：`domain.ItemReason` 的 JSON（`{code, params}`），UI 逐條翻譯（brief §6.5、
    #: M2 票 07）。讀寫都走 `services/plan_view.py` 的 `reasons_of` / `dump_reasons`。
    reasons_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonText, default=None)
    #: medium 信心自動入庫時掛的旗標（CONTEXT.md 的 Audit、brief §6.5）。
    #: M2 的 Review Queue 以「已入庫待確認」列出它們，一鍵撤銷或確認。
    audit: Mapped[bool] = mapped_column(default=False)
    #: importer 真的鏈接完的時間（票 12）。
    applied_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    error: Mapped[str] = mapped_column(Text, default="")
