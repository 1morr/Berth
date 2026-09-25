"""排除條件：規則的格式、比對，與一筆 Feed Item 過不過（brief §15「全部接受，只排除」、M3 票 10）。

**規則格式照 Sonarr 的 release profile**（「Must Not Contain」）：一般字詞是不分大小寫的子字串；
`/…/` 包起來是正則，預設分大小寫、`/…/i` 不分。比對整個標題（`re.search`，不錨定）。
一條規則就是一個字串，三層都存成字串清單。

合集那一條不是規則：它看的是解析器的 `release_kind`（合集、區間、季包的寫法太多，一條關鍵字
寫不完），所以是一個開關，只在全域那一層。
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from functools import lru_cache

from berth.domain import ReleaseKind, SkipCode, SkipReason, skipped
from berth.parser.release import parse_release

#: `/pattern/flags`。旗標只認 `i`。
_REGEX = re.compile(r"^/(?P<body>.*)/(?P<flags>[A-Za-z]*)$", re.DOTALL)

#: 一層規則：這一層擋下時的理由 code，與它的規則。
Layer = tuple[SkipCode, Sequence[str]]

type _Matcher = Callable[[str], bool]


class RuleError(ValueError):
    """一條規則寫壞了。`why` 是原因（英文原文，正則的那一種是 Python `re` 的訊息）。"""

    def __init__(self, rule: str, why: str) -> None:
        super().__init__(f"{rule}: {why}")
        self.rule = rule
        self.why = why


def normalize_rules(rules: Iterable[str]) -> tuple[str, ...]:
    """去掉前後空白、去重（保留順序），每一條都編譯得過才回。壞的那一條丟 `RuleError`。"""
    kept: dict[str, None] = {}
    for raw in rules:
        rule = raw.strip()
        if not rule:
            raise RuleError(rule, "empty rule")
        _compiled(rule)
        kept.setdefault(rule, None)
    return tuple(kept)


def matches(rule: str, title: str) -> bool:
    """這一條規則對不對得上這個標題。規則要先過 `normalize_rules`。"""
    return _compiled(rule)(title)


def screen(title: str, *, not_single: bool, layers: Sequence[Layer]) -> SkipReason | None:
    """一筆 Feed Item 過不過排除條件：過了是 `None`，擋下的回理由。

    三層取聯集，**先對上的那一條是理由**：合集預設排最前，其餘照 `layers` 的順序（全域、Feed、
    RSS Series）。
    """
    if not_single and parse_release(title).release_kind is not ReleaseKind.SINGLE:
        return skipped(SkipCode.NOT_SINGLE)
    for code, rules in layers:
        for rule in rules:
            if matches(rule, title):
                return skipped(code, rule=rule)
    return None


@lru_cache(maxsize=256)
def _compiled(rule: str) -> _Matcher:
    found = _REGEX.match(rule)
    if found is None:
        needle = rule.casefold()
        return lambda title: needle in title.casefold()
    body, flags = found["body"], found["flags"]
    if not body:
        raise RuleError(rule, "empty regex")
    unknown = sorted(set(flags) - {"i"})
    if unknown:
        raise RuleError(rule, f"unknown flag {''.join(unknown)} (only i is supported)")
    try:
        pattern = re.compile(body, re.IGNORECASE if "i" in flags else 0)
    except re.error as exc:
        raise RuleError(rule, str(exc)) from exc
    return lambda title: pattern.search(title) is not None
