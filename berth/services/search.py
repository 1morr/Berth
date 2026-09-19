"""索引站搜尋（plan §6 search 群組、§8.4、brief §13、票 08）。

這是使用者第一次看見解析器的判斷。一次搜尋做四件事，順序不能換：

1. **一部作品有好幾個名字**，所以查詢不只一個。英文、原文與各語言別名各發一次，播到第二季
   以後的劇集另加季號變體。2026-09-10 實測 SPY×FAMILY 的三個標題各自搜出 1200 / 908 / 1210 筆，
   聯集 1854 筆——每一個標題都帶來另外兩個問不到的東西（各 391 / 196 / 169 筆）。
2. **併發**。單一聚合查詢實測 60–85 秒（Prowlarr 要現場去連五個追蹤站），三個查詢併發
   共 35 秒——逐個問會變成三分鐘。一個查詢垮掉時剩下的照樣回得來（票 08 驗收）。
3. **合併去重，然後把對不上這部作品的丟掉**。去重的鑰匙是 info hash，寫法正規化過
   （同一個發佈在 Mikan 是十六進位、在 dmhy 是 base32，實測單次查詢的 1200 筆裡有 47 筆是
   這樣重複的）。丟掉那一步是實跑逼出來的：**The Pirate Bay 對搜不到的關鍵字會回它的熱門
   清單**，而那些東西動輒五六千個做種，會把真正的結果整批擠出前 100 筆（2026-09-10 搜
   SPY×FAMILY，前六筆是 Spider-Man、Ted Lasso、Reacher）。丟掉幾筆另外報，不藏起來。
4. **逐筆問解析器**。`parse_release` 給 Tags、`map_episode` 給預估季集，兩者都是純函式，
   所以這一步不打任何服務。

搜尋不看 Route：入庫到哪一條是送單時才決定的事（票 04b、09），而季號變體對所有劇集都做
（票 14e），查詢長什麼樣子只由作品的快照決定。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import zip_longest

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceError
from berth.adapters.indexer import IndexerResult, IndexerSearch, SearchQuery
from berth.domain import (
    EpisodeStatus,
    IndexerKind,
    IndexerProblem,
    MappingStrategy,
    MediaKind,
    MediaSnapshot,
    ParseContext,
    SeasonSnapshot,
    StepStatus,
    Tags,
    collection_type_for,
)
from berth.models import IndexerSettings, SetupSettings
from berth.parser import map_episode, mentions, parse_release, tags_of
from berth.parser.structure import StructureHints
from berth.services.clients import ServiceClientFactory
from berth.services.inventory import EpisodeView, SeasonView
from berth.services.media import read_media, read_snapshot
from berth.services.settings import read_settings
from berth.services.steps import StepView, message

#: 一次搜尋最多發幾個查詢。每一個都是「請這台索引站現場去連它認得的每一個追蹤站」，
#: 所以上限不是為了省 Berth 的力氣，是為了不要替使用者把那些公開站打到封 IP。
#: 五個涵蓋英文 + 原文 + 兩三個別名，或英文 + 原文 + 顯示用標題 + 兩個季號變體。
MAX_QUERIES = 5

#: 送給畫面的筆數上限。實測一次搜尋去重後有 1854 筆——全部送出去是一份 1–2 MB 的 JSON，
#: 而 390px 的手機上沒有人捲得完。取 100 筆，總數另外報（票 08 拍板）。
RESULT_LIMIT = 100

#: 單一查詢的上限。adapter 自己也有 HTTP 逾時，這一層是**整次搜尋的保證**：
#: 換一個逾時寬鬆的 adapter 進來時，畫面等待的時間仍然有一個說得出口的上限。
QUERY_TIMEOUT_SECONDS = 150.0


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
    #: 送單時要交給 qBittorrent 的那一條（票 09）。
    download_url: str
    #: 這一列的身分（info hash 或 guid）。前端畫列表用它。
    key: str
    #: 索引站報的 info hash，**只有真的是 hash 時才有值**。送單拿它短路重複檢查（票 09）——
    #: `key` 不行：不報 hash 的站（實測 ACG.RIP）那一格是 guid，拿去當 hash 是在說謊。
    info_hash: str
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


@dataclass(frozen=True, slots=True)
class SearchView:
    """一次搜尋的整份形狀。

    **失敗也是 200**（與探索頁同一個道理，票 03）：索引站是精靈裡唯一可以跳過的一步，
    所以「沒接」「接了但連不上」「接上了但這個關鍵字沒東西」是三件不同的事，
    而它們的下一步完全不同。做成 HTTP 錯誤的話畫面只剩一個狀態碼。
    """

    rows: tuple[SearchResult, ...]
    #: 對得上這部作品的總筆數。`rows` 只有其中的前 `RESULT_LIMIT` 筆，逐站輪流取（`_take`）。
    total: int
    #: 實際問出去的關鍵字與逐個的成敗。形狀與精靈的纜繩一樣——同一件事同一種說法。
    attempts: tuple[StepView, ...]
    #: 索引站回了、但名字對不上這部作品的筆數。**不藏起來**：「索引站什麼都沒回」與
    #: 「回了一千八百筆但沒有一筆是這部作品」的下一步不同（前者換關鍵字，後者換索引站）。
    discarded: int = 0
    problem: IndexerProblem | None = None
    #: 失敗時服務回的原文（英文），與精靈的纜繩同一個規矩。
    detail: str = ""


async def plan_queries(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    media_id: str,
    missing: bool = False,
    season: int | None = None,
) -> tuple[str, ...]:
    """按下搜尋之前，Berth 會拿哪幾個名字去問（PRODUCT 原則 2：動手前先給看）。

    存在的理由是**這條規則只能有一份實作**：`search_titles` 要看快照的標題集合與季數，前端重算
    一份的話「第二季以後多兩個季號變體」遲早會在兩邊長出不同的答案。不打索引站，只讀快照。

    `missing` 是缺集一鍵搜（M1.5 票 10）：預覽與真的送出去的那幾個查詢走同一個 `_texts`，
    所以畫面上寫的就是待會兒問出去的。
    """
    snapshot = await read_snapshot(session, factory, media_id)
    return await _texts(session, factory, media_id, snapshot, missing=missing, season=season)


async def _texts(
    session: AsyncSession,
    factory: ServiceClientFactory,
    media_id: str,
    snapshot: MediaSnapshot | None,
    *,
    missing: bool,
    season: int | None,
) -> tuple[str, ...]:
    """這一次要問的那幾個關鍵字。預覽與搜尋共用**一份**（票 10）。

    缺集那一種要的是現在的帳本與 Job 說了什麼（`read_media` 的季表），不是快照上的季集——
    快照只知道 TMDB 有幾集，缺哪幾集是這一台機器上的事。
    """
    if not missing:
        return search_titles(snapshot)
    # 快照由呼叫端讀過了（那一趟已經套過 24 小時的規則），所以這一趟只讀資料庫，不打 TMDB。
    view = await read_media(session, factory, media_id)
    return missing_queries(snapshot, view.seasons, season=season)


async def search_torrents(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    media_id: str,
    query: str = "",
    missing: bool = False,
    season: int | None = None,
    timeout: float = QUERY_TIMEOUT_SECONDS,
) -> SearchView:
    """一部作品現在有哪些發佈可以下載。

    `missing` 是從季表的缺集開始搜（M1.5 票 10），`season` 再把範圍收到那一季。
    """
    settings = await read_settings(session, IndexerSettings)
    setup = await read_settings(session, SetupSettings)
    if not settings.base_url or setup.indexer.skipped:
        return _blank(IndexerProblem.NOT_CONFIGURED)

    snapshot = await read_snapshot(session, factory, media_id)
    typed = query.strip()
    narrowed = missing and not typed
    texts = (
        (typed,)
        if typed
        else await _texts(session, factory, media_id, snapshot, missing=missing, season=season)
    )
    if not texts:
        return _blank(IndexerProblem.NO_QUERY)

    client = factory.indexer_search(IndexerKind(settings.kind), settings.base_url, settings.api_key)
    try:
        capability = await client.capabilities()
        if not capability.searchable:
            return _blank(IndexerProblem.NO_SEARCH)
        # 缺集搜尋不走 id 那條路：id 找的是**整部作品**，收窄到缺的那幾集就沒了，
        # 而預覽已經告訴使用者要問那幾集（票 10）。
        queries = _queries(texts, snapshot, frozenset() if narrowed else capability.tmdb_id)
        outcomes = await asyncio.gather(
            *(_attempt(client, item, timeout) for item in queries), return_exceptions=False
        )
    except ServiceError as exc:
        # `capabilities()` 垮掉是「這個端點現在整個問不動」，與逐查詢的失敗不同：
        # 那時候一個關鍵字都還沒問出去，所以畫面要說的是連線，不是搜尋結果。
        return _blank(_problem(exc), message(exc))
    finally:
        await client.aclose()

    found = _dedupe(row for _, rows in outcomes for row in rows)
    # 自己打了關鍵字時不篩：他要的就是那一串字，不是這部作品（票 08）。
    results = found if query.strip() else [row for row in found if _about(row, snapshot)]
    context = _context(snapshot)
    return SearchView(
        rows=tuple(_row(result, snapshot, context) for result in _take(results, RESULT_LIMIT)),
        total=len(results),
        discarded=len(found) - len(results),
        attempts=tuple(attempt for attempt, _ in outcomes),
    )


def _take(results: Sequence[IndexerResult], limit: int) -> list[IndexerResult]:
    """上限內盡量讓每個站都出現：逐站輪流取，站內照做種由多到少。

    純粹取做種前 100 筆會**把中文字幕組整批刪掉**：2026-09-10 實跑搜 SPY×FAMILY，
    The Pirate Bay 的 scene 發佈有 28–86 個做種，而 Mikan 那 1070 筆多半是個位數，
    於是前 100 筆全部來自同一個站——使用者要的 CHT 內嵌版一筆都看不到。

    輪流取也照顧單一 Torznab 端點：只有一個站在答時它自己填滿一百筆。
    """
    by_indexer: dict[str, list[IndexerResult]] = {}
    for result in results:
        by_indexer.setdefault(result.indexer, []).append(result)
    taken: list[IndexerResult] = []
    for round_ in zip_longest(*by_indexer.values()):
        for result in round_:
            if result is not None and len(taken) < limit:
                taken.append(result)
        if len(taken) >= limit:
            break
    return taken


def _about(result: IndexerResult, snapshot: MediaSnapshot | None) -> bool:
    """這一筆是這部作品嗎。

    粗篩用 `mentions`（純字串），不是 `parse_release` + `matches`——後者實測每筆 14 毫秒，
    一兩千筆會把事件迴圈卡住半分鐘。精確的那一份判斷留給活下來的一百筆。

    沒有快照時不篩：那時候 Berth 根本不知道這部作品叫什麼，篩了等於全丟。
    """
    return snapshot is None or mentions(result.title, snapshot)


def search_titles(snapshot: MediaSnapshot | None) -> tuple[str, ...]:
    """這部作品要用哪幾個名字去問（plan §8.4）。

    順序即優先序，因為 `MAX_QUERIES` 會從尾巴砍：英文標題（檔名用的那一個，brief §7.5）、
    原文標題、**顯示用標題**，然後才是其餘別名——2026-09-10 實測三個標題各自帶來
    391 / 196 / 169 筆另外兩個問不到的結果，所以「多一個名字」是真的多一批東西，
    不是重複發同一個請求。

    顯示用標題要**明確**排在第三而不是跟著 `titles` 走：TMDB 的 `alternative_titles` 沒有
    順序可言，照收的話由它決定誰進得了前五名。實測 SPY×FAMILY 就是這樣把 `Agent x Ailə`
    （亞塞拜然語）排到中文標題前面——而使用者的索引站上是中文字幕組（票 08 實跑）。
    """
    if snapshot is None:
        return ()
    variants = _season_variants(snapshot)
    titles = _title_order(snapshot)
    # 季號變體**佔掉的是排最後的別名**，不是額外的配額。上限管的是「那些公開站被問幾次」，
    # 而找最新一季時「第 N 季」比第四個羅馬拼音別名更可能命中（plan §8.4）。
    return _unique([*titles[: MAX_QUERIES - len(variants)], *variants])


def missing_queries(
    snapshot: MediaSnapshot | None, seasons: Sequence[SeasonView], *, season: int | None = None
) -> tuple[str, ...]:
    """季表上缺的那幾集要拿哪幾個名字去問（M1.5 票 10、plan §6）。

    季表已經知道缺哪幾集，所以搜尋不必再從作品名開始。查詢是**標題 × 記號**，記號由缺的形狀
    決定（使用者 2026-09-19 拍板）：

    - **整季缺**（那一季播出了的每一集都缺）→ 一個季記號 `S03`。
    - **缺幾集 / 缺一集** → 一集一個記號：TMDB 給了絕對編號就用它（兩位數補零，照 Sonarr 的
      動漫查詢），否則 `S03E05`。有絕對編號的作品，發佈就是照絕對編號編的——`S02E01` 在那些
      站上一筆都搜不到；反過來也一樣，所以**一集只有一個記號**，兩種都送會讓記號數加倍。
    - 記號放不下 `MAX_QUERIES` 時逐級退：先整批收成季記號，季記號也放不下就退回作品名
      （`search_titles`，今天的行為）。

    展開成查詢時**標題優先**：第一個標題先問完它的每一個記號，缺的每一集才至少都被問過一次。
    `season` 有值時只看那一季（展開區那一顆按鈕）。沒有缺集就回空的——不退回作品名，
    使用者按的是「搜缺的集」。
    """
    if snapshot is None:
        return ()
    if season is not None:
        seasons = [row for row in seasons if row.season_number == season]
    tokens = tuple(token for row in seasons for token in _season_tokens(row))
    if len(tokens) > MAX_QUERIES:
        # 逐集放不下就整批收成季記號：問前五集等於默默漏掉其餘那幾集，而使用者按的是
        # 「搜缺的集」。收窄到季之後那一季的發佈都回得來，逐集交給結果表的預估去分。
        tokens = tuple(f"S{row.season_number:02d}" for row in seasons if _gaps(row))
    if len(tokens) > MAX_QUERIES:
        # 連季記號都放不下（六季以上有缺）：沒有東西收窄得了，退回作品名。
        return search_titles(snapshot)
    return _unique(f"{title} {token}" for title in _title_order(snapshot) for token in tokens)[
        :MAX_QUERIES
    ]


def _season_tokens(season: SeasonView) -> tuple[str, ...]:
    """這一季缺的那幾集寫成記號。整季都缺時是一個季記號，否則一集一個。"""
    gaps = _gaps(season)
    if not gaps:
        return ()
    if len(gaps) == season.aired:
        return (f"S{season.season_number:02d}",)
    return tuple(_episode_token(season.season_number, episode) for episode in gaps)


def _gaps(season: SeasonView) -> list[EpisodeView]:
    """這一季缺的那幾集。**判定在後端一處**（`EpisodeStatus.MISSING`：已經播了、沒有任何
    下載在處理它），季表上的「只看缺集」數的也是它。"""
    return [episode for episode in season.episodes if episode.status is EpisodeStatus.MISSING]


def _episode_token(season_number: int, episode: EpisodeView) -> str:
    """一集一個記號：有絕對編號就用它（兩位數補零，照 Sonarr 的動漫查詢），否則 `S03E05`。"""
    if episode.absolute_number is not None:
        return f"{episode.absolute_number:02d}"
    return f"S{season_number:02d}E{episode.episode_number:02d}"


def _title_order(snapshot: MediaSnapshot) -> tuple[str, ...]:
    """這部作品的名字，照優先序（理由見 `search_titles`）。作品名搜尋與缺集搜尋共用同一份順序。"""
    return _unique([snapshot.title_en, snapshot.title_original, snapshot.title, *snapshot.titles])


def _season_variants(snapshot: MediaSnapshot) -> tuple[str, ...]:
    """`SPY x FAMILY Season 3` / `間諜家家酒 第3季`。

    只做**最新的一季**，而且只在它不是第一季時做：第一季的發佈幾乎不寫季號，而每多一個變體
    就是每一個追蹤站再被問一次。使用者要找舊季時自己打字，那條路一直都在。

    **不分動漫**（票 14e，brief §19）：美劇的 `The Bear Season 3` 一樣是真的發佈名。效果沒有量，
    要打真的索引站才量得到。電影沒有季，自然不產生。
    """
    numbers = [season.season_number for season in snapshot.seasons if season.season_number > 0]
    if len(numbers) < 2:
        return ()
    latest = max(numbers)
    return tuple(
        variant
        for title, variant in (
            (snapshot.title_en, f"{snapshot.title_en} Season {latest}"),
            (snapshot.title, f"{snapshot.title} 第{latest}季"),
        )
        if title
    )


def _queries(
    texts: Sequence[str], snapshot: MediaSnapshot | None, id_search: frozenset[MediaKind]
) -> tuple[SearchQuery, ...]:
    """關鍵字 → 查詢。端點認得 tmdbid 時整批換成**一個** id 查詢。

    id 問得比關鍵字準，而且準到不需要問第二次——別名存在的理由正是「同一部作品有好幾個
    名字」，而 id 沒有這個問題。實測十個預設公開站一個都不支援，所以這條路平常走不到
    （627 份定義裡 93 份支援，全部是私站，brief §20.7）。
    """
    if snapshot is not None and snapshot.kind in id_search:
        return (SearchQuery(tmdb_id=snapshot.tmdb_id, kind=snapshot.kind),)
    kind = snapshot.kind if snapshot is not None else MediaKind.TV
    return tuple(SearchQuery(text=text, kind=kind) for text in texts)


async def _attempt(
    client: IndexerSearch, query: SearchQuery, timeout: float
) -> tuple[StepView, tuple[IndexerResult, ...]]:
    """一個查詢，一條纜繩。

    **失敗不往上冒**：十個公開站裡有幾個連不上是常態（brief §20.7），一個關鍵字問不動時
    另外四個的結果仍然值得看。垮掉的那一個變成一條紅色的纜繩，不是一片空白。
    """
    step = query.text or f"tmdbid-{query.tmdb_id}"
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
            ),
            (),
        )
    except ServiceError as exc:
        return (StepView(step=step, status=StepStatus.FAILED, detail="", error=message(exc)), ())
    return (
        StepView(step=step, status=StepStatus.OK, detail=str(len(rows)), error=""),
        rows,
    )


def _dedupe(results: Iterable[IndexerResult]) -> list[IndexerResult]:
    """合併去重，然後把做種最多的排到前面。

    同一個 key 保留**先看到的那一筆**：查詢是照 `search_titles` 的優先序發的，所以先看到的
    來自更可靠的那個名字。做種數相同時保留原順序（`sorted` 穩定，`reverse=True` 不動同分的
    相對順序），沒有做種數的排最後——「那個站沒報」不該冒充「零個人做種」擠到底，但它也拿不出
    理由排前面。
    """
    seen: dict[str, IndexerResult] = {}
    for result in results:
        seen.setdefault(result.key, result)
    return sorted(
        seen.values(), key=lambda row: -1 if row.seeders is None else row.seeders, reverse=True
    )


def _context(snapshot: MediaSnapshot | None) -> ParseContext:
    return ParseContext(
        media=snapshot,
        route_collection_type=collection_type_for(snapshot.kind) if snapshot is not None else None,
    )


def _row(
    result: IndexerResult, snapshot: MediaSnapshot | None, context: ParseContext
) -> SearchResult:
    """索引站回的一列 → 結果表的一列。

    解析只看發佈名：這時候還沒有 torrent 的檔案清單（那要等送單之後 qBittorrent 才報得出
    內容），所以 `StructureHints` 是空的——路徑上一句話都還沒說。預估因此比入庫時的判斷粗，
    而那正是它叫「預估」的理由。
    """
    info = parse_release(result.title)
    candidates = map_episode(info, StructureHints(), context, release_name=result.title)
    best = candidates[0] if candidates else None
    season = best.season if best is not None else None
    start = best.episode_start if best is not None else None
    # `map_episode` 的 `episode_end` 只在區間時有值，單集是 `None`。這裡補成與 `start` 相同：
    # 畫面要分的是「單集 / 區間 / 判斷不出來」，而 `None` 在這裡同時代表後兩者。
    end = (best.episode_end or start) if best is not None else None
    return SearchResult(
        title=result.title,
        indexer=result.indexer,
        size=result.size,
        seeders=result.seeders,
        info_url=result.info_url,
        download_url=result.download_url,
        key=result.key,
        info_hash=result.info_hash,
        tags=tags_of(info),
        season=season,
        episode_start=start,
        episode_end=end,
        whole_season=_whole_season(snapshot, season, start, end),
        strategy=best.strategy if best is not None else None,
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
    """憑證被拒與連不上的下一步不同：前者去精靈第 5 步改 key，後者只能等或查網路。"""
    return (
        IndexerProblem.CREDENTIAL_REJECTED
        if isinstance(exc, AuthFailedError)
        else IndexerProblem.UNREACHABLE
    )


def _blank(problem: IndexerProblem, detail: str = "") -> SearchView:
    """沒有結果的那幾種。`detail` 只放**服務回的原文**——沒有服務答話的那幾種就是空的，
    畫面上那句話由 `problem` 決定，不靠這一欄拼湊。"""
    return SearchView(rows=(), total=0, attempts=(), problem=problem, detail=detail)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    """去掉空字串與重複，保留第一次出現的順序與**原樣的大小寫**。

    比對用小寫，送出去用原文：索引站對大小寫多半不敏感，但發佈名裡的 `SPY x FAMILY`
    才是使用者認得的那一串字，而纜繩上顯示的就是送出去的那一個。
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = value.strip()
        if not text or text.casefold() in seen:
            continue
        seen.add(text.casefold())
        ordered.append(text)
    return tuple(ordered)
