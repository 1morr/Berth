"""把一包檔案變成一份 Plan（plan §4.1 的 `plan` 階段）。

**這一版只走到 brief §6.3**：分類、CJK 正規化、發佈名解析與 tag 渲染都在，季集對應（票 06）
與目標路徑（票 07）還沒有。所以除了分類就決定得了的那幾種（extra、可忽略的附屬檔、
整張光碟）之外，每個影片與字幕都是 `review` —— 那是誠實的答案：現在還沒有人能說它是第幾集。

benchmark 量的就是這一支（`services/bench.py`），所以它的形狀從第一天就是最終形狀：
票 06 換掉 `_decide` 裡「還不知道」的那一段，票 07 補上 `target_path`。
"""

from __future__ import annotations

from collections.abc import Sequence

from berth.domain import Confidence, FileEntry, FileKind, PlanAction, PlanItem, ReleaseInfo
from berth.parser.classify import classify
from berth.parser.release import merge_release, parse_release, tags_of

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


def plan(torrent_name: str, files: Sequence[FileEntry]) -> tuple[PlanItem, ...]:
    """一包檔案 → 逐檔的 `PlanItem`。純函式，沒有 IO。"""
    release = parse_release(torrent_name)
    return tuple(_item(entry, release) for entry in classify(files))


def _item(entry: FileEntry, torrent: ReleaseInfo) -> PlanItem:
    # 檔名說了算，torrent 名補空缺：字幕語言常常只寫在 torrent 名上（`简繁外挂`）。
    info = merge_release(parse_release(entry.name), torrent)
    action, confidence, reasons = _decide(entry.kind)
    return PlanItem(
        rel_path=entry.rel_path,
        kind=entry.kind,
        action=action,
        tags=tags_of(info),
        confidence=confidence,
        reasons=reasons,
    )


def _decide(kind: FileKind) -> tuple[PlanAction, Confidence, tuple[str, ...]]:
    ignored = _IGNORED.get(kind)
    if ignored is not None:
        return ignored, Confidence.HIGH, (f"classified as {kind.value}",)
    if kind is FileKind.DISC:
        # `BDMV/` 整包標記為需人工（brief §6.2）。第一階段不拆光碟結構。
        return PlanAction.REVIEW, Confidence.LOW, ("disc structure needs a human",)
    return PlanAction.REVIEW, Confidence.LOW, ("episode mapping is not implemented yet",)
