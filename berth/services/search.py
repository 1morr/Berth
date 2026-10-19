"""索引站搜尋（plan §6 search 群組、§8.4、brief §13、票 08）。

這是使用者第一次看見解析器的判斷。一次搜尋做四件事，順序不能換：

1. **一部作品有好幾個名字**，所以查詢不只一個。英文、原文與各語言別名各發一次，播到第二季
   以後的劇集另加季號變體。2026-09-10 實測 SPY×FAMILY 的三個標題各自搜出 1200 / 908 / 1210 筆，
   聯集 1854 筆——每一個標題都帶來另外兩個問不到的東西（各 391 / 196 / 169 筆）。
2. **併發**。單一聚合查詢實測 60–85 秒（Prowlarr 要現場去連五個追蹤站），三個查詢併發
   共 35 秒——逐個問會變成三分鐘。一個查詢垮掉時剩下的照樣回得來（票 08 驗收）。
3. **合併去重，然後每一筆歸到一類**（`_judge`，M4 票 83）。去重的鑰匙是 info hash，寫法正規化過
   （同一個發佈在 Mikan 是十六進位、在 dmhy 是 base32，實測單次查詢的 1200 筆裡有 47 筆是
   這樣重複的）。分類是實跑逼出來的：**The Pirate Bay 對搜不到的關鍵字會回它的熱門
   清單**，而那些東西動輒五六千個做種，會把真正的結果整批擠出前 100 筆（2026-09-10 搜
   SPY×FAMILY，前六筆是 Spider-Man、Ted Lasso、Reacher）。對不上的不丟：照 Sonarr 互動搜尋，
   每一類各自取一份送出去，畫面預設只開「符合」，其他類按了才看。自己打的關鍵字只分「對得上」與
   「對不上」（`_judge_typed`，M4 票 83b）：熱門清單照樣會淹掉那幾筆真正的結果。
4. **逐筆問解析器**。`parse_release` 給 Tags、`map_episode` 給預估季集，兩者都是純函式，
   所以這一步不打任何服務。

搜尋不看 Route：入庫到哪一條是送單時才決定的事（票 04b、09），而季號變體對所有劇集都做
（票 14e），查詢長什麼樣子只由作品的快照決定。
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from itertools import zip_longest

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceError
from berth.adapters.indexer import IndexerResult, IndexerSearch, SearchQuery
from berth.domain import (
    IndexerProblem,
    MappingStrategy,
    MediaSnapshot,
    NameKind,
    ParseContext,
    SearchVerdict,
    SeasonSnapshot,
    StepFailure,
    StepStatus,
    Tags,
)
from berth.models import IndexerSettings, SearchSettings, SetupSettings
from berth.parser import (
    map_episode,
    mentions,
    misfit,
    parse_release,
    partial_title,
    tags_of,
    typed_fits,
)
from berth.parser.structure import StructureHints
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.jobs import JobSource
from berth.services.media import read_media, read_snapshot
from berth.services.search_queries import (
    MAX_QUERIES,
    QueryBatch,
    QueryChoice,
    SearchName,
    chosen_names,
    default_choice,
    missing_batches,
    search_names,
    season_numbers,
    title_queries,
)
from berth.services.settings import read_settings, update_settings
from berth.services.sources import SourceCache
from berth.services.steps import StepView, failure_of, message

#: 送給畫面的筆數上限（「符合」與自己打字時的「對得上」）。實測一次搜尋去重後有 1854 筆——全部送出去
#: 是一份 1–2 MB 的 JSON，而 390px 的手機上沒有人捲得完。取 100 筆，總數另外報（票 08 拍板）。
RESULT_LIMIT = 100

#: 其餘每一類各送幾筆（M4 票 83，使用者確認 shape）。它們預設不顯示，按了才看；六類全滿最多
#: 100 + 5 × 50 = 350 列（約 220 KB），解析每筆 14 毫秒，最壞比票 83 之前的 200 列多兩秒。
#: The Pirate Bay 對查不到的字回的熱門清單常常一百筆，所以「名字對不上」看得到的是做種前 50 筆。
OTHERS_LIMIT = 50

#: 單一查詢的上限。adapter 自己也有 HTTP 逾時，這一層是**整次搜尋的保證**：
#: 換一個逾時寬鬆的 adapter 進來時，畫面等待的時間仍然有一個說得出口的上限。
QUERY_TIMEOUT_SECONDS = 150.0

#: Newznab 的成人分類（`XXX` 6000 與它的子分類 6010–6090，Prowlarr `NewznabStandardCategory`）。
#: Prowlarr 回的 `categories` 帶站定義映射到的標準碼，The Pirate Bay 的 Porn 映射到這裡
#: （brief §20.19）。
ADULT_CATEGORIES = range(6000, 7000)


@dataclass(frozen=True, slots=True)
class QueryScope:
    """要問哪些：開了的名字與季，與缺集搜尋的範圍。預覽與搜尋拿同一份組查詢（票 10、84）。"""

    #: 使用者在 chip 上開了的（M4 票 84）。`None` 是沒帶：取預設（`default_choice`）。
    choice: QueryChoice | None = None
    #: 從季表的缺集開始搜（M1.5 票 10）。
    missing: bool = False
    #: 缺集搜尋再收到這一季。
    season: int | None = None
    #: 缺集分批時這一批從哪一季起（M3 票 20，`BatchView`）。
    from_season: int = 0


#: 沒帶 `scope`：記住的名字種類與預設的季，整部作品搜。
DEFAULT_SCOPE = QueryScope()


@dataclass(frozen=True, slots=True)
class SearchResult:
    """結果表的一列（brief §13：大小、做種、來源、解析出的 tags、預估匹配）。"""

    #: 發佈名，原樣。解析器讀的就是它，所以畫面也顯示同一串字——判斷與證據要對得起來。
    title: str
    indexer: str
    size: int
    seeders: int | None
    #: 站上的頁面。使用者要自己看一眼時連過去。
    info_url: str
    #: 送單時帶的 id（`SourceCache`，M4 票 79）。下載連結是 Prowlarr 的代理網址、帶著它的 API key，
    #: 所以記在伺服器上，這一列只有換得回它的 id。
    source_id: str
    #: 這一列的身分（info hash 或 guid）。前端畫列表用它。**不是送單的 hash**：不報 hash 的站
    #: （實測 ACG.RIP）那一格是 guid，`source_id` 記的是索引站真的報了的那一個（票 09）。
    key: str
    #: `parse_release` 認出來、之後會進檔名的那幾格（brief §6.8）。
    tags: Tags
    #: 預估季集。三者皆 `None` = 判斷不出來，畫面就說判斷不出來，不猜。
    season: int | None
    episode_start: int | None
    episode_end: int | None
    #: 這個範圍蓋掉那一季 TMDB 已知的每一集——畫面才說得出「S03 全季」而不是「S03E01–E13」。
    whole_season: bool
    #: 季集是怎麼算出來的。電影靠它說得出「這一格沒有季集是因為它是電影」，而不是留白。
    strategy: MappingStrategy | None
    #: 索引站報的發佈時間（brief §20.11）。結果表的「發佈」欄，送單時跟著 Job 存下來比播出日
    #: （M3 票 14）。那個站沒報是 `None`。
    published_at: datetime | None
    #: 這一筆歸到哪一類（M4 票 83，`_judge`）。畫面上不是「符合」的那幾類預設不顯示。
    verdict: SearchVerdict
    #: 歸到那一類的證據：發佈名裡的那一段字（`S04E02`、`- 05`、`1990`、`Law and Order SVU`）或
    #: 成人分類的碼（`6040`）。符合、名字對不上與自己打字的兩類是空字串：打的字不是發佈名裡的一段，
    #: 畫面用它自己送出的那串字。畫面那一句話引它，不翻。
    evidence: str


@dataclass(frozen=True, slots=True)
class VerdictCount:
    """一類在一站有幾筆（M4 票 83）。是總數不是送出來的筆數：畫面的按鈕在「只看某個站」時
    數字跟著變，而送出來的只是每類逐站輪流取的前幾筆。"""

    verdict: SearchVerdict
    indexer: str
    total: int


@dataclass(frozen=True, slots=True)
class Judged:
    """索引站回的一筆與它歸到的那一類（`_judge`）。"""

    result: IndexerResult
    verdict: SearchVerdict
    evidence: str = ""


@dataclass(frozen=True, slots=True)
class SearchView:
    """一次搜尋的整份形狀。

    **失敗也是 200**（與探索頁同一個道理，票 03）：索引站是精靈裡唯一可以跳過的一步，
    所以「沒接」「接了但連不上」「接上了但這個關鍵字沒東西」是三件不同的事，
    而它們的下一步完全不同。做成 HTTP 錯誤的話畫面只剩一個狀態碼。
    """

    #: 每一類各自逐站輪流取（`_take`）之後合在一起，照 `SearchVerdict` 的順序一類接一類：「符合」與
    #: 「對得上」取 `RESULT_LIMIT` 筆，其餘每類 `OTHERS_LIMIT` 筆。
    #: **每一類都送、不藏起來**（M4 票 83，照 Sonarr 互動搜尋）：判斷只看發佈名，可能看錯，而
    #: 「索引站什麼都沒回」與「回了一千八百筆但沒有一筆是這部作品」的下一步不同。
    rows: tuple[SearchResult, ...]
    #: 實際問出去的關鍵字與逐個的成敗。形狀與精靈的纜繩一樣——同一件事同一種說法。
    attempts: tuple[StepView, ...]
    #: 每一類在每一站的總筆數（`VerdictCount`）。是 0 的那一組不列。
    counts: tuple[VerdictCount, ...] = ()
    #: 每個查詢回的筆數加起來（M4 票 69）。畫面上的幾個數字照這一條加得起來：
    #: `returned = merged + Σ counts.total`。
    returned: int = 0
    #: 不同查詢（或不同站）回了同一個發佈，合併掉的筆數（`_dedupe`）。不叫 duplicates：
    #: CONTEXT.md 的 **Duplicate** 是帳本裡的重複版本。
    merged: int = 0
    problem: IndexerProblem | None = None
    #: 失敗時服務回的原文（英文），與精靈的纜繩同一個規矩。
    detail: str = ""
    #: 缺集搜尋時問的這一批。作品名與自己打的關鍵字沒有批次，是 `None`。
    batch: BatchView | None = None


@dataclass(frozen=True, slots=True)
class BatchView:
    """缺集搜尋的這一批（M3 票 20）：畫面說得出「這一批問了哪幾季，下一批是哪幾季」。

    **批次以季定位，不以序號**：下一批是「從 `next_seasons[0]` 那一季起還缺的」，照那一刻的
    季表重切。以序號定位的話，問完第一批、從結果送了幾季之後季表就變了，第二批會落到別的季、甚至漏掉一季
    （code review 抓到）。
    """

    seasons: tuple[int, ...]
    #: 這一批之後還有幾批（照現在的季表算）。
    later: int = 0
    #: 下一批問哪幾季；這是最後一批時是空的。
    next_seasons: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class QueryPlan:
    """按下搜尋之前畫面要說的：會問哪幾個名字，以及不必問索引站就知道的問題。"""

    queries: tuple[str, ...]
    #: 只有 `NOT_CONFIGURED`（M2 票 13）：預覽不打索引站，連不上、憑證錯要按下去才知道。
    problem: IndexerProblem | None = None
    #: 缺集搜尋時要問的這一批（M3 票 20）。
    batch: BatchView | None = None
    #: 名字 chip（M4 票 84）：這部作品的每一個名字與它是哪幾種。快照還沒讀到時是空的。
    names: tuple[SearchName, ...] = ()
    #: 逐季 chip 的那幾季（`season_numbers`）。
    seasons: tuple[int, ...] = ()
    #: 這一次開著的：呼叫端帶來的那一份，沒帶就是預設（`default_choice`）。
    choice: QueryChoice = field(default_factory=lambda: QueryChoice(names=()))
    #: 一次最多幾個查詢；`queries` 比它多時搜尋整次不問（`TOO_MANY_QUERIES`）。
    limit: int = MAX_QUERIES


async def plan_queries(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    media_id: str,
    scope: QueryScope = DEFAULT_SCOPE,
) -> QueryPlan:
    """按下搜尋之前，Berth 會拿哪幾個名字去問（PRODUCT 原則 2：動手前先給看）。

    存在的理由是**這條規則只能有一份實作**：查詢要看快照的名字與季數（`search_queries`），前端重算
    一份遲早會在兩邊長出不同的答案。不打索引站，只讀快照與記住的名字種類。

    `scope` 與真的送出去的那幾個查詢走同一個 `_texts`，所以畫面上寫的就是待會兒問出去的。

    **沒接索引站時先說**（M2 票 13）：與 `search_torrents` 同一個判準（`_indexer`）。名字照樣列——
    接上之後會問的就是這幾個。
    """
    snapshot = await read_snapshot(session, factory, media_id)
    chosen = scope.choice or await _default(session, snapshot)
    batches, queries = await _texts(session, factory, media_id, snapshot, scope, chosen)
    ready = await _indexer(session) is not None
    return QueryPlan(
        queries,
        None if ready else IndexerProblem.NOT_CONFIGURED,
        _batch(batches),
        names=search_names(snapshot) if snapshot else (),
        seasons=season_numbers(snapshot) if snapshot else (),
        choice=chosen,
    )


@command(Effect.REVERSIBLE, inverse="search.remember_names")
async def remember_names(
    session: AsyncSession, changes: Mapping[NameKind, bool]
) -> dict[NameKind, bool]:
    """記住哪幾種名字預設開著（M4 票 84）：在一部作品按了中文名，之後每一部打開時中文名都開著。

    **全域、在伺服器上**（票面）：換裝置一樣，任何登入的人按了都算——搜尋本來就是一般使用者做的事。
    只改帶來的那幾種，其餘照舊；回寫回去的整份。別名不記（`NameKind.ALIAS`）：拒絕，不默默丟掉。
    反向命令是它自己：把那一種按回去。
    """
    if NameKind.ALIAS in changes:
        raise ValueError("aliases have no language, so they are not remembered")

    def apply(settings: SearchSettings) -> None:
        settings.names = {**settings.names, **changes}

    return (await update_settings(session, SearchSettings, apply)).names


async def _default(session: AsyncSession, snapshot: MediaSnapshot | None) -> QueryChoice:
    """沒帶 `choice` 時開著哪些：記住的名字種類，加上預設的季（`default_choice`）。"""
    if snapshot is None:
        return QueryChoice(names=())
    return default_choice(snapshot, (await read_settings(session, SearchSettings)).names)


async def _texts(
    session: AsyncSession,
    factory: ServiceClientFactory,
    media_id: str,
    snapshot: MediaSnapshot | None,
    scope: QueryScope,
    chosen: QueryChoice,
) -> tuple[tuple[QueryBatch, ...], tuple[str, ...]]:
    """要問的查詢（與缺集時的每一批）。預覽與搜尋共用**這一份**（票 10、84）。

    `chosen` 是 `scope.choice` 補上預設之後的那一份：呼叫端自己也要它（預覽回給畫面）。
    """
    if snapshot is None:
        return (), ()
    if not scope.missing:
        return (), title_queries(snapshot, chosen)
    names = chosen_names(snapshot, chosen)
    batches = await _missing(session, factory, media_id, names, scope.season, scope.from_season)
    return batches, (batches[0].queries if batches else ())


async def _indexer(session: AsyncSession) -> IndexerSettings | None:
    """接好的索引站設定；精靈第 6 步跳過了或位址是空的時是 `None`。"""
    settings = await read_settings(session, IndexerSettings)
    setup = await read_settings(session, SetupSettings)
    if not settings.base_url or setup.indexer.skipped:
        return None
    return settings


async def _missing(
    session: AsyncSession,
    factory: ServiceClientFactory,
    media_id: str,
    names: tuple[str, ...],
    season: int | None,
    from_season: int,
) -> tuple[QueryBatch, ...]:
    """從 `from_season` 那一季起的每一批，第一個就是這一次要問的。預覽與搜尋共用**一份**（票 10）。

    記號照那幾季重算：只剩兩三季時缺的集可能放得下逐集問，下一批就比預告的「S06、S07」問得更窄，
    季還是那幾季。

    缺集那一種要的是現在的帳本與 Job 說了什麼（`read_media` 的季表），不是快照上的季集——
    快照只知道 TMDB 有幾集，缺哪幾集是這一台機器上的事。
    """
    # 快照由呼叫端讀過了（那一趟已經套過 24 小時的規則），所以這一趟只讀資料庫，不打 TMDB。
    view = await read_media(session, factory, media_id)
    later = [row for row in view.seasons if row.season_number >= from_season]
    return missing_batches(names, later, season=season)


def _batch(batches: tuple[QueryBatch, ...]) -> BatchView | None:
    """畫面上那一行：這一批（第一個）問哪幾季、之後還有幾批、下一批是哪幾季。"""
    if not batches:
        return None
    return BatchView(
        seasons=batches[0].seasons,
        later=len(batches) - 1,
        next_seasons=batches[1].seasons if len(batches) > 1 else (),
    )


async def search_torrents(
    session: AsyncSession,
    factory: ServiceClientFactory,
    sources: SourceCache,
    *,
    media_id: str,
    query: str = "",
    scope: QueryScope = DEFAULT_SCOPE,
    timeout: float = QUERY_TIMEOUT_SECONDS,
) -> SearchView:
    """一部作品現在有哪些發佈可以下載。

    `query` 有值時取代 `scope`，只問這一個。`scope` 組出來的查詢比 `MAX_QUERIES` 多時
    **整次不問**（`TOO_MANY_QUERIES`），不砍尾巴——名字與季是使用者自己開的，默默少問幾個
    等於替他做了決定。

    **不限定站**：查詢問 Prowlarr 啟用中的每一站；各站多久能問幾次是 Prowlarr 的 Query Limit 的事
    （M4 票 107 刪掉 Berth 自己那一份請求預算）。

    **每一列的下載連結記進 `sources`**（M4 票 79）：送出去的列只帶換得回它的 id。
    """
    settings = await _indexer(session)
    if settings is None:
        return _blank(IndexerProblem.NOT_CONFIGURED)

    snapshot = await read_snapshot(session, factory, media_id)
    typed = query.strip()
    batches: tuple[QueryBatch, ...] = ()
    judge: Callable[[IndexerResult], Judged]
    if typed:
        texts: tuple[str, ...] = (typed,)
        # 自己打了關鍵字時只判對不對得上那串字，不判是不是這部作品（票 08、M4 票 83b）。
        judge = partial(_judge_typed, typed=typed, snapshot=snapshot)
    elif snapshot is None:
        # Berth 還不知道這部作品叫什麼：沒有名字可問。
        return _blank(IndexerProblem.NO_QUERY)
    else:
        chosen = scope.choice or await _default(session, snapshot)
        batches, texts = await _texts(session, factory, media_id, snapshot, scope, chosen)
        judge = partial(_judge, snapshot=snapshot)
    if not texts:
        return _blank(IndexerProblem.NO_QUERY)
    if len(texts) > MAX_QUERIES:
        return _blank(IndexerProblem.TOO_MANY_QUERIES)

    client = factory.indexer_search(settings.base_url, settings.api_key)
    try:
        queries = tuple(SearchQuery(text=text) for text in texts)
        outcomes = await asyncio.gather(*(_attempt(client, item, timeout) for item in queries))
    finally:
        await client.aclose()

    errors = [error for _, _, error in outcomes if error is not None]
    if len(errors) == len(outcomes):
        # 每一個查詢都被索引站本身拒絕（連不上、憑證被拒）：這台 Prowlarr 現在整個問不動，畫面要說的
        # 是連線，不是一排紅色的纜繩。逾時不算——那是索引站在、背後的站慢。
        return _blank(_problem(errors[0]), message(errors[0]))
    returned = [row for _, rows, _ in outcomes for row in rows]
    found = _dedupe(returned)
    judged = [judge(result) for result in found]
    return SearchView(
        rows=_rows(judged, snapshot, sources),
        counts=_counts(judged),
        returned=len(returned),
        merged=len(returned) - len(found),
        attempts=tuple(attempt for attempt, _, _ in outcomes),
        batch=_batch(batches),
    )


def _take(results: Sequence[Judged], limit: int) -> list[Judged]:
    """上限內盡量讓每個站都出現：逐站輪流取，站內照做種由多到少。

    純粹取做種前 100 筆會**把中文字幕組整批刪掉**：2026-09-10 實跑搜 SPY×FAMILY，
    The Pirate Bay 的 scene 發佈有 28–86 個做種，而 Mikan 那 1070 筆多半是個位數，
    於是前 100 筆全部來自同一個站——使用者要的 CHT 內嵌版一筆都看不到。

    只有一個站在答時它自己填滿一百筆。
    """
    by_indexer: dict[str, list[Judged]] = {}
    for judged in results:
        by_indexer.setdefault(judged.result.indexer, []).append(judged)
    taken: list[Judged] = []
    for round_ in zip_longest(*by_indexer.values()):
        for judged in round_:
            if judged is not None and len(taken) < limit:
                taken.append(judged)
        if len(taken) >= limit:
            break
    return taken


def _judge(result: IndexerResult, snapshot: MediaSnapshot) -> Judged:
    """這一筆歸到哪一類、證據是哪一段字（M4 票 83）。**先後即判定順序**，證據硬的先：

    1. 名字（`mentions`，純字串）——不是 `parse_release` + `matches`：後者實測每筆 14 毫秒，
       一兩千筆會把事件迴圈卡住半分鐘。精確的解析留給送出去的那幾百筆。
    2. 索引站分在成人類（M4 票 69，審計 S3）：發佈名說不出這件事，分類說得出。分類碼不拿來**查**
       （各站映射自訂，plan §8.4），拿來歸類是因為歸錯了按一下就看得到。
    3. 類型與年份（`parser.misfit`，M4 票 49）：集數記號（不是電影）、年份。
    4. 只對上部分名字（`parser.partial_title`）：最軟的一條——「可能是衍生作品」，放在最後：
       同名動畫的 `Tsuki to Laika to Nosferatu - 05` 片名也包住《Nosferatu》，先判它的話這一筆
       說的會是「名字多一段」，而更硬的證據是 `- 05` 這個集號。
    """
    if not mentions(result.title, snapshot):
        return Judged(result, SearchVerdict.UNRELATED)
    adult = next((code for code in result.categories if code in ADULT_CATEGORIES), None)
    if adult is not None:
        return Judged(result, SearchVerdict.ADULT, str(adult))
    if (found := misfit(result.title, snapshot)) is not None:
        return Judged(result, found.verdict, found.evidence)
    if lead := partial_title(result.title, snapshot):
        return Judged(result, SearchVerdict.PARTIAL_TITLE, lead)
    return Judged(result, SearchVerdict.FITS)


def _judge_typed(result: IndexerResult, *, typed: str, snapshot: MediaSnapshot | None) -> Judged:
    """自己打的關鍵字：只分對得上與對不上（M4 票 83b，`parser.typed_fits`）。年份、類型、成人、
    部分名字一律不判——使用者問的就是那串字。沒有快照時只看打的字。"""
    fits = typed_fits(result.title, typed, snapshot)
    return Judged(result, SearchVerdict.TYPED_MATCH if fits else SearchVerdict.TYPED_MISS)


def _rows(
    judged: Sequence[Judged], snapshot: MediaSnapshot | None, sources: SourceCache
) -> tuple[SearchResult, ...]:
    """每一類各自逐站輪流取，照 `SearchVerdict` 的順序一類接一類。只有送出去的這幾百筆才解析。"""
    return tuple(
        _row(one, snapshot, sources)
        for verdict in SearchVerdict
        for one in _take(
            [one for one in judged if one.verdict is verdict],
            RESULT_LIMIT if verdict in _LISTED else OTHERS_LIMIT,
        )
    )


#: 畫面預設就列出來的那一類（照作品名搜是「符合」，自己打字是「對得上」），送 `RESULT_LIMIT` 筆；
#: 其餘按了才看，送 `OTHERS_LIMIT` 筆。
_LISTED = frozenset({SearchVerdict.FITS, SearchVerdict.TYPED_MATCH})


def _counts(judged: Sequence[Judged]) -> tuple[VerdictCount, ...]:
    """每一類在每一站的總筆數，照 `SearchVerdict` 的順序、站名照第一次出現的順序。"""
    tally = Counter((one.verdict, one.result.indexer) for one in judged)
    return tuple(
        VerdictCount(verdict=verdict, indexer=indexer, total=tally[(verdict, indexer)])
        for verdict in SearchVerdict
        for (seen, indexer) in tally
        if seen is verdict
    )


async def _attempt(
    client: IndexerSearch, query: SearchQuery, timeout: float
) -> tuple[StepView, tuple[IndexerResult, ...], ServiceError | None]:
    """一個查詢，一條纜繩；第三格是索引站丟的例外（逾時與成功是 `None`）。

    **失敗不往上冒**：十個公開站裡有幾個連不上是常態（brief §20.7），一個關鍵字問不動時
    另外四個的結果仍然值得看。垮掉的那一個變成一條紅色的纜繩，不是一片空白。
    """
    step = query.text
    try:
        async with asyncio.timeout(timeout):
            rows = await client.search(query)
    except TimeoutError:
        return (
            StepView(
                step=step,
                status=StepStatus.FAILED,
                detail="",
                error=f"the indexer did not answer within {timeout:.0f}s",
                failure=StepFailure.UNREACHABLE,
            ),
            (),
            None,
        )
    except ServiceError as exc:
        failure, params = failure_of(exc)
        failed = StepView(
            step=step,
            status=StepStatus.FAILED,
            detail="",
            error=message(exc),
            failure=failure,
            params=params,
        )
        return (failed, (), exc)
    return (
        StepView(step=step, status=StepStatus.OK, detail=str(len(rows)), error=""),
        rows,
        None,
    )


def _dedupe(results: Iterable[IndexerResult]) -> list[IndexerResult]:
    """合併去重，然後把做種最多的排到前面。

    同一個 key 保留**先看到的那一筆**：查詢是照 chip 的順序發的（`search_queries`，名字優先），
    所以先看到的來自更可靠的那個名字。做種數相同時保留原順序（`sorted` 穩定，`reverse=True`
    不動同分的相對順序），沒有做種數的排最後——「那個站沒報」不該冒充「零個人做種」擠到底，
    但它也拿不出理由排前面。
    """
    seen: dict[str, IndexerResult] = {}
    for result in results:
        seen.setdefault(result.key, result)
    return sorted(
        seen.values(), key=lambda row: -1 if row.seeders is None else row.seeders, reverse=True
    )


@dataclass(frozen=True, slots=True)
class Estimate:
    """只看發佈名估的季集（`SearchResult` 那幾格的意思）。三者皆 `None` = 判斷不出來。"""

    season: int | None
    episode_start: int | None
    episode_end: int | None
    whole_season: bool
    strategy: MappingStrategy | None


def estimate(title: str, published_at: datetime | None, snapshot: MediaSnapshot | None) -> Estimate:
    """一個發佈名 → 預估季集。結果表與一次性 RSS 連結（M3 票 18）共用。

    解析只看發佈名：這時候還沒有 torrent 的檔案清單（那要等送單之後 qBittorrent 才報得出
    內容），所以 `StructureHints` 是空的——路徑上一句話都還沒說。預估因此比入庫時的判斷粗，
    而那正是它叫「預估」的理由。發佈時間跟著走：送單之後規劃也拿同一個時間推測虛擬季（M3 票 16）。
    """
    context = ParseContext(
        media=snapshot,
        published_at=published_at,
    )
    candidates = map_episode(parse_release(title), StructureHints(), context, release_name=title)
    best = candidates[0] if candidates else None
    season = best.season if best is not None else None
    start = best.episode_start if best is not None else None
    # `map_episode` 的 `episode_end` 只在區間時有值，單集是 `None`。這裡補成與 `start` 相同：
    # 畫面要分的是「單集 / 區間 / 判斷不出來」，而 `None` 在這裡同時代表後兩者。
    end = (best.episode_end or start) if best is not None else None
    return Estimate(
        season=season,
        episode_start=start,
        episode_end=end,
        whole_season=_whole_season(snapshot, season, start, end),
        strategy=best.strategy if best is not None else None,
    )


def _row(judged: Judged, snapshot: MediaSnapshot | None, sources: SourceCache) -> SearchResult:
    """索引站回的一列 → 結果表的一列。下載連結留在 `sources`，這一列帶它的 id。"""
    result = judged.result
    guess = estimate(result.title, result.published_at, snapshot)
    return SearchResult(
        title=result.title,
        indexer=result.indexer,
        size=result.size,
        seeders=result.seeders,
        info_url=result.info_url,
        source_id=sources.remember(
            JobSource(
                url=result.download_url,
                title=result.title,
                info_hash=result.info_hash,
                published_at=result.published_at,
                size=result.size,
            )
        ),
        key=result.key,
        tags=tags_of(parse_release(result.title)),
        season=guess.season,
        episode_start=guess.episode_start,
        episode_end=guess.episode_end,
        whole_season=guess.whole_season,
        strategy=guess.strategy,
        published_at=result.published_at,
        verdict=judged.verdict,
        evidence=judged.evidence,
    )


def _whole_season(
    snapshot: MediaSnapshot | None, season: int | None, start: int | None, end: int | None
) -> bool:
    """這個範圍蓋掉那一季 TMDB 已知的每一集嗎。

    比的是**已知集數**而不是檔名寫的字：`[01-13Fin]` 的 `Fin` 是字幕組說的，而 TMDB 說
    那一季有幾集。兩者不合時信 TMDB——它才是入庫之後 Jellyfin 會對照的那一份。
    """
    if snapshot is None or season is None or start != 1 or end is None:
        return False
    rows = next((row for row in snapshot.seasons if row.season_number == season), None)
    if rows is None:
        return False
    known = _known_episodes(rows)
    # TMDB 還不知道這一季有幾集時說不出「全季」——那是一句沒有根據的話。
    return known > 0 and end >= known


def _known_episodes(season: SeasonSnapshot) -> int:
    """TMDB 對這一季報的集數。兩個來源取大的——未播的集數已經先列進 `episode_count`，
    而 `episodes` 偶爾比它多（TMDB 加了集但沒更新計數）。都是 0 就是「還不知道」。"""
    return max(season.episode_count, len(season.episodes))


def _problem(exc: ServiceError) -> IndexerProblem:
    """憑證被拒與連不上的下一步不同：前者去精靈第 6 步改 key，後者只能等或查網路。"""
    return (
        IndexerProblem.CREDENTIAL_REJECTED
        if isinstance(exc, AuthFailedError)
        else IndexerProblem.UNREACHABLE
    )


def _blank(problem: IndexerProblem, detail: str = "") -> SearchView:
    """沒有結果的那幾種。`detail` 只放**服務回的原文**——沒有服務答話的那幾種就是空的，
    畫面上那句話由 `problem` 決定，不靠這一欄拼湊。"""
    return SearchView(rows=(), attempts=(), problem=problem, detail=detail)
