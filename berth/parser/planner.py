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
from collections.abc import Sequence

from berth.domain import (
    AUTO_APPLIED,
    Candidate,
    Confidence,
    FileEntry,
    FileKind,
    MediaKind,
    MediaSnapshot,
    ParseContext,
    PlanAction,
    PlanItem,
    ReleaseInfo,
)
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
    items = _resolve(_targets(score(decisions, resolved), resolved.media))

    subtitles = [entry for entry in entries if entry.kind is FileKind.SUBTITLE]
    items = _resolve((*items, *_attach(subtitles, items, release, resolved.media)))

    by_path = {item.rel_path: item for item in items}
    return tuple(by_path[entry.rel_path] for entry in entries)


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
                    "no video in this torrent carries this subtitle",
                ).item
            )
        else:
            decided.append(_subtitle(entry, info, videos[found.video], found))
    return tuple(decided)


def _subtitle(
    entry: FileEntry, info: ReleaseInfo, video: PlanItem, found: SubtitleMatch
) -> PlanItem:
    """一個配到影片的字幕檔。

    語言由字幕自己的檔名與資料夾決定（`match_subtitle`），`info` 的 tag 才用 torrent 名補
    ——`附官方日英简繁中字幕` 說的是這一包有四種字幕，不是這一個檔案有四種。
    """
    reasons = (*found.reasons, f"it follows {video.rel_path!r}")
    if video.action is PlanAction.IMPORT and video.target_path:
        return PlanItem(
            rel_path=entry.rel_path,
            kind=entry.kind,
            action=PlanAction.SUBTITLE,
            season=video.season,
            episode_start=video.episode_start,
            episode_end=video.episode_end,
            tags=tags_of(info),
            confidence=video.confidence,
            target_path=subtitle_target(
                video.target_path, langs=found.langs, ext=extension(entry.name)
            ),
            reasons=reasons,
        )
    # 影片沒有入庫，字幕就沒有地方掛。跟著它走，人在 review 裡看到的才是一對。
    action = PlanAction.UNMATCHED if video.action is PlanAction.UNMATCHED else PlanAction.REVIEW
    return PlanItem(
        rel_path=entry.rel_path,
        kind=entry.kind,
        action=action,
        tags=tags_of(info),
        confidence=Confidence.LOW,
        reasons=(*reasons, f"that video is {video.action.value}"),
    )


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
            "reasons": (
                *item.reasons,
                f"another file in this torrent would be written to {item.target_path!r}",
            ),
        }
    )
