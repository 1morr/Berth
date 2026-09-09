"""命名與路徑模板的純函式（plan §5）。

模板在 M0 票 04 的實驗後**凍結**：實測確認電影檔名含 `[tmdbid-{id}]` 才會被 Jellyfin 當成
同一部片的多版本，而方括號不會滲進 Series 或 Episode 名稱（brief §20.6 / §20.7）。
要改模板只改這裡，不影響其他模組。

這一層只認 `MediaSnapshot`，不認 TMDB。
"""

from __future__ import annotations

import re

from berth.domain import MediaSnapshot

#: 作品資料夾（plan §5）。劇集與電影同一個模板。
FOLDER_TEMPLATE = "{title} ({year}) [tmdbid-{tmdb_id}]"
#: 年份未定時的樣子。TMDB 對還沒定檔的作品不給日期，而 `(None)` 會真的變成資料夾名。
FOLDER_TEMPLATE_UNDATED = "{title} [tmdbid-{tmdb_id}]"

#: Windows 的檔名不接受這幾個字元；Linux 只擋 `/`，但入庫目標可能是任何一種宿主，
#: 所以一律照最嚴的那一套來（plan §5、brief §4.5）。
ILLEGAL = re.compile(r'[/\\:*?"<>|]')

#: 控制字元。TMDB 的標題偶爾夾帶它們，而它們在路徑裡是看不見的地雷。
CONTROL = re.compile(r"[\x00-\x1f\x7f]")

WHITESPACE = re.compile(r"\s+")

#: 整體上限（plan §5）。算的是 **UTF-8 位元組**而不是字元——ext4 的單段檔名上限是 255 位元組，
#: 而一個中文字佔三個，照字元數算會在中文標題上超標。
MAX_BYTES = 200


def folder_name(media: MediaSnapshot) -> str:
    """作品資料夾名。**一旦寫進 `media.folder_name` 就只從那裡讀**（plan §5）。

    TMDB 之後改了標題也不會讓已經入庫的資料夾對不上——改名是顯式動作（brief §4.5）。
    """
    template = FOLDER_TEMPLATE if media.year is not None else FOLDER_TEMPLATE_UNDATED
    return sanitize(template.format(title=title_of(media), year=media.year, tmdb_id=media.tmdb_id))


def title_of(media: MediaSnapshot) -> str:
    """檔名用的標題（brief §7.5）：英文 `name`，缺了才落回 `original_name`。"""
    return media.title_en.strip() or media.title_original.strip()


def sanitize(name: str) -> str:
    """檔案系統與 Jellyfin 都吞得下的名字（plan §5）。

    **這一票就要它**：`folder_name` 在追蹤那一刻凍結進資料庫，`Mission: Impossible` 這種
    標題如果現在被寫成非法路徑，票 07 補規則時那幾列已經改不掉了。

    票 07 接手其餘五種模板（季資料夾、劇集檔、電影檔、外掛字幕、extras），共用這一支。
    """
    cleaned = CONTROL.sub(" ", ILLEGAL.sub("", name))
    cleaned = WHITESPACE.sub(" ", cleaned).strip()
    # 尾端的 `.` 與空白最後才去：截斷有可能自己造出一個。Windows 上這種目錄建得起來也開不了。
    return _clip(cleaned).rstrip(". ")


def _clip(name: str) -> str:
    """截到 `MAX_BYTES` 個位元組，而且不從一個字的中間切開。"""
    encoded = name.encode("utf-8")
    if len(encoded) <= MAX_BYTES:
        return name
    # `errors="ignore"` 把切在中間的那一個字整個丟掉，而不是留下半個位元組。
    return encoded[:MAX_BYTES].decode("utf-8", errors="ignore").rstrip()
