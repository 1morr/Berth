"""把一包檔案變成一份 Plan（plan §4.1 的 `plan` 階段）。

**這一版走到 brief §6.5**：分類、CJK 正規化、發佈名解析、季集對應與信心都在，外掛字幕的
附掛與目標路徑（票 07）還沒有。所以字幕仍然是 `review`——那是誠實的答案，現在還沒有人
能說它該掛在哪一個影片上。

benchmark 量的就是這一支（`services/bench.py`），所以它的形狀從第一天就是最終形狀：
票 07 補上 `match_subtitle` 與 `target_path`。
"""

from __future__ import annotations

from collections.abc import Sequence

from berth.domain import (
    AUTO_APPLIED,
    Candidate,
    Confidence,
    FileEntry,
    FileKind,
    ParseContext,
    PlanAction,
    PlanItem,
    ReleaseInfo,
)
from berth.parser.classify import classify
from berth.parser.mapping import map_episode, own_numbering
from berth.parser.release import merge_release, parse_release, tags_of
from berth.parser.score import Decision, score
from berth.parser.structure import StructureHints, structure_hints

#: 分類就決定得了處置的那幾種：不進媒體庫，也不需要人看（brief §6.2）。
_IGNORED: dict[FileKind, PlanAction] = {
    FileKind.FONT: PlanAction.SKIP,
    FileKind.AUDIO: PlanAction.SKIP,
    FileKind.IMAGE: PlanAction.SKIP,
    FileKind.ARCHIVE: PlanAction.SKIP,
    FileKind.SAMPLE: PlanAction.SKIP,
    FileKind.OTHER: PlanAction.SKIP,
    FileKind.EXTRA: PlanAction.EXTRA,
}


def plan(
    torrent_name: str, files: Sequence[FileEntry], context: ParseContext | None = None
) -> tuple[PlanItem, ...]:
    """一包檔案 → 逐檔的 `PlanItem`。純函式，沒有 IO。

    `context` 缺席時（沒有 Media 快照）每個影片都是 `review`：沒有可以對照的季集，
    任何數字都只是檔名的複述。
    """
    resolved = context or ParseContext()
    release = parse_release(torrent_name)
    decisions = [_decide(entry, release, resolved, torrent_name) for entry in classify(files)]
    return score(decisions, resolved)


def _decide(
    entry: FileEntry, torrent: ReleaseInfo, context: ParseContext, torrent_name: str
) -> Decision:
    # 檔名說了算，torrent 名補空缺：字幕語言常常只寫在 torrent 名上（`简繁外挂`）。
    info = merge_release(parse_release(entry.name), torrent)

    if (ignored := _IGNORED.get(entry.kind)) is not None:
        return _plain(entry, info, ignored, Confidence.HIGH, f"classified as {entry.kind.value}")
    if entry.kind is FileKind.DISC:
        # `BDMV/` 整包標記為需人工（brief §6.2）。第一階段不拆光碟結構。
        return _plain(
            entry, info, PlanAction.REVIEW, Confidence.LOW, "disc structure needs a human"
        )
    if entry.kind is FileKind.SUBTITLE:
        return _plain(
            entry,
            info,
            PlanAction.REVIEW,
            Confidence.LOW,
            "subtitle matching is not implemented yet",
        )

    structure = structure_hints(entry.rel_path)
    candidates = map_episode(info, structure, context, release_name=torrent_name)
    if not candidates:
        return _unmapped(entry, info, structure, context)
    return _mapped(entry, info, candidates[0])


def _mapped(entry: FileEntry, info: ReleaseInfo, best: Candidate) -> Decision:
    action = PlanAction.IMPORT if best.confidence in AUTO_APPLIED else PlanAction.REVIEW
    return Decision(
        item=PlanItem(
            rel_path=entry.rel_path,
            kind=entry.kind,
            action=action,
            season=best.season,
            episode_start=best.episode_start,
            episode_end=best.episode_end,
            tags=tags_of(info),
            confidence=best.confidence,
            reasons=best.reasons,
        ),
        strategy=best.strategy,
    )


def _unmapped(
    entry: FileEntry, info: ReleaseInfo, structure: StructureHints, context: ParseContext
) -> Decision:
    """對不到季集的影片。**像正片的**進 Unmatched，其餘進 review（brief §7.6）。

    差別在下一步：Unmatched 是「這是一個節目，但我不知道它是哪一集」——使用者指派給某一集
    就結案了；review 是「我連它是什麼都還沒想清楚」。
    """
    if context.media is None:
        return _plain(entry, info, PlanAction.REVIEW, Confidence.LOW, "the job carries no media")
    if own_numbering(info, structure):
        return _plain(
            entry,
            info,
            PlanAction.UNMATCHED,
            Confidence.LOW,
            "a special numbered by the release itself; TMDB numbers its specials differently",
        )
    return _plain(
        entry, info, PlanAction.REVIEW, Confidence.LOW, "no season and episode could be worked out"
    )


def _plain(
    entry: FileEntry,
    info: ReleaseInfo,
    action: PlanAction,
    confidence: Confidence,
    reason: str,
) -> Decision:
    return Decision(
        item=PlanItem(
            rel_path=entry.rel_path,
            kind=entry.kind,
            action=action,
            tags=tags_of(info),
            confidence=confidence,
            reasons=(reason,),
        )
    )
