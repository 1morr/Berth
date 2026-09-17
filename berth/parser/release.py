"""第二層：發佈名 → `ReleaseInfo`（plan §4.1、brief §6.3、§6.8）。

分工是 brief §6.3 決定的：CJK 那一半由 `cjk.normalize_cjk` 撈乾淨，剩下的西方命名交給
guessit（brief §20.4 的結論——沒有現成庫兩邊都行）。這裡是把兩份結果併起來，
再補上 guessit 在字幕組格式上會漏的幾條（guessit#929 至今仍開著）。

**併的規則只有一條**：明說的贏推論的，CJK 詞典贏 guessit——詞典認得的是這一行字裡
真的有的字，guessit 在方括號堆裡是用猜的。
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from guessit import guessit

from berth.domain import (
    CjkHints,
    ReleaseInfo,
    ReleaseKind,
    Source,
    SpecialKind,
    SubtitleKind,
    Tags,
    sort_langs,
)
from berth.parser.cjk import normalize_cjk

#: guessit 的 `source` → brief §6.8 的 token。`Remux` 走 `other`，在 `_source_of` 裡加判。
_SOURCES: dict[str, Source] = {
    "Blu-ray": Source.BD,
    "Ultra HD Blu-ray": Source.BD,
    "Web": Source.WEB,
    "DVD": Source.DVD,
    "HDTV": Source.HDTV,
    "Digital TV": Source.HDTV,
    "Satellite": Source.HDTV,
}

#: 結尾的 `-[Group].ext`。guessit 對這一種**不穩定**：`-[YTS.MX]` 給 `YTS.MX`，
#: `-[y2flix.cc]` 卻切成 `y2flix` 並把 `cc` 讀成 Criterion Collection 版本。
#: 括號裡是原文，照抄就好（brief §6.8「去掉括號，保留大小寫與連字號」）。
_TRAILING_GROUP = re.compile(r"-\[([^\]]+)\](?=\.[A-Za-z0-9]{2,4}$)")

#: `HD1080P`、`1920x1080` 這種 guessit 認不出的解析度寫法（真實語料：韓劇的 `HD1080P`）。
_RESOLUTION = re.compile(r"(?<![A-Za-z0-9])(?:HD)?(2160|1080|720|480)[pPiI](?![A-Za-z0-9])")

#: 方括號裡的集號：`[01]`、`[135]`、`[01-12]`、`[01v2]`。guessit 在多方括號的字幕組格式下
#: 常常整個漏掉（`[Comicat][Mushoku Tensei S3][10]` 只認得 S3）。
_BRACKET_EPISODE = re.compile(
    r"\[\s*([0-9]{1,4})\s*(?:[-~]\s*([0-9]{1,4})\s*)?(?:v[0-9]|fin|end)?\s*\]", re.IGNORECASE
)

#: `The_Final_Season[28]`、`The Final Season [75]`：`Season` 與方括號之間只隔空白、底線或點時，
#: guessit 把方括號裡的集號讀成季號，而且不再回集號。判準看的是**這個字的位置**，不是「季號
#: 等於方括號集號」——`Mushoku Tensei S2 [02]` 的兩個數字也相等，但 `S2` 是自己一格的季號
#: （M1 票 14f 以票 01 的 Mikan 標題驗證過，兩種寫法分得一個不差）。
_SEASON_WORD_BEFORE_BRACKET = re.compile(r"season[\s_.]*\[\s*[0-9]{1,4}\s*\]", re.IGNORECASE)

#: `Fin` / `END` 黏在集號後面是中文字幕組的季末寫法（`[01-13Fin]`）。`完` / `完結` 不在
#: 這裡——`normalize_cjk` 已經把它們吃掉了，而 ASCII 的這兩個它認不得。少了這兩個字，
#: `[01-13Fin]` 會被讀成「第 1 集」（2026-09-10 票 08 在真的索引站回應裡抓到）。

#: 沒有方括號的集號區間：`S01 | 01-28+SPx11`、`True Beauty 01-16`。
_LOOSE_RANGE = re.compile(r"(?<![0-9A-Za-z])([0-9]{1,4})\s*[-~]\s*([0-9]{1,4})(?![0-9A-Za-z])")

#: 年份長得像集號，所以四位數的 19xx / 20xx 不當集號用。
_YEAR_RANGE = range(1900, 2100)

#: 六位數的短日期年份在前：韓國電視台的 `Show.E079.150524` 是 2015-05-24，guessit 預設卻讀成
#: 2024-05-15（M1 票 14c 實測；guessit 文件的 `-Y, --date-year-first`，brief §20.4）。
#: 四位數年份的 `2024-02-29` 不受影響。
_GUESSIT_OPTIONS = {"date_year_first": True}


def parse_release(name: str) -> ReleaseInfo:
    """一個發佈名（torrent 名或檔名）→ `ReleaseInfo`。缺的欄位留空，不猜（brief §6.3）。"""
    trailing = _TRAILING_GROUP.search(name)
    stripped = _TRAILING_GROUP.sub("", name) if trailing else name
    cleaned, hints = normalize_cjk(stripped)
    guess: dict[str, Any] = dict(guessit(cleaned, _GUESSIT_OPTIONS))

    season, episode, episode_end = _numbers(cleaned, hints, guess)
    group = (
        hints.group or (trailing.group(1) if trailing else "") or _text(guess.get("release_group"))
    )

    return ReleaseInfo(
        raw_title=name,
        title_candidates=_titles(guess),
        season=season,
        # cour 標記兩邊都可能寫：`Part.2` guessit 讀得出來，`第二部分` 只有詞典認得。
        part=hints.part or _int(guess.get("part")),
        episode=episode,
        episode_end=episode_end,
        absolute_number=_int(guess.get("absolute_episode")),
        version=_int(guess.get("version")),
        group=group,
        source=_source_of(guess),
        resolution=_resolution_of(name, guess),
        video_codec=_text(guess.get("video_codec")),
        bit_depth=_text(guess.get("color_depth")),
        audio=_text(guess.get("audio_codec")),
        subtitle_langs=sort_langs(hints.subs),
        subtitle_kind=hints.subtitle_kind,
        edition=_text(guess.get("edition")) or hints.edition,
        year=_int(guess.get("year")),
        air_date=_date(guess.get("date")),
        special_kind=hints.special or (SpecialKind.MOVIE if hints.movie else None),
        release_kind=_release_kind(hints, episode_end, guess),
        matched_tokens=hints.matched,
    )


def merge_release(primary: ReleaseInfo, fallback: ReleaseInfo) -> ReleaseInfo:
    """檔名說了算，torrent 名補空缺。

    存在的理由是**兩邊各知道一半**：`[DBD-Raws][不死者之王 第二季][01][1080P]…mkv` 的檔名
    沒有字幕語言（那寫在 torrent 名的 `简繁外挂` 上），而 torrent 名沒有這一個檔案是第幾集。
    """
    filled = primary.model_dump()
    for field, value in fallback.model_dump().items():
        if field in ("raw_title", "matched_tokens", "special_kind"):
            # `special_kind` 不補：`[01-13TV全集+SP]` 說的是「這一包裡有特典」，
            # 不是「這個檔案是特典」。整包 13 集正片會因此全部被當成 SP（真實語料）。
            continue
        # `episode_end` 與 `air_date` 跟著 `episode` 走：檔名說了第 5 集，torrent 名的 `01-28`
        # 不會讓它變成第 5 到 28 集，包名上的日期也不是第 5 集的播出日。
        if field in ("episode_end", "air_date") and primary.episode is not None:
            continue
        if _empty(filled[field]) and not _empty(value):
            filled[field] = value
    filled["matched_tokens"] = tuple(primary.matched_tokens) + tuple(fallback.matched_tokens)
    return ReleaseInfo.model_validate(filled)


def tags_of(info: ReleaseInfo) -> Tags:
    """`ReleaseInfo` 裡會進檔名的那幾格（brief §6.8）。"""
    return Tags(
        source=info.source,
        resolution=info.resolution,
        subs=info.subtitle_langs,
        hardsub=info.subtitle_kind is SubtitleKind.HARDSUB,
        group=info.group,
        # 一般集數不加版本 token（brief §6.8）；v1 不是一個版本，是「沒有重製過」。
        version=f"v{info.version}" if info.version is not None and info.version > 1 else "",
        edition=info.edition,
    )


def _empty(value: object) -> bool:
    """「這個欄位沒有話說」。三個 enum 的預設值也算空——它們的意思就是「沒說」。"""
    return value in (None, "", (), ReleaseKind.SINGLE, SubtitleKind.UNKNOWN)


def _numbers(
    cleaned: str, hints: CjkHints, guess: dict[str, Any]
) -> tuple[int | None, int | None, int | None]:
    """季、集、集尾。三個一起算是因為 guessit 會把它們互相搞混。"""
    season = hints.season
    episode = hints.episode
    episode_end = hints.episode_end

    raw_season = guess.get("season")
    raw_episode = guess.get("episode")

    # `Mushoku Tensei Season 3 [04]` → guessit 回 `season: [3, 4]`：第二個其實是集號。
    if isinstance(raw_season, list) and raw_episode is None:
        raw_season, raw_episode = raw_season[0], raw_season[1] if len(raw_season) > 1 else None

    if season is None and isinstance(raw_season, int):
        # `GTO.2026.EP08` → guessit 同時給 `year` 與 `season` 2026。年份不是季號。
        season = None if raw_season == guess.get("year") else raw_season

    # guessit 只回季號、沒回集號時，那個季號就是 `Season [N]` 的 N，所以不必再比數字；
    # `Season 3 [04]` 會回兩個數字，走不到這裡。
    if (
        season is not None
        and hints.season is None
        and raw_episode is None
        and _SEASON_WORD_BEFORE_BRACKET.search(cleaned)
    ):
        season = None

    # 方括號裡的區間先問：`[135-136]` guessit 只回最後一個數字，區間比單一個數字更具體。
    if episode is None:
        bracketed, bracketed_end = _episode_from_brackets(cleaned)
        if bracketed_end is not None:
            episode, episode_end = bracketed, bracketed_end

    if episode is None:
        if isinstance(raw_episode, list) and raw_episode:
            episode, episode_end = raw_episode[0], raw_episode[-1]
        elif isinstance(raw_episode, int):
            episode = raw_episode

    if episode is None:
        episode, episode_end = _episode_from_brackets(cleaned)
    if episode is None and not isinstance(raw_season, list):
        episode, episode_end = _episode_from_range(cleaned)

    return season, episode, episode_end


def _episode_from_brackets(cleaned: str) -> tuple[int | None, int | None]:
    for found in _BRACKET_EPISODE.finditer(cleaned):
        start = int(found.group(1))
        if len(found.group(1)) == 4 and start in _YEAR_RANGE:
            continue
        return start, int(found.group(2)) if found.group(2) else None
    return None, None


def _episode_from_range(cleaned: str) -> tuple[int | None, int | None]:
    for found in _LOOSE_RANGE.finditer(cleaned):
        start, end = int(found.group(1)), int(found.group(2))
        if start in _YEAR_RANGE or end <= start:
            continue
        return start, end
    return None, None


def _release_kind(hints: CjkHints, episode_end: int | None, guess: dict[str, Any]) -> ReleaseKind:
    """`single | range | batch | collection`（brief §6.3）。

    `batch` 不在這裡：一個名字看不出「這包有很多集但沒寫成區間」，那要數檔案，
    是呼叫端的事（plan §4.1 的 `plan` 階段）。
    """
    if hints.collection:
        return ReleaseKind.COLLECTION
    if episode_end is not None or isinstance(guess.get("episode"), list):
        return ReleaseKind.RANGE
    return ReleaseKind.SINGLE


def _titles(guess: dict[str, Any]) -> tuple[str, ...]:
    candidates = [_text(guess.get("title")), _text(guess.get("alternative_title"))]
    return tuple(dict.fromkeys(value for value in candidates if value))


def _source_of(guess: dict[str, Any]) -> Source | None:
    other = guess.get("other")
    others = other if isinstance(other, list) else [other]
    if "Remux" in others:
        return Source.REMUX
    raw = guess.get("source")
    first = raw[0] if isinstance(raw, list) and raw else raw
    return _SOURCES.get(first) if isinstance(first, str) else None


def _resolution_of(name: str, guess: dict[str, Any]) -> str:
    screen = _text(guess.get("screen_size"))
    if screen:
        return screen
    found = _RESOLUTION.search(name)
    return f"{found.group(1)}p" if found else ""


def _text(value: object) -> str:
    """guessit 的欄位可能是 str、list 或 babelfish 物件。一律收斂成一個字串。"""
    if isinstance(value, list):
        value = value[0] if value else ""
    if value is None:
        return ""
    return str(value)


def _int(value: object) -> int | None:
    if isinstance(value, list):
        value = value[0] if value else None
    return value if isinstance(value, int) else None


def _date(value: object) -> date | None:
    if isinstance(value, list):
        value = value[0] if value else None
    return value if isinstance(value, date) else None
