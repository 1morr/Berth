"""把一包檔案變成一份 Plan（plan §4.1 的 `plan` 階段）。

一份 Plan 回答三個問題，順序不能換：**這個檔案是什麼**（分類）、**它是哪一集**（對應與
信心）、**它會被寫到哪裡**（命名）。字幕排在影片後面，因為字幕自己說不出它是第幾集——
它只說得出「我跟哪一個影片是一對」（brief §6.7）。

最後一步是衝突：兩個檔案指到同一條目標路徑時**誰都不自動入庫**（brief §6.4 第 5 點）。
比的是路徑而不是（季, 集），因為同一集的兩個版本本來就該並存——它們的 tags 不同，
檔名也就不同（brief §7.7）。

benchmark 量的就是這一支（`services/bench.py`）。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Sequence

from berth.domain import (
    AUTO_APPLIED,
    EDITABLE_ACTIONS,
    Candidate,
    Confidence,
    FileEntry,
    FileKind,
    ItemReason,
    MediaKind,
    MediaSnapshot,
    ParseContext,
    PlanAction,
    PlanItem,
    ReleaseInfo,
    Tags,
    why,
)
from berth.domain import ReasonCode as Code
from berth.naming import episode_target, extension, extras_target, movie_target, subtitle_target
from berth.parser.classify import classify
from berth.parser.mapping import map_episode, own_numbering
from berth.parser.release import merge_release, parse_release, tags_of
from berth.parser.score import Decision, score
from berth.parser.structure import StructureHints, structure_hints
from berth.parser.subtitles import SubtitleMatch, match_subtitle

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
    """一包檔案 → 逐檔的 `PlanItem`，順序與輸入相同。純函式，沒有 IO。

    `context` 缺席時（沒有 Media 快照）每個影片都是 `review`：沒有可以對照的季集，
    任何數字都只是檔名的複述，也就沒有目標路徑可以算。
    """
    resolved = context or ParseContext()
    release = parse_release(torrent_name)
    entries = classify(files)

    videos = [entry for entry in entries if entry.kind is not FileKind.SUBTITLE]
    decisions = [_decide(entry, release, resolved, torrent_name) for entry in videos]
    items = _spans(_resolve(_targets(score(decisions, resolved), resolved.media)))

    subtitles = [entry for entry in entries if entry.kind is FileKind.SUBTITLE]
    items = _resolve((*items, *_attach(subtitles, items, release, resolved.media)))

    by_path = {item.rel_path: item for item in items}
    return tuple(by_path[entry.rel_path] for entry in entries)


def written_episode(torrent_name: str, rel_path: str) -> int | None:
    """檔名自己寫的集號：RSS Series 的 offset 加上去之前的那一個（M3 票 13）。

    改正一集並套用到 RSS Series 時，offset 就是「人說的集號減去它」。讀法與規劃同一條
    （`_release_of`），不然算出來的 offset 下一次規劃時會差一截。
    """
    return _release_of(rel_path.rpartition("/")[2], parse_release(torrent_name)).episode


def _release_of(file_name: str, torrent: ReleaseInfo) -> ReleaseInfo:
    # 檔名說了算，torrent 名補空缺：字幕語言常常只寫在 torrent 名上（`简繁外挂`）。
    return merge_release(parse_release(file_name), torrent)


def _decide(
    entry: FileEntry, torrent: ReleaseInfo, context: ParseContext, torrent_name: str
) -> Decision:
    info = _release_of(entry.name, torrent)

    if (ignored := _IGNORED.get(entry.kind)) is not None:
        return _plain(
            entry, info, ignored, Confidence.HIGH, why(Code.CLASSIFIED, kind=entry.kind.value)
        )
    if entry.kind is FileKind.DISC:
        # `BDMV/` 整包標記為需人工（brief §6.2）。第一階段不拆光碟結構。
        return _plain(entry, info, PlanAction.REVIEW, Confidence.LOW, why(Code.DISC_STRUCTURE))

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
        return _plain(entry, info, PlanAction.REVIEW, Confidence.LOW, why(Code.NO_MEDIA))
    if own_numbering(info, structure):
        return _plain(
            entry,
            info,
            PlanAction.UNMATCHED,
            Confidence.LOW,
            why(Code.OWN_NUMBERED_SPECIAL),
        )
    return _plain(entry, info, PlanAction.REVIEW, Confidence.LOW, why(Code.NO_EPISODE))


def _plain(
    entry: FileEntry,
    info: ReleaseInfo,
    action: PlanAction,
    confidence: Confidence,
    reason: ItemReason,
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


# --- 目標路徑（plan §5） ----------------------------------------------------------------


def _targets(items: Sequence[PlanItem], media: MediaSnapshot | None) -> tuple[PlanItem, ...]:
    """替會被寫出去的檔案算目標路徑。

    沒有快照就沒有作品資料夾，也就沒有路徑——那時每個影片本來就都在 review。
    """
    if media is None:
        return tuple(items)
    return tuple(_with_target(item, media) for item in items)


def _with_target(item: PlanItem, media: MediaSnapshot) -> PlanItem:
    target = _target_of(item, media)
    return item if not target else item.model_copy(update={"target_path": target})


def _target_of(item: PlanItem, media: MediaSnapshot) -> str:
    ext = extension(item.rel_path)
    if item.action is PlanAction.EXTRA:
        return extras_target(media, item.name)
    if item.action is not PlanAction.IMPORT:
        return ""
    if media.kind is MediaKind.MOVIE:
        return movie_target(media, tags=item.tags, ext=ext)
    if item.season is None or item.episode_start is None:
        # 劇集沒有季集就命不了名。這裡只在資料自相矛盾時走到，不要靜靜地產一條假路徑。
        return ""
    return episode_target(
        media,
        season=item.season,
        episode=item.episode_start,
        episode_end=item.episode_end,
        tags=item.tags,
        ext=ext,
    )


# --- 外掛字幕（brief §6.7） -------------------------------------------------------------


def _attach(
    entries: Sequence[FileEntry],
    items: Sequence[PlanItem],
    torrent: ReleaseInfo,
    media: MediaSnapshot | None,
) -> tuple[PlanItem, ...]:
    """字幕 → 影片。**影片已經決定完了**，所以字幕只要繼承它的答案。"""
    videos = {item.rel_path: item for item in items if item.kind is FileKind.VIDEO}
    decided: list[PlanItem] = []
    for entry in entries:
        info = merge_release(parse_release(entry.name), torrent)
        found = match_subtitle(entry, list(videos.values()))
        if found is None or media is None:
            decided.append(
                _plain(
                    entry,
                    info,
                    PlanAction.UNMATCHED,
                    Confidence.LOW,
                    why(Code.SUBTITLE_ORPHAN),
                ).item
            )
        else:
            decided.append(_subtitle(entry, tags_of(info), videos[found.video], found))
    return tuple(decided)


def _subtitle(entry: FileEntry, tags: Tags, video: PlanItem, found: SubtitleMatch) -> PlanItem:
    """一個配到影片的字幕檔。

    語言由字幕自己的檔名與資料夾決定（`match_subtitle`），`tags` 的語言才用 torrent 名補
    ——`附官方日英简繁中字幕` 說的是這一包有四種字幕，不是這一個檔案有四種。
    """
    reasons = (*found.reasons, why(Code.SUBTITLE_FOLLOWS, video=video.rel_path))
    if video.action is PlanAction.IMPORT and video.target_path:
        return PlanItem(
            rel_path=entry.rel_path,
            kind=entry.kind,
            action=PlanAction.SUBTITLE,
            season=video.season,
            episode_start=video.episode_start,
            episode_end=video.episode_end,
            tags=tags,
            confidence=video.confidence,
            target_path=subtitle_target(
                video.target_path, langs=found.langs, ext=extension(entry.name)
            ),
            reasons=reasons,
        )
    # 影片沒有入庫，字幕就沒有地方掛。跟著它走，人在 review 裡看到的才是一對。
    return PlanItem(
        rel_path=entry.rel_path,
        kind=entry.kind,
        action=_FOLLOWS.get(video.action, PlanAction.REVIEW),
        tags=tags,
        confidence=Confidence.LOW,
        reasons=(*reasons, why(Code.VIDEO_NOT_IMPORTED, action=video.action.value)),
    )


#: 影片沒有入庫時字幕跟著它去哪裡。影片還在等人決定時字幕也等（`review`）；影片被人略過或改成
#: 特典時字幕跟著略過——特典旁邊不掛字幕，而留在 review 會擋住一份已經決定完的 Plan。
#: 解析器自己產不出略過或特典的影片（分類成 extra 的不在影片那一堆裡），那兩格只在人改過之後用到。
_FOLLOWS: dict[PlanAction, PlanAction] = {
    PlanAction.UNMATCHED: PlanAction.UNMATCHED,
    PlanAction.SKIP: PlanAction.SKIP,
    PlanAction.EXTRA: PlanAction.SKIP,
}


# --- 人改過之後（M2 票 07） ---------------------------------------------------------------


def promote(items: Sequence[PlanItem], media: MediaSnapshot | None) -> tuple[PlanItem, ...]:
    """核准＝照提案入庫（2026-09-23 使用者拍板）：待審核的列季集完整就變成 `import`。

    「完整」的判準就是**算得出目標路徑**——與 importer 要的是同一件事，所以不另外寫一份
    「季集夠不夠」的規則。只有分類上能入庫的列才升（`EDITABLE_ACTIONS`）：光碟結構算得出一條
    電影路徑也不行。字幕不在這裡升，它在 `revise` 裡跟著影片走。
    """
    if media is None:
        return tuple(items)
    promoted: list[PlanItem] = []
    for item in items:
        candidate = item.model_copy(update={"action": PlanAction.IMPORT})
        ready = (
            item.action is PlanAction.REVIEW
            and PlanAction.IMPORT in EDITABLE_ACTIONS[item.kind]
            and _target_of(candidate, media)
        )
        promoted.append(candidate if ready else item)
    return tuple(promoted)


def revise(
    items: Sequence[PlanItem],
    media: MediaSnapshot | None,
    *,
    settled: Collection[str] = (),
) -> tuple[PlanItem, ...]:
    """人改過之後重算目標路徑與字幕的附掛。**與規劃時同一份 `_target_of` 與 `_subtitle`**，
    所以畫面上那一條路徑就是 importer 待會兒寫的那一條（票 07 的驗收）。

    `settled` 是已經鏈接進媒體庫的那幾列（rel_path）：它們的路徑是磁碟上的事實，不重算——
    快照後來補上的集標題會讓同一集算出另一個檔名（brief §7.1：不自動改名）。字幕照樣可以
    跟著它們走。**不偵測衝突**：兩列寫到同一條路徑時規劃是把兩列都送 review，而這裡是人剛做的
    決定，要拒絕並說出來（`services/plan_review.py`），不是默默改回去。
    """
    retargeted = tuple(
        item
        if item.rel_path in settled or item.kind is FileKind.SUBTITLE
        else item.model_copy(
            update={"target_path": _target_of(item, media) if media is not None else ""}
        )
        for item in items
    )
    videos = [item for item in retargeted if item.kind is FileKind.VIDEO]
    return tuple(
        _refollow(item, videos, media)
        if item.kind is FileKind.SUBTITLE
        and item.rel_path not in settled
        and item.action is not PlanAction.SKIP
        else item
        for item in retargeted
    )


def _refollow(item: PlanItem, videos: Sequence[PlanItem], media: MediaSnapshot | None) -> PlanItem:
    """一個字幕重新找它的影片。配不到的照規劃時的那一句（`subtitle_orphan`）。"""
    # `size` 是必填欄位而字幕配對不看它（只看檔名與資料夾），存下來的 Plan Item 也沒有這一格。
    entry = FileEntry(rel_path=item.rel_path, size=0, kind=FileKind.SUBTITLE)
    found = match_subtitle(entry, videos)
    if found is None or media is None:
        return item.model_copy(
            update={
                "action": PlanAction.UNMATCHED,
                "target_path": "",
                "confidence": Confidence.LOW,
                "reasons": (why(Code.SUBTITLE_ORPHAN),),
            }
        )
    video = next(video for video in videos if video.rel_path == found.video)
    return _subtitle(entry, item.tags, video, found)


# --- 衝突（brief §6.4 第 5 點） ---------------------------------------------------------


def _resolve(items: Sequence[PlanItem]) -> tuple[PlanItem, ...]:
    """兩個檔案指到同一條目標路徑 → 誰都不自動入庫（brief §6.4 第 5 點）。

    誰對誰錯這一層答不出來——它只知道其中一個會蓋掉另一個，而蓋掉是不可逆的。
    """
    counted = Counter(item.target_path for item in items if item.target_path)
    return tuple(_contested(item) if counted[item.target_path] > 1 else item for item in items)


def _contested(item: PlanItem) -> PlanItem:
    return item.model_copy(
        update={
            "action": PlanAction.REVIEW,
            "confidence": Confidence.LOW,
            "target_path": "",
            "reasons": (*item.reasons, why(Code.TARGET_CONTESTED, target=item.target_path)),
        }
    )


# --- 涵蓋範圍衝突（brief §7.8、§20.9） ---------------------------------------------------


def _spans(items: Sequence[PlanItem]) -> tuple[PlanItem, ...]:
    """多集檔與同起始集的單集 → 誰都不自動入庫（brief §7.8，2026-09-15 使用者拍板）。

    `_resolve` 比的是目標路徑，而 `S01E03-E04` 與 `S01E03` 的檔名不同，路徑也就不同——
    它擋不下這一組。Jellyfin 12 的版本分組鍵**只有季號與集號**（`IndexNumberEnd` 不在裡面），
    所以它們會被併成同一集的兩個版本，第 4 集從集列表上消失（brief §20.9 實測）。
    同一集有兩份涵蓋範圍不同的正片，本來就該由人決定留哪一份——這條規則不分 Jellyfin 版本。
    """
    ends: dict[tuple[int, int], set[int]] = {}
    for item in items:
        span = episode_span(item)
        if span is not None:
            season, start, end = span
            ends.setdefault((season, start), set()).add(end)
    return tuple(_clashing(item, ends) for item in items)


def _clashing(item: PlanItem, ends: dict[tuple[int, int], set[int]]) -> PlanItem:
    span = episode_span(item)
    if span is None or len(ends[(span[0], span[1])]) < 2:
        return item
    return item.model_copy(
        update={
            "action": PlanAction.REVIEW,
            "confidence": Confidence.LOW,
            "reasons": (*item.reasons, why(Code.SPAN_CLASH)),
        }
    )


def episode_span(item: PlanItem) -> tuple[int, int, int] | None:
    """這一列蓋到的（季, 起始集, 結束集）。不是正片、或說不出季集的回 `None`。

    **比帳本的那一半也用它**（`services/plan.py`）：判準一分岔，同一份檔案在兩條路徑上
    就會得到兩個答案。

    **目標路徑留著**：兩個檔案各有各的路徑，都寫得出去，停下來只是因為該由人挑一份
    （與 `_apply_policy` 同一個道理）。
    """
    if item.action is not PlanAction.IMPORT or item.season is None or item.episode_start is None:
        return None
    return (item.season, item.episode_start, item.episode_end or item.episode_start)
