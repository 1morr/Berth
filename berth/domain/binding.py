"""RSS Series 自動綁定的理由（brief §15「綁定」、§6.5、M3 票 09）。

**形狀照解析器的 `reasons`**（`domain/parser.py` 的 `ReasonCode` / `why`）：封閉集合的 code 加參數，
句子只在前端（`rss.grounds.*`，zh-Hant 與 en 各一份）；參數是標題、日期、Route 名這種**不翻譯**的
事實。一個 RSS Series 手上的理由有兩種讀法：

- 自動綁上了：那幾條就是**依據**（標題相同、開播日期對得上、只有一條 Route 收得下），Job 的時間線
  照它說出「為什麼是這一部」。
- 留在待綁定：那幾條是**為什麼沒綁**（沒有候選、同名不同年、兩個以上、Route 不只一條……），
  待綁定清單照它說話、列出候選。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class BindReasonCode(StrEnum):
    """一條綁定理由是哪一種。"""

    # --- 依據（綁上了） ---------------------------------------------------------------
    #: `{clue}`（Mikan 的番組名或發佈名的標題骨幹）正規化後與 TMDB 的 `{title}` 相同。
    TITLE_EQUAL = "title_equal"
    #: Mikan 寫 `{premiere}` 開播，TMDB 的第 `{season}` 季 `{aired}` 首播。
    PREMIERE_NEAR = "premiere_near"
    #: 電影那一種：Mikan 寫 `{premiere}`，TMDB 的上映日是 `{aired}`。
    RELEASE_NEAR = "release_near"
    #: 收得下這種作品的啟用中 Route 只有 `{route}`。
    ONLY_ROUTE = "only_route"
    #: 收得下這種作品的 Route 不只一條，長出它的 Feed 說送進 `{route}`（M3 票 21）。
    FEED_ROUTE = "feed_route"

    # --- 為什麼沒綁 -------------------------------------------------------------------
    #: TMDB 搜不到標題相同的作品。
    NO_CANDIDATE = "no_candidate"
    #: 標題相同的是 `{title}`，但 Mikan 寫 `{premiere}` 開播，TMDB 沒有一季在那附近首播
    #: （同名不同年）。
    PREMIERE_FAR = "premiere_far"
    #: 標題相同、開播日期也對得上的有 `{number}` 部。
    SEVERAL_CANDIDATES = "several_candidates"
    #: Mikan 的番組頁讀不到開播日期，年份無從確認。
    NO_PREMIERE = "no_premiere"
    #: Nyaa、acg.rip 這種來源沒有番組頁，開播日期無從確認：候選只從標題來，一律留給人（票 11）。
    NO_SHOW_PAGE = "no_show_page"
    #: 番組頁或 TMDB 這一次查不到（`{detail}` 是原文）。
    LOOKUP_FAILED = "lookup_failed"
    #: `{site}` 這一小時的請求預算用完了，番組頁下一輪再讀（M3 票 20）。不是查不到：
    #: 只有它會在之後的輪詢裡重認。
    LOOKUP_DEFERRED = "lookup_deferred"
    #: 作品認出來了，但收得下它的 Route 有好幾條（`{routes}`），要人選。
    ROUTE_AMBIGUOUS = "route_ambiguous"
    #: 作品認出來了，但沒有一條啟用中的 Route 收得下它。
    NO_ROUTE = "no_route"


_C = BindReasonCode

#: 每一種理由帶哪幾個參數。前端兩份語言的 `rss.grounds.*` 由 `tests/unit/test_bind_reasons.py`
#: 逐句比對。**沒有叫 `count` 的鍵**：i18next 看到它就去找單複數那一對鍵。
BIND_PARAMS: dict[BindReasonCode, frozenset[str]] = {
    _C.TITLE_EQUAL: frozenset({"clue", "title"}),
    _C.PREMIERE_NEAR: frozenset({"premiere", "season", "aired"}),
    _C.RELEASE_NEAR: frozenset({"premiere", "aired"}),
    _C.ONLY_ROUTE: frozenset({"route"}),
    _C.FEED_ROUTE: frozenset({"route"}),
    _C.NO_CANDIDATE: frozenset(),
    _C.PREMIERE_FAR: frozenset({"title", "premiere"}),
    _C.SEVERAL_CANDIDATES: frozenset({"number"}),
    _C.NO_PREMIERE: frozenset(),
    _C.NO_SHOW_PAGE: frozenset(),
    _C.LOOKUP_FAILED: frozenset({"detail"}),
    _C.LOOKUP_DEFERRED: frozenset({"site"}),
    _C.ROUTE_AMBIGUOUS: frozenset({"routes"}),
    _C.NO_ROUTE: frozenset(),
}


class BindReason(BaseModel):
    """一條綁定理由：`code` 加它的參數。"""

    model_config = ConfigDict(frozen=True)

    code: BindReasonCode
    params: dict[str, str | int] = {}


def because(code: BindReasonCode, **params: str | int) -> BindReason:
    """組一條綁定理由。**參數要剛好是 `BIND_PARAMS` 那幾個**（同 `why()`）：少一個，畫面就印出
    佔位符。"""
    if frozenset(params) != BIND_PARAMS[code]:
        raise ValueError(f"{code.value} takes {sorted(BIND_PARAMS[code])}, got {sorted(params)}")
    return BindReason(code=code, params=params)
