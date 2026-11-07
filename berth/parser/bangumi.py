"""一部作品在 Mikan 上是哪一個番組（M5.6 票 08）。

`parser.binding.judge` 讀的是反方向（番組 → 作品）；這裡是作品 → 番組，用的是同一個「有把握」
（brief §15〈綁定〉、§6.5）：

- 名字正規化、拆掉季名之後**相等**。「包含」不算：續作名常常包住前作名，那正是挑錯的樣子。
- 番組頁的「放送开始」落在作品首播日（`first_air_date`）前後 `PREMIERE_WINDOW` 內。同名不同年、
  Mikan 另開一個番組的第二個 cour 都由它分開。
- 兩個命中一樣近就是不知道（`None`）；作品沒有首播日時只在名字恰好命中一個時給它。

**與 `binding.judge` 的差別**：作品在 Berth 手上是一列（整個系列），訂閱問的是「這部作品的番組」，
所以只比 `first_air_date`；`binding` 那一頭拿得到發佈名的季名，才比各季的播出期間（`_dated`）。
兩邊不要互相改寫成對方：換過去會讓其中一邊少一種線索。

這一層沒有 IO：候選是呼叫端讀回來的番組頁（`BangumiCandidate`），搜尋與讀頁在
`services.bangumi` 那一邊。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from berth.domain import MediaSnapshot
from berth.parser.binding import PREMIERE_WINDOW
from berth.parser.seasons import split_season
from berth.parser.title import normalize_title

#: 名字裡有沒有 CJK：排序用（搜尋的請求數有限，先搜命中率高的）。
_cjk = re.compile(r"[぀-ヿ㐀-鿿豈-﫿]")


@dataclass(frozen=True, slots=True)
class BangumiCandidate:
    """Mikan 搜尋頁上的一個番組，加上番組頁讀回來的開播日。"""

    id: int
    #: 番組頁的中文名（多半是簡體）。
    title: str
    #: 番組頁的「放送开始」。讀不到是 `None`。
    premiere: date | None


def names(snapshot: MediaSnapshot) -> tuple[str, ...]:
    """拿去搜 Mikan 的名字，簡體中文優先（番組名多半是它），同一個名字只留一次。

    比對的是拆掉季名之後的形式：`與妳相戀到生命盡頭 第二季` 與本名是同一次搜尋。CJK 的名字排在
    英文前面：Mikan 的番組名是中文或日文，每次搜尋都要真的打一次站上的搜尋頁（約 1.5 秒），先搜
    命中率高的那幾個。
    """
    everywhere = [snapshot.title, snapshot.title_original, *snapshot.titles]
    wanted = [
        snapshot.title_zh_cn,
        *(name for name in everywhere if _cjk.search(name)),
        *(name for name in everywhere if not _cjk.search(name)),
        snapshot.title_en,
    ]
    seen: dict[str, str] = {}
    for name in wanted:
        bare = _bare(name)
        key = normalize_title(bare)
        if key and key not in seen:
            seen[key] = bare
    return tuple(seen.values())


def same_work(snapshot: MediaSnapshot, title: str) -> bool:
    """番組名是不是這部作品的某個名字（拆掉季名、正規化後相等）。"""
    wanted = normalize_title(_bare(title))
    return bool(wanted) and any(wanted == normalize_title(name) for name in names(snapshot))


def choose(
    snapshot: MediaSnapshot, candidates: Sequence[BangumiCandidate]
) -> BangumiCandidate | None:
    """這部作品在候選裡的番組；不知道是哪一個（含找不到）是 `None`。

    呼叫端可以先用 `same_work` 篩掉不必讀頁的番組；這裡再篩一次，規則只有一份。
    """
    matched = [candidate for candidate in candidates if same_work(snapshot, candidate.title)]
    if not matched:
        return None
    if snapshot.first_air_date is None:
        return matched[0] if len(matched) == 1 else None
    gaps = [
        (abs(candidate.premiere - snapshot.first_air_date), candidate)
        for candidate in matched
        if candidate.premiere is not None
    ]
    near = [(gap, candidate) for gap, candidate in gaps if gap <= PREMIERE_WINDOW]
    if near:
        closest = min(gap for gap, _ in near)
        winners = [candidate for gap, candidate in near if gap == closest]
        return winners[0] if len(winners) == 1 else None
    # 沒有開播日落進窗口：唯一一個讀不到開播日的才用（無法確認，但也沒有相反的證據）。
    unknown = [candidate for candidate in matched if candidate.premiere is None]
    return unknown[0] if len(unknown) == 1 and len(matched) == 1 else None


def _bare(name: str) -> str:
    """拿掉季名的名字（`parser.seasons`）。"""
    return split_season(name)[0].strip()
