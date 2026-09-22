"""Issue：一件「要有人決定」的事（plan §2.4、brief §9.1、M2 票 05）。

**Issue 不是事件**。`events` 記的是發生過什麼（歷史，只增不改），`issues` 記的是**還沒有人
決定**的那一件——它有 `open` / `resolved` / `ignored`，有人按了才改。同一件事兩邊都寫：管線
發現 torrent 報錯時寫一筆 `issue_detected` 事件（時間線上那一行），也寫一列 `issues`（清單上
那一列）。少了前者時間線會斷，少了後者那件事沒有人會回來看。

形狀上只有兩件事要解釋：

- **冪等鍵是 `(type, subject)`，而 `subject` 是一個存下來的欄位**。plan §2.4 的欄位表上沒有
  它——那一段說的是「`subject` 依型別取哪一欄」，而**取**這個動作要有結果落在某處，唯一索引
  才守得住它。算在 Python 裡再查一次的話，兩個迴圈同時偵測到同一件事就會寫出兩筆 `open`。
  值由 `subject_of()` 從同一張 `SUBJECT_OF` 表算出來，所以「取哪一欄」仍然只有一份定義。
- **唯一索引只蓋 `open`**（partial index）：決定過的留著當歷史，同一件事再發生時開的是新的
  一筆。蓋住全部的話，一條路徑一輩子只能出一次問題。

`job_hash` 與 `ledger_id` 都是**弱引用**，與 `events`、`ledger` 同一個理由（`models/ledger.py`）：
刪除範圍的「清除帳本」與「清除 Job 紀錄」是獨立的旗標，而一件已經決定過的 Issue 要能說出
「你當時把那條路徑怎麼了」——`path` 帶著那句話，指標斷了不影響它。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import SUBJECT_OF, IssueStatus, IssueSubject, IssueType
from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, enum_column, utcnow


def subject_of(
    kind: IssueType, *, path: str = "", job_hash: str | None = None, ledger_id: int | None = None
) -> str:
    """這一件的冪等鍵取哪一格的值（plan §2.4 的 `SUBJECT_OF`）。

    空字串是**寫不下去**的訊號而不是一個合法的鍵：呼叫端給了型別卻沒給那一種要的欄位時，
    `record_issue` 會拒絕，而不是讓一堆沒有鍵的列互相覆蓋。
    """
    column = SUBJECT_OF[kind]
    if column is IssueSubject.PATH:
        return path
    if column is IssueSubject.JOB_HASH:
        return job_hash or ""
    return "" if ledger_id is None else str(ledger_id)


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (
        # 冪等鍵（plan §2.4）。**只蓋 `open`**：歷史上同一條路徑可以出過很多次問題。
        Index(
            "ix_issues_open_subject",
            "type",
            "subject",
            unique=True,
            sqlite_where=text(f"status = '{IssueStatus.OPEN.value}'"),
        ),
        # 清單預設就是「還沒決定的那幾件，新的在前」。
        Index("ix_issues_status_detected_at", "status", "detected_at"),
        Index("ix_issues_job_hash", "job_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[IssueType] = mapped_column(enum_column(IssueType))
    #: 冪等鍵的後半，由 `subject_of()` 依型別從下面三欄之一取。
    subject: Mapped[str] = mapped_column(Text)
    #: 弱引用（沒有外鍵）。管線那四種一定有，對帳那幾種看情況。
    job_hash: Mapped[str | None] = mapped_column(Text, default=None)
    #: 弱引用。帳本那一列被「承認刪除並清帳本」刪掉之後仍留著當歷史，`path` 才是那句話。
    ledger_id: Mapped[int | None] = mapped_column(default=None)
    #: 出問題的那一條路徑（媒體庫目標、complete 來源或目錄）。不適用的型別是空字串。
    path: Mapped[str] = mapped_column(Text, default="")
    #: 逐型別不同的那幾格。畫面照型別挑要顯示哪幾個，與 `events.payload_json` 同一個規矩。
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JsonText, default=None)
    status: Mapped[IssueStatus] = mapped_column(enum_column(IssueStatus), default=IssueStatus.OPEN)
    #: 最後一次**偵測到**的時間。再偵測到就更新它與 `detail_json`（plan §2.4）。
    detected_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    #: 按下去的那個人（user id 字串）或 `system`。按的是哪一顆存在 `detail_json.action`。
    resolved_by: Mapped[str] = mapped_column(Text, default="")
