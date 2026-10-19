"""作品搜尋要拿哪幾個字去問（plan §8.4、M4 票 84，`.scratch/m4/search-choose-shape.md`）。

純函式：輸入是快照（與缺集時季表那一份 `SeasonView`）加上使用者開了哪些名字與季，
輸出是查詢。`GET /search/queries` 的預覽與真的送出去的那幾個查詢都走這裡
（`services/search.py`），前端不重算——兩邊各算一份，遲早會長出不同的答案。

**名字與季由使用者在搜尋面板上開關**（票 84 推翻票 08 起「由 Berth 決定、取前五個」）：
一個名字一顆 chip，帶它是哪一種（`NameKind`）；種類的開關全域記住（`SearchSettings`），季的不記。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from berth.domain import EpisodeStatus, MediaSnapshot, NameKind
from berth.parser import season_tokens, spell_ampersand
from berth.services.inventory import EpisodeView, SeasonView

#: 一次搜尋最多發幾個查詢。每一個都是「請這台索引站現場去連它認得的每一個追蹤站」，
#: 所以上限不是為了省 Berth 的力氣，是為了不要替使用者把那些公開站打到封 IP。
#: 超過時不砍尾巴、整次不問（畫面停用搜尋鍵）：名字與季是使用者自己開的，默默少問幾個
#: 等於替他做了決定。10 個放得下動畫的英文名、原名、兩種中文名各配「不指定季」與最新一季
#: （拉丁字名字一季兩個記號，`season_tokens`）（使用者 2026-10-13 拍板）。
MAX_QUERIES = 10


@dataclass(frozen=True, slots=True)
class SearchName:
    """搜尋面板上的一顆名字 chip：名字原樣，與它是哪幾種（同一串字可以既是英文名也是原名）。"""

    text: str
    kinds: tuple[NameKind, ...]


@dataclass(frozen=True, slots=True)
class QueryChoice:
    """開了哪些名字與季。順序不重要：查詢照 chip 的順序排，不照按的順序。"""

    names: tuple[str, ...]
    #: 開了的季（逐季那幾顆）。缺集搜尋不看它——缺的形狀決定問哪幾季。
    seasons: tuple[int, ...] = ()
    #: 「不指定季」那一顆：名字本身不帶季記號。
    any_season: bool = True


@dataclass(frozen=True, slots=True)
class QueryBatch:
    """缺集搜尋的一批：一次按下去問出去的那幾個查詢，與它們問的是哪幾季（M3 票 20）。"""

    queries: tuple[str, ...]
    #: 這一批的記號歸到哪幾季。畫面用它說「這一批問了 S01–S05」。
    seasons: tuple[int, ...]


def search_names(snapshot: MediaSnapshot) -> tuple[SearchName, ...]:
    """這部作品的名字，一個一顆 chip：英文名、原名、中文名、簡體中文名，然後是其餘別名。

    同一串字是兩種時合成一顆（`The Bear` 英文名 · 原名）。顯示名等於英文名時不算中文名——
    那是 TMDB 沒有 `zh-TW` 翻譯時的退路。別名照 `titles` 的順序（TMDB 的別名本來就沒有順序
    可言），已經列過的去掉。
    """
    kinds: dict[str, list[NameKind]] = {}
    known = (
        (snapshot.title_en, NameKind.ENGLISH),
        (snapshot.title_original, NameKind.ORIGINAL),
        (snapshot.title if snapshot.title != snapshot.title_en else "", NameKind.CHINESE),
        (snapshot.title_zh_cn, NameKind.SIMPLIFIED),
    )
    for text, kind in known:
        if text:
            kinds.setdefault(text, []).append(kind)
    for text in snapshot.titles:
        if text:
            kinds.setdefault(text, [NameKind.ALIAS])
    return tuple(SearchName(text, tuple(found)) for text, found in kinds.items())


def season_numbers(snapshot: MediaSnapshot) -> tuple[int, ...]:
    """逐季 chip 的那幾季。第 0 季特別篇不算：`S00` 在索引站上搜不到東西。電影沒有季。"""
    return tuple(sorted({row.season_number for row in snapshot.seasons if row.season_number > 0}))


def default_choice(snapshot: MediaSnapshot, remembered: Mapping[NameKind, bool]) -> QueryChoice:
    """打開作品頁時開著哪些。

    名字：記住的種類開著的那幾顆（兩種的 chip 有一種開就開），別名永遠關。季：「不指定季」，
    兩季以上另開最新一季——第一季的發佈幾乎不寫季號，而找最新一季時「第 N 季」比作品名本身
    更可能命中（plan §8.4）。
    """
    names = tuple(
        name.text
        for name in search_names(snapshot)
        if any(remembered.get(kind, False) for kind in name.kinds if kind is not NameKind.ALIAS)
    )
    numbers = season_numbers(snapshot)
    return QueryChoice(names=names, seasons=numbers[-1:] if len(numbers) > 1 else ())


def chosen_names(snapshot: MediaSnapshot, choice: QueryChoice) -> tuple[str, ...]:
    """開了的名字，照 chip 的順序。不是這部作品的名字不問：要問別的字，打關鍵字那條路一直在。"""
    wanted = set(choice.names)
    return tuple(name.text for name in search_names(snapshot) if name.text in wanted)


def title_queries(snapshot: MediaSnapshot, choice: QueryChoice) -> tuple[str, ...]:
    """照作品名搜時的查詢：開了的名字 × 開了的季（「不指定季」是名字本身）。

    名字優先：一個名字問完它的每一季再換下一個。名字有 `&` 的原樣一個、寫成 `and` 一個（M4 票 69）。
    """
    numbers = [number for number in season_numbers(snapshot) if number in set(choice.seasons)]
    return _unique(
        query
        for spelled in _spellings(chosen_names(snapshot, choice))
        for query in (
            *([spelled] if choice.any_season else []),
            *(
                f"{spelled} {token}"
                for number in numbers
                for token in season_tokens(spelled, number)
            ),
        )
    )


def missing_batches(
    names: Sequence[str], seasons: Sequence[SeasonView], *, season: int | None = None
) -> tuple[QueryBatch, ...]:
    """季表上缺的那幾集要拿哪幾個名字去問，分成幾批（M1.5 票 10、M3 票 20、M4 票 84、plan §8.4）。

    季表已經知道缺哪幾集，所以搜尋不必再從作品名開始。查詢是**名字 × 記號**，記號由缺的形狀決定
    （使用者 2026-09-19 拍板）：

    - **整季缺**（那一季播出了的每一集都缺）→ 季記號，與照作品名搜同一個 `season_tokens`。
    - **缺幾集 / 缺一集** → 一集一個記號：TMDB 給了絕對編號就用它（兩位數補零，照 Sonarr 的
      動漫查詢），否則 `S03E05`。有絕對編號的作品，發佈就是照絕對編號編的——`S02E01` 在那些
      站上一筆都搜不到；反過來也一樣，所以**一集只有一個記號**，兩種都送會讓記號數加倍。
    - 逐集的查詢放不下 `MAX_QUERIES` 時整批收成季記號；季記號也放不下就**分批**（M3 票 20）：
      每一批是一組季，第一批先填滿到放不下下一季為止。下一批由人再按一次搜尋去問，
      不再退回作品名——退回去的話第六季以後的缺集一次都問不到。

    **開了的每一個名字都問到這一批的每一個記號**（M4 票 84）：票 84 之前一批是「第一個名字問完
    五個記號就滿了」，中文字幕組認得的名字常常輪不到。`season` 有值時只看那一季
    （展開區那一顆按鈕）。
    沒有缺集或沒開名字就回空的——不退回作品名，使用者按的是「搜缺的集」。
    """
    spellings = _spellings(names)
    if not spellings:
        return ()
    if season is not None:
        seasons = [row for row in seasons if row.season_number == season]
    marks = [(row.season_number, mark) for row in seasons for mark in _gap_marks(row)]
    if len(_queries(spellings, marks)) > MAX_QUERIES:
        # 逐集放不下就整批收成季記號：問前幾集等於默默漏掉其餘那幾集，而使用者按的是
        # 「搜缺的集」。收窄到季之後那一季的發佈都回得來，逐集交給結果表的預估去分。
        marks = [(row.season_number, None) for row in seasons if _gaps(row)]

    chunks: list[list[tuple[int, str | None]]] = []
    for mark in marks:
        if chunks and len(_queries(spellings, [*chunks[-1], mark])) <= MAX_QUERIES:
            chunks[-1].append(mark)
        else:
            chunks.append([mark])
    return tuple(
        QueryBatch(
            queries=_queries(spellings, chunk),
            seasons=tuple(dict.fromkeys(number for number, _ in chunk)),
        )
        for chunk in chunks
    )


def _queries(spellings: Sequence[str], marks: Sequence[tuple[int, str | None]]) -> tuple[str, ...]:
    """一批的查詢，名字優先。記號是 `None` 的是整季，照名字的文字系統換成季記號。"""
    return _unique(
        f"{spelled} {token}"
        for spelled in spellings
        for number, mark in marks
        for token in ((mark,) if mark is not None else season_tokens(spelled, number))
    )


def _gap_marks(season: SeasonView) -> tuple[str | None, ...]:
    """這一季缺的那幾集寫成記號。整季都缺時是一個 `None`（季記號），否則一集一個。"""
    gaps = _gaps(season)
    if not gaps:
        return ()
    if len(gaps) == season.aired:
        return (None,)
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


def _spellings(names: Iterable[str]) -> tuple[str, ...]:
    """每個名字原樣一個，拉丁字名字有 `&` 的緊接寫成 `and` 的一個（`spell_ampersand`，M4 票 69）。

    兩種站各認一種：The Pirate Bay 對 `Law & Order` 一筆都不回、`Law and Order` 回 100 筆，
    Mikan 對 `TIGER & BUNNY` 回 81 筆、`TIGER and BUNNY` 0 筆（2026-10-10 實測）。
    Sonarr / Radarr 只送寫開的那一個（brief §20.19），照抄會丟掉字幕組那一邊。
    """
    return _unique(spelled for name in names for spelled in (name, spell_ampersand(name)))


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
