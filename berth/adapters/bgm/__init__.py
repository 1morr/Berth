"""Bangumi 番組計劃（bgm.tv）adapter（M5 票 16、plan §8.10、brief §20.3〈動漫資料來源〉）。

只用 `GET /calendar`（本季每日放送表）：中文名與社群評分附票數，推薦新番時補 AniList 沒有的那兩樣。
叫 `bgm` 不叫 `bangumi`：`services/bangumi.py` 是 Mikan 的番組（它的番組名本來就出自 bgm.tv）。

所有欄位在官方 OpenAPI 都不是必填，實測也有缺（`rank` 一半沒有、`rating.score` 有的沒有），
所以這裡每一格都可能是空的。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from berth.adapters.http import ProtocolMismatchError
from berth.config import VERSION

API_URL = "https://api.bgm.tv"

#: Bangumi 要求非瀏覽器的 User-Agent 帶開發者 ID 與應用名，分發的應用帶版本、開源的帶主頁；
#: 預設的（`python-httpx/…`）可能被擋（brief §20.3）。
USER_AGENT = f"1morr/berth/{VERSION} (https://github.com/1morr/Berth)"


@dataclass(frozen=True, slots=True)
class CalendarItem:
    id: int
    #: 原文名（多半是日文）。
    name: str
    #: 中文名；沒有是空字串。
    name_cn: str
    #: `2026-10-04`；沒有是空字串。
    air_date: str
    #: 1 是星期一 … 7 是星期日。
    weekday: int
    #: 1–10；沒人打分時是 `None`。
    score: float | None
    #: 打分的人數。
    votes: int
    rank: int | None


class Bgm(Protocol):
    async def calendar(self) -> list[CalendarItem]:
        """本季每日放送表，七天攤平成一串（星期一在前）。"""
        ...


def parse_calendar(answer: Any) -> list[CalendarItem]:
    if not isinstance(answer, list):
        raise ProtocolMismatchError("GET /calendar: not a list of weekdays")
    items: list[CalendarItem] = []
    for day in answer:
        if not isinstance(day, dict):
            continue
        weekday = (day.get("weekday") or {}).get("id")
        for item in day.get("items") or ():
            if isinstance(item, dict) and isinstance(item.get("id"), int):
                items.append(_item(item, weekday if isinstance(weekday, int) else 0))
    return items


def _item(item: dict[str, Any], weekday: int) -> CalendarItem:
    rating: dict[str, Any] = item["rating"] if isinstance(item.get("rating"), dict) else {}
    score = rating.get("score")
    votes = rating.get("total")
    rank = item.get("rank")
    return CalendarItem(
        id=int(item["id"]),
        name=str(item.get("name") or ""),
        name_cn=str(item.get("name_cn") or ""),
        air_date=str(item.get("air_date") or ""),
        weekday=weekday,
        score=float(score) if isinstance(score, int | float) and score > 0 else None,
        votes=votes if isinstance(votes, int) else 0,
        rank=rank if isinstance(rank, int) and rank > 0 else None,
    )


__all__ = ["API_URL", "USER_AGENT", "Bgm", "CalendarItem", "parse_calendar"]
