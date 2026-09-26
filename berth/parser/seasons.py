"""季名的寫法（plan §4.4、M4 票 14）：一份規則，三個讀者。

`cjk` 從發佈名撈季號、`structure` 讀資料夾名（整個資料夾名就是季名才算）、`binding` 把季名從
搜尋詞拆出來（TMDB 的作品名不帶季名：「Re：从零开始的异世界生活 第四季」搜不到，拿掉就找到，
2026-09-26 實測）。
寫法各寫一份的話，三邊遲早分岔，所以字串在這裡，各自照需要加錨點或邊界再編譯。
"""

from __future__ import annotations

import re

#: 中文數字。只到十二——季號不會更大，而更長的表會開始誤吃標題裡的字。
CN_DIGITS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
    "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12,
}  # fmt: skip

#: `第N季` / `第N期`，中文或阿拉伯數字。
SEASON_CN = r"第\s*([0-9]+|[一二三四五六七八九十]{1,3})\s*[季期]"

#: `Season 2`、`Season.2`、`S2`、`S02`。`S` 後面要接數字，`Subs` 不算。不分大小寫。
SEASON_LATIN = r"(?:season[\s._-]*|s)([0-9]{1,2})"

#: `2nd Season`、`3rd Season`、`1st Season`。不分大小寫。
SEASON_ORDINAL = r"([0-9]{1,2})(?:st|nd|rd|th)[\s._-]*season"

#: 名字裡的季名：兩側不接英數（`SS2`、`Seasons` 不算），中文那一種本身就有 `第` 與 `季` 收邊。
_IN_NAME = re.compile(
    rf"(?<![A-Za-z0-9])(?:{SEASON_LATIN}|{SEASON_ORDINAL})(?![A-Za-z0-9])|{SEASON_CN}",
    re.IGNORECASE,
)


def numeral(raw: str) -> int | None:
    """`4` / `四` → 4：季號與 `第N部分` 的分部號都這樣寫。認不得是 `None`。"""
    return int(raw) if raw.isdigit() else CN_DIGITS.get(raw)


def split_season(name: str) -> tuple[str, int | None]:
    """名字 → （拿掉季名之後的名字, 季號）。沒有季名時原樣回來、季號 `None`。

    只拿第一個季名：`第四季` 與 `4th Season` 同時寫在一個名字裡時說的是同一件事，而一個名字裡
    寫兩個不同季號的沒見過。
    """
    found = _IN_NAME.search(name)
    if found is None:
        return name, None
    raw = next(group for group in found.groups() if group is not None)
    rest = " ".join(f"{name[: found.start()]} {name[found.end() :]}".split())
    return rest, numeral(raw)
