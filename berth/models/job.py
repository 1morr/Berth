"""Download Job 與它的檔案（plan §2.3、§3.1）。

**主鍵是 info hash 而不是流水號**（plan §2.3）。那是這個 torrent 在 qBittorrent、在索引站、
在 RSS feed 上共同的身分，所以「同一個 torrent 送兩次」在資料庫層就成立為同一列，不必靠
應用程式記得去查（plan §3.3 的冪等就是這一條）。

`media_id` 與 `route_id` 都是 nullable：M2 的重新入庫（brief §9.3）從 complete 目錄建 Job，
那時候還不知道它是哪一部作品。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import FileKind, JobState, JobTrigger
from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, enum_column, utcnow


class Job(Base):
    """一個 torrent 在 Berth 中的生命週期紀錄（`CONTEXT.md`）。"""

    __tablename__ = "jobs"

    #: 小寫十六進位的 info hash（`adapters.indexer.normalise_info_hash` 的形狀）。
    hash: Mapped[str] = mapped_column(Text, primary_key=True)
    #: 發佈名。索引站上的那一串字，原樣——它是使用者認得出這一列的東西。
    name: Mapped[str] = mapped_column(Text)
    #: 索引站上的那一條下載連結。**存著是為了重試**（plan §3.1 的 `submit_failed` →
    #: `requested`）：送單失敗之後畫面上那一輪搜尋早就不在了，而 Prowlarr 的代理連結
    #: 每次搜尋都不一樣（brief §20.7），重新搜一次不會給出同一條。
    source_url: Mapped[str] = mapped_column(Text, default="")
    trigger: Mapped[JobTrigger] = mapped_column(enum_column(JobTrigger))
    #: RSS Series 的 id 或 import source 路徑。`manual` 時是空字串。
    trigger_ref: Mapped[str] = mapped_column(Text, default="")
    #: 誰按的。RSS 與重新入庫沒有人在場，那時是 `None`。
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    #: 哪一部作品。M2 的重新入庫在比對出來之前是 `None`。
    media_id: Mapped[str | None] = mapped_column(
        ForeignKey("media.id", ondelete="SET NULL"), default=None
    )
    route_id: Mapped[int | None] = mapped_column(
        ForeignKey("routes.id", ondelete="SET NULL"), default=None
    )
    state: Mapped[JobState] = mapped_column(enum_column(JobState), default=JobState.REQUESTED)
    #: 失敗時服務回的原文（英文）。成功的轉換會把它清空。
    error: Mapped[str] = mapped_column(Text, default="")
    #: qBittorrent 報的下載目錄與內容路徑。送單當下還不知道，由票 10 的 poller 填。
    save_path: Mapped[str] = mapped_column(Text, default="")
    content_path: Mapped[str] = mapped_column(Text, default="")
    total_size: Mapped[int] = mapped_column(default=0)
    #: 0.0–1.0。qBittorrent 的 `progress` 原值。
    progress: Mapped[float] = mapped_column(default=0.0)
    #: qBittorrent 自己的狀態字串（`stalledDL`、`pausedUP`…），原樣存。**不翻譯成
    #: `JobState`**：兩者回答的是不同的問題，而畫面要說得出「客戶端那邊現在是什麼樣子」。
    client_state: Mapped[str] = mapped_column(Text, default="")
    #: 來源說它什麼時候發佈的：索引站結果的 `publishDate`、或 Feed Item 的發佈時間（M3 票 14）。
    #: 規劃時拿它比換算出的那一集的播出日（`parser.airing`）。來源沒給、或這一筆不是從來源送的
    #: （認領、重新入庫）是 `None`。
    published_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    added_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    imported_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    #: 上一次在 qBittorrent 的清單裡看到它。torrent 從客戶端消失時要拿它說「最後一次是何時」。
    last_seen_in_client_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)


class JobFile(Base):
    """Job 內容裡的一個檔案（plan §2.3、§4.1）。

    由票 10 的 `metadata_ready` 建立——`torrents/files` 回得出清單的那一刻。這一票只建表，
    因為送單當下 qBittorrent 還沒有 metadata（磁力連結尤其明顯）。
    """

    __tablename__ = "job_files"
    __table_args__ = (
        UniqueConstraint("job_hash", "rel_path", name="uq_job_files_job_hash_rel_path"),
        Index("ix_job_files_job_hash", "job_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_hash: Mapped[str] = mapped_column(ForeignKey("jobs.hash", ondelete="CASCADE"))
    #: 相對 `save_path`（brief §20.7 實測：`torrents/files[].name` 就是這個）。
    rel_path: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(default=0)
    #: qBittorrent 的檔案優先序。`0` 是「不下載」，那種檔案不進 Plan（brief §5.1）。
    priority: Mapped[int] = mapped_column(default=1)
    kind: Mapped[FileKind | None] = mapped_column(enum_column(FileKind), default=None)
    mediainfo_json: Mapped[dict[str, Any] | None] = mapped_column(JsonText, default=None)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
