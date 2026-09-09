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
from datetime import timedelta

from berth.domain import (
    Candidate,
    Confidence,
    EpisodeSnapshot,
    MappingStrategy,
    MediaKind,
    MediaSnapshot,
    ParseContext,
    Profile,
    ReleaseInfo,
    SeasonSnapshot,
    SpecialKind,
    at_most,
)
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
    reason: str


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
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _Mapped:
    """一次換算的結果。算不出來時呼叫端拿到的是 `None`，不是一組空欄位。"""

    season: int
    start: int
    end: int | None
    why: str


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
                ("the job points at a movie, which has no season or episode",),
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
        return _from_hint(hint, media, info, structure, span, check)
    return _from_number(media, context, span, check)


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
            "the job names the season",
        )
    if info.season is not None:
        return _Hint(
            info.season,
            MappingStrategy.EXPLICIT,
            Confidence.HIGH,
            f"the release name says season {info.season}",
        )
    if structure.season is not None:
        return _Hint(
            structure.season,
            MappingStrategy.FOLDER,
            Confidence.HIGH,
            f"the folder says season {structure.season}",
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
            f"the release name carries the arc {best[2]!r}",
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
        f"the release name says final season; the last season is {last}",
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

    known = _exists(season, span.start) and _exists(season, span.end)
    reasons: tuple[str, ...] = (hint.reason,)
    if not known:
        reasons = (*reasons, f"TMDB has no episode {span.start} in season {season.season_number}")
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
    if span.start > len(rows):
        return None
    return _Mapped(
        season=season.season_number,
        start=rows[span.start - 1].episode_number,
        end=_end_of(rows, span.end),
        why=f"part {part} of season {season.season_number} starts at episode "
        f"{rows[0].episode_number}, so its episode {span.start} is episode "
        f"{rows[span.start - 1].episode_number}",
    )


def _end_of(rows: tuple[EpisodeSnapshot, ...], episode_end: int | None) -> int | None:
    """區間的尾巴換算之後是第幾集。落在這一輪之外時當作沒有寫（單集檔）。"""
    if episode_end is None or episode_end > len(rows):
        return None
    return rows[episode_end - 1].episode_number


def _virtual(
    media: MediaSnapshot, hint: _Hint, span: _Span, check: _Check
) -> tuple[Candidate, ...]:
    """檔名的季號對不到任何一季時，用 `air_date` 切出來的虛擬季換算（plan §4.4）。"""
    cours = [(season, rows) for season in _regular(media) for rows in _cours(season)]
    if hint.season > len(cours) or hint.season < 1:
        return ()
    season, rows = cours[hint.season - 1]
    if span.start > len(rows):
        return ()
    mapped = _Mapped(
        season=season.season_number,
        start=rows[span.start - 1].episode_number,
        end=_end_of(rows, span.end),
        why=f"TMDB has no season {hint.season}; air dates split its seasons into "
        f"{len(cours)} runs and run {hint.season} starts at "
        f"S{season.season_number:02d}E{rows[0].episode_number:02d}",
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
    media: MediaSnapshot, context: ParseContext, span: _Span, check: _Check
) -> tuple[Candidate, ...]:
    """沒有任何季號提示（brief §6.4 的第四條）。

    **虛擬季換算不在這裡**：它要有一個季號才索引得到那一輪播出（`_virtual`），而這條路上
    連季號都沒有。brief §6.4 另外提到的「以發佈時間推測」需要索引站給的發佈時間，
    解析器現在拿不到它（票 08 才有），沒有它就只是換一種猜法。
    """
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
                ("the release only numbers episodes and TMDB has one season",),
                check,
            ),
        )

    # 絕對編號的換算法各產一個 Candidate 並附理由（plan §4.1）。
    confidence = Confidence.MEDIUM if context.profile is Profile.ANIME else Confidence.LOW
    aside = (
        ()
        if context.profile is Profile.ANIME
        else ("absolute numbering is an anime convention; this route is not anime",)
    )
    conversions = (
        (MappingStrategy.ABSOLUTE_GROUP, _absolute_group(regular, span)),
        (MappingStrategy.ABSOLUTE_CUMULATIVE, _cumulative(regular, span)),
    )
    return tuple(
        _from_mapped(found, strategy, confidence, span, check, aside)
        for strategy, found in conversions
        if found is not None
    )


def _from_mapped(
    mapped: _Mapped,
    strategy: MappingStrategy,
    confidence: Confidence,
    span: _Span,
    check: _Check,
    aside: tuple[str, ...] = (),
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
                (
                    f"the release covers {span.start}-{span.end} but that range does not fit "
                    f"one season",
                )
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
                why=f"TMDB's absolute episode group puts #{span.start} at "
                f"S{season.season_number:02d}E{row.episode_number:02d}",
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
                why=f"counting seasons in order puts #{span.start} at "
                f"S{season.season_number:02d}E{start:02d}",
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
        reasons=(
            f"the job carries no media; {found.media.title_en!r} matched by title",
            *found.reasons,
        ),
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
                f"the release title {info.title_candidates[0]!r} does not look like "
                f"{media.title_en!r}",
            ),
        )
    return _Check(ceiling=Confidence.HIGH)


def _specials(season_number: int, check: _Check) -> _Check:
    """季 0 最多 medium：字幕組的特典編號與 TMDB 的 S0 編號**不保證一致**（票 05 語料筆記）。"""
    if season_number != 0:
        return check
    return _Check(
        ceiling=at_most(check.ceiling, Confidence.MEDIUM),
        reasons=(*check.reasons, "TMDB numbers its specials differently from most releases"),
    )


def _candidate(
    season: int | None,
    start: int | None,
    end: int | None,
    strategy: MappingStrategy,
    confidence: Confidence,
    reasons: tuple[str, ...],
    check: _Check,
) -> Candidate:
    """組一個 Candidate。標題覆核的上限與它那一句理由在這裡一次併進去。"""
    return Candidate(
        season=season,
        episode_start=start,
        episode_end=end,
        strategy=strategy,
        confidence=at_most(confidence, check.ceiling),
        reasons=tuple(reason for reason in (*reasons, *check.reasons) if reason),
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
