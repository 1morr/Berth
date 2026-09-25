"""解析器的核心型別（plan §4.2、brief §6.2、§6.3、§6.8）。

住在 `domain/` 的理由與 `MediaSnapshot` 一樣：`parser` 產生它們、`naming` 消費它們、
`models` 拿它們當 `plan_items.tags_json` 的型別，
而前兩層依契約只 import `domain`（plan §1.3）。

全部是**純資料**：沒有 IO，也不知道 TMDB 或 qBittorrent 的存在。
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from berth.domain.enums import CollectionType, ReviewReason
from berth.domain.media import MediaSnapshot


class FileKind(StrEnum):
    """檔案分類（brief §6.2）。第一層，決定這個檔案還要不要往下走。"""

    VIDEO = "video"
    SUBTITLE = "subtitle"
    FONT = "font"
    AUDIO = "audio"
    IMAGE = "image"
    ARCHIVE = "archive"
    #: 檔名含 sample 且大小遠小於同目錄最大影片。
    SAMPLE = "sample"
    #: `BDMV/`、`VIDEO_TS/` 結構；整包標記為需人工。
    DISC = "disc"
    #: NCOP/NCED/PV/CM/Menu/Trailer/特典，或位於 extras 類資料夾。
    EXTRA = "extra"
    OTHER = "other"


class Lang(StrEnum):
    """檔名 tag 用的字幕語言 token（brief §6.8）。

    不是 ISO 語言碼，也不打算是：Jellyfin 分不出繁簡（brief §20.1），所以繁簡是**自由文字
    標題**而不是語言碼。`CHT` / `CHS` 在這裡是那個標題欄位的詞彙表。
    """

    CHS = "CHS"
    CHT = "CHT"
    JP = "JP"
    EN = "EN"


#: `subs` 在檔名裡的固定順序（brief §6.8）。宣告順序就是排序，不另外維護一張表。
LANG_ORDER: tuple[Lang, ...] = (Lang.CHS, Lang.CHT, Lang.JP, Lang.EN)


def sort_langs(langs: frozenset[Lang] | set[Lang] | tuple[Lang, ...]) -> tuple[Lang, ...]:
    """依 `CHS < CHT < JP < EN` 排序（brief §6.8）。"""
    return tuple(lang for lang in LANG_ORDER if lang in langs)


class Source(StrEnum):
    """來源 token（brief §6.8）。BDRip / BluRay → `BD`，WEB-DL / WebRip → `WEB`。"""

    BD = "BD"
    WEB = "WEB"
    DVD = "DVD"
    HDTV = "HDTV"
    #: BD 原盤 remux。比 `BD` 更精確，所以是獨立的一個 token 而不是 `BD` 的別名。
    REMUX = "REMUX"


class SubtitleKind(StrEnum):
    """字幕怎麼跟著影片走（brief §6.3）。`hardsub` 是唯一會進檔名的那一種（§6.8）。"""

    HARDSUB = "hardsub"
    SOFTSUB = "softsub"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class SpecialKind(StrEnum):
    """非正篇的種類（brief §6.3 的 `special_kind`）。

    是封閉集合而不是自由文字（plan §4.2 原文寫 `str`）：`SP` 與 `NC` 的**下一步不同**——
    前者可能對得到 TMDB season 0，後者一律進 extras（brief §7.6）。
    """

    SP = "SP"
    OVA = "OVA"
    OAD = "OAD"
    MOVIE = "Movie"
    #: NCOP / NCED（無字幕片頭尾）。
    NC = "NC"


class ReleaseKind(StrEnum):
    """一個發佈涵蓋幾集（brief §6.3，對齊 AutoBangumi 的 `release_kind`）。"""

    SINGLE = "single"
    #: 檔名寫出集號區間（`01-12`）。
    RANGE = "range"
    #: 一次多集但沒寫成區間（季包）。
    BATCH = "batch"
    #: `合集` / `全集` / `全N话`。
    COLLECTION = "collection"


class Confidence(StrEnum):
    """brief §6.5 的三級。`HIGH` 與 `MEDIUM` 都自動入庫，`LOW` 進 review。"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


#: 由低到高。信心要比大小，而 `Confidence` 是字串 enum——順序只能寫在一個地方，
#: 不然「至多 medium」與「至少 medium」會在不同模組裡長出相反的表（票 06 code-review）。
CONFIDENCE_ORDER: tuple[Confidence, ...] = (Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH)

#: high 與 medium 都自動入庫（brief §6.5）。
AUTO_APPLIED: frozenset[Confidence] = frozenset({Confidence.HIGH, Confidence.MEDIUM})


def at_most(confidence: Confidence, ceiling: Confidence) -> Confidence:
    """封頂：不超過 `ceiling`。"""
    return min(confidence, ceiling, key=CONFIDENCE_ORDER.index)


def at_least(confidence: Confidence, floor: Confidence) -> bool:
    """有沒有到 `floor`。語料的 `min_confidence` 比的就是它。"""
    return CONFIDENCE_ORDER.index(confidence) >= CONFIDENCE_ORDER.index(floor)


class PlanAction(StrEnum):
    """一個檔案的處置（plan §2.3 的 `plan_items.action`）。"""

    IMPORT = "import"
    EXTRA = "extra"
    SUBTITLE = "subtitle"
    SKIP = "skip"
    UNMATCHED = "unmatched"
    REVIEW = "review"


#: 一個檔案在 Review Queue 上改得成哪幾種處置，依它的分類（M2 票 07）。**動作與分類矛盾的
#: 改動一律拒絕**：字型不會變成一集、字幕只能跟著它的影片走或被略過。
#:
#: 影片與特典可以互換——mediainfo 把短的正片降成 extra（brief §6.2），而 NCOP 偶爾被當成正片。
#: 光碟結構第一階段不拆（brief §6.2），只能留在原位或略過。`review` 不在任何一格裡：它是
#: 「還沒決定」，而這裡的每一次改動都是一個決定。
EDITABLE_ACTIONS: dict[FileKind, tuple[PlanAction, ...]] = {
    FileKind.VIDEO: (PlanAction.IMPORT, PlanAction.EXTRA, PlanAction.UNMATCHED, PlanAction.SKIP),
    FileKind.EXTRA: (PlanAction.EXTRA, PlanAction.IMPORT, PlanAction.UNMATCHED, PlanAction.SKIP),
    FileKind.SUBTITLE: (PlanAction.SUBTITLE, PlanAction.SKIP),
    FileKind.DISC: (PlanAction.UNMATCHED, PlanAction.SKIP),
    FileKind.FONT: (PlanAction.SKIP,),
    FileKind.AUDIO: (PlanAction.SKIP,),
    FileKind.IMAGE: (PlanAction.SKIP,),
    FileKind.ARCHIVE: (PlanAction.SKIP,),
    FileKind.SAMPLE: (PlanAction.SKIP,),
    FileKind.OTHER: (PlanAction.SKIP,),
}

#: 一個已經在 complete 裡的檔案**事後**改得成哪幾種處置（brief §7.4、§9.4 的 rematch，M2 票 08）：
#: 指派為某一集（`import`）、標記為 extra、忽略（`skip`）。依分類，與 `EDITABLE_ACTIONS`
#: 同一個道理。
#:
#: **字幕只能忽略**（2026-09-23 使用者拍板）：字幕要掛在某一個影片版本旁邊，一集有好幾個版本時
#: 掛哪一個是另一道題。光碟結構第一階段不拆，也只能忽略。
REMATCH_ACTIONS: dict[FileKind, tuple[PlanAction, ...]] = {
    kind: (
        (PlanAction.IMPORT, PlanAction.EXTRA, PlanAction.SKIP)
        if kind in (FileKind.VIDEO, FileKind.EXTRA)
        else (PlanAction.SKIP,)
    )
    for kind in FileKind
}


class ReasonCode(StrEnum):
    """Plan Item 的一條理由是哪一種（brief §6.5 的 `reasons[]`，M2 票 07）。

    **封閉集合加參數，不是後端拼好的句子**：句子由前端照 code 挑、以 zh-Hant 與 en 各寫一份，
    參數是檔名、季集、日期這種**不翻譯**的事實。拼好的英文句子翻不了譯，測試也只能比子字串。

    依來源分段：季號從哪裡來、集號怎麼換算、為什麼信心被壓下來、字幕跟著誰、整包一起看的結果。
    """

    # --- 作品 -------------------------------------------------------------------------
    #: Job 指向一部電影，電影沒有季集。
    MOVIE = "movie"
    #: Job 沒有帶作品，`{title}` 是從候選裡以標題認出來的（brief §6.4 第 2 點）。
    MEDIA_BY_TITLE = "media_by_title"
    #: 發佈標題與 `{title}` 完全相同。
    TITLE_EXACT = "title_exact"
    #: 發佈名裡整串出現 `{title}`。
    TITLE_CONTAINED = "title_contained"
    #: 發佈名帶著 `{title}` 的大部分詞。
    TITLE_PARTIAL = "title_partial"
    #: 發佈寫的年份 `{year}` 對上了。
    YEAR_MATCHES = "year_matches"
    #: 發佈寫的是 `{year}`，作品是 `{expected}`。
    YEAR_DIFFERS = "year_differs"
    #: 發佈標題 `{release_title}` 看起來不像 `{title}`（信心上限 medium）。
    TITLE_MISMATCH = "title_mismatch"
    #: Job 沒有帶作品，所以沒有季集可以對照。
    NO_MEDIA = "no_media"

    # --- 季號從哪裡來 -----------------------------------------------------------------
    #: Job 或 Rule 指定了第 `{season}` 季。
    SEASON_FROM_JOB = "season_from_job"
    #: 發佈名寫了第 `{season}` 季。
    SEASON_FROM_RELEASE = "season_from_release"
    #: 資料夾寫了第 `{season}` 季。
    SEASON_FROM_FOLDER = "season_from_folder"
    #: 發佈名帶著篇章名 `{arc}`，那是第 `{season}` 季的名字（plan §4.4）。
    SEASON_FROM_ARC = "season_from_arc"
    #: 發佈名說最終季，而最後一季是第 `{season}` 季。
    FINAL_SEASON = "final_season"

    # --- 集號怎麼來的 -----------------------------------------------------------------
    #: 只有集號，而 TMDB 上這部作品只有一季。
    SINGLE_SEASON = "single_season"
    #: TMDB 的絕對編號分組把 `#{number}` 放在 `{episode}`。
    ABSOLUTE_GROUP = "absolute_group"
    #: 各季集數累加，`#{number}` 落在 `{episode}`。
    ABSOLUTE_CUMULATIVE = "absolute_cumulative"
    #: 第 `{season}` 季的第 `{part}` 部分從第 `{first}` 集開始，
    #: 所以它的第 `{number}` 集是 `{episode}`。
    COUR_OFFSET = "cour_offset"
    #: TMDB 沒有第 `{season}` 季；播出日把各季切成 `{runs}` 輪，
    #: 第 `{season}` 輪從 `{episode}` 開始。
    AIR_DATE_RUN = "air_date_run"

    # --- 信心被壓下來 -----------------------------------------------------------------
    #: TMDB 第 `{season}` 季沒有第 `{number}` 集。
    EPISODE_NOT_ON_TMDB = "episode_not_on_tmdb"
    #: `#{number}` 沒有超過第 `{season}` 季的 `{episodes}` 集，也可能是後面某季重新從 01 數的。
    ABSOLUTE_WITHIN_FIRST_SEASON = "absolute_within_first_season"
    #: 發佈說它在 `{aired}` 播出，TMDB 沒有 `{episode}` 的播出日。
    AIR_DATE_UNKNOWN = "air_date_unknown"
    #: 發佈說它在 `{aired}` 播出，TMDB 說 `{episode}` 在 `{tmdb_aired}`。
    AIR_DATE_MISMATCH = "air_date_mismatch"
    #: 發佈涵蓋 `{start}`–`{end}`，但那一段放不進同一季。
    RANGE_SPANS_SEASONS = "range_spans_seasons"
    #: 字幕組的特典編號與 TMDB 的 S00 不保證一致。
    SPECIALS_NUMBERING = "specials_numbering"

    # --- 播出日比對（M3 票 14，`parser.airing`） ----------------------------------------
    #: 發佈於 `{published}`，比 TMDB 上 `{episode}` 的播出日 `{aired}` 早了兩天以上：
    #: 集數多半換算錯了。
    RELEASED_BEFORE_AIRING = "released_before_airing"
    #: `{episode}` 在 `{aired}` 播出，而這部作品發佈當時最近播出的是 `{latest}`
    #: （`{latest_aired}`）：連載中的 RSS Series 對到這麼早的一集，季號或 offset 多半錯了。
    BEHIND_LATEST_EPISODE = "behind_latest_episode"
    #: TMDB 沒有 `{episode}` 的播出日，所以沒有比對發佈時間。
    AIR_DATE_MISSING = "air_date_missing"
    #: 來源沒有給發佈時間，所以沒有比對播出日。
    PUBLISHED_MISSING = "published_missing"

    # --- 處置 -------------------------------------------------------------------------
    #: 分類就決定了處置：它是 `{kind}`（`FileKind`）。
    CLASSIFIED = "classified"
    #: 光碟結構，第一階段不拆（brief §6.2）。
    DISC_STRUCTURE = "disc_structure"
    #: 字幕組自己編號的特典，TMDB 的特典編號不同（brief §7.6）。
    OWN_NUMBERED_SPECIAL = "own_numbered_special"
    #: 推不出季集。
    NO_EPISODE = "no_episode"
    #: 這一包裡沒有影片配得上這個字幕。
    SUBTITLE_ORPHAN = "subtitle_orphan"
    #: 字幕與影片同名。
    SUBTITLE_SAME_NAME = "subtitle_same_name"
    #: 字幕在字幕資料夾裡、寫著第 `{number}` 集。
    SUBTITLE_FOLDER_EPISODE = "subtitle_folder_episode"
    #: 它跟著 `{video}` 走。
    SUBTITLE_FOLLOWS = "subtitle_follows"
    #: 它跟著的影片的處置是 `{action}`（`PlanAction`），所以它也沒有地方掛。
    VIDEO_NOT_IMPORTED = "video_not_imported"

    # --- 整包一起看 -------------------------------------------------------------------
    #: 這一包裡另一個檔案也會寫到 `{target}`（brief §6.4 第 5 點）。
    TARGET_CONTESTED = "target_contested"
    #: 同一包裡另一個正片從同一集開始、涵蓋的範圍不同；Jellyfin 12 會把它們併成一集（brief §7.8）。
    SPAN_CLASH = "span_clash"
    #: 媒體庫已經有 `{known}`，從同一集開始、範圍不同（同上，比的是帳本）。
    LIBRARY_SPAN_CLASH = "library_span_clash"
    #: 媒體庫已經有 `{known}`：同一集、同一組 Tags（brief §7.8 的重複版本）。
    SAME_VERSION = "same_version"
    #: 這一包把 `{files}` 個檔案對進第 `{season}` 季，TMDB 說那一季有 `{episodes}` 集。
    TOO_MANY_FILES = "too_many_files"
    #: 這一包其餘的檔案以 `{strategy}`（`MappingStrategy`）讀出來，這一個不是。
    STRATEGY_OUTLIER = "strategy_outlier"
    #: 這一包從頭到尾蓋滿第 `{season}` 季。
    SEASON_COMPLETE = "season_complete"
    #: 這條 Route 不讓 medium 自己入庫（brief §6.5）。
    MEDIUM_HELD_BY_ROUTE = "medium_held_by_route"

    # --- 人 ---------------------------------------------------------------------------
    #: 管理員在 Review Queue 改過這一列（M2 票 07）。
    SET_BY_USER = "set_by_user"
    #: 管理員改正同一個 RSS Series 的另一集並套用到整個 Series，這一列照新的第 `{season}` 季、集號
    #: offset `{offset}` 重算（M3 票 13）。`offset` 帶正負號（`+12`）。
    SERIES_CORRECTED = "series_corrected"


_C = ReasonCode

#: 每一種理由帶哪幾個參數。**句子裡的佔位符就是這幾個**：`why()` 在組的那一刻核對，前端兩份語言的
#: `jobs.plan.why.*` 由 `tests/unit/test_reason_codes.py` 逐句比對——參數改了名而句子沒跟上，
#: 畫面上就會印出一個 `{{season}}`。
REASON_PARAMS: dict[ReasonCode, frozenset[str]] = {
    _C.MOVIE: frozenset(),
    _C.MEDIA_BY_TITLE: frozenset({"title"}),
    _C.TITLE_EXACT: frozenset({"title"}),
    _C.TITLE_CONTAINED: frozenset({"title"}),
    _C.TITLE_PARTIAL: frozenset({"title"}),
    _C.YEAR_MATCHES: frozenset({"year"}),
    _C.YEAR_DIFFERS: frozenset({"year", "expected"}),
    _C.TITLE_MISMATCH: frozenset({"release_title", "title"}),
    _C.NO_MEDIA: frozenset(),
    _C.SEASON_FROM_JOB: frozenset({"season"}),
    _C.SEASON_FROM_RELEASE: frozenset({"season"}),
    _C.SEASON_FROM_FOLDER: frozenset({"season"}),
    _C.SEASON_FROM_ARC: frozenset({"arc", "season"}),
    _C.FINAL_SEASON: frozenset({"season"}),
    _C.SINGLE_SEASON: frozenset(),
    _C.ABSOLUTE_GROUP: frozenset({"number", "episode"}),
    _C.ABSOLUTE_CUMULATIVE: frozenset({"number", "episode"}),
    _C.COUR_OFFSET: frozenset({"part", "season", "first", "number", "episode"}),
    _C.AIR_DATE_RUN: frozenset({"season", "runs", "episode"}),
    _C.EPISODE_NOT_ON_TMDB: frozenset({"season", "number"}),
    _C.ABSOLUTE_WITHIN_FIRST_SEASON: frozenset({"number", "episodes", "season"}),
    _C.AIR_DATE_UNKNOWN: frozenset({"aired", "episode"}),
    _C.AIR_DATE_MISMATCH: frozenset({"aired", "episode", "tmdb_aired"}),
    _C.RANGE_SPANS_SEASONS: frozenset({"start", "end"}),
    _C.SPECIALS_NUMBERING: frozenset(),
    _C.RELEASED_BEFORE_AIRING: frozenset({"published", "episode", "aired"}),
    _C.BEHIND_LATEST_EPISODE: frozenset({"episode", "aired", "latest", "latest_aired"}),
    _C.AIR_DATE_MISSING: frozenset({"episode"}),
    _C.PUBLISHED_MISSING: frozenset(),
    _C.CLASSIFIED: frozenset({"kind"}),
    _C.DISC_STRUCTURE: frozenset(),
    _C.OWN_NUMBERED_SPECIAL: frozenset(),
    _C.NO_EPISODE: frozenset(),
    _C.SUBTITLE_ORPHAN: frozenset(),
    _C.SUBTITLE_SAME_NAME: frozenset(),
    _C.SUBTITLE_FOLDER_EPISODE: frozenset({"number"}),
    _C.SUBTITLE_FOLLOWS: frozenset({"video"}),
    _C.VIDEO_NOT_IMPORTED: frozenset({"action"}),
    _C.TARGET_CONTESTED: frozenset({"target"}),
    _C.SPAN_CLASH: frozenset(),
    _C.LIBRARY_SPAN_CLASH: frozenset({"known"}),
    _C.SAME_VERSION: frozenset({"known"}),
    _C.TOO_MANY_FILES: frozenset({"files", "season", "episodes"}),
    _C.STRATEGY_OUTLIER: frozenset({"strategy"}),
    _C.SEASON_COMPLETE: frozenset({"season"}),
    _C.MEDIUM_HELD_BY_ROUTE: frozenset(),
    _C.SET_BY_USER: frozenset(),
    _C.SERIES_CORRECTED: frozenset({"season", "offset"}),
}

#: 一條理由的參數：檔名、季集標記、日期、數字。**原文，不翻譯**——只有 `kind`、`action`、
#: `strategy` 三個鍵是封閉集合的值，畫面自己翻（`web/src/plans/reasonText.ts`）。**沒有叫
#: `count` 的鍵**（`REASON_PARAMS` 裡沒有，測試守著）：i18next 看到 `count` 就去找單複數那一對鍵。
ReasonParams = dict[str, str | int]


class ItemReason(BaseModel):
    """Plan Item 的一條理由：`code` 加上它的參數（M2 票 07）。"""

    model_config = ConfigDict(frozen=True)

    code: ReasonCode
    params: ReasonParams = {}


def why(code: ReasonCode, **params: str | int) -> ItemReason:
    """組一條理由。解析器每一處說理由的地方都走這裡，參數因此一眼看得出是哪幾格。

    **參數要剛好是 `REASON_PARAMS` 那幾個**，多一個少一個都丟 `ValueError`：句子由前端照
    code 挑，少一個參數的話畫面印出來的是 `{{season}}`。在組的那一刻就炸，benchmark 與解析器的
    單元測試走過的每一條路因此都核對過一次。
    """
    if frozenset(params) != REASON_PARAMS[code]:
        raise ValueError(f"{code.value} takes {sorted(REASON_PARAMS[code])}, got {sorted(params)}")
    return ItemReason(code=code, params=params)


def episode_label(season: int, episode: int, episode_end: int | None = None) -> str:
    """`S01E05` / `S01E05-E06`：季集的機器字串，理由的參數與畫面都寫這個形狀。"""
    label = f"S{season:02d}E{episode:02d}"
    return label if episode_end is None or episode_end == episode else f"{label}-E{episode_end:02d}"


class FileEntry(BaseModel):
    """torrent 裡的一個檔案（plan §4.2、§2.3 的 `job_files`）。

    `rel_path` 是**相對於 torrent 內容根**的路徑——qBittorrent 報的那一份去掉根資料夾。
    分隔符一律 `/`：它是 torrent metadata 的原文，不是本機路徑。
    """

    model_config = ConfigDict(frozen=True)

    rel_path: str
    size: int
    kind: FileKind = FileKind.OTHER
    #: qBittorrent 的下載優先序（0 = 不下載）。分類階段用不到，跟著檔案一路帶下去。
    priority: int = 0
    #: mediainfo 量到的秒數（票 11）。**`None` 是「還沒量」，不是 0**：pre-plan 那一輪
    #: 檔案還在下載，一個訊號都沒有，而分類器拿它把短的正片降為 extra（brief §6.2）。
    #: 解析器仍然沒有 IO——量的人是 `services/plan.py`，這裡收的是它量到的結果。
    duration_s: int | None = None

    @property
    def name(self) -> str:
        """檔名。解析發佈名的是它，不是整條相對路徑。"""
        return self.rel_path.rpartition("/")[2]

    @property
    def directory(self) -> str:
        """所在資料夾（根目錄是空字串）。`sample` 比大小與 extras 判資料夾都要它。"""
        return self.rel_path.rpartition("/")[0]


class CjkHints(BaseModel):
    """`normalize_cjk` 從中文字幕組命名裡撈出來的東西（plan §4.2、brief §6.3）。

    每個欄位都是「檔名**說了**什麼」，不是「推論出什麼」：沒寫就是 `None` / 空，
    不猜（brief §6.3）。推論是 `map_episode` 的事（票 06）。
    """

    model_config = ConfigDict(frozen=True)

    subs: frozenset[Lang] = frozenset()
    #: `None` = 檔名沒說。`True` = 內嵌，`False` = 內封或外掛。
    hardsub: bool | None = None
    subtitle_kind: SubtitleKind = SubtitleKind.UNKNOWN
    #: `第N季` / `第N期` / 羅馬數字 / `Nnd Season`。
    season: int | None = None
    #: `第N话` / `第N集`。
    episode: int | None = None
    episode_end: int | None = None
    #: `第N部分`（split-cour 的第幾個 cour）。季號說的是第幾季，這個說的是那一季的第幾段。
    part: int | None = None
    #: `合集` / `全集` / `全N话` / `總集篇`。
    collection: bool = False
    special: SpecialKind | None = None
    #: `劇場版` / `電影版`。
    movie: bool = False
    #: `重製` / `重制`。brief §6.3 的詞典列了它，而 guessit 只認得英文的 `Remastered`。
    #: 值是 brief §6.8 的 token（`Remaster`），不是原文——它會進檔名。
    edition: str = ""
    #: 字幕組名（原文，去掉括號）。
    group: str = ""
    #: 這一層真的認出來的片段，原文照抄。往上併進 `ReleaseInfo.matched_tokens`，
    #: 讓 UI 說得出「為什麼這樣判」（brief §6.3）。
    matched: tuple[str, ...] = ()


class Tags(BaseModel):
    """會進檔名的那幾個欄位（brief §6.8）。

    tag 以結構化欄位存在 Plan item 與帳本裡，檔名只是它們的一種呈現——`render()` 是那個
    唯一的呈現函式，改詞彙不改邏輯。
    """

    model_config = ConfigDict(frozen=True)

    source: Source | None = None
    resolution: str = ""
    subs: tuple[Lang, ...] = ()
    hardsub: bool = False
    group: str = ""
    #: `v2` / `v3`；一般集數不加。
    version: str = ""
    edition: str = ""

    def render(self) -> str:
        """`[<source>][<resolution>][<subtitle>][Hardsub]?[<group>][<version>][<edition>]`。

        缺的片段直接省略（brief §6.8），所以全空時回空字串——呼叫端據此決定要不要
        在檔名裡留那個空格（plan §5）。
        """
        parts: list[str] = []
        if self.source is not None:
            parts.append(self.source.value)
        if self.resolution:
            parts.append(self.resolution)
        if self.subs:
            parts.append("+".join(lang.value for lang in sort_langs(self.subs)))
        if self.hardsub:
            parts.append("Hardsub")
        for value in (self.group, self.version, self.edition):
            if value:
                parts.append(value)
        return "".join(f"[{part}]" for part in parts)


class ReleaseInfo(BaseModel):
    """發佈名解析的結果（brief §6.3）。缺就留空，不猜。

    `raw_title` 與 `matched_tokens` 讓 UI 說得出「為什麼這樣判」（brief §6.3 最後一條）。
    """

    model_config = ConfigDict(frozen=True)

    raw_title: str = ""
    #: 可能的作品標題，最像的排前面。比對階段（票 06）逐個試。
    title_candidates: tuple[str, ...] = ()
    #: 顯式季號（`S02`、`第二季`、`Season 3`）。
    season: int | None = None
    #: `Part.2` / `第二部分`：同一季的第幾個 cour。集號從 01 重數的那一種寫法（plan §4.4）。
    part: int | None = None
    episode: int | None = None
    episode_end: int | None = None
    #: 只有集號而且看起來超過單季範圍時的那個數字。換算是票 06 的事。
    absolute_number: int | None = None
    version: int | None = None
    group: str = ""
    source: Source | None = None
    resolution: str = ""
    video_codec: str = ""
    bit_depth: str = ""
    audio: str = ""
    subtitle_langs: tuple[Lang, ...] = ()
    subtitle_kind: SubtitleKind = SubtitleKind.UNKNOWN
    edition: str = ""
    year: int | None = None
    #: 檔名寫的播出日（`2024-02-29`、韓國電視台的 `150524`）。只有集號時，它是絕對編號換算
    #: 對不對的證據：換算出的那一集在 TMDB 上不是這一天播的，就不自動入庫（brief §6.4）。
    air_date: date | None = None
    special_kind: SpecialKind | None = None
    release_kind: ReleaseKind = ReleaseKind.SINGLE
    #: 解析時真的認出來的片段，原文照抄。
    matched_tokens: tuple[str, ...] = ()


class PlanSummary(BaseModel):
    """一份 Plan 的一句話（`plans.summary_json`，plan §2.3、票 11）。

    存下來而不是每次數一遍：下載列表上一列 Job 只想說「12 個檔案要入庫、2 個等人看」，
    而那句話不該讓每一列都去掃一次 `plan_items`。

    住在 `domain/` 的理由與 `MediaSnapshot` 一樣（plan §2.2 的同一條偏差）：`models` 拿它
    當一個 `*_json` 欄位的型別，`services` 算它，而 `api` 直接把它送出去——三層都要它，
    而 `api` 依契約不 import `models`（plan §1.3）。
    """

    model_config = ConfigDict(extra="ignore")

    #: 會被寫進媒體庫的檔案數（import + extra + subtitle）。
    files: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    #: 逐個 `PlanAction` 的檔案數。鍵是 action 的值，畫面照它畫那一列的摘要。
    actions: dict[str, int] = {}
    #: 為什麼停下來等人。`auto` 的 Plan 沒有理由。
    review_reason: ReviewReason | None = None


class MappingStrategy(StrEnum):
    """季集是**怎麼**決定的（plan §4.2 的 `Candidate.strategy`）。

    這個欄位不是註解：`review` 佇列靠它分組，benchmark 靠它回答「哪一條規則在賺錢、
    哪一條在賠錢」，而信心的上限也是逐條策略定的（brief §6.5）。
    """

    #: 檔名寫了 `SxxEyy` / `第二季` / `Season 3`——明說的。
    EXPLICIT = "explicit"
    #: 資料夾說的（`Season 2/`、`Specials/`）。
    FOLDER = "folder"
    #: Job 或 RSS Rule 帶進來的季號（brief §6.4 第 1 點）。
    CONTEXT = "context"
    #: 篇章名對到某一季的季名（plan §4.4，九成失敗的那一條）。
    ARC_NAME = "arc_name"
    #: 只有集號，而作品只有一季——韓劇的 `E01` 與單季動漫（brief §6.4）。
    SINGLE_SEASON = "single_season"
    #: TMDB Absolute episode group 的絕對編號。
    ABSOLUTE_GROUP = "absolute_group"
    #: 各季集數累加換算的絕對編號。
    ABSOLUTE_CUMULATIVE = "absolute_cumulative"
    #: 季內 `air_date` 間隔切出的虛擬季（plan §4.4 的 180 天）。
    AIR_DATE_OFFSET = "air_date_offset"
    #: `Part.2` / `第二部分`：同季前面幾個 cour 的長度加上去（plan §4.4）。
    COUR_OFFSET = "cour_offset"
    #: 電影沒有季集。有這個值是為了讓「為什麼沒有季集」也說得出口。
    MOVIE = "movie"


class Candidate(BaseModel):
    """一個「這個檔案是第幾季第幾集」的提案（plan §4.2）。

    `map_episode` 可以一次產好幾個（brief §6.4 的絕對編號三法各一個），排序即優先序：
    第一個就是目前最好的答案。每一個都帶得走自己的理由，review 佇列因此說得出
    「它是這樣算出來的」而不只是一個數字。
    """

    model_config = ConfigDict(frozen=True)

    season: int | None = None
    episode_start: int | None = None
    episode_end: int | None = None
    strategy: MappingStrategy
    confidence: Confidence
    reasons: tuple[ItemReason, ...] = ()


class ParseContext(BaseModel):
    """解析器看得到的上下文（plan §4.3）。

    `media` 是**已經抓好的快照**而不是一個 TMDB client：解析器沒有 IO，所以它要的事實
    由呼叫端先取好放進來（plan §4）。快照缺席時季集對應只能做標題比對（brief §6.4 第 2 點）。
    """

    model_config = ConfigDict(frozen=True)

    #: Job 帶的 Media（brief §6.4 第 1 點）。`None` = RSS 或重新入庫，要自己認作品。
    media: MediaSnapshot | None = None
    #: `media` 缺席時可以比對的作品（brief §6.4 第 2 點）。呼叫端先搜好放進來——
    #: 解析器沒有 IO，認得出作品的前提是有人把候選遞給它。
    candidates: tuple[MediaSnapshot, ...] = ()
    #: RSS Rule 或使用者指定的季號。有值時勝過檔名（brief §6.4）。
    season_hint: int | None = None
    #: RSS Rule 的手動偏移量。有值時**優先且信心可為 high**（plan §4.4）。
    episode_offset: int | None = None
    #: 這個 Job 要進哪一種媒體庫。劇集不能進 movies（`domain.collection_type_for`）。
    route_collection_type: CollectionType | None = None


class PlanItem(BaseModel):
    """一個檔案的處置決定（plan §4.2、§2.3 的 `plan_items`）。

    `media_id` 還不在這裡：Job 一路都帶著同一個 Media，所以要等到 Plan 存進資料庫
    （票 11）才有第二個來源需要它。欄位在有東西可以放進去的那一票才出現——
    空著的欄位會被當成「已經算過但沒結果」。
    """

    model_config = ConfigDict(frozen=True)

    rel_path: str
    kind: FileKind
    action: PlanAction
    season: int | None = None
    episode_start: int | None = None
    episode_end: int | None = None
    tags: Tags = Tags()
    confidence: Confidence = Confidence.LOW
    #: 相對於 Route 目標路徑的位置（plan §5）。**只有真的會被寫出去的檔案有值**：
    #: unmatched 留在 complete 原位（brief §7.4），review 還沒有決定，兩者都是空字串。
    target_path: str = ""
    #: 為什麼是這個決定。UI 逐條翻譯顯示，review 時看得到（brief §6.5）。
    reasons: tuple[ItemReason, ...] = ()

    @property
    def name(self) -> str:
        """檔名。字幕比對主幹、extras 保住原檔名，兩邊要的都是它而不是整條相對路徑。"""
        return self.rel_path.rpartition("/")[2]
