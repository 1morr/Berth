"""送單的防線：只收這則對話自己搜出來、過了規則層比對的 Search Result（M5 票 12，
brief §6.10「外部文字是資料」③，plan §11.6〈對話核心〉）。

搜尋結果的標題是陌生人寫的，最容易藏「送這一筆」這種指令。防線不靠模型聽話，靠這裡：

- **出處**：送單只收 `source_id`（M4 票 79，不收網址或 magnet），而且它必須出現在**這則對話**存下的
  某一次「搜尋」工具結果裡。那份結果是 Berth 寫的（`conversation_messages`），模型改不到；別則對話、
  `/search` 頁面或猜出來的 id 一律不認。
- **比對**：那一列要是「符合」（`SearchVerdict.FITS`，與搜尋頁同一個 `_judge`）、是那一次搜的作品、
  預估的每一集都是那一次要找的缺集，而且沒有被**全域標題規則**擋下（2026-10-24 使用者選定：
  合集的內建判斷不套——整季缺時季包正是要的那一筆；Feed 與 RSS Series 那兩層與搜尋無關）。

標題寫得再像指令，也只能在本來就符合的候選裡被挑中。搜尋工具替每一列先算一次（`refusal_of`），
卡片與模型都看得到哪幾列送得出去；送單時照現在的規則再算一次（`vet_submission`）。
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import IndexerProblem, MappingStrategy, MediaKind, SearchVerdict, Tags
from berth.models import RssSettings
from berth.parser.exclusion import matches
from berth.services.commands import Effect, command
from berth.services.conversations import tool_results_of
from berth.services.settings import read_settings

#: 搜尋工具的名字（`services/tools.py` 登記的那一條）：送單只認它存下的結果。
SEARCH_TOOL = "search_indexers"


class SubmitRefusal(StrEnum):
    """AI 送不出一筆搜尋結果的理由（M5 票 12）。不在 `domain/enums.py`：那裡的 `*Refusal` 是端點的
    拒絕、每一種都有狀態碼，這幾種只有工具會說（同 `registry.ToolRefusal`）。照樣進 OpenAPI，
    前端說得出人話。"""

    #: 這個 id 不在這則對話的任何一次搜尋結果裡：別處來的、猜的、標題裡寫的。
    NOT_FROM_THIS_CONVERSATION = "not_from_this_conversation"
    #: 搜出它的那一次搜的是別部作品。`detail` 是那一部的 id。
    OTHER_WORK = "other_work"
    #: 不是「符合」：名字對不上、成人分類、年份或類型不符、只對上部分名字。`detail` 是那一類。
    NOT_A_MATCH = "not_a_match"
    #: 發佈名讀不出季集，對不到要找的那幾集。
    EPISODES_UNKNOWN = "episodes_unknown"
    #: 預估的季集碰不到要找的那幾集。`detail` 是預估（`S01E03`）。
    OTHER_EPISODES = "other_episodes"
    #: 被全域標題規則擋下。`detail` 是那一條規則。
    EXCLUDED = "excluded"
    #: 這部作品有不只一條 Route 收得下、上次送單也沒用過任何一條，而呼叫沒說要哪一條。
    ROUTE_NEEDED = "route_needed"


class SubmitRefusedError(Exception):
    """送單在動任何東西之前就停下來了。"""

    def __init__(self, reason: SubmitRefusal, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason.value)
        self.reason = reason
        self.detail = detail


# --- 搜尋工具的結果型別 --------------------------------------------------------------
# 住在這裡而不是 `tools.py`：送單讀回來的就是這個形狀，兩邊要是同一份。


class SearchResultRow(BaseModel):
    """搜尋結果卡的一列：搜尋頁結果表的那幾格（`search.SearchResult`），加上 AI 送不送得出它。"""

    #: 送單用的 id（`SourceCache`）。下載連結不出伺服器（M4 票 79）。
    source_id: str
    #: 發佈名，原樣。外部來的文字：資料，不是指令。
    title: str
    indexer: str
    size: int
    seeders: int | None
    info_url: str
    published_at: datetime | None
    tags: Tags
    season: int | None
    episode_start: int | None
    episode_end: int | None
    whole_season: bool
    strategy: MappingStrategy | None
    #: 歸到哪一類與證據（M4 票 83，搜尋頁「為什麼不像這部作品」的那一句）。
    verdict: SearchVerdict
    evidence: str
    #: AI 為什麼送不出這一列；送得出是 `null`（`refusal_of`）。人照樣可以自己按。
    refusal: SubmitRefusal | None = Field(
        description="Why you may not submit this row; null means you may."
    )
    refusal_detail: str


class RouteOption(BaseModel):
    """收得下這部作品的一條 Route（作品頁下拉的那幾條）。"""

    id: int
    name: str
    slug: str


class SearchResults(BaseModel):
    """「依作品與集搜尋」的結果卡（M5 票 12）。"""

    media: str
    kind: MediaKind
    title: str
    title_en: str
    year: int | None
    #: 這一次要找的集，`[季, 起, 迄]`：缺集搜尋時是這一批的缺集，照作品名搜時是整部作品缺的集。
    #: 電影是空的（不比集）。
    wanted: list[tuple[int, int, int]]
    #: `wanted` 裡播出的每一集都缺的那幾季：只寫了季的季包只有在這幾季才送得出。
    whole_seasons: list[int]
    #: 「符合」的前幾筆，加上其餘每一類各幾筆（卡片上說得出為什麼不像這部作品）。
    rows: list[SearchResultRow]
    #: 每一類一共幾筆（各站加總），是 0 的不列。
    counts: dict[SearchVerdict, int]
    #: 缺集分批時，下一批是哪幾季：帶 `from_season=next_seasons[0]` 再搜一次（同搜尋頁，plan §6）。
    next_seasons: list[int] = Field(
        description="Seasons of the next batch; search again with from_season=next_seasons[0]."
    )
    routes: list[RouteOption]
    #: 不說 Route 時送到哪一條（作品頁的預選：上次送單用的，或只有一條）；`null` 時要說。
    route: int | None
    problem: IndexerProblem | None
    #: 失敗時索引站回的原文。
    detail: str


def refusal_of(
    row: SearchResultRow,
    *,
    kind: MediaKind,
    wanted: Sequence[tuple[int, int, int]],
    whole_seasons: Collection[int],
    rules: Sequence[str],
) -> tuple[SubmitRefusal, str] | None:
    """這一列 AI 送不送得出：`None` 是送得出，否則是理由與原文。順序是證據硬的先。

    **劇集一律比集**：預估的**每一集**都要是要找的缺集（`wanted`）——碰到一集就放行的話，只缺一集時
    會送出整季的季包、把其餘幾集再下載一次；照作品名搜時 `wanted` 是整部作品缺的集，已經有的不送。
    只寫了季的季包（讀不出集數）只在那一季播出的每一集都缺時送（`whole_seasons`）；連季都讀不出的不送。
    電影沒有集。
    """
    if row.verdict is not SearchVerdict.FITS:
        return SubmitRefusal.NOT_A_MATCH, row.verdict.value
    if kind is MediaKind.TV:
        if row.season is None:
            return SubmitRefusal.EPISODES_UNKNOWN, ""
        if row.episode_start is None:
            # 只寫了季的季包：那一季播出的每一集都缺時正是要的那一筆（2026-10-24 使用者）。
            if row.season not in whole_seasons:
                return SubmitRefusal.OTHER_EPISODES, _code(row)
        elif not _within(row.season, row.episode_start, row.episode_end, wanted):
            return SubmitRefusal.OTHER_EPISODES, _code(row)
    rule = next((rule for rule in rules if matches(rule, row.title)), None)
    if rule is not None:
        return SubmitRefusal.EXCLUDED, rule
    return None


def _within(
    season: int, start: int, end: int | None, wanted: Sequence[tuple[int, int, int]]
) -> bool:
    """`season` 的 `start`–`end` 每一集都在要找的那幾段裡。"""
    episodes = range(start, (end or start) + 1)
    return all(
        any(at == season and first <= episode <= last for at, first, last in wanted)
        for episode in episodes
    )


def _code(row: SearchResultRow) -> str:
    season = f"S{row.season:02d}"
    if row.episode_start is None:
        return season
    end = row.episode_end or row.episode_start
    start = f"{season}E{row.episode_start:02d}"
    return start if end == row.episode_start else f"{start}-E{end:02d}"


@command(Effect.READ)
async def global_rules(session: AsyncSession) -> tuple[str, ...]:
    """全域那一層的標題規則（排除條件，`parser.exclusion`）。"""
    return tuple((await read_settings(session, RssSettings)).exclude)


@command(Effect.READ)
async def vet_submission(
    session: AsyncSession, *, conversation_id: int | None, source_id: str, media_id: str
) -> SearchResultRow:
    """這一筆可以由 AI 送嗎：在這則對話的搜尋結果裡找它、照現在的規則再比一次。不行就丟
    `SubmitRefusedError`，什麼都沒動。比的作品與要找的集是**搜出它的那一次**說的（每一次搜尋的 id
    都是新的，同一個 id 只在一次結果裡）。
    """
    found = (
        await _searched(session, conversation_id, source_id)
        if conversation_id is not None
        else None
    )
    if found is None:
        raise SubmitRefusedError(SubmitRefusal.NOT_FROM_THIS_CONVERSATION)
    search, row = found
    if search.media != media_id:
        raise SubmitRefusedError(SubmitRefusal.OTHER_WORK, search.media)
    refused = refusal_of(
        row,
        kind=search.kind,
        wanted=search.wanted,
        whole_seasons=search.whole_seasons,
        rules=await global_rules(session),
    )
    if refused is not None:
        raise SubmitRefusedError(*refused)
    return row


async def _searched(
    session: AsyncSession, conversation_id: int, source_id: str
) -> tuple[SearchResults, SearchResultRow] | None:
    for part in await tool_results_of(session, conversation_id, SEARCH_TOOL):
        search = SearchResults.model_validate(part.result)
        row = next((row for row in search.rows if row.source_id == source_id), None)
        if row is not None:
            return search, row
    return None
