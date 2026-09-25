"""RSS Series 是哪一部作品：自動綁定的規則（brief §15「綁定」、§6.4 第 2 點、§6.5、M3 票 09）。

線索是 Mikan 番組頁的中文名與「放送开始」，加上長出這個 Series 的那一筆發佈名的**標題骨幹**；
候選是呼叫端拿線索去 TMDB 搜、讀回來的快照（這一層沒有 IO，同 `ParseContext.candidates`）。

**有把握**是 brief §6.5「標題 + 年份精確命中」在 RSS 這一頭的樣子，三條同時成立才算：

1. 某一條線索正規化後與 TMDB 的某個名字**相等**（`normalize_title`，與解析器同一支）。「包含」不算：
   續作名常常包住前作名（`某某 第二季` 包住 `某某`），那正是綁錯的樣子。
2. Mikan 寫的開播日期落在那部作品**某一季的首播**前後 `PREMIERE_WINDOW` 之內（電影看上映日）。
   它就是「年份」那一半，而且比年份細：同名重拍、同一部的第二季都分得開。
3. 這樣的作品**只有一部**。

其餘留在待綁定，理由碼各不相同；認得出標題的那幾部當成候選，畫面列出來讓人一鍵選。
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from berth.domain import BindReason, MediaKind, MediaSnapshot, because
from berth.domain import BindReasonCode as Code
from berth.parser.title import normalize_title

#: 開播日期要落在 TMDB 那一季首播的前後幾天內。起點 14 天：Mikan 寫的多半是日本首播，TMDB 也是，
#: 差距來自時區與先行上映；對岸平台晚幾天開播時 Mikan 偶爾寫它的日期。實測 10 部差 0–1 天
#: （`docs/research/rss-sources.md` §2.8）。
PREMIERE_WINDOW = timedelta(days=14)

#: 一個新 Series 最多搜幾次 TMDB。番組名、骨幹的最後一段（英文或羅馬字）通常就夠了。
MAX_SEARCHES = 3

#: 開頭的組名 `[喵萌奶茶屋&LoliHouse] `（可能不只一段）。
_GROUPS = re.compile(r"^\s*(?:\[[^\]]*\]\s*)+")
#: ` - 12`：集號以後都不是標題。
_EPISODE = re.compile(r"\s+-\s+\d")


@dataclass(frozen=True, slots=True)
class SeriesClues:
    """認一個 RSS Series 的線索。"""

    #: Mikan 番組頁的中文名。讀不到是空字串。
    title: str
    #: 「放送开始」。讀不到是 `None`——那時年份無從確認，一律不自動綁。
    premiere: date | None
    #: 長出這個 Series 的那一筆 Feed Item 的標題。
    release_title: str


@dataclass(frozen=True, slots=True)
class BindVerdict:
    """判定結果。`media` 不是 `None` 就是有把握的那一部。"""

    media: MediaSnapshot | None
    #: 畫面上給人一鍵選的那幾部：有把握時就是 `media` 自己，同名不同年時是標題相同的那幾部。
    candidates: tuple[MediaSnapshot, ...]
    #: 有把握時是依據，沒有時是為什麼。
    reasons: tuple[BindReason, ...]


def skeleton(release_title: str) -> tuple[str, ...]:
    """發佈名的標題骨幹：去掉開頭的組名與 ` - 集號` 之後的一切，` / ` 分開的每一個名字都留。

    `[組名] 中文名 / 英文或羅馬字名 - 12 [tags…]` 是字幕組最常見的寫法（`web/src/rss/searchTerm.ts`
    挑的是最後一段，這裡每一段都要：哪一段與 TMDB 相等事先不知道）。
    """
    name = _EPISODE.split(_GROUPS.sub("", release_title), maxsplit=1)[0]
    return tuple(part for part in (piece.strip() for piece in name.split(" / ")) if part)


def search_terms(clues: SeriesClues) -> tuple[str, ...]:
    """拿去搜 TMDB 的字：番組名，接著骨幹從最後一段往前（英文或羅馬字多半在最後）。最多三個。"""
    wanted = [clues.title, *reversed(skeleton(clues.release_title))]
    seen: dict[str, str] = {}
    for term in wanted:
        key = normalize_title(term)
        if key and key not in seen:
            seen[key] = term.strip()
    return tuple(seen.values())[:MAX_SEARCHES]


def could_be(kind: MediaKind, year: int | None, premiere: date | None) -> bool:
    """只憑搜尋結果的年份，這部作品還有沒有可能是它。排除掉的不必去讀詳情（一部 3 + 季數個請求）。

    劇集的年份是第一季的，後面幾季只會更晚，所以只排除**晚於**開播日（加窗口）才開始的；電影就是
    那一年，前後差一年。只有較晚的同名重拍時因此是 `no_candidate` 而不是 `premiere_far`——
    它不可能是這一部，不必列成候選。
    """
    if premiere is None or year is None:
        return True
    if kind is MediaKind.MOVIE:
        return abs(year - premiere.year) <= 1
    return year <= (premiere + PREMIERE_WINDOW).year


def judge(clues: SeriesClues, candidates: Sequence[MediaSnapshot]) -> BindVerdict:
    """線索 + 搜回來的作品 → 綁哪一部，或為什麼不綁。"""
    named = [(shot, found) for shot in candidates if (found := _equal_title(clues, shot))]
    if not named:
        return BindVerdict(media=None, candidates=(), reasons=(because(Code.NO_CANDIDATE),))
    titled = tuple(_unique(shot for shot, _ in named))
    if clues.premiere is None:
        return BindVerdict(media=None, candidates=titled, reasons=(because(Code.NO_PREMIERE),))

    near = [
        (shot, title_reason, dated)
        for shot, title_reason in named
        if (dated := _premiere_near(clues.premiere, shot)) is not None
    ]
    fitting = tuple(_unique(shot for shot, _, _ in near))
    if not fitting:
        first = titled[0]
        return BindVerdict(
            media=None,
            candidates=titled,
            reasons=(
                because(
                    Code.PREMIERE_FAR,
                    title=first.title_en,
                    premiere=clues.premiere.isoformat(),
                ),
            ),
        )
    if len(fitting) > 1:
        return BindVerdict(
            media=None,
            candidates=fitting,
            reasons=(because(Code.SEVERAL_CANDIDATES, number=len(fitting)),),
        )
    shot, title_reason, (season, first_aired) = near[0]
    date_reason = (
        because(
            Code.RELEASE_NEAR, premiere=clues.premiere.isoformat(), aired=first_aired.isoformat()
        )
        if shot.kind is MediaKind.MOVIE
        else because(
            Code.PREMIERE_NEAR,
            premiere=clues.premiere.isoformat(),
            season=season,
            aired=first_aired.isoformat(),
        )
    )
    return BindVerdict(media=shot, candidates=(shot,), reasons=(title_reason, date_reason))


def _equal_title(clues: SeriesClues, shot: MediaSnapshot) -> BindReason | None:
    """哪一條線索與這部作品的哪一個名字相等。沒有是 `None`。"""
    known = [
        (normalize_title(name), name)
        for name in (shot.title, shot.title_en, shot.title_original, *shot.titles)
    ]
    for clue in (clues.title, *skeleton(clues.release_title)):
        target = normalize_title(clue)
        if not target:
            continue
        for key, name in known:
            if key == target:
                return because(Code.TITLE_EQUAL, clue=clue.strip(), title=name)
    return None


def _premiere_near(premiere: date, shot: MediaSnapshot) -> tuple[int, date] | None:
    """離 `premiere` 最近、又在窗口內的那一季（季號, 首播日）。電影只有上映日，季號記 0。"""
    if shot.kind is MediaKind.MOVIE:
        dated = [(0, shot.first_air_date)]
    else:
        dated = [(row.season_number, row.air_date) for row in shot.seasons if row.season_number > 0]
        if not dated:
            dated = [(1, shot.first_air_date)]
    near = [
        (abs(aired - premiere), number, aired)
        for number, aired in dated
        if aired is not None and abs(aired - premiere) <= PREMIERE_WINDOW
    ]
    if not near:
        return None
    _, number, aired = min(near)
    return number, aired


def _unique(shots: Iterable[MediaSnapshot]) -> list[MediaSnapshot]:
    """同一部作品（kind + id）只留第一次出現的那一份，順序照搜尋結果。"""
    seen: set[tuple[MediaKind, int]] = set()
    kept: list[MediaSnapshot] = []
    for shot in shots:
        key = (shot.kind, shot.tmdb_id)
        if key not in seen:
            seen.add(key)
            kept.append(shot)
    return kept
