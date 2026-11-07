"""集數的寫法：連續的集收成一段，多集檔算它蓋到的每一集。

給模型與畫面看的集數範圍只有這一種寫法（`{"1": "1-5, 7-12"}`）：媒體庫的命中
（`inventory.find_in_library`）與作品的集表、對不上的集（`agent_tools`）都用它。編號本身**不**在這裡
產生或換算——那是 Jellyfin 或 TMDB 的事，這裡只排版。
"""

from __future__ import annotations

from collections.abc import Iterable


def number_ranges(numbers: Iterable[int]) -> str:
    """`[1, 2, 3, 5]` → `"1-3, 5"`；重複的只算一次，空的給空字串。"""
    ordered = sorted(set(numbers))
    if not ordered:
        return ""
    spans: list[str] = []
    start = previous = ordered[0]
    for number in [*ordered[1:], None]:
        if number is not None and number == previous + 1:
            previous = number
            continue
        spans.append(str(start) if start == previous else f"{start}-{previous}")
        if number is not None:
            start = previous = number
    return ", ".join(spans)


def season_ranges(episodes: Iterable[tuple[int, int, int | None]]) -> dict[str, str]:
    """`(季號, 第一集, 最後一集或 None)` → `{"1": "1-5, 7-12"}`：一季一個字串，多集檔算它蓋到的
    每一集（`end` 比 `start` 小時照 `start` 算）。沒有季號或集號的集由呼叫端先濾掉。"""
    by_season: dict[str, list[int]] = {}
    for season, start, end in episodes:
        last = end if end is not None and end >= start else start
        by_season.setdefault(str(season), []).extend(range(start, last + 1))
    return {season: number_ranges(numbers) for season, numbers in by_season.items()}
