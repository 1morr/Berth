"""RSS：Feed、RSS Series、Feed Item（plan §2.4、brief §15、`CONTEXT.md` 的 RSS 一節）。

三張表的關係是 **Feed 長出 Item、Item 長出（或找到）Series**，而 Series 不屬於任何一個 Feed：
它是「一部作品 × 一個來源」（Mikan 的番組 × 字幕組），同一個組合出現在兩個 Feed 裡是同一個
Series。所以刪 Feed 連它的 Item 一起刪（`CASCADE`），Series 與它的綁定留著
（`.scratch/m3/rss-shape.md` §4）。

欄位只建用得到的（M3 票 08 起）：排除條件（`exclude_json`）與跳過理由（`skip_json`）在票 10；
第一輪預覽（`primed_at`，票 11）、第一批確認（`confirmed`，票 13）、補舊集（`backfilled_at`，
票 12）等到用它的那一票再加。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import FeedItemStatus, FeedKind
from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, enum_column, utcnow

#: 一個 Feed 預設多久輪詢一次（plan §3.2）。
DEFAULT_INTERVAL_SEC = 15 * 60


class RssFeed(Base):
    """一個 RSS 來源（`CONTEXT.md` 的 Feed）。"""

    __tablename__ = "rss_feeds"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    #: 使用者貼上的整條網址，原樣。Mikan 的聚合 feed 帶著 token——它就是憑證，
    #: 所以 `/rss/*` 只有 admin。
    url: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[FeedKind] = mapped_column(enum_column(FeedKind))
    interval_sec: Mapped[int] = mapped_column(default=DEFAULT_INTERVAL_SEC)
    last_polled_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    #: 上一輪失敗的原文（英文）。成功的那一輪清空。
    last_error: Mapped[str] = mapped_column(Text, default="")
    #: 這一層的排除條件（`parser.exclusion` 的格式），與全域、RSS Series 那兩層取聯集（brief §15）。
    exclude_json: Mapped[list[str]] = mapped_column(JsonText, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class RssSeries(Base):
    """一部作品 × 一個來源（`CONTEXT.md` 的 RSS Series）。`media_id` 是 `NULL` 就是待綁定。"""

    __tablename__ = "rss_series"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Mikan 是 `mikan:<番組 id>:<字幕組 id>`（plan §2.4）。其他來源在票 11 定。
    key: Mapped[str] = mapped_column(Text, unique=True)
    mikan_bangumi_id: Mapped[int | None] = mapped_column(default=None)
    mikan_subgroup_id: Mapped[int | None] = mapped_column(default=None)
    #: 長出它的那一筆 Item 的標題，原樣。待綁定清單上認得出這是哪一部、哪一組的就是它。
    title_raw: Mapped[str] = mapped_column(Text)
    media_id: Mapped[str | None] = mapped_column(
        ForeignKey("media.id", ondelete="SET NULL"), default=None
    )
    route_id: Mapped[int | None] = mapped_column(
        ForeignKey("routes.id", ondelete="SET NULL"), default=None
    )
    #: 規劃時交給解析器的季號與集號偏移（brief §15、plan §4.3）。改正與重算在票 13。
    season: Mapped[int | None] = mapped_column(default=None)
    episode_offset: Mapped[int | None] = mapped_column(default=None)
    #: 誰綁的：`system`（票 09 的自動綁定）或使用者 id（`events.actor` 的形狀）。沒綁是空字串。
    bound_by: Mapped[str] = mapped_column(Text, default="")
    #: 第一次見到它時自動綁定查到的結果（票 09）：`domain.BindReason` 的 JSON。綁上了是依據，
    #: 留在待綁定是為什麼。`None` 是沒查過（票 09 之前長出來的）。
    reasons_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonText, default=None)
    #: 給人一鍵選的作品 id（`tv:<tmdb>`），照搜尋結果的順序。
    candidates_json: Mapped[list[str] | None] = mapped_column(JsonText, default=None)
    #: 這一層的排除條件（與 Feed 那一欄同一個格式）。
    exclude_json: Mapped[list[str]] = mapped_column(JsonText, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class RssItem(Base):
    """Feed 裡的一筆（`CONTEXT.md` 的 Feed Item）。"""

    __tablename__ = "rss_items"
    __table_args__ = (
        UniqueConstraint("feed_id", "guid", name="uq_rss_items_feed_id_guid"),
        Index("ix_rss_items_series_id", "series_id"),
        Index("ix_rss_items_seen_at", "seen_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    feed_id: Mapped[int] = mapped_column(ForeignKey("rss_feeds.id", ondelete="CASCADE"))
    #: 同一個 Feed 裡的去重鍵（plan §8.5）。Mikan 是 info hash——它的 `<guid>` 是標題，改標題就變。
    guid: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    #: 單集頁。
    link: Mapped[str] = mapped_column(Text, default="")
    torrent_url: Mapped[str] = mapped_column(Text, default="")
    #: 小寫十六進位；來源不報時空字串（acg.rip，票 11）。
    info_hash: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    seen_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("rss_series.id", ondelete="SET NULL"), default=None
    )
    #: 送出去之後的那一筆。弱引用：刪 Job 不回頭改這一列（與帳本的 `job_hash` 同一個理由）。
    job_hash: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[FeedItemStatus] = mapped_column(
        enum_column(FeedItemStatus), default=FeedItemStatus.UNBOUND
    )
    #: 上一次送單被拒的原文（`reason: detail`）。送成了清空。
    error: Mapped[str] = mapped_column(Text, default="")
    #: `excluded` / `duplicate` 的那一條理由（`domain.SkipReason` 的 JSON）；其他狀態是 `None`。
    skip_json: Mapped[dict[str, Any] | None] = mapped_column(JsonText, default=None)
