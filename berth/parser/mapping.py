"""季集對應：這個檔案是第幾季第幾集（plan §4.1 的 `map_episode`、§4.4，brief §6.4、§6.5）。

順序就是 brief §6.4 第 3 點：**明說的贏推論的**。上下文的季號、檔名的 `SxxEyy`、資料夾、
篇章名、只有集號——一路往下試，第一個說得出話的就是答案，其餘的路只在它說不出話時才走。

三條規則來自 M1 票 01 的量測（`docs/research/anime-episode-source.md`，7,833 筆真實釋出），
它們是**失敗率的主要槓桿**，不是補丁：

- 篇章名 → 季號（§6.1，佔 TMDB 失敗的 91%）。比對各季的名字，命中就等同季號提示。
- `第二部分` / `Part.2` → cour 偏移（§6.1.1，唯一「有季號還是錯」的一類）。
- 虛擬季門檻 **180 天**（§6.4）。已被量測支持，調小會變差。

信心的上限逐條策略定（brief §6.5）：明說的可以 high，推論出來的最多 medium，
TMDB 上不存在的那一集一律 low——low 進 review，那正是它該去的地方。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from berth.domain import (
    Candidate,
    Confidence,
    EpisodeSnapshot,
    ItemReason,
    MappingStrategy,
    MediaKind,
    MediaSnapshot,
    ParseContext,
    ReleaseInfo,
    SeasonSnapshot,
    SpecialKind,
    at_most,
    episode_label,
    why,
)
from berth.domain import ReasonCode as Code
from berth.parser.publishing import BEHIND_LATEST, RELEASE_TOLERANCE
from berth.parser.structure import StructureHints
from berth.parser.title import match_media, matches, normalize_title

#: 季內間隔超過這麼久就是另一輪播出（plan §4.4）。**不要調小**：一季分兩 cour 的間隔常常
#: 不到 180 天，調成 60 天會把一季切成兩個虛擬季，季號提示反而對不上（研究 §6.4，
#: 整體換算失敗率 8.0% → 9.7%）。
VIRTUAL_SEASON_GAP = timedelta(days=180)

#: 用自己的序號編的特典。對得到 TMDB 的 season 0 純屬巧合（brief §7.6）。
_OWN_NUMBERING = frozenset({SpecialKind.SP, SpecialKind.OVA, SpecialKind.OAD, SpecialKind.MOVIE})

#: 篇章名至少要這麼長才算數。太短的季名（`第1季`）與標題碎片會到處命中。
_MIN_ARC = 3

#: 「最終季」的各種寫法。TMDB 沒把最後一季取名叫 Final 時的退路（plan §4.4）。
_FINAL_SEASON = ("最終季", "最终季", "finalseason")

#: 只是季號的翻譯，不是篇章名。命中它們等於什麼都沒說。比的是正規化之後的字，
#: 所以 `Season 1` 是 `season1`、`第 1 季` 是 `第1季`。
_GENERIC_SEASON = re.compile(
    r"^(?:season|series|part|specials?|第[0-9]+[季期]|特別篇|特别篇)[0-9]*$"
)


@dataclass(frozen=True, slots=True)
class _Hint:
    """季號從哪裡來的。`confidence` 是這個來源的**上限**，不是最後的答案。"""

    season: int
    strategy: MappingStrategy
    confidence: Confidence
    reason: ItemReason


@dataclass(frozen=True, slots=True)
class _Span:
    """檔名說的集號區間。`end` 是 `None` 表示單集檔（brief §6.6）。"""

    start: int
    end: int | None = None


@dataclass(frozen=True, slots=True)
class _Check:
    """標題覆核的結果：信心的上限，以及要一起寫進理由的那一句。

    兩件事總是一起旅行，因為它們是同一個判斷的兩半——「這一包看起來是不是這部作品」。
    """

    ceiling: Confidence
    reasons: tuple[ItemReason, ...] = ()


@dataclass(frozen=True, slots=True)
class _Mapped:
    """一次換算的結果。算不出來時呼叫端拿到的是 `None`，不是一組空欄位。"""

    season: int
    start: int
    end: int | None
    why: ItemReason

    @property
    def target(self) -> _Target:
        return (self.season, self.start, self.end)


#: 一種讀法換算出的（季, 第一集, 最後一集）。單集檔的最後一集是 `None`，與 `Candidate` 一樣。
_Target = tuple[int | None, int | None, int | None]


def map_episode(
    info: ReleaseInfo,
    structure: StructureHints,
    context: ParseContext,
    *,
    release_name: str = "",
) -> tuple[Candidate, ...]:
    """一個影片檔 → 排序過的 `Candidate`（最好的在前）。說不出話時回空的。

    `release_name` 是索引站上的發佈標題。它與檔名**各知道一半**：篇章名常常只寫在發佈
    標題上，而集號只寫在檔名裡（M1 票 05 實測），所以兩邊的原文都要看。
    """
    media, check = _resolve(info, context)
    if media is None:
        # 認不出作品就沒有可以對照的季集。這時候任何數字都只是檔名的複述。
        return ()

    if media.kind is MediaKind.MOVIE:
        return (
            _candidate(
                None,
                None,
                None,
                MappingStrategy.MOVIE,
                Confidence.HIGH,
                (why(Code.MOVIE),),
                check,
            ),
        )

    if own_numbering(info, structure):
        # `SP/[…][SP][01]` 的 01 是字幕組自己的特典序號。對不到就是對不到（brief §7.6）。
        return ()

    span = _span(info, context)
    if span is None:
        return ()

    text = f"{info.raw_title} {release_name}"
    hint = _hint(info, structure, context, media, text)
    if hint is not None:
        return _from_hint(hint, media, info, structure, span, check, context)
    return _from_number(media, info, span, check, context)


# --- 季號的來源 ------------------------------------------------------------------------


def _hint(
    info: ReleaseInfo,
    structure: StructureHints,
    context: ParseContext,
    media: MediaSnapshot,
    text: str,
) -> _Hint | None:
    """brief §6.4 第 3 點的優先序。第一個說得出話的就是它。"""
    if context.season_hint is not None:
        return _Hint(
            context.season_hint,
            MappingStrategy.CONTEXT,
            Confidence.HIGH,
            why(Code.SEASON_FROM_JOB, season=context.season_hint),
        )
    if info.season is not None:
        return _Hint(
            info.season,
            MappingStrategy.EXPLICIT,
            Confidence.HIGH,
            why(Code.SEASON_FROM_RELEASE, season=info.season),
        )
    if structure.season is not None:
        return _Hint(
            structure.season,
            MappingStrategy.FOLDER,
            Confidence.HIGH,
            why(Code.SEASON_FROM_FOLDER, season=structure.season),
        )
    return _arc(media, text)


def _arc(media: MediaSnapshot, text: str) -> _Hint | None:
    """篇章名 → 季號（plan §4.4）。

    比的是**各季的每一個名字**：`Hashira Training Arc` / `柱訓練篇` / `柱训练篇` 是同一季的
    三種寫法，而真實發佈用哪一種都有（`MediaSnapshot.names` 就是為此而存在）。
    最長的命中贏——`Overlord II` 比 `Overlord` 說得更多。
    """
    haystack = normalize_title(text)
    title = tuple(
        normalize_title(name) for name in (media.title, media.title_en, media.title_original)
    )
    best: tuple[int, int, str] | None = None
    for season in media.seasons:
        if season.season_number == 0:
            continue
        for name in _season_names(season):
            key = normalize_title(name)
            if len(key) < _MIN_ARC or _generic(key, title) or key not in haystack:
                continue
            if best is None or len(key) > best[0]:
                best = (len(key), season.season_number, name)
    if best is not None:
        return _Hint(
            best[1],
            MappingStrategy.ARC_NAME,
            Confidence.MEDIUM,
            why(Code.SEASON_FROM_ARC, arc=best[2], season=best[1]),
        )
    return _final_season(media, haystack)


def _final_season(media: MediaSnapshot, haystack: str) -> _Hint | None:
    """「最終季 / Final Season」對到最後一季（plan §4.4）。"""
    regular = _regular(media)
    if not regular or not any(marker in haystack for marker in _FINAL_SEASON):
        return None
    last = regular[-1].season_number
    return _Hint(
        last,
        MappingStrategy.ARC_NAME,
        Confidence.MEDIUM,
        why(Code.FINAL_SEASON, season=last),
    )


def _season_names(season: SeasonSnapshot) -> tuple[str, ...]:
    return season.names or ((season.name,) if season.name else ())


def _generic(key: str, title: tuple[str, ...]) -> bool:
    """只是季號的翻譯，或就是作品標題本身——兩種都不帶新資訊。"""
    if _GENERIC_SEASON.match(key):
        return True
    return any(known and key in known for known in title)


# --- 有季號提示 ------------------------------------------------------------------------


def _from_hint(
    hint: _Hint,
    media: MediaSnapshot,
    info: ReleaseInfo,
    structure: StructureHints,
    span: _Span,
    check: _Check,
    context: ParseContext,
) -> tuple[Candidate, ...]:
    season = _season(media, hint.season)
    if season is None:
        # TMDB 沒有這一季：好幾輪播出被併成一季了（plan §4.4）。
        return _virtual(media, hint, span, check)

    part = info.part or structure.part
    if part is not None and part > 1:
        cour = _cour(season, part, span)
        if cour is not None:
            # cour 標記說「照字面讀是錯的」，所以字面那一個不再是候選（研究 §6.1.1）。
            return (
                _from_mapped(
                    cour,
                    MappingStrategy.COUR_OFFSET,
                    Confidence.MEDIUM,
                    span,
                    check,
                    (hint.reason,),
                ),
            )

    # 明說了分部的（`Part.1` 也算）不推測：分部說的就是哪一輪。
    restarted = _restarted_within(season, hint, media, span, context) if part is None else None
    if restarted is not None:
        return (_guessed(restarted, media, info, span, check, (hint.reason,)),)

    known = _exists(season, span.start) and _exists(season, span.end)
    reasons: tuple[ItemReason, ...] = (hint.reason,)
    if not known:
        reasons = (
            *reasons,
            why(Code.EPISODE_NOT_ON_TMDB, season=season.season_number, number=span.start),
        )
    return (
        _candidate(
            season.season_number,
            span.start,
            span.end,
            hint.strategy,
            hint.confidence if known else Confidence.LOW,
            reasons,
            _specials(season.season_number, check),
        ),
    )


def _cour(season: SeasonSnapshot, part: int, span: _Span) -> _Mapped | None:
    """`Part.2` 的第 N 集是這一季的第幾集（plan §4.4）。

    切法與虛擬季同一條規則（間隔 > 180 天），因為它們是同一件事：一季裡的兩輪播出。
    算出來超出這一季時回 `None`——那表示字幕組其實是**季內連號**（直接從 13 接下去），
    照字面讀才是對的。
    """
    cours = _cours(season)
    if part > len(cours):
        return None
    rows = cours[part - 1]
    counted = _counted_in(rows, span)
    if counted is None:
        return None
    return _Mapped(
        season=season.season_number,
        start=counted[0],
        end=counted[1],
        why=why(
            Code.COUR_OFFSET,
            part=part,
            season=season.season_number,
            first=rows[0].episode_number,
            number=span.start,
            episode=episode_label(season.season_number, rows[span.start - 1].episode_number),
        ),
    )


def _counted_in(rows: tuple[EpisodeSnapshot, ...], span: _Span) -> tuple[int, int | None] | None:
    """集號從這一輪的 01 數起是哪幾集：（第一集, 最後一集）。第一集不在這一輪裡時是 `None`——
    包括 `00`，它不是任何一輪從 01 數的集數。"""
    if not 1 <= span.start <= len(rows):
        return None
    return rows[span.start - 1].episode_number, _end_of(rows, span.end)


def _end_of(rows: tuple[EpisodeSnapshot, ...], episode_end: int | None) -> int | None:
    """區間的尾巴換算之後是第幾集。落在這一輪之外時當作沒有寫（單集檔）。"""
    if episode_end is None or episode_end > len(rows):
        return None
    return rows[episode_end - 1].episode_number


def _virtual(
    media: MediaSnapshot, hint: _Hint, span: _Span, check: _Check
) -> tuple[Candidate, ...]:
    """檔名的季號對不到任何一季時，用 `air_date` 切出來的虛擬季換算（plan §4.4）。"""
    runs = _runs(media)
    if hint.season > len(runs) or hint.season < 1:
        return ()
    run = runs[hint.season - 1]
    counted = _counted_in(run.rows, span)
    if counted is None:
        return ()
    number = run.season.season_number
    mapped = _Mapped(
        season=number,
        start=counted[0],
        end=counted[1],
        why=why(
            Code.AIR_DATE_RUN,
            season=hint.season,
            runs=len(runs),
            episode=episode_label(number, run.rows[0].episode_number),
        ),
    )
    return (
        _from_mapped(
            mapped, MappingStrategy.AIR_DATE_OFFSET, Confidence.MEDIUM, span, check, (hint.reason,)
        ),
    )


def _cours(season: SeasonSnapshot) -> tuple[tuple[EpisodeSnapshot, ...], ...]:
    """一季按播出間隔切成幾輪（plan §4.4 的虛擬季）。沒有播出日的集數跟著前一輪走。"""
    groups: list[list[EpisodeSnapshot]] = [[]]
    previous = None
    for episode in sorted(season.episodes, key=lambda row: row.episode_number):
        if (
            episode.air_date is not None
            and previous is not None
            and episode.air_date - previous > VIRTUAL_SEASON_GAP
        ):
            groups.append([])
        if episode.air_date is not None:
            previous = episode.air_date
        groups[-1].append(episode)
    return tuple(tuple(group) for group in groups if group)


# --- 只有集號 --------------------------------------------------------------------------


def _from_number(
    media: MediaSnapshot, info: ReleaseInfo, span: _Span, check: _Check, context: ParseContext
) -> tuple[Candidate, ...]:
    """沒有任何季號提示（brief §6.4 的第四條）。

    **發佈時間說得出話時它先說**（M3 票 16，`_published_run`）：它挑出的那一輪就是答案，其餘的
    讀法不再產生——它分得開的正是它們分不開的那兩種（`_doubts` 的第一條）。說不出話時照舊：
    只有一季就是那一季，否則是絕對編號。

    絕對編號換算的信心**只看證據，不看 Route 是不是動漫**（M1 票 14c 量過，「是不是動漫」
    預測不了換算對錯）：預設 medium，`_doubts` 說得出理由時降到 low。
    """
    readings = _by_number(media, info, span, check)
    day = _published_day(context)
    if day is None:
        return readings
    literal = tuple((item.season, item.episode_start, item.episode_end) for item in readings)
    restarted = _published_run(media, span, day, _runs(media), literal)
    if restarted is None:
        return readings
    return (_guessed(restarted, media, info, span, check),)


def _by_number(
    media: MediaSnapshot, info: ReleaseInfo, span: _Span, check: _Check
) -> tuple[Candidate, ...]:
    """只看集號的讀法：只有一季就是那一季，否則是絕對編號的各種換算。"""
    regular = _regular(media)
    if len(regular) == 1 and _exists(regular[0], span.start) and _exists(regular[0], span.end):
        only = regular[0]
        return (
            _candidate(
                only.season_number,
                span.start,
                span.end,
                MappingStrategy.SINGLE_SEASON,
                Confidence.MEDIUM,
                (why(Code.SINGLE_SEASON),),
                check,
            ),
        )

    # 絕對編號的換算法各產一個 Candidate 並附理由（plan §4.1）。
    conversions = (
        (MappingStrategy.ABSOLUTE_GROUP, _absolute_group(regular, span)),
        (MappingStrategy.ABSOLUTE_CUMULATIVE, _cumulative(regular, span)),
    )
    candidates: list[Candidate] = []
    for strategy, found in conversions:
        if found is None:
            continue
        doubts = _doubts(media, info, span, found)
        confidence = Confidence.LOW if doubts else Confidence.MEDIUM
        candidates.append(_from_mapped(found, strategy, confidence, span, check, doubts))
    return tuple(candidates)


def _doubts(
    media: MediaSnapshot, info: ReleaseInfo, span: _Span, found: _Mapped
) -> tuple[ItemReason, ...]:
    """絕對編號換算不該自動入庫的理由（brief §6.4、§6.5，M1 票 14d）。沒有理由就是空的。

    1. **集號沒超過第一季的集數**：這個數字同時讀得成「第一季第 N 集」與「後面某季從 01
       重數的第 N 集」，檔名裡沒有東西分得出來——Erai-raws《死神 千年血戰篇 相剋譚》的
       01–14 是後者。「標題有認不出的多餘字」試過分不開這兩種：在 M1 票 01 的真實發佈上
       不是漏掉後者，就是只靠 TMDB 英文標題碰巧夠長才擋下（研究 `profile-effect.md` §6.1）。
    2. **檔名的播出日不是換算出的那一集的播出日**：日期是發佈明說的，換算是推論的。
       **沒有容忍範圍**——日播的劇差一集就是差一天；TMDB 沒有那一集的播出日也算對不上，
       因為沒有東西證實它。
    """
    doubts: list[ItemReason] = []
    first = _regular(media)[0]
    length = _length(first)
    if span.start <= length:
        doubts.append(
            why(
                Code.ABSOLUTE_WITHIN_FIRST_SEASON,
                number=span.start,
                episodes=length,
                season=first.season_number,
            )
        )
    return (*doubts, *_date_doubt(media, info, found))


def _date_doubt(media: MediaSnapshot, info: ReleaseInfo, found: _Mapped) -> tuple[ItemReason, ...]:
    """檔名的播出日不是換算出的那一集的播出日（`_doubts` 的第二條）。檔名沒寫日期時是空的。

    推測虛擬季也吃它：檔名的日期是明說的，發佈時間推測出的那一輪是推論的。
    """
    if info.air_date is None:
        return ()
    label = episode_label(found.season, found.start)
    aired = _aired(media, found.season, found.start)
    if aired is None:
        return (why(Code.AIR_DATE_UNKNOWN, aired=info.air_date.isoformat(), episode=label),)
    if aired != info.air_date:
        return (
            why(
                Code.AIR_DATE_MISMATCH,
                aired=info.air_date.isoformat(),
                episode=label,
                tmdb_aired=aired.isoformat(),
            ),
        )
    return ()


@dataclass(frozen=True, slots=True)
class _Run:
    """一輪播出：某一季按播出間隔切出的一段（CONTEXT.md 的 Cour；那一季是 TMDB 併起來的時候
    就是 Virtual season）。`number` 是它在全部正片的季裡依序的編號，從 1 起。"""

    number: int
    season: SeasonSnapshot
    rows: tuple[EpisodeSnapshot, ...]


def _runs(media: MediaSnapshot) -> tuple[_Run, ...]:
    """全部正片的季各自按播出間隔切開，依序編號。"""
    cours = ((season, rows) for season in _regular(media) for rows in _cours(season))
    return tuple(_Run(number, season, rows) for number, (season, rows) in enumerate(cours, start=1))


def season_airing(media: MediaSnapshot, season: int) -> tuple[int, tuple[EpisodeSnapshot, ...]]:
    """寫著「第 `season` 季」的發佈在 TMDB 上是哪幾集，與規劃同一個讀法：TMDB 有那一季就是它的
    每一集；沒有時是按播出間隔切出的第 `season` 輪（虛擬季，`_virtual`）。回（那幾集在 TMDB 的季號,
    那幾集），都沒有是空的。自動綁定拿它們的播出日比 Mikan 的開播日（M4 票 14）。
    """
    found = _season(media, season)
    if found is not None and season > 0:
        return season, tuple(sorted(found.episodes, key=lambda row: row.episode_number))
    runs = _runs(media)
    if not 1 <= season <= len(runs):
        return season, ()
    run = runs[season - 1]
    return run.season.season_number, run.rows


def _published_day(context: ParseContext) -> date | None:
    """推測虛擬季要用的發佈日。RSS Series 的 offset 是人說的，有值就不推測（plan §4.4）。"""
    if context.published_at is None or context.episode_offset is not None:
        return None
    return context.published_at.date()


def _restarted_within(
    season: SeasonSnapshot, hint: _Hint, media: MediaSnapshot, span: _Span, context: ParseContext
) -> _Mapped | None:
    """季號來自篇章名，而那一季裡有好幾輪播出時，集號是不是那一季後面某輪從 01 重數的（M3 票 16）。

    《死神》千年血戰篇的形狀：篇章名說了第 2 季，TMDB 把四輪播出都放在第 2 季，字幕組每輪從 01 數。
    字面讀法（這一季第 N 集）與第一輪重數是同一個答案，所以候選只有後面幾輪。**只有篇章名**：
    篇章名說的是「哪一部分的故事」，不是字幕組怎麼編號；明說的季號（`S02E08`、`第二季`）、資料夾與
    RSS Series 的季號是發佈或人照自己的編號寫的，照字面採用（brief §6.4）。
    """
    day = _published_day(context)
    if day is None or hint.strategy is not MappingStrategy.ARC_NAME:
        return None
    same = tuple(run for run in _runs(media) if run.season.season_number == season.season_number)
    literal = ((season.season_number, span.start, span.end),)
    return _published_run(media, span, day, same[1:], literal)


def _published_run(
    media: MediaSnapshot,
    span: _Span,
    day: date,
    runs: tuple[_Run, ...],
    literal: tuple[_Target, ...],
) -> _Mapped | None:
    """發佈時間挑得出的那一輪：集號照那一輪從 01 數（brief §6.4、plan §4.4，M3 票 16）。

    AutoBangumi v3.2 的做法，用來分開 `profile-effect.md` §4 的兩種讀法：`- 05` 是照字面讀的那一集
    （`literal`，第一季第 5 集或絕對編號），還是後面某輪從 01 重數的第 5 集。檔名分不出來，
    發佈時間分得出來：**新的發佈，發的是剛播的那一集**。

    每一種讀法換算出的那一集（區間取最後一集）有沒有「剛播」——播出日落在發佈日往前 `BEHIND_LATEST`
    到往後 `RELEASE_TOLERANCE` 之間，兩個門檻與播出日比對同一組。**剛好一種讀法剛播，而它是某一輪的
    重數**才算數。沒有一種剛播（BD、補檔、重播、慢很多的字幕組）或不只一種（前一季剛播完、下一季就
    開播）都是分不開，照舊。至多 medium，推測出的集數照樣過播出日比對（`parser.airing`）。
    """
    total = len(_runs(media))
    restarts = (_restart(run, span, day, total) for run in runs)
    fresh: dict[_Target, _Mapped] = {
        mapped.target: mapped
        for mapped in restarts
        if mapped is not None and _just_aired(media, mapped.target, day)
    }
    targets = set(fresh) | {target for target in literal if _just_aired(media, target, day)}
    if len(targets) != 1:
        return None
    return fresh.get(targets.pop())


def _restart(run: _Run, span: _Span, day: date, total: int) -> _Mapped | None:
    """集號照這一輪從 01 數是哪一集。這一輪沒有那麼多集、或集號是 00 時是 `None`。

    區間要整段落在這一輪裡：推測只在它說得清楚的時候說話，跨出這一輪的交給原本的讀法。
    """
    counted = _counted_in(run.rows, span)
    if counted is None or (span.end or span.start) > len(run.rows):
        return None
    return _Mapped(
        season=run.season.season_number,
        start=counted[0],
        end=counted[1],
        why=why(
            Code.PUBLISHED_IN_RUN,
            published=day.isoformat(),
            run=run.number,
            runs=total,
            episode=episode_label(run.season.season_number, run.rows[0].episode_number),
        ),
    )


def _just_aired(media: MediaSnapshot, target: _Target, day: date) -> bool:
    """那一集（區間取最後一集）是不是剛播：發佈前 `BEHIND_LATEST` 到發佈後 `RELEASE_TOLERANCE`。"""
    season, start, end = target
    if season is None or start is None:
        return False
    aired = _aired(media, season, end or start)
    return aired is not None and -BEHIND_LATEST <= aired - day <= RELEASE_TOLERANCE


def _guessed(
    mapped: _Mapped,
    media: MediaSnapshot,
    info: ReleaseInfo,
    span: _Span,
    check: _Check,
    aside: tuple[ItemReason, ...] = (),
) -> Candidate:
    """推測出的那一輪 → Candidate：至多 medium，檔名明說的播出日對不上時 low（`_date_doubt`）。"""
    doubt = _date_doubt(media, info, mapped)
    return _from_mapped(
        mapped,
        MappingStrategy.PUBLISHED_RUN,
        Confidence.LOW if doubt else Confidence.MEDIUM,
        span,
        check,
        (*aside, *doubt),
    )


def _aired(media: MediaSnapshot, season: int, episode: int) -> date | None:
    """TMDB 說這一集哪天播。沒有這一集、或 TMDB 沒填日期，都是 `None`。"""
    found = _season(media, season)
    if found is None:
        return None
    return next((row.air_date for row in found.episodes if row.episode_number == episode), None)


def _from_mapped(
    mapped: _Mapped,
    strategy: MappingStrategy,
    confidence: Confidence,
    span: _Span,
    check: _Check,
    aside: tuple[ItemReason, ...] = (),
) -> Candidate:
    """換算結果 → Candidate。**區間的尾巴算不出來時降到 low**。

    檔名說了它涵蓋兩集而我們只講得出第一集，照樣自動入庫就會少入一集
    （brief §6.6 的多集檔）。少入一集與入錯一集一樣看不見，所以那時候讓人來看。
    """
    lost = span.end is not None and mapped.end is None
    return _candidate(
        mapped.season,
        mapped.start,
        mapped.end,
        strategy,
        Confidence.LOW if lost else confidence,
        (
            mapped.why,
            *aside,
            *(
                (why(Code.RANGE_SPANS_SEASONS, start=span.start, end=span.end or span.start),)
                if lost
                else ()
            ),
        ),
        check,
    )


def _absolute_group(seasons: tuple[SeasonSnapshot, ...], span: _Span) -> _Mapped | None:
    """TMDB 的 Absolute episode group（brief §20.3）。有的作品沒有這種 group，那就沒有。

    區間的尾巴**只在同一季裡找**：一個 Plan item 只有一個季號，跨季的區間表達不出來
    （Jellyfin 的檔名也表達不出來）。找不到時 `end` 是 `None`，呼叫端據此降信心。
    """
    for season in seasons:
        for row in season.episodes:
            if row.absolute_number != span.start:
                continue
            end = next(
                (
                    other.episode_number
                    for other in season.episodes
                    if other.absolute_number == span.end
                ),
                None,
            )
            return _Mapped(
                season=season.season_number,
                start=row.episode_number,
                end=end,
                why=why(
                    Code.ABSOLUTE_GROUP,
                    number=span.start,
                    episode=episode_label(season.season_number, row.episode_number),
                ),
            )
    return None


def _cumulative(seasons: tuple[SeasonSnapshot, ...], span: _Span) -> _Mapped | None:
    """各季集數累加。TMDB 沒有絕對編號欄位時只剩這條路（brief §20.3、研究 §6.2）。"""
    offset = 0
    for season in seasons:
        count = _length(season)
        if span.start - offset <= count:
            start = span.start - offset
            end = span.end - offset if span.end is not None else None
            return _Mapped(
                season=season.season_number,
                start=start,
                end=end if end is not None and end <= count else None,
                why=why(
                    Code.ABSOLUTE_CUMULATIVE,
                    number=span.start,
                    episode=episode_label(season.season_number, start),
                ),
            )
        offset += count
    return None


# --- 共用 ------------------------------------------------------------------------------


def _span(info: ReleaseInfo, context: ParseContext) -> _Span | None:
    """檔名的集號加上 Rule 的手動偏移（plan §4.4）。檔名沒有集號時是 `None`。"""
    if info.episode is None:
        return None
    offset = context.episode_offset or 0
    end = info.episode_end + offset if info.episode_end is not None else None
    return _Span(start=info.episode + offset, end=end)


def own_numbering(info: ReleaseInfo, structure: StructureHints) -> bool:
    """特典用的是自己的序號嗎（brief §7.6）。明說 `S00Exx` 的不算——那是照 TMDB 的編號寫的。

    公開的：`map_episode` 用它決定不產候選，`planner` 用同一個答案決定那個檔案是
    `unmatched` 而不是 `review`。兩邊各判一次的話，兩個決定遲早會不一致。
    """
    if info.season == 0:
        return False
    return structure.special or info.special_kind in _OWN_NUMBERING


def _resolve(info: ReleaseInfo, context: ParseContext) -> tuple[MediaSnapshot | None, _Check]:
    """這一包是哪一部作品（brief §6.4 的第 1、2 點）。

    Job 帶了 Media 就是它，標題比對只是覆核；沒帶的時候（RSS、重新入庫）就從候選池裡認，
    認不出來就回 `None`——猜一部作品出來的代價是入庫到別人的資料夾底下。
    """
    if context.media is not None:
        return context.media, _title_check(info, context.media)

    found = match_media(info, context.candidates)
    if found is None:
        return None, _Check(ceiling=Confidence.LOW)
    return found.media, _Check(
        # 「標題 + 年份精確命中」才配得上 high（brief §6.5）。
        ceiling=Confidence.HIGH if found.exact else Confidence.MEDIUM,
        reasons=(why(Code.MEDIA_BY_TITLE, title=found.media.title_en), *found.reasons),
    )


def _title_check(info: ReleaseInfo, media: MediaSnapshot) -> _Check:
    """發佈的標題與上下文的作品對得起來嗎（brief §6.5 的 high 定義）。

    對不上時把上限壓到 medium：追蹤的是 A 而 torrent 是 B 的時候，季集算得再漂亮也是錯的。
    **認不出標題不算對不上**——字幕組格式常常一個字都認不出來，那時這一層什麼都不說。
    """
    found = matches(info, media)
    if found is not None:
        return _Check(ceiling=Confidence.HIGH, reasons=found.reasons[:1])
    if info.title_candidates:
        return _Check(
            ceiling=Confidence.MEDIUM,
            reasons=(
                why(
                    Code.TITLE_MISMATCH,
                    release_title=info.title_candidates[0],
                    title=media.title_en,
                ),
            ),
        )
    return _Check(ceiling=Confidence.HIGH)


def _specials(season_number: int, check: _Check) -> _Check:
    """季 0 最多 medium：字幕組的特典編號與 TMDB 的 S0 編號**不保證一致**（票 05 語料筆記）。"""
    if season_number != 0:
        return check
    return _Check(
        ceiling=at_most(check.ceiling, Confidence.MEDIUM),
        reasons=(*check.reasons, why(Code.SPECIALS_NUMBERING)),
    )


def _candidate(
    season: int | None,
    start: int | None,
    end: int | None,
    strategy: MappingStrategy,
    confidence: Confidence,
    reasons: tuple[ItemReason, ...],
    check: _Check,
) -> Candidate:
    """組一個 Candidate。標題覆核的上限與它那一句理由在這裡一次併進去。"""
    return Candidate(
        season=season,
        episode_start=start,
        episode_end=end,
        strategy=strategy,
        confidence=at_most(confidence, check.ceiling),
        reasons=(*reasons, *check.reasons),
    )


def _regular(media: MediaSnapshot) -> tuple[SeasonSnapshot, ...]:
    """正片的季。Specials 不是一季——它存在不代表這部作品有兩季。"""
    return tuple(season for season in media.seasons if season.season_number > 0)


def _season(media: MediaSnapshot, number: int) -> SeasonSnapshot | None:
    return next((season for season in media.seasons if season.season_number == number), None)


def _length(season: SeasonSnapshot) -> int:
    """這一季有幾集。TMDB 自己報的數字與收錄的集數不一定一樣，取大的。"""
    return max(season.episode_count, len(season.episodes))


def _exists(season: SeasonSnapshot, number: int | None) -> bool:
    if number is None:
        return True
    if any(row.episode_number == number for row in season.episodes):
        return True
    return 1 <= number <= season.episode_count
