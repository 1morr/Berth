"""一部作品的 TMDB 快照（plan §2.2、§4.3）。

住在 `domain/` 而不是 `models/` 的理由是**三個消費者**：`naming` 拿它組資料夾名與檔名、
`parser` 拿它當 `ParseContext.media`、`models` 拿它當 `media.tmdb_snapshot_json` 的型別。
前兩個依契約只能 import `domain`（plan §1.3、import-linter），所以它只能在這裡。

它是 TMDB 回應的**收斂結果**，不是回應本身：adapter 那一層已經把劇集與電影的兩組欄位名
合併掉了，解析器與命名不知道 TMDB API 的存在。
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from berth.domain.enums import MediaKind


class EpisodeSnapshot(BaseModel):
    """一集。欄位就是 Media 詳情要顯示、而且命名與比對要用到的那幾個（plan §2.2）。"""

    model_config = ConfigDict(extra="ignore")

    episode_number: int
    #: TMDB 的英文集名。它會進檔名（plan §5 的 `{episode_title}`），所以存的是英文那一輪。
    name: str = ""
    #: 播出日。TMDB 未定檔時回空字串，那時這裡是 `None`。§4.4 的虛擬季偵測要用它算間隔。
    air_date: date | None = None
    #: 分鐘。TMDB 對還沒播的集數常常回 `null`。
    runtime: int | None = None
    #: Absolute episode group 給的絕對編號（若這部作品有人建過那種 group）。
    #: **不是每部都有**（brief §20.3 實測 10 部只有 6 部），沒有時整欄是 `None`。
    absolute_number: int | None = None


class SeasonSnapshot(BaseModel):
    """一季。

    `name` 不是裝飾：TMDB 的季名可能是 `Hashira Training Arc` 這種篇章名，而那正是
    plan §4.4「篇章名 → 季號」唯一的來源。原樣存、原樣顯示，不要正規化成 `Season N`。
    """

    model_config = ConfigDict(extra="ignore")

    season_number: int
    name: str = ""
    #: 這一季**已知的所有名字**（英文、繁體、簡體），去重。`name` 也在裡面。
    #:
    #: 比對用，不顯示：篇章名比對的對手是「柱训练篇」這種簡體字幕組寫法，而 `name` 是
    #: 英文的 `Hashira Training Arc`——只留一個語言的季名，plan §4.4 那條規則對九成的
    #: 真實發佈都不會命中（`docs/research/anime-episode-source.md` §6.1）。
    names: tuple[str, ...] = ()
    #: TMDB 自己報的集數。與 `episodes` 的長度可能不同（未播的集數 TMDB 已經先列進來）。
    episode_count: int = 0
    air_date: date | None = None
    episodes: tuple[EpisodeSnapshot, ...] = ()


class MediaSnapshot(BaseModel):
    """一部作品的快照。`media.tmdb_snapshot_json` 存的就是它（plan §2.2）。"""

    model_config = ConfigDict(extra="ignore")

    tmdb_id: int
    kind: MediaKind
    #: `zh-Hant` 介面的顯示用標題（`zh-TW` 那一輪）。缺翻譯時與 `title_en` 相同。
    title: str
    #: 英文標題。**檔名與比對用的那一個**（brief §7.5），也是 `en` 介面的顯示用標題。
    title_en: str
    title_original: str
    #: 首播 / 上映年。TMDB 未定檔時是 `None`。
    year: int | None = None
    #: `zh-Hant` 介面的簡介（`zh-TW` 那一輪，缺就是英文）。詳情頁靠它回答「這是不是我要的那部」。
    overview: str = ""
    #: `en` 介面的簡介（`en-US` 那一輪，brief §7.5）。缺就是空字串，不落回中文。
    #: M1.5 之前寫下的快照沒有這一欄，讀出來是空字串，下一次刷新（至多 24 小時）補上。
    overview_en: str = ""
    #: `zh-Hant` 介面的海報（`zh-TW` 那一輪，缺就是英文那一張）。
    poster_url: str = ""
    #: `en` 介面的海報。**TMDB 的海報也分語言**（brief §7.5，M1.5 票 11）。
    #: 票 11 之前寫下的快照沒有這一欄，讀出來是空字串，下一次刷新（至多 24 小時）補上。
    poster_url_en: str = ""
    #: 首播日 / 上映日。年份由它導出，但整個日期在 §4.4 的 offset 偵測裡也有用。
    first_air_date: date | None = None
    #: 電影片長（分鐘）。劇集是 `None`——劇集的片長在每一集上。
    runtime: int | None = None
    #: 比對用的標題集合：英文、原文、各國別名與各語言翻譯，去重後的一份（plan §4.3）。
    #: 票 08 的索引站搜尋逐個發一次，票 06 的比對拿它認檔名。
    titles: tuple[str, ...] = ()
    #: 劇集的各季各集；電影是空的。
    seasons: tuple[SeasonSnapshot, ...] = ()
    #: 凍結的作品資料夾名（CONTEXT.md 的 Folder Name、`media.folder_name`，brief §4.5）。
    #: **不是 TMDB 的資料**：`models.Media.snapshot()` 讀出來時才放進來，所以不進快照的 JSON。
    #: 空字串 = 還沒凍結，命名照標題算。
    folder_name: str = Field(default="", exclude=True)

    def episode(self, season: int, number: int) -> EpisodeSnapshot | None:
        """TMDB 上的那一集。沒有那一季或那一集是 `None`（程式檢查拿它的播出日與片長）。"""
        return next(
            (
                row
                for block in self.seasons
                if block.season_number == season
                for row in block.episodes
                if row.episode_number == number
            ),
            None,
        )
