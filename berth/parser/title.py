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

from berth.domain import ItemReason, MediaKind, MediaSnapshot, ReleaseInfo, SearchVerdict, why
from berth.domain import ReasonCode as Code
from berth.parser.seasons import SEASON_CN, SEASON_LATIN, SEASON_ORDINAL

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

#: 發佈名裡的年份。前後不能是英數：`1920x1080`、`1990s` 都不是年份。
_YEAR = re.compile(r"(?<![0-9A-Za-z])((?:19|20)[0-9]{2})(?![0-9A-Za-z])")
#: 年份容許差幾年。Radarr 要完全相同，但它另認一個「第二年份」（影展與各國上映跨年），
#: 快照沒有那一格，差一年代替它（brief §20.16）。
_YEAR_SLACK = 1
#: 讀得出季集的記號，只給電影用。季名的寫法與 `seasons` 共用（`S01`、`Season 2`、`2nd Season`、
#: `第2季`），再加集號：`S04E02`、`S01E01E02`、`S01E05v2`、`1x05`、`EP05`、`第05話`、`第01-12话`。
_SERIES_MARK = re.compile(
    rf"(?<![0-9A-Za-z])(?:{SEASON_LATIN}(?:E[0-9]{{1,4}})*(?:v[0-9])?|{SEASON_ORDINAL}"
    r"|[0-9]{1,2}x[0-9]{2,3}|EP[0-9]{1,4})(?![0-9A-Za-z])"
    rf"|{SEASON_CN}|第\s*[0-9]{{1,4}}(?:\s*[~-]\s*[0-9]{{1,4}})?\s*[话話集]",
    re.IGNORECASE,
)
#: 字幕組的集號 `- 05`、`- 07v2`、`- 01 ~ 12`、`[05]`、`[01-12]`、`【12 END】`、`[01-12合集]`
#: （M4 票 69：同名動畫的各集）。只認兩到三位數：四位數是年份（`Nosferatu - 1922`、`[1922]`），
#: 一位數多半是光碟數或續集（`- 2 Disc`、`[3]`，code-review 抓到）——字幕組的集號補零到兩位。
_FANSUB_EPISODE = re.compile(
    r"(?<=\s)-\s*[0-9]{2,3}(?:v[0-9])?(?:\s*[~-]\s*[0-9]{2,3})?(?=[\s\[(]|\.(?![0-9])|$)"
    r"|[\[【][0-9]{2,3}(?:v[0-9])?(?:\s*[~-]\s*[0-9]{2,3})?\s*(?:END|Fin|合集)?[\]】]",
    re.IGNORECASE,
)
#: 片名那一段裡分隔不同名字的符號：字幕組把幾個名字寫在一起時用 `/`、`|` 或方括號隔開。`_` 不算：
#: scene 拿它當空白（`Law_and_Order_SVU`），中文名與拉丁字名之間的 `_` 由 `_SCRIPT_RUN` 切開。
_NAME_BREAK = re.compile(r"[/|\[\]【】()（）]+")
#: 一段裡的 CJK 與非 CJK：`SPY×FAMILY 間諜家家酒` 是兩個名字，中間只有一個空白。
_SCRIPT_RUN = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]+|[^぀-ヿ㐀-䶿一-鿿가-힯]+")
#: scene 寫法的分隔字，畫面上的證據換成空白。
_SCENE_SEPARATOR = re.compile(r"[._\s]+")

#: CJK 字。名字裡有它的不寫開 `&`（`spell_ampersand`）。
_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]")
#: 名字裡的 `&`，連同兩側的空白。
_AMPERSAND = re.compile(r"\s*&\s*")


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


def spell_ampersand(title: str) -> str:
    """`Law & Order` → `Law and Order`：拉丁字的名字裡，`&` 寫成 `and`（M4 票 69）。

    照 Sonarr / Radarr 的 `GetCleanSceneTitle`（送查詢前 `&` 換成 `and`，brief §20.19）：scene 的
    發佈名寫 `Law.and.Order`，而 The Pirate Bay 對帶 `&` 的查詢一筆都不回（2026-10-09 實測）。
    有 CJK 字的名字原樣：中文名的 `&` 不是英文的 and。
    """
    if _CJK.search(title):
        return title
    return _AMPERSAND.sub(" and ", title).strip()


@dataclass(frozen=True, slots=True)
class Misfit:
    """名字對上了、類型或年份對不上（`misfit`）：哪一條，以及發佈名裡的哪一段字。"""

    verdict: SearchVerdict
    #: 觸發的那一段字，原樣：`S04E02`、`- 05`、`1990`。畫面上那一句話引它，不翻。
    evidence: str


def misfit(release_name: str, media: MediaSnapshot) -> Misfit | None:
    """名字對上之後，年份與類型對不上的是哪一條——`mentions` 之後的第二道粗篩（M4 票 49、83）。

    同樣**不跑 guessit**，理由與 `mentions` 相同。審計 S6 搜《活死人之夜》（1968）時，主清單
    混進 1990、2006 的重拍與《Below Deck Down Under S04E02 Night of the Living Dead》。
    說得過去是 `None`。

    - **電影**：讀得出季集記號或字幕組的集號（多半是同名動畫）就不是它（`NOT_MOVIE`，證據是
      先讀到的那一種）。
      劇集反過來不篩——沒有季集記號的劇集發佈是常態（`Title - 05`、`[01-12]`），`Movie` 又可能是
      S00（brief §6.3 的 `special_kind`）。
    - **年份**照 Radarr：發佈名寫的年份要對上作品的年份，沒寫年份照收（brief §20.16）。
      Radarr 另認一個「第二年份」，Berth 的快照沒有，所以容許差一年（`_YEAR_SLACK`）。
      劇集的年份是整段播出期間（各季首播年），Sonarr 不以年份拒絕，Berth 只擋播出期間之外的。
      寫了好幾個年份時有一個對上就算；片名自己帶的數字（`Blade Runner 2049`）不算年份。

    先說記號再說年份：記號是更硬的證據（看得出這是一集；年份可能是修復版的那一年）。
    """
    if media.kind is MediaKind.MOVIE:
        for pattern in (_SERIES_MARK, _FANSUB_EPISODE):
            if found := pattern.search(release_name):
                return Misfit(SearchVerdict.NOT_MOVIE, found.group(0).strip())
    window = _year_window(media)
    if window is None:
        return None
    in_titles = _title_years(media)
    written = [
        found for found in _YEAR.finditer(release_name) if int(found.group(1)) not in in_titles
    ]
    low, high = window
    if not written or any(low <= int(found.group(1)) <= high for found in written):
        return None
    return Misfit(SearchVerdict.YEAR, written[0].group(1))


def partial_title(release_name: str, media: MediaSnapshot) -> str:
    """發佈名的片名那一段只對上這部作品的**一部分**名字時，回那一段（可能是衍生劇，M4 票 83）。

    照 Sonarr（brief §20.20）：片名是**第一個記號前面**那一段——季集記號、字幕組的集號、年份
    （片名自己帶的年份不算）——比對要**完全相等**才算這一部，不是包含。`Law.and.Order.SVU.S28E01`
    的片名 `Law and Order SVU` 包住 `Law & Order` 但不等於它。

    那一段先照 `_NAME_BREAK` 與文字系統切成一個一個名字：字幕組常把中文名與拉丁字名寫在一起
    （`SPY×FAMILY 間諜家家酒`），整段比的話每一筆都像衍生劇。**有一個名字等於**這部作品的某個名字
    就不是部分；沒有相等、但有一個包住某個名字的，回那一個。讀不出記號（沒有片名那一段）、
    或片名那一段根本沒有這部作品的名字時不判，回空字串——寧可放進「符合」讓人看見。
    """
    lead = release_name[: _lead_end(release_name, media)]
    if lead == release_name:
        return ""
    names = [
        run.group(0)
        for piece in _NAME_BREAK.split(lead)
        for run in _SCRIPT_RUN.finditer(piece)
        if normalize_title(run.group(0))
    ]
    known = {target for target in map(normalize_title, _known_titles(media)) if target}
    if any(normalize_title(name) in known for name in names):
        return ""
    wider = next(
        (
            name
            for name in names
            if any(
                len(target) >= _MIN_CONTAINED and target in normalize_title(name)
                for target in known
            )
        ),
        "",
    )
    return _SCENE_SEPARATOR.sub(" ", wider).strip(" -")


def _lead_end(release_name: str, media: MediaSnapshot) -> int:
    """第一個記號的位置；一個都沒有時是整串的長度。"""
    in_titles = _title_years(media)
    starts = [
        found.start()
        for pattern in (_SERIES_MARK, _FANSUB_EPISODE)
        if (found := pattern.search(release_name))
    ]
    starts += [
        found.start()
        for found in _YEAR.finditer(release_name)
        if int(found.group(1)) not in in_titles
    ]
    return min(starts, default=len(release_name))


def _title_years(media: MediaSnapshot) -> set[int]:
    """片名自己帶的數字（`Blade Runner 2049`）：發佈名裡的它不是年份。"""
    return {year for known in _known_titles(media) for year in _years(known)}


def _years(text: str) -> set[int]:
    return {int(found) for found in _YEAR.findall(text)}


def _year_window(media: MediaSnapshot) -> tuple[int, int] | None:
    """這部作品的發佈名寫得出哪幾年，兩端都放寬 `_YEAR_SLACK`。TMDB 沒有年份時是 `None`。"""
    if media.year is None:
        return None
    last = max(
        (season.air_date.year for season in media.seasons if season.air_date is not None),
        default=media.year,
    )
    return media.year - _YEAR_SLACK, max(last, media.year) + _YEAR_SLACK


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
    """TMDB 那一端所有叫得出來的名字（plan §4.3 的 `titles` 已經是去重過的一份）。

    帶 `&` 的另加寫開的那一種（`spell_ampersand`）：正規化把 `&` 丟掉、`and` 留著，`Law & Order`
    與 `Law.and.Order` 不加這一種就是兩串字（M4 票 69）。
    """
    names = (media.title, media.title_en, media.title_original, *media.titles)
    return (*names, *(spell_ampersand(name) for name in names if "&" in name))


def _reason(score: float, known: str) -> ItemReason:
    if score == _EXACT:
        return why(Code.TITLE_EXACT, title=known)
    if score == _CONTAINED:
        return why(Code.TITLE_CONTAINED, title=known)
    return why(Code.TITLE_PARTIAL, title=known)
