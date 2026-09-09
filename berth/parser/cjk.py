"""中文字幕組命名的正規化與欄位抽取（plan §4.1、brief §6.3、§20.4）。

沒有現成的解析庫處理中文字幕組命名（brief §20.4 查了八個），所以這一層自己維護詞典：
先把 CJK 的資訊撈成 `CjkHints`、把只有中文讀得懂的裝飾剝掉，剩下的字串才交給 guessit。
規則的起點是 AutoBangumi 的 `tokenizer/classic.py` 與 Sonarr 的 `Parser.cs`（brief §20.4）。

**兩個實測踩過的坑**（M1 票 01，7,833 筆真實釋出）：季號寫成**全形羅馬數字**
（`无职转生Ⅲ`，U+2160 起）與**不以空白收邊的半形羅馬數字**（`Mushoku Tensei III:`）。
漏掉這兩種會把整輪播出錯置成第一季（`docs/research/anime-episode-source.md` §6.1）。
"""

from __future__ import annotations

import re

from berth.domain import CjkHints, Lang, SpecialKind, SubtitleKind

#: 全形括號一律轉半形：字幕組混用 `【】` 與 `[]`，後面的規則只想寫一次。
_BRACKETS = str.maketrans({"【": "[", "】": "]", "［": "[", "］": "]", "（": "(", "）": ")"})

#: 中文數字。只到十二——季號不會更大，而更長的表會開始誤吃標題裡的字。
#: 公開的：`structure` 讀資料夾名時要的是同一張表（`第二季/` 與 `第二季` 是同一件事）。
CN_DIGITS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
    "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12,
}  # fmt: skip

#: 全形羅馬數字（U+2160 起）。一個字元一個數字，沒有邊界問題，所以整段都收。
_ROMAN_FULLWIDTH = {
    "Ⅰ": 1, "Ⅱ": 2, "Ⅲ": 3, "Ⅳ": 4, "Ⅴ": 5, "Ⅵ": 6,
    "Ⅶ": 7, "Ⅷ": 8, "Ⅸ": 9, "Ⅹ": 10, "Ⅺ": 11, "Ⅻ": 12,
}  # fmt: skip

#: 半形羅馬數字。**故意不收單字母的 `I` / `V` / `X`**：`Vol`、`X` 這類詞會把它們變成假季號，
#: 而字幕組寫季號時幾乎只寫得出 `II` 以上。邊界用 `\b`，不是空白——`Mushoku Tensei III:`
#: 與 `Mushoku Tensei II]` 都要認得出來（票 01 實測）。
_ROMAN_HALFWIDTH = {"II": 2, "III": 3, "IV": 4, "VI": 6, "VII": 7, "VIII": 8, "IX": 9}

_ROMAN_HALFWIDTH_RE = re.compile(
    r"(?<![A-Za-z0-9])("
    + "|".join(sorted(_ROMAN_HALFWIDTH, key=len, reverse=True))
    + r")(?![A-Za-z0-9])"
)

_ROMAN_FULLWIDTH_RE = re.compile("[" + "".join(_ROMAN_FULLWIDTH) + "]")

#: `第N季` / `第N期`，中文或阿拉伯數字。**字串是公開的**：`structure` 讀資料夾名時要的是
#: 同一種寫法，只差它要求整個資料夾名就是它（各寫一份的話兩邊遲早分岔）。
SEASON_CN = r"第\s*([0-9]+|[一二三四五六七八九十]{1,3})\s*[季期]"
_SEASON_CN = re.compile(SEASON_CN)

#: `第N部分`：同一季的第幾個 cour（plan §4.4）。與 `_SEASON_CN` 分開一條，因為它們
#: 在同一個名字裡會同時出現（`第三季 第二部分`），共用一條規則會互相吃掉。
PART_CN = r"第\s*([0-9]+|[一二三四五六七八九十]{1,3})\s*部分"
_PART_CN = re.compile(PART_CN)

#: `第N话` / `第N集`，可帶結尾標記。區間寫法 `第01-12話` 也在這裡。
_EPISODE_CN = re.compile(
    r"第\s*([0-9]{1,4})\s*(?:-\s*([0-9]{1,4})\s*)?[话話集](?:\s*(?:END|完|Fin))?",
    re.IGNORECASE,
)

#: 字幕語言。全部以 union 併入，所以規則之間重疊沒關係——只要沒有一條**多claim**。
#: ASCII token 一律要求前後不是英數：`[5.8GB]` 裡的 `GB` 不是簡體字幕（真實語料踩過）。
_SUB_TOKENS: tuple[tuple[re.Pattern[str], frozenset[Lang]], ...] = (
    (
        re.compile(r"简繁日|簡繁日|简中日|中日双语|中日雙語"),
        frozenset({Lang.CHS, Lang.CHT, Lang.JP}),
    ),
    (re.compile(r"简日|簡日|(?<![A-Za-z0-9])JPSC(?![A-Za-z0-9])"), frozenset({Lang.CHS, Lang.JP})),
    (re.compile(r"繁日|(?<![A-Za-z0-9])JPTC(?![A-Za-z0-9])"), frozenset({Lang.CHT, Lang.JP})),
    (re.compile(r"简繁|簡繁"), frozenset({Lang.CHS, Lang.CHT})),
    (
        re.compile(r"简体|簡體|简中|簡中|简体中文|(?<![A-Za-z0-9])(?:CHS|GB)(?![A-Za-z0-9])"),
        frozenset({Lang.CHS}),
    ),
    (
        re.compile(
            r"繁体|繁體|繁中|正體|正体|繁體中文|(?<![A-Za-z0-9])(?:CHT|BIG5)(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
        frozenset({Lang.CHT}),
    ),
    (re.compile(r"日语|日語|日文|日字|(?<![A-Za-z0-9])JPN(?![A-Za-z0-9])"), frozenset({Lang.JP})),
    (
        re.compile(r"英语|英語|英文|(?<![A-Za-z0-9])(?:ENG|ESubs?)(?![A-Za-z0-9])", re.IGNORECASE),
        frozenset({Lang.EN}),
    ),
    #: `日英简繁中` 這種連寫：逐字併，`中` 不表態繁簡所以不算一種語言。
    (re.compile(r"日英"), frozenset({Lang.JP, Lang.EN})),
)

_HARDSUB = re.compile(r"内嵌|內嵌|硬字幕|hardsub", re.IGNORECASE)
_SOFTSUB = re.compile(r"内封|內封|内嵌式?字幕组?|softsub", re.IGNORECASE)
_EXTERNAL = re.compile(r"外挂|外掛")

_COLLECTION = re.compile(r"合集|全集|總集篇|总集篇|全\s*[0-9]{1,4}\s*[话話集]|\[全\]")

_SPECIALS: tuple[tuple[re.Pattern[str], SpecialKind], ...] = (
    (re.compile(r"(?<![A-Za-z0-9])NC(?:OP|ED)(?![A-Za-z0-9])"), SpecialKind.NC),
    (re.compile(r"(?<![A-Za-z0-9])OAD(?![A-Za-z0-9])"), SpecialKind.OAD),
    (re.compile(r"(?<![A-Za-z0-9])OVA(?![A-Za-z0-9])"), SpecialKind.OVA),
    (re.compile(r"番外|特別篇|特别篇|映像特典|(?<![A-Za-z0-9])SP(?![A-Za-z0-9])"), SpecialKind.SP),
)

_MOVIE = re.compile(r"劇場版|剧场版|電影版|电影版")

#: `重製` / `重制`（brief §6.3 的詞典）。對到 brief §6.8 的 `Remaster` token——
#: guessit 只認得英文的 `Remastered`，中文發佈寫的是這兩個字。
_EDITION_CN: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"重製版?|重制版?"), "Remaster"),
)

#: `★1月新番★`、`★10月新番`、`[7月新番]`、`【2026夏季日剧】`、`【新】`、`【终】`、`【生】`。
#: 播出檔期與投稿狀態，與作品無關，剝掉。
_PREFIX = re.compile(
    r"★[^★]*★|★\s*[0-9]{1,2}月新番|\[\s*[0-9]{1,2}月新番\s*\]"
    r"|\[\s*[0-9]{4}[春夏秋冬]季?[日韩美]?剧\s*\]|\[\s*[新终終生完]\s*\]"
)

#: 招募廣告與地區限制。整段括號或整段全形括號都剝。
_RECRUIT = re.compile(r"[（(\[][^）)\]]*(?:招募|招新|招人|招收)[^）)\]]*[）)\]]|招募中|長期招募")
_REGION = re.compile(r"[（(\[]?[仅僅只]限[港澳台繁简體体]{2,}[）)\]]?|港澳台地[区區]限定")

#: 中日韓文字（含假名與全形標點）。剝掉之後剩下的就是拉丁字母那一半（brief §6.3）。
_CJK_RUN = re.compile(r"[　-〿぀-ヿ㐀-䶿一-鿿！-･]+")

#: 已經被 `_take_subs` 認走的 ASCII 字幕 token。留在字串裡 guessit 會把它們當**組名**
#: （`True.Beauty…AAC.Korean.CHS.mp4` → release_group `CHS`，真實語料踩過），所以認完就剝。
_ASCII_SUB_TOKENS = re.compile(
    r"(?<![A-Za-z0-9])(?:CHS|CHT|BIG5|JPSC|JPTC|JPN|ENG|ESubs?|GB)(?![A-Za-z0-9])",
    re.IGNORECASE,
)

#: 剝完之後留下的空殼：`[]`、`()`、連成一串的 `/` 與 `|`。
#: `-` 與 `_` **不合併**：`Title - 01` 的那一槓是 guessit 認集號的依據。
_EMPTY_BRACKETS = re.compile(r"\[[\s/|,]*\]|\([\s/|,]*\)")
_SEPARATOR_RUN = re.compile(r"(?:\s*[/|]\s*){2,}")
_WHITESPACE = re.compile(r"\s+")


def normalize_cjk(name: str) -> tuple[str, CjkHints]:
    """回（交給 guessit 的乾淨字串, `CjkHints`）。

    順序是有意的：先抽再剝。抽的時候看得到的是原文，剝完就沒有了。
    """
    text = name.translate(_BRACKETS)
    matched: list[str] = []

    group = _take_group(text)
    subs = _take_subs(text, matched)
    hardsub, subtitle_kind = _take_subtitle_kind(text, matched)
    season, text = _take_season(text, matched)
    part = _take_part(text, matched)
    episode, episode_end = _take_episode(text, matched)
    collection = _take(text, _COLLECTION, matched)
    special = _take_special(text, matched)
    movie = _take(text, _MOVIE, matched)
    edition = _take_edition(text, matched)

    hints = CjkHints(
        subs=subs,
        hardsub=hardsub,
        subtitle_kind=subtitle_kind,
        season=season,
        part=part,
        episode=episode,
        episode_end=episode_end,
        collection=collection,
        special=special,
        movie=movie,
        edition=edition,
        group=group,
        matched=tuple(matched),
    )
    return _clean(text, group, name), hints


def _take(text: str, pattern: re.Pattern[str], matched: list[str]) -> bool:
    """有沒有命中，順便把命中的原文記進 `matched_tokens`。"""
    found = pattern.search(text)
    if found is None:
        return False
    matched.append(found.group(0))
    return True


def _take_group(text: str) -> str:
    """字幕組名：開頭的方括號，去掉括號（brief §6.8）。

    只認**開頭**那幾個：`[01]`、`[1080P]`、`[BIG5]` 也是方括號，而它們不是組名。
    開頭那個不像組名時往後看一格——`[合集]女神降临…` 與 `[7月新番][愛戀字幕社]`
    都是真實語料，前者的第一格是發佈形態、後者是播出檔期。
    """
    stripped = _RECRUIT.sub(" ", _PREFIX.sub(" ", text)).lstrip()
    while True:
        found = re.match(r"\[([^\]]*)\]\s*", stripped)
        if found is None:
            return ""
        inner = found.group(1).strip()
        if inner and not _not_a_group(inner):
            return inner
        stripped = stripped[found.end() :]


def _not_a_group(inner: str) -> bool:
    """集號、解析度與發佈形態不是組名。"""
    if re.fullmatch(r"[0-9]{1,4}(?:[-~][0-9]{1,4})?|[0-9]{3,4}[pPiI]", inner):
        return True
    return bool(_COLLECTION.search(inner))


def langs_in(text: str) -> frozenset[Lang]:
    """這一段字說了哪幾種字幕語言（brief §6.8）。

    公開的：`structure` 讀語言資料夾名（`繁體/`、`简体/`）用的是同一張表——各寫一份的話
    詞彙遲早會分岔成兩套。
    """
    return _take_subs(text, [])


def _take_subs(text: str, matched: list[str]) -> frozenset[Lang]:
    langs: set[Lang] = set()
    for pattern, add in _SUB_TOKENS:
        found = pattern.search(text)
        if found is not None:
            matched.append(found.group(0))
            langs |= add
    return frozenset(langs)


def _take_subtitle_kind(text: str, matched: list[str]) -> tuple[bool | None, SubtitleKind]:
    """內嵌 / 內封 / 外掛。三個都沒說時是 `None` + `UNKNOWN`——不猜（brief §6.3）。"""
    if _take(text, _HARDSUB, matched):
        return True, SubtitleKind.HARDSUB
    if _take(text, _EXTERNAL, matched):
        return False, SubtitleKind.EXTERNAL
    if _take(text, _SOFTSUB, matched):
        return False, SubtitleKind.SOFTSUB
    return None, SubtitleKind.UNKNOWN


def _take_season(text: str, matched: list[str]) -> tuple[int | None, str]:
    """季號，以及**拿掉羅馬數字之後**的字串。

    羅馬數字一律從字串裡拿掉，不管季號最後是誰給的：留著的話 `Mushoku Tensei III` 會讓
    guessit 把 `III` 當標題的一部分，而同一部作品的另一個發佈寫成 `Mushoku Tensei S3`
    時，兩個標題就對不起來了。

    優先序是**中文季號 > 全形羅馬數字 > 半形羅馬數字**：`第三季` 是明說的，
    羅馬數字是慣例。三者同時出現時（`無職轉生 第三季 / Mushoku Tensei III`）說的是同一件事。
    """
    season: int | None = None

    found = _SEASON_CN.search(text)
    if found is not None:
        matched.append(found.group(0))
        raw = found.group(1)
        season = int(raw) if raw.isdigit() else CN_DIGITS.get(raw)

    full = _ROMAN_FULLWIDTH_RE.search(text)
    if full is not None:
        matched.append(full.group(0))
        season = season if season is not None else _ROMAN_FULLWIDTH[full.group(0)]
        text = _ROMAN_FULLWIDTH_RE.sub(" ", text)

    half = _ROMAN_HALFWIDTH_RE.search(text)
    if half is not None:
        matched.append(half.group(1))
        season = season if season is not None else _ROMAN_HALFWIDTH[half.group(1)]
        text = _ROMAN_HALFWIDTH_RE.sub(" ", text)

    return season, text


def _take_part(text: str, matched: list[str]) -> int | None:
    found = _PART_CN.search(text)
    if found is None:
        return None
    matched.append(found.group(0))
    raw = found.group(1)
    return int(raw) if raw.isdigit() else CN_DIGITS.get(raw)


def _take_episode(text: str, matched: list[str]) -> tuple[int | None, int | None]:
    found = _EPISODE_CN.search(text)
    if found is None:
        return None, None
    matched.append(found.group(0))
    end = int(found.group(2)) if found.group(2) else None
    return int(found.group(1)), end


def _take_edition(text: str, matched: list[str]) -> str:
    for pattern, token in _EDITION_CN:
        if _take(text, pattern, matched):
            return token
    return ""


def _take_special(text: str, matched: list[str]) -> SpecialKind | None:
    for pattern, kind in _SPECIALS:
        if _take(text, pattern, matched):
            return kind
    return None


def _clean(text: str, group: str, original: str) -> str:
    """交給 guessit 的那一半：剝掉裝飾與 CJK，只留拉丁字母那一段（brief §6.3）。

    整串都是 CJK 時**回原文**——剝到空字串等於把檔名丟掉，那比讓 guessit 猜錯更糟。
    """
    text = _PREFIX.sub(" ", text)
    text = _RECRUIT.sub(" ", text)
    text = _REGION.sub(" ", text)
    if group:
        text = text.replace(f"[{group}]", " ", 1)
    text = _CJK_RUN.sub(" ", text)
    text = _ASCII_SUB_TOKENS.sub(" ", text)
    text = _EMPTY_BRACKETS.sub(" ", text)
    text = _SEPARATOR_RUN.sub(" / ", text)
    text = _WHITESPACE.sub(" ", text).strip(" /|~-_")
    return text or original
