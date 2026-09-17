"""命名與路徑模板的純函式（plan §5）。

模板在 M0 票 04 的實驗後**凍結**：實測確認電影檔名含 `[tmdbid-{id}]` 才會被 Jellyfin 當成
同一部片的多版本，而方括號不會滲進 Series 或 Episode 名稱（brief §20.6 / §20.7）。
要改模板只改這裡，不影響其他模組。

這一層只認 `MediaSnapshot`，不認 TMDB。
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from berth.domain import Lang, MediaSnapshot, Tags, sort_langs

#: 作品資料夾（plan §5）。劇集與電影同一個模板。
FOLDER_TEMPLATE = "{title} ({year}) [tmdbid-{tmdb_id}]"
#: 年份未定時的樣子。TMDB 對還沒定檔的作品不給日期，而 `(None)` 會真的變成資料夾名。
FOLDER_TEMPLATE_UNDATED = "{title} [tmdbid-{tmdb_id}]"

#: 劇集檔名的開頭。**沒有 `[tmdbid-…]`**——那個只在資料夾與電影檔名上（brief §7.1 的範例）。
SERIES_PREFIX_TEMPLATE = "{title} ({year})"
SERIES_PREFIX_TEMPLATE_UNDATED = "{title}"

#: 季資料夾（plan §5）。Jellyfin 不接受 `S01`，一定要兩位數的 `Season NN`（brief §20.1）。
SEASON_TEMPLATE = "Season {season:02d}"

#: extras 落在作品資料夾底下的這一格（plan §5、brief §7.3；2026-09-07 對 10.10 與 10.11 實測）。
EXTRAS_DIR = "extras"

#: Jellyfin 唯一分得出繁簡的方式是自由文字標題，所以中文一律用這個碼（brief §6.7）。
CHINESE = "zh"

#: 語言 token → 檔名裡的語言碼。`CHT` / `CHS` 都是 `zh`（brief §20.1、§20.6 實測）。
_LANGUAGE_CODE: dict[Lang, str] = {
    Lang.CHS: CHINESE,
    Lang.CHT: CHINESE,
    Lang.JP: "ja",
    Lang.EN: "en",
}

#: 集名的上限（plan §5）。算的是字元不是位元組——它只是檔名的一段，整體上限由 `sanitize` 顧。
MAX_EPISODE_TITLE = 80

#: TMDB 還沒有正式集名時回的佔位（brief §7.1）。它不是標題，不進檔名。
PLACEHOLDER_EPISODE_TITLE = re.compile(r"^Episode \d+$")

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
    """作品資料夾名。**一旦凍結進 `media.folder_name` 就只從那裡讀**（plan §5）。

    凍結發生在第一次送單成功那一刻（票 09）——第一次真的通向磁碟。在那之前每次刷新快照都
    重算一次，畫面上它是「將會是」的預覽；之後 TMDB 改了標題也不會讓已經入庫的資料夾對不上，
    改名是顯式動作（brief §4.5）。凍結的那一串由 `Media.snapshot()` 放進 `media.folder_name`。
    """
    if media.folder_name:
        return media.folder_name
    dated = _dated(media)
    template = FOLDER_TEMPLATE if dated else FOLDER_TEMPLATE_UNDATED
    return sanitize(template.format(title=title_of(media), year=media.year, tmdb_id=media.tmdb_id))


def season_folder(season: int) -> str:
    """季資料夾名。Specials 是 `Season 00`（brief §7.1）。"""
    return SEASON_TEMPLATE.format(season=season)


def episode_target(
    media: MediaSnapshot,
    *,
    season: int,
    episode: int,
    episode_end: int | None = None,
    tags: Tags,
    ext: str,
) -> str:
    """一集的目標路徑，相對於 Route 的目標路徑（plan §5）。

    `{title} ({year}) - S01E01[-E02][ - {集名}][ {tags}].{ext}`，放在
    `{作品資料夾}/Season NN/` 底下。集名由快照決定（見 `episode_title`），tags 由
    `Tags.render()` 決定——這一層只負責把它們接起來。
    """
    head = f"{_series_prefix(media)} - S{season:02d}E{episode:02d}"
    if episode_end is not None and episode_end != episode:
        head += f"-E{episode_end:02d}"
    rendered = tags.render()
    name = _fit(
        head,
        episode_title(media, season, episode),
        f" {rendered}" if rendered else "",
        ext,
    )
    return "/".join((folder_name(media), season_folder(season), name))


def movie_target(media: MediaSnapshot, *, tags: Tags, ext: str) -> str:
    """一部電影的目標路徑，相對於 Route 的目標路徑（plan §5、brief §7.2）。

    檔名在 ` - ` 之前**必須與資料夾名一字不差，`[tmdbid-…]` 也算在內**：2026-09-07 實測，
    少了那一段 Jellyfin 就不是把兩個檔案當成同一部片的兩個版本，而是當成兩部電影
    （brief §20.6；§7.2 原本的範例是錯的）。所以這裡的開頭是 `folder_name` 本人，
    不是另外組一次的同款字串。
    """
    folder = folder_name(media)
    rendered = tags.render()
    # **不截**：前綴少一個字就不是同一部片。`folder_name` 已經在上限之內，接上 tags 之後
    #  最多多出一個版本標籤（與側掛字幕同一個例外），仍然低於 ext4 的 255 位元組。
    name = f"{folder} - {rendered}" if rendered else folder
    return "/".join((folder, _clean(name) + ext))


def subtitle_target(video_target: str, *, langs: Sequence[Lang], ext: str) -> str:
    """外掛字幕掛在影片旁邊（plan §5、brief §6.7）。

    `{影片檔名主幹}.{SUBTOKEN}.{lang}.{ext}`。**繁簡不走語言碼**：Jellyfin 沒有一個
    分得出繁簡而且兩個版本都認得的碼——`zh-Hant` / `zh-Hans` 只有 10.11 認得，10.10 會
    退化成「未定義」（2026-09-07 實測，brief §20.6）。所以語言碼一律 `zh`，`CHT` / `CHS`
    放在自由文字標題欄位，兩個版本的字幕選單都排在最前面看得見。

    **影片的主幹一個字都不能少**：Jellyfin 靠它認出這個字幕屬於哪一個影片。所以側掛字幕
    是唯一可以超過 `MAX_BYTES` 的檔名——最多多出一個語言段（22 位元組），仍然遠低於
    ext4 的 255。為了守上限而截短它，換來的是一個掛不上去的字幕。
    """
    return stem(video_target) + _subtitle_suffix(langs) + ext


def _subtitle_suffix(langs: Sequence[Lang]) -> str:
    """`.CHT.zh` / `.CHS.zh` / `.ja` / `.en`；說不出語言時什麼都不加。

    日文與英文不需要標題欄位——`ja` 與 `en` 在兩個版本都顯示得出來，多寫一個 `JP` 只是
    重複。中文才是那個沒有碼可用的例外。
    """
    ordered = sort_langs(tuple(langs))
    if not ordered:
        return ""
    code = _LANGUAGE_CODE[ordered[0]]
    if code != CHINESE:
        return f".{code}"
    return "." + "+".join(lang.value for lang in ordered) + f".{CHINESE}"


def extras_target(media: MediaSnapshot, name: str) -> str:
    """特典（plan §5、brief §7.3）。**原檔名照抄**：它對不到任何一集，改名只會讓人認不出來。

    落點是作品資料夾底下的 `extras/`；2026-09-07 對 10.10 與 10.11 實測，兩版都把它列進
    該作品的額外內容，而且不會被當成正片集數（brief §20.6）。
    """
    return "/".join((folder_name(media), EXTRAS_DIR, _file_name(stem(name), extension(name))))


def stem(name: str) -> str:
    """去掉副檔名的檔名。

    公開的：側掛字幕靠它與影片配對（`parser.subtitles`），extras 靠它保住原檔名，
    各切一次遲早會分岔（與 `extension` 同一個理由）。
    """
    ext = extension(name)
    return name[: -len(ext)] if ext else name


def episode_title(media: MediaSnapshot, season: int, episode: int) -> str:
    """檔名裡的集名（plan §5）。缺、空、或 `Episode 5` 這種佔位就省略。

    **Jellyfin 不從檔名取集名**（brief §20.1 實測），所以這一段純粹是給人看的：
    快照裡沒有這一集時省略它，而不是讓整個檔名產不出來。
    """
    found = next(
        (
            row
            for known in media.seasons
            if known.season_number == season
            for row in known.episodes
            if row.episode_number == episode
        ),
        None,
    )
    if found is None or not found.name.strip():
        return ""
    title = found.name.strip()
    if PLACEHOLDER_EPISODE_TITLE.match(title):
        return ""
    return title[:MAX_EPISODE_TITLE].rstrip()


def _series_prefix(media: MediaSnapshot) -> str:
    """劇集檔名的開頭。與資料夾名同源，只差沒有 `[tmdbid-…]`。"""
    template = SERIES_PREFIX_TEMPLATE if _dated(media) else SERIES_PREFIX_TEMPLATE_UNDATED
    return sanitize(template.format(title=title_of(media), year=media.year))


def _dated(media: MediaSnapshot) -> bool:
    """名字後面要不要接年份。

    TMDB 未定檔時沒有年份，`(None)` 會真的變成資料夾名；而有些標題**自己就帶著年份**
    （`GTO (2026)`，語料 `tv/gto-2026-magicstar`），照字面套會寫成 `GTO (2026) (2026)`。
    只有同一個年份才算重複——`Show (1999)` 的 2020 重製版兩個數字說的是兩件事。
    """
    if media.year is None:
        return False
    return not title_of(media).rstrip().endswith(f"({media.year})")


def title_of(media: MediaSnapshot) -> str:
    """檔名用的標題（brief §7.5）：英文 `name`，缺了才落回 `original_name`。"""
    return media.title_en.strip() or media.title_original.strip()


def sanitize(name: str, *, limit: int = MAX_BYTES) -> str:
    """檔案系統與 Jellyfin 都吞得下的名字（plan §5）。

    **票 04 就要它**：`folder_name` 每次寫快照都會寫進資料庫，`Mission: Impossible` 這種
    標題如果被寫成非法路徑，凍結（票 09）之後那幾列就改不掉了。

    六種模板共用這一支，而且是**逐段**呼叫：`/` 是分隔符不是字元，整條路徑丟進來會被吃掉。
    """
    # 尾端的 `.` 與空白最後才去：截斷有可能自己造出一個。Windows 上這種目錄建得起來也開不了。
    return _clip(_clean(name), limit).rstrip(". ")


def _clean(name: str) -> str:
    """拿掉檔案系統吞不下的字元，**不動長度也不動尾端的 `.`**。

    後面還要接東西（副檔名、tags）的片段用它：`It Didn't Have to Be Magic...` 的三個點
    在名字中間是合法的，去掉它們是把 TMDB 的集名改掉（語料 `anime/frieren-7acg-bd-batch`）。
    """
    cleaned = CONTROL.sub(" ", ILLEGAL.sub("", name))
    return WHITESPACE.sub(" ", cleaned).strip()


def _file_name(stem: str, ext: str) -> str:
    """檔名 = 主幹 + 副檔名。上限扣掉副檔名再算，**副檔名不能被截掉**——
    截到一半的 `.mk` 不是影片檔，Jellyfin 連掃都不會掃它。
    """
    cleaned = _clip(_clean(stem), MAX_BYTES - _size(ext))
    # 尾端的 `.` 只有在後面沒有副檔名時才是問題：`Foo..mkv` 這個檔名結尾是 `v`。
    return (cleaned if ext else cleaned.rstrip(". ")) + ext


def _fit(head: str, title: str, tail: str, ext: str) -> str:
    """`{head}[ - {title}]{tail}{ext}`，塞進 `MAX_BYTES`，而且**只從 `title` 剪**。

    三段的優先序不是美感問題，每一段少一個字的後果都不一樣：

    - 副檔名截掉就不是影片檔，Jellyfin 連掃都不會掃它。
    - `tail` 是 tags，那是「同一集的兩個版本」唯一的差別（brief §7.7）。從尾端截會把
      兩個版本截成**同一個檔名**，於是 `plan()` 判它們衝突、兩個都不入庫——本來該並存的
      兩個版本一個都進不去。
    - 集名純粹是給人看的（Jellyfin 不從檔名取集名，brief §20.1），所以可以捨的只有它。

    連 `head` 加 `tail` 都超標時才回頭截 `head`：那是病態的長標題，而截在哪裡對同一部
    作品是決定性的，同一集的每個版本仍然截在同一個位置。
    """
    room = MAX_BYTES - _size(ext)
    kept = _clip(_clean(title), room - _size(head) - _size(tail) - len(" - "))
    middle = f" - {kept}" if kept else ""
    return _clean(_clip(head, room - _size(middle) - _size(tail)) + middle + tail) + ext


def _size(text: str) -> int:
    return len(text.encode("utf-8"))


def extension(name: str) -> str:
    """檔名的副檔名，含點，小寫（`.MKV` → `.mkv`）。沒有副檔名時是空字串。

    公開的：分類（`parser.classify`）與目標檔名要的是同一個答案，各切一次遲早會分岔。
    """
    _, dot, suffix = name.rpartition(".")
    return f".{suffix.lower()}" if dot else ""


def _clip(name: str, limit: int) -> str:
    """截到 `limit` 個位元組，而且不從一個字的中間切開。放不下一個字就整段不要。"""
    if limit <= 0:
        return ""
    encoded = name.encode("utf-8")
    if len(encoded) <= limit:
        return name
    # `errors="ignore"` 把切在中間的那一個字整個丟掉，而不是留下半個位元組。
    return encoded[:limit].decode("utf-8", errors="ignore").rstrip()
