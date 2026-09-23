"""命名與路徑模板的純函式（plan §5）。

模板在 M0 票 04 的實驗後**凍結**：實測確認電影檔名含 `[tmdbid-{id}]` 才會被 Jellyfin 當成
同一部片的多版本，而方括號不會滲進 Series 或 Episode 名稱（brief §20.6 / §20.7）。
要改模板只改這裡，不影響其他模組。

這一層只認 `MediaSnapshot`，不認 TMDB。
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field

from berth.domain import FileKind, Lang, MediaSnapshot, PlanAction, Source, Tags, sort_langs

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


# --- 反解（M2 票 10） -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Reading:
    """一條媒體庫路徑照命名模板讀回來的樣子：它是哪一種處置、哪一季哪一集、哪一組 Tags。

    `berth rebuild-ledger` 靠它把帳本長回來（plan §11.3 決定 9）。**不是另一套規則**：讀的方法是
    「從路徑取出候選 → 用上面同一組模板重算一次 → 一字不差才算」，所以讀得出來的每一條都保證是
    這些模板會寫出來的那一條，讀不出來的就是沒有，呼叫端不猜。
    """

    action: PlanAction
    season: int | None = None
    episode_start: int | None = None
    episode_end: int | None = None
    tags: Tags = field(default_factory=Tags)


def read_target(
    media: MediaSnapshot, relative: str, *, kind: FileKind, siblings: Sequence[str] = ()
) -> Reading | None:
    """`relative`（相對 Route 目標路徑、以 `/` 分段）是不是這部作品的某一條目標路徑。

    `kind` 是那個檔案的分類（`parser.classify`，呼叫端算）：同一個檔名形狀的 `.ass` 與 `.mkv`
    一個是字幕一個是正片，這一層不認副檔名。字幕靠 `siblings`（同一個資料夾裡的其他檔案）找到它
    跟著的那個影片，因為字幕的檔名就是影片的主幹加一段語言（`subtitle_target`）。

    **Tags 的讀法是正規的那一種**：`render()` 不是一對一的——`[X]` 可能是發佈組也可能是版本名。
    這裡把沒有形狀的 token 依序放進發佈組、再放進版本名，而形狀固定的（來源、解析度、語言、
    `Hardsub`、`v2`）放進它們自己的那一格。重算出來一字不差，所以檔名上說的事一件都沒丟。
    """
    parts = relative.split("/")
    if not parts or parts[0] != folder_name(media):
        return None
    if len(parts) == 3 and parts[1] == EXTRAS_DIR:
        return Reading(PlanAction.EXTRA) if extras_target(media, parts[2]) == relative else None
    if kind is FileKind.SUBTITLE:
        return _read_subtitle(media, relative, siblings)
    if kind is not FileKind.VIDEO:
        return None
    return _read_video(media, relative)


def _read_video(media: MediaSnapshot, relative: str) -> Reading | None:
    """正片：劇集是 `Season NN/{前綴} - SxxEyy…`，電影是作品資料夾底下那一個檔案。"""
    parts = relative.split("/")
    name = parts[-1]
    ext = extension(name)
    body = name[: -len(ext)] if ext else name
    if len(parts) == 2:
        found = {
            tags
            for tags in _tag_readings(
                body, lead=f"{folder_name(media)} - ", bare=folder_name(media)
            )
            if movie_target(media, tags=tags, ext=ext) == relative
        }
        return Reading(PlanAction.IMPORT, tags=found.pop()) if len(found) == 1 else None
    if len(parts) != 3:
        return None
    head = _EPISODE_HEAD.match(body[len(_series_prefix(media)) :])
    if not body.startswith(_series_prefix(media)) or head is None:
        return None
    season, start = int(head["season"]), int(head["episode"])
    end = int(head["end"]) if head["end"] else None
    if parts[1] != season_folder(season):
        return None
    found = {
        tags
        for tags in _tag_readings(body, lead=" ", bare=body)
        if episode_target(media, season=season, episode=start, episode_end=end, tags=tags, ext=ext)
        == relative
    }
    if len(found) != 1:
        return None
    return Reading(
        PlanAction.IMPORT,
        season=season,
        episode_start=start,
        # 單集是 `None`，與解析器寫的一樣（`domain.PlanItem`）：帳本比重複時靠它。
        episode_end=end,
        tags=found.pop(),
    )


def _read_subtitle(media: MediaSnapshot, relative: str, siblings: Sequence[str]) -> Reading | None:
    """字幕：`{影片主幹}.{SUBTOKEN}.{lang}.{ext}`。季集與 Tags 是它跟著的那個影片的。"""
    folder, _, name = relative.rpartition("/")
    ext = extension(name)
    for sibling in siblings:
        sibling_folder, _, sibling_name = sibling.rpartition("/")
        video_stem = stem(sibling_name)
        if sibling_folder != folder or sibling == relative or not name.startswith(f"{video_stem}."):
            continue
        video = _read_video(media, sibling)
        langs = _langs_of(name[len(video_stem) : len(name) - len(ext)])
        if video is None or langs is None:
            continue
        if subtitle_target(sibling, langs=langs, ext=ext) == relative:
            return Reading(
                PlanAction.SUBTITLE,
                season=video.season,
                episode_start=video.episode_start,
                episode_end=video.episode_end,
                tags=video.tags,
            )
    return None


def _langs_of(suffix: str) -> tuple[Lang, ...] | None:
    """`.CHT.zh` / `.CHS+CHT.zh` / `.ja` / `.en` / 空字串 → 語言。讀不懂是 `None`。"""
    if not suffix:
        return ()
    segments = suffix[1:].split(".")
    by_code = {code: lang for lang, code in _LANGUAGE_CODE.items() if code != CHINESE}
    if len(segments) == 1 and segments[0] in by_code:
        return (by_code[segments[0]],)
    if len(segments) == 2 and segments[1] == CHINESE:
        tokens = segments[0].split("+")
        if all(token in Lang.__members__ for token in tokens):
            return tuple(Lang(token) for token in tokens)
    return None


#: 劇集檔名在前綴之後的那一段：` - S01E01` 或 ` - S01E01-E02`。
_EPISODE_HEAD = re.compile(r" - S(?P<season>\d{2,})E(?P<episode>\d{2,})(?:-E(?P<end>\d{2,}))?")

#: 檔名結尾那一串 `[..][..]`，前面接的是 `lead`。
_TRAILING_TAGS = re.compile(r"((?:\[[^\[\]]*\])+)$")
_TOKEN = re.compile(r"\[([^\[\]]*)\]")

_RESOLUTION = re.compile(r"^(?:\d{3,4}[pi]|\dK)$", re.IGNORECASE)
_VERSION = re.compile(r"^v\d+$")


def _tag_readings(body: str, *, lead: str, bare: str) -> Iterator[Tags]:
    """這個主幹可能帶著的 Tags：一個都沒有、或結尾那一串方括號。

    兩種都給，由呼叫端重算比對：集名自己也可能以方括號結尾（`Foo [Bar]`），這時候「沒有 Tags」
    那一種才是對的。`bare` 是沒有 Tags 時主幹該有的樣子（電影），劇集不限定（集名在中間）。
    """
    if body == bare or lead == " ":
        yield Tags()
    found = _TRAILING_TAGS.search(body)
    if found is None or not body[: found.start()].endswith(lead):
        return
    tags = _slotted(_TOKEN.findall(found.group(1)))
    if tags is not None:
        yield tags


#: `Tags.render()` 的順序，每一格收得下哪一種 token。發佈組不收 `v2` 那種形狀：那是版本。
_SLOTS: tuple[tuple[str, Callable[[str], bool]], ...] = (
    ("source", lambda token: token in Source.__members__),
    ("resolution", lambda token: bool(_RESOLUTION.match(token))),
    ("subs", lambda token: all(part in Lang.__members__ for part in token.split("+"))),
    ("hardsub", lambda token: token == "Hardsub"),
    ("group", lambda token: bool(token) and not _VERSION.match(token)),
    ("version", lambda token: bool(_VERSION.match(token))),
    ("edition", lambda token: bool(token)),
)


def _slotted(tokens: Sequence[str]) -> Tags | None:
    """依 `render()` 的順序把 token 放進第一個收得下它的格子。放不下（順序不對、太多）是 `None`。"""
    values: dict[str, object] = {}
    slot = 0
    for token in tokens:
        while slot < len(_SLOTS) and not _SLOTS[slot][1](token):
            slot += 1
        if slot == len(_SLOTS):
            return None
        field = _SLOTS[slot][0]
        if field == "source":
            values[field] = Source(token)
        elif field == "subs":
            values[field] = tuple(Lang(part) for part in token.split("+"))
        elif field == "hardsub":
            values[field] = True
        else:
            values[field] = token
        slot += 1
    return Tags(**values)  # type: ignore[arg-type]  # 鍵是 `_SLOTS` 的欄位名，型別逐格換過了
