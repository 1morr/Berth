"""解析器的核心型別（plan §4.2、brief §6.2、§6.3、§6.8）。

住在 `domain/` 的理由與 `MediaSnapshot` 一樣：`parser` 產生它們、`naming` 消費它們、
`models` 拿它們當 `job_files.release_info_json` 與 `plan_items.tags_json` 的型別，
而前兩層依契約只 import `domain`（plan §1.3）。

全部是**純資料**：沒有 IO，也不知道 TMDB 或 qBittorrent 的存在。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from berth.domain.enums import CollectionType, Profile, ReviewReason
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
    reasons: tuple[str, ...] = ()


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
    profile: Profile = Profile.STANDARD
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
    #: 為什麼是這個決定。UI 逐條顯示，review 時看得到（brief §6.5）。
    reasons: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        """檔名。字幕比對主幹、extras 保住原檔名，兩邊要的都是它而不是整條相對路徑。"""
        return self.rel_path.rpartition("/")[2]
