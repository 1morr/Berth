"""路徑講的話（plan §4.1 的 `structure_hints`、brief §6.4、§6.7）。

只讀**資料夾**，不讀檔名：`Season 2/Show - 05.mkv` 的季號寫在路徑上，而 `Show.S02E05.mkv`
的季號寫在名字裡——後者是 `parse_release` 的事。兩層各讀各的，合起來是 `map_episode` 的事
（plan §4.2「資料夾提示不進 `ReleaseInfo`」）。

讀不到就留空。`Specials/` 說的是「這不是正片」，不是「這是第 0 季」——那個決定要看
TMDB 有沒有那一集，屬於下一層。
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from berth.domain import Lang
from berth.parser.cjk import CN_DIGITS, PART_CN, SEASON_CN, langs_in

#: `Season 2`、`Season.2`、`S2`、`S02`。`S` 後面要接數字，`Subs` 不算。
_SEASON_LATIN = re.compile(r"^(?:season[\s._-]*|s)([0-9]{1,2})$", re.IGNORECASE)

#: `2nd Season`、`3rd Season`、`1st Season`。
_SEASON_ORDINAL = re.compile(r"^([0-9]{1,2})(?:st|nd|rd|th)[\s._-]*season$", re.IGNORECASE)

#: `第二季` / `第2期`。與 `cjk` 同一個寫法，只差這裡整個資料夾名就是它。
_SEASON_CN = re.compile(f"^{SEASON_CN}$")

#: `Part 2` / `Part.2` / `第二部分`。cour，不是季（plan §4.4）。
_PART_LATIN = re.compile(r"^part[\s._-]*([0-9]{1,2})$", re.IGNORECASE)
_PART_CN = re.compile(f"^{PART_CN}$")

#: 特典資料夾。`SP` / `SPs` 是字幕組的寫法，`Specials` 是 Jellyfin 的（brief §20.1）。
_SPECIAL_DIRS = frozenset({"specials", "special", "sp", "sps", "特典", "映像特典"})

#: 外掛字幕資料夾（brief §6.7 第 2 點）。
_SUBTITLE_DIRS = re.compile(r"^(?:subs?|subtitles?|字幕|外挂字幕|外掛字幕)$", re.IGNORECASE)

#: 這四個縮寫不在 `cjk` 的字幕 token 表裡：它們是**字幕檔後綴**的寫法（brief §6.7 第 3 點），
#: 而字幕組也拿它們當資料夾名。留在這裡而不是併進詞典，是因為發佈名裡的 `EN` 與 `JP` 太短，
#: 當成語言 token 會誤吃（`JP` 在 `JPBD` 裡是片源不是字幕）。整個資料夾名才算數。
_LANG_DIRS: dict[str, Lang] = {"tc": Lang.CHT, "sc": Lang.CHS, "jp": Lang.JP, "en": Lang.EN}


class StructureHints(BaseModel):
    """一條相對路徑上的資料夾說了什麼（plan §4.1）。"""

    model_config = ConfigDict(frozen=True)

    #: `Season 2/`、`第二季/`。
    season: int | None = None
    #: `Part 2/`：同一季的第幾個 cour（plan §4.4）。
    part: int | None = None
    #: 在 `Specials/` / `SPs/` 底下。
    special: bool = False
    #: 在 `Subs/` / `字幕/` 底下。
    subtitle_folder: bool = False
    #: 語言資料夾說的語言。兩種語言寫在同一個資料夾名上時是 `None`——分不出來就別猜。
    subtitle_lang: Lang | None = None
    #: 認出來的資料夾名，原文照抄（brief §6.3 的「說得出為什麼」）。
    matched: tuple[str, ...] = ()


def structure_hints(rel_path: str) -> StructureHints:
    """相對路徑 → `StructureHints`。最後一段是檔名，不看。

    由外往內走，內層覆蓋外層：`Fleabag (2016)/Season 2/` 的季號是內層那一個。
    """
    season: int | None = None
    part: int | None = None
    special = False
    subtitle_folder = False
    lang: Lang | None = None
    matched: list[str] = []

    for segment in rel_path.split("/")[:-1]:
        name = segment.strip()
        if (found_season := _season_of(name)) is not None:
            season = found_season
        elif (found_part := _part_of(name)) is not None:
            part = found_part
        elif name.lower() in _SPECIAL_DIRS:
            special = True
        elif _SUBTITLE_DIRS.match(name):
            subtitle_folder = True
        elif (found_lang := _lang_of(name)) is not None:
            lang = found_lang
        else:
            continue
        matched.append(segment)

    return StructureHints(
        season=season,
        part=part,
        special=special,
        subtitle_folder=subtitle_folder,
        subtitle_lang=lang,
        matched=tuple(matched),
    )


def _season_of(name: str) -> int | None:
    for pattern in (_SEASON_LATIN, _SEASON_ORDINAL):
        found = pattern.match(name)
        if found is not None:
            return int(found.group(1))
    found = _SEASON_CN.match(name)
    return _number(found.group(1)) if found is not None else None


def _part_of(name: str) -> int | None:
    found = _PART_LATIN.match(name)
    if found is not None:
        return int(found.group(1))
    found = _PART_CN.match(name)
    return _number(found.group(1)) if found is not None else None


def _lang_of(name: str) -> Lang | None:
    """語言資料夾。**只認得出一種**才算數：`简繁/` 底下的檔案是哪一種，路徑沒有說。"""
    direct = _LANG_DIRS.get(name.lower())
    if direct is not None:
        return direct
    langs = langs_in(name)
    return next(iter(langs)) if len(langs) == 1 else None


def _number(raw: str) -> int | None:
    return int(raw) if raw.isdigit() else CN_DIGITS.get(raw)
