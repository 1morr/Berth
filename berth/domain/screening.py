"""Feed Item 為什麼沒有送出去：排除條件與去重（brief §15「全部接受，只排除」「處理」、M3 票 10）。

**形狀照 `BindReason`**（`domain/binding.py`）：封閉集合的 code 加參數，句子只在前端（`rss.skip.*`，
zh-Hant 與 en 各一份）；參數是規則原文、檔名這種**不翻譯**的事實。排除與去重擋下的都不是錯誤——
`/rss` 的 Feed Item 清單照它說出「這一筆為什麼沒下載」。

排除條件分三層（全域、Feed、RSS Series），三層取聯集；是哪一層擋的由 code 說，參數只有那一條規則。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class SkipCode(StrEnum):
    """一筆 Feed Item 被擋下的原因。"""

    # --- 排除（`excluded`）-------------------------------------------------------------
    #: 預設的那一條：不是單集（合集、區間、季包；`release_kind != single`）。
    NOT_SINGLE = "not_single"
    #: 全域的排除條件 `{rule}` 對上了標題。
    GLOBAL_RULE = "global_rule"
    #: 這個 Feed 的排除條件 `{rule}` 對上了標題。
    FEED_RULE = "feed_rule"
    #: 這個 RSS Series 的排除條件 `{rule}` 對上了標題。
    SERIES_RULE = "series_rule"

    # --- 重複（`duplicate`）------------------------------------------------------------
    #: 同一個 torrent（info hash）已經送過：另一個 Feed、或手動送單。那一筆 Job 在 Item 的
    #: `job_hash`（Job 連紀錄一起清掉了的是空字串）。
    SAME_TORRENT = "same_torrent"
    #: 帳本已有同一部作品、同一季集、同一組 Tags 的那一份（`{known}` 是媒體庫裡的檔名）。
    IN_LIBRARY = "in_library"


_C = SkipCode

#: 每一種理由帶哪幾個參數。前端兩份語言的 `rss.skip.*` 由 `tests/unit/test_skip_reasons.py`
#: 逐句比對。
#: **沒有叫 `count` 的鍵**（i18next 會去找單複數那一對鍵）。
SKIP_PARAMS: dict[SkipCode, frozenset[str]] = {
    _C.NOT_SINGLE: frozenset(),
    _C.GLOBAL_RULE: frozenset({"rule"}),
    _C.FEED_RULE: frozenset({"rule"}),
    _C.SERIES_RULE: frozenset({"rule"}),
    _C.SAME_TORRENT: frozenset(),
    _C.IN_LIBRARY: frozenset({"known"}),
}


class SkipReason(BaseModel):
    """一條跳過理由：`code` 加它的參數。"""

    model_config = ConfigDict(frozen=True)

    code: SkipCode
    params: dict[str, str | int] = {}


def skipped(code: SkipCode, **params: str | int) -> SkipReason:
    """組一條跳過理由。**參數要剛好是 `SKIP_PARAMS` 那幾個**（同 `because()`）。"""
    if frozenset(params) != SKIP_PARAMS[code]:
        raise ValueError(f"{code.value} takes {sorted(SKIP_PARAMS[code])}, got {sorted(params)}")
    return SkipReason(code=code, params=params)
