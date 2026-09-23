"""標題比對：這一包東西是哪一部作品（plan §4.1、§4.3，brief §6.4 第 2 點）。

Job 帶了 Media 時這一層只是覆核——但那個覆核值得做：追蹤的是 A 而 torrent 是 B 時，
沒有它就會一路自動入庫到錯的作品底下。RSS 與重新入庫沒有上下文，那時它是唯一的辦法。

比對的兩個來源都不可靠，所以兩個都用：guessit 認出來的標題（西方命名準、字幕組格式常常
整個認不出來），以及**整行原文**（中文標題只寫在方括號堆裡時只剩這條路）。
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from berth.domain import ItemReason, MediaSnapshot, ReleaseInfo, why
from berth.domain import ReasonCode as Code

#: 正規化之後留下來的字：字母、數字與 CJK。分隔符、括號、`×`、`:` 全部丟掉——
#: 同一部作品在不同發佈裡的差別幾乎都在這些字元上。
_NOISE = re.compile(r"[^0-9a-z぀-ヿ㐀-䶿一-鿿가-힯]+")

#: 完全相同。
_EXACT = 1.0
#: 一邊包住另一邊（標題出現在整行發佈名裡）。夠當證據，但不夠當「精確命中」。
_CONTAINED = 0.7
#: 大部分的詞都在，但不是同一串字。字幕組用羅馬字而 TMDB 只收官方譯名時就是這樣
#: （`Shingeki no Kyojin Movie The Last Attack` 對 `Attack on Titan: THE LAST ATTACK`）。
_PARTIAL = 0.6
#: 這麼多比例的詞對上就算數。
_MIN_OVERLAP = 0.6
#: 少於這麼多個詞的標題不做詞比對——一個詞的重疊率不是 0 就是 1，那是「包含」不是「大部分」。
_MIN_TOKENS = 2
#: 年份也對上。brief §6.4 的「年份加權」。
_YEAR_BONUS = 0.2
#: 年份對不上。同名重拍是真實情況，扣到門檻以下。
_YEAR_PENALTY = 0.5
#: 認得算數的最低分。`_PARTIAL` 剛好及格，光靠年份不及格；年份對不上則一律掉到門檻以下。
THRESHOLD = 0.6
#: 短到不能用「包含」判定的長度。`Up` 出現在半數發佈名裡。
_MIN_CONTAINED = 4

#: 切詞用。CJK 沒有空白，所以詞比對只對拉丁字有意義——中文標題走「包含」那一條。
_WORD = re.compile(r"[^0-9a-z]+")


@dataclass(frozen=True, slots=True)
class MediaMatch:
    """比對結果。`score` 只在同一次比對裡有意義，不是跨作品的絕對值。"""

    media: MediaSnapshot
    score: float
    reasons: tuple[ItemReason, ...]

    @property
    def exact(self) -> bool:
        """標題精確命中**而且**年份也對上——brief §6.5 允許 high 的那一種命中。"""
        return self.score >= _EXACT + _YEAR_BONUS


def normalize_title(text: str) -> str:
    """比對用的形式：NFKC、小寫、只留字母數字與 CJK。

    NFKC 一併把全形收掉——`Ⅲ`（U+2162）變成 `III`、全形英數變成半形，那是字幕組
    真的會寫的兩種形式（M1 票 01）。
    """
    return _NOISE.sub("", unicodedata.normalize("NFKC", text).casefold())


def match_media(info: ReleaseInfo, candidates: Sequence[MediaSnapshot]) -> MediaMatch | None:
    """發佈 → 最像的那一部作品。誰都不夠像時回 `None`（brief §6.4 第 2 點）。"""
    best: MediaMatch | None = None
    for media in candidates:
        found = _score(info, media)
        if found.score >= THRESHOLD and (best is None or found.score > best.score):
            best = found
    return best


def matches(info: ReleaseInfo, media: MediaSnapshot) -> MediaMatch | None:
    """這個發佈的標題與這一部作品**對得起來嗎**。上下文已經給了 Media 時的覆核。"""
    found = _score(info, media)
    return found if found.score >= THRESHOLD else None


def mentions(release_name: str, media: MediaSnapshot) -> bool:
    """這串發佈名裡出現得了這部作品的名字嗎——**不跑 guessit** 的粗篩（票 08）。

    `matches()` 是精確的那一支，但它要一份 `ReleaseInfo`，而 `parse_release` 實測每筆
    14 毫秒（2026-09-10，1200 筆 17.4 秒）。一次索引站搜尋回一兩千筆，全部解析會把事件
    迴圈卡住半分鐘，所以粗篩只做字串包含，解析留給篩完的那一百筆。

    判準與 `_compare` 的 `_CONTAINED` 那一條相同：正規化之後 TMDB 的某個名字整串出現在
    發佈名裡。太短的名字不算——`Up` 出現在半數發佈名裡。
    """
    haystack = normalize_title(release_name)
    if not haystack:
        return False
    return any(
        len(target) >= _MIN_CONTAINED and target in haystack
        for target in (normalize_title(known) for known in _known_titles(media))
    )


def _score(info: ReleaseInfo, media: MediaSnapshot) -> MediaMatch:
    reasons: list[ItemReason] = []
    score = 0.0
    for known in _known_titles(media):
        matched = _compare(info, known)
        if matched > score:
            score, reasons = matched, [_reason(matched, known)]

    if score and info.year is not None and media.year is not None:
        if info.year == media.year:
            score += _YEAR_BONUS
            reasons.append(why(Code.YEAR_MATCHES, year=info.year))
        else:
            score -= _YEAR_PENALTY
            reasons.append(why(Code.YEAR_DIFFERS, year=info.year, expected=media.year))
    return MediaMatch(media=media, score=score, reasons=tuple(reasons))


def _compare(info: ReleaseInfo, known: str) -> float:
    """一個 TMDB 標題對上這個發佈能拿幾分。"""
    target = normalize_title(known)
    if not target:
        return 0.0
    if any(normalize_title(candidate) == target for candidate in info.title_candidates):
        return _EXACT
    if len(target) < _MIN_CONTAINED:
        return 0.0
    if target in normalize_title(info.raw_title):
        return _CONTAINED
    if _overlap(known, info.raw_title) >= _MIN_OVERLAP:
        return _PARTIAL
    return 0.0


def _overlap(known: str, raw: str) -> float:
    """TMDB 標題的詞有多少比例出現在發佈名裡。詞太少時不算（回 0）。"""
    wanted = _words(known)
    if len(wanted) < _MIN_TOKENS:
        return 0.0
    return len(wanted & _words(raw)) / len(wanted)


def _words(text: str) -> frozenset[str]:
    """拉丁詞。三個字母以下的（`no`、`on`、`的`）到處都是，不當證據。"""
    return frozenset(
        word
        for word in _WORD.split(unicodedata.normalize("NFKC", text).casefold())
        if len(word) > 2
    )


def _known_titles(media: MediaSnapshot) -> tuple[str, ...]:
    """TMDB 那一端所有叫得出來的名字（plan §4.3 的 `titles` 已經是去重過的一份）。"""
    return (media.title, media.title_en, media.title_original, *media.titles)


def _reason(score: float, known: str) -> ItemReason:
    if score == _EXACT:
        return why(Code.TITLE_EXACT, title=known)
    if score == _CONTAINED:
        return why(Code.TITLE_CONTAINED, title=known)
    return why(Code.TITLE_PARTIAL, title=known)
