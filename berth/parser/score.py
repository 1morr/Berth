"""信心：一包檔案一起看（plan §4.1 的 `score`、brief §6.4 第 4 點、§6.5）。

逐檔的信心由 `map_episode` 給，但有些話**只有整包才說得出來**：十二個檔案用同一種模式解出
連續的 01–12、而 TMDB 那一季正好十二集——那是一份互相佐證的答案；兩個檔案同時宣稱自己是
第三集，或者一季十二集卻對出二十個檔案——那是一份互相矛盾的答案，而矛盾在哪裡檔名沒有說。

所以這一層只做兩件事，都是**往下調**或加一句理由，不會把推論出來的答案升成 high：
高信心的來源是「明說的季集」（brief §6.5），數量吻合不會讓推論變成明說。
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from berth.domain import (
    Confidence,
    MappingStrategy,
    ParseContext,
    PlanAction,
    PlanItem,
    at_most,
)


@dataclass(frozen=True, slots=True)
class Decision:
    """一個檔案這一輪的決定，加上它是**怎麼**決定的。

    `strategy` 不在 `PlanItem` 上（plan §4.2 沒有這個欄位），但批次一致性要比的就是它，
    所以逐檔的結果先攤成這個型別再進 `score`。
    """

    item: PlanItem
    strategy: MappingStrategy | None = None


def score(decisions: Sequence[Decision], context: ParseContext) -> tuple[PlanItem, ...]:
    """整包看過一次，回逐檔的 `PlanItem`。"""
    imports = [row for row in decisions if _counts(row)]
    contradicted = _contradicted(imports, context)
    dominant = _dominant(imports)
    complete = _complete_seasons(imports, context)
    return tuple(_adjust(row, contradicted, dominant, complete) for row in decisions)


def _counts(row: Decision) -> bool:
    """會被自動入庫的、有季集的那些。其餘的檔案不參與批次一致性。"""
    return row.item.action is PlanAction.IMPORT and row.item.episode_start is not None


def _contradicted(rows: Sequence[Decision], context: ParseContext) -> dict[str, str]:
    """互相矛盾、因此誰都不該自動入庫的檔案 → 說得出口的理由（brief §6.4 第 4 點、§6.5）。"""
    return {**_duplicated(rows), **_overrun(rows, context)}


def _duplicated(rows: Sequence[Decision]) -> dict[str, str]:
    """兩個檔案宣稱同一集。

    誰對誰錯檔名裡沒有答案——多版本並存是 brief §7.8 的事，這裡只負責不要自動入庫。
    """
    seen = Counter((row.item.season, row.item.episode_start) for row in rows)
    return {
        row.item.rel_path: "another file in this torrent claims the same episode"
        for row in rows
        if seen[(row.item.season, row.item.episode_start)] > 1
    }


def _overrun(rows: Sequence[Decision], context: ParseContext) -> dict[str, str]:
    """影片數量明顯超過 TMDB 那一季的集數（brief §6.5 的 low）。

    一季十二集卻對出二十個檔案，表示這一包裡有東西被讀錯了——但**是哪一個檔案讀錯了
    看不出來**，所以整季一起交給人看，而不是挑一個代罪的。
    """
    counts = _episode_counts(context)
    per_season: defaultdict[int, list[Decision]] = defaultdict(list)
    for row in rows:
        if row.item.season is not None:
            per_season[row.item.season].append(row)
    return {
        row.item.rel_path: f"this torrent maps {len(found)} files into season {season}, "
        f"which TMDB says has {counts[season]} episodes"
        for season, found in per_season.items()
        if counts.get(season, 0) and len(found) > counts[season]
        for row in found
    }


def _dominant(rows: Sequence[Decision]) -> MappingStrategy | None:
    """整包最常用的那一種模式。少數派是例外，例外要被看見（brief §6.5 的 medium）。

    要**過半**才算數：兩個檔案兩種模式時誰都不是「其餘的檔案」，隨便挑一個當多數
    只會任意降低另一個的信心。
    """
    counted = Counter(row.strategy for row in rows if row.strategy is not None)
    if len(counted) < 2:
        return None
    strategy, count = counted.most_common(1)[0]
    return strategy if count * 2 > len(rows) else None


def _complete_seasons(rows: Sequence[Decision], context: ParseContext) -> frozenset[int]:
    """從第一集連號到最後一集、**數量也與 TMDB 吻合**的那幾季（brief §6.4 第 4 點）。"""
    counts = _episode_counts(context)
    numbers: defaultdict[int, list[int]] = defaultdict(list)
    for row in rows:
        if row.item.season is not None and row.item.episode_start is not None:
            numbers[row.item.season].extend(
                range(row.item.episode_start, (row.item.episode_end or row.item.episode_start) + 1)
            )
    return frozenset(
        season
        for season, found in numbers.items()
        if sorted(found) == list(range(1, counts.get(season, 0) + 1))
    )


def _episode_counts(context: ParseContext) -> dict[int, int]:
    """`{季號: TMDB 說的集數}`。沒有快照時是空的，靠它的兩條規則因此都不成立。"""
    if context.media is None:
        return {}
    return {season.season_number: season.episode_count for season in context.media.seasons}


def _adjust(
    row: Decision,
    contradicted: dict[str, str],
    dominant: MappingStrategy | None,
    complete: frozenset[int],
) -> PlanItem:
    item = row.item
    problem = contradicted.get(item.rel_path)
    if problem is not None:
        return item.model_copy(
            update={
                "action": PlanAction.REVIEW,
                "confidence": Confidence.LOW,
                "reasons": (*item.reasons, problem),
            }
        )
    if _counts(row) and dominant is not None and row.strategy is not dominant:
        return item.model_copy(
            update={
                "confidence": at_most(item.confidence, Confidence.MEDIUM),
                "reasons": (
                    *item.reasons,
                    f"the rest of this torrent was read as {dominant.value}, this file was not",
                ),
            }
        )
    if _counts(row) and item.season in complete:
        return item.model_copy(
            update={
                "reasons": (*item.reasons, f"this torrent covers season {item.season} end to end"),
            }
        )
    return item
