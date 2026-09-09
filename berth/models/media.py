"""Media 與 TMDB 快取（plan §2.2）。

兩張表的分工：`media` 是**被追蹤的作品**——它的資料夾名一凍結就進了檔案系統與帳本，
所以那一列要活得跟檔案一樣久；`tmdb_cache` 是**探索與搜尋的短期快取**，一小時就過期，
整列丟掉不會失去任何東西（plan §8.3）。混成一張表會讓「刪得掉的」與「刪不得的」同住。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import MediaKind
from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, enum_column, utcnow


def media_id(kind: MediaKind, tmdb_id: int) -> str:
    """`media.id`：`tv:1234` / `movie:1234`（plan §2.2）。

    複合鍵而不是流水號：TMDB id 在劇集與電影兩個命名空間各自編號，`1234` 兩邊都存在。
    """
    return f"{kind.value}:{tmdb_id}"


class MediaCard(BaseModel):
    """一張作品卡：探索、搜尋與（票 04 起）媒體庫牆上的一格。

    也是 `tmdb_cache.value_json` 存的形狀——快取存的就是畫面要的那份東西，
    存 TMDB 的原始 payload 只會讓「解析」發生兩次而且兩次可能不一樣。
    """

    model_config = ConfigDict(extra="ignore")

    tmdb_id: int
    kind: MediaKind
    #: 顯示用標題：`zh-TW` 那一輪有值就用它，沒有就落回英文（plan §8.3）。
    title: str
    #: 英文標題。檔名與比對用的那一個（brief §7.5、§5）；與 `title` 不同時卡片兩個都顯示。
    title_en: str
    #: 首播 / 上映年。TMDB 未定檔時是空字串，那時這裡是 `None`。
    year: int | None = None
    #: 完整的海報網址（`configuration` 的 secure base + 尺寸 + 路徑）。沒有海報時是空字串。
    poster_url: str = ""

    @property
    def id(self) -> str:
        return media_id(self.kind, self.tmdb_id)


def dump_cards(cards: Sequence[MediaCard]) -> list[dict[str, Any]]:
    """`tmdb_cache.value_json` 的序列化。`*_json` 的兩個方向都住在 `models/`（plan §2）。"""
    return [card.model_dump(mode="json") for card in cards]


def load_cards(value: Any) -> tuple[MediaCard, ...]:
    """讀回來。上一版寫下的形狀少一個欄位時，`extra="ignore"` 與預設值讓它仍然解得開。"""
    if not isinstance(value, Iterable) or isinstance(value, str | bytes | dict):
        return ()
    return tuple(MediaCard.model_validate(row) for row in value)


class Media(Base):
    """一部被追蹤的作品（plan §2.2）。

    只有 track 過的作品才有這一列——探索頁上的其他幾百部只是 `tmdb_cache` 裡的一格。
    """

    __tablename__ = "media"

    #: `tv:<tmdb>` / `movie:<tmdb>`，見 `media_id()`。
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tmdb_id: Mapped[int]
    kind: Mapped[MediaKind] = mapped_column(enum_column(MediaKind))
    title_en: Mapped[str] = mapped_column(Text)
    title_original: Mapped[str] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(default=None)
    #: 第一次 track 時決定並**凍結**：TMDB 之後改名不會動它，改名是顯式動作（brief §4.5）。
    folder_name: Mapped[str] = mapped_column(Text)
    tracked: Mapped[bool] = mapped_column(default=False)
    #: 送單時預選的 Route。Route 被刪掉時只是回到「沒有預選」，不該連 Media 一起帶走。
    default_route_id: Mapped[int | None] = mapped_column(
        ForeignKey("routes.id", ondelete="SET NULL"), default=None
    )
    #: 季集結構、各季 `name`、別名與翻譯（plan §2.2、§4.3）。票 04 開始寫。
    tmdb_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JsonText, default=None)
    tmdb_fetched_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)


class TmdbCache(Base):
    """探索與搜尋的短期快取（plan §2.2、§8.3：一小時）。

    Media 快照**不走這裡**——它有自己的 24 小時規則且存在 `media.tmdb_snapshot_json`。
    """

    __tablename__ = "tmdb_cache"

    #: 查詢的完整識別，見 `services/discover.py` 的 `cache_key()`。
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value_json: Mapped[Any] = mapped_column(JsonText)
    fetched_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
