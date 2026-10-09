"""文字裡網址的 query 值遮成 `***`（M4 票 76）。

log 與錯誤訊息都會帶網址，而網址的 query 常常就是憑證：Mikan 的聚合 feed 只靠 `?token=` 認人、
TMDB 的 v3 key 走 `?api_key=`、私有站的 RSS 帶 passkey。**遮的是每一個值、不認參數名**：
私有站的參數名各家不同，列一份名單的話第一個沒列到的站就漏了。參數名留著，讀 log 的人還看得出
那是哪一種請求。

住在 `berth/` 的根而不是某一層底下：`logs`（每一行 log）與 `adapters.http`（每一個錯誤訊息）
都要用它，而它只 import 標準庫。
"""

from __future__ import annotations

import re

MASK = "***"

#: `?` 之後到這一段文字結束（空白、引號、角括號）或 fragment 為止。`?` 前面要緊貼著字：
#: 散文裡的「reachable? no」不是網址。
_QUERY = re.compile(r"(?<=[^\s\"'<>?])\?([^\s\"'<>#]+)")

#: 緊接在網址後面、不屬於它的標點：`HttpSession` 的錯誤訊息是「GET <url>: connection refused」。
_TRAILING = re.compile(r"[:,.;)\]]+$")


def redact_queries(text: str) -> str:
    """把 `text` 裡每一個網址的 query 值換成 `***`；沒有 query 的網址原樣留著。"""
    return _QUERY.sub(_mask, text)


def _mask(match: re.Match[str]) -> str:
    query = match.group(1)
    trailing = _TRAILING.search(query)
    tail = trailing.group(0) if trailing else ""
    body = query[: len(query) - len(tail)]
    return "?" + "&".join(_mask_segment(segment) for segment in body.split("&")) + tail


def _mask_segment(segment: str) -> str:
    key, equals, value = segment.partition("=")
    if not equals:
        # 沒有等號的段落整段就是值（`?<passkey>`）。
        return MASK if segment else segment
    return f"{key}={MASK}" if value else segment


__all__ = ["MASK", "redact_queries"]
