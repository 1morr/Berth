"""解析器的核心型別（plan §4.2、brief §6.2、§6.3、§6.8）。

住在 `domain/` 的理由與 `MediaSnapshot` 一樣：`parser` 產生它們、`naming` 消費它們、
`models` 拿它們當 `job_files.release_info_json` 與 `plan_items.tags_json` 的型別，
而前兩層依契約只 import `domain`（plan §1.3）。

全部是**純資料**：沒有 IO，也不知道 TMDB 或 qBittorrent 的存在。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


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


class PlanAction(StrEnum):
    """一個檔案的處置（plan §2.3 的 `plan_items.action`）。"""

    IMPORT = "import"
    EXTRA = "extra"
    SUBTITLE = "subtitle"
    SKIP = "skip"
    UNMATCHED = "unmatched"
    REVIEW = "review"


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
    special_kind: SpecialKind | None = None
    release_kind: ReleaseKind = ReleaseKind.SINGLE
    #: 解析時真的認出來的片段，原文照抄。
    matched_tokens: tuple[str, ...] = ()


class PlanItem(BaseModel):
    """一個檔案的處置決定（plan §4.2、§2.3 的 `plan_items`）。

    `media_id` 與 `target_path` 還不在這裡：前者由季集對應填（票 06），後者由命名引擎填
    （票 07）。欄位在有東西可以放進去的那一票才出現——空著的欄位會被當成「已經算過但沒結果」。
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
    #: 為什麼是這個決定。UI 逐條顯示，review 時看得到（brief §6.5）。
    reasons: tuple[str, ...] = ()
