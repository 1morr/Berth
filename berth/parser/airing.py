"""播出日比對：發佈時間對換算出的那一集的播出日（M3 票 14、plan §11.4 的「三道程式檢查」①）。

規則層有把握卻算錯的集數，它自己看不出來；Jellyfin 認集數靠 Berth 取的檔名，所以入庫之後的
回驗也看不出來。發佈時間是唯一從外面來的證據：**那一集在它之前已經播出**（brief §20.11——
發佈時間是條目貼出的時間、會偏晚，只能當下限，不能量「多新」）。兩條規則：

- **規則一**：發佈早於換算出的那一集的播出日、超過兩天容忍，就一定是算錯——換算過頭，對到還沒
  播的集數（整季合集的絕對編號、offset 加太多）。
- **規則二**：連載中的 RSS Series 對到的那一集，比同一部作品在發佈當時最近播出的一集早很多——
  split-cour 從 01 重數而 offset 沒設。規則一抓不到它：對到的是早就播過的集數。只看 RSS Series：
  手動送單搜的常常本來就是舊集。

可疑的那一列送審核（`PlanAction.REVIEW`），季集與目標路徑留著：BD 版晚幾個月才發也會落在規則二，
那時核准就照這一格入庫（`parser.promote`）。

**不寫死在 RSS 的路徑裡**：手動送單套規則一，M5 的 AI 結果也要過同一條（brief §14「AI 說了不算」），
所以它只吃 Plan Item、快照與一個發佈時間。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from berth.domain import (
    MediaSnapshot,
    PlanItem,
    episode_label,
    why,
)
from berth.domain import ReasonCode as Code
from berth.parser.planner import episode_span, hold, note
from berth.parser.publishing import BEHIND_LATEST, RELEASE_TOLERANCE

#: 播出日比對把一列送審核時留下的理由。規劃器看到其中一條就把整份 Plan 的理由說成
#: `ReviewReason.AIR_DATE_CONFLICT`（`services/plan._verdict`）。
HELD_BY_AIRING: frozenset[Code] = frozenset(
    {Code.RELEASED_BEFORE_AIRING, Code.BEHIND_LATEST_EPISODE}
)


def check_airing(
    items: Sequence[PlanItem],
    media: MediaSnapshot | None,
    published: datetime | None,
    *,
    from_series: bool,
) -> tuple[PlanItem, ...]:
    """逐列比對，可疑的送審核並說出兩個日期。純函式。

    只看**要入庫的正片**（`episode_span`）：其餘的列沒有一集可以比。`from_series` 是「這一筆是
    RSS Series 送的」——規則二只對它（作品在發佈時還在不在連載，由 `_far_behind` 另外看）。
    缺發佈時間、或 TMDB 沒有那一集的播出日時不擋，記一筆（沒有日期就沒有證據說它錯）。
    """
    if media is None:
        return tuple(items)
    return tuple(_checked(item, media, published, from_series=from_series) for item in items)


def _checked(
    item: PlanItem, media: MediaSnapshot, published: datetime | None, *, from_series: bool
) -> PlanItem:
    span = episode_span(item)
    if span is None:
        return item
    season, start, end = span
    label = episode_label(season, start, end if end != start else None)
    if published is None:
        return note(item, why(Code.PUBLISHED_MISSING))
    aired = _aired(media, season, end)
    if aired is None:
        return note(item, why(Code.AIR_DATE_MISSING, episode=label))
    day = published.date()
    if aired - day > RELEASE_TOLERANCE:
        return hold(
            item,
            why(
                Code.RELEASED_BEFORE_AIRING,
                published=day.isoformat(),
                episode=label,
                aired=aired.isoformat(),
            ),
        )
    latest = _latest(media, day) if from_series and season > 0 else None
    if latest is not None and _far_behind(aired, latest[1], day):
        number, when = latest
        return hold(
            item,
            why(
                Code.BEHIND_LATEST_EPISODE,
                episode=label,
                aired=aired.isoformat(),
                latest=episode_label(*number),
                latest_aired=when.isoformat(),
            ),
        )
    return item


def _far_behind(aired: date, latest: date, day: date) -> bool:
    """對到的那一集比最近播出的一集早超過門檻，**而且作品在發佈時還在播**。

    「還在播」＝最近播出的一集離發佈不到門檻那麼久。播完很久之後才發的（BD、補檔）最近播出的
    就是最後一集，拿它比每一集都「早很多」，那不是算錯。
    """
    return latest - aired > BEHIND_LATEST and day - latest <= BEHIND_LATEST


def _latest(media: MediaSnapshot, day: date) -> tuple[tuple[int, int], date] | None:
    """發佈當時最近播出的一集（正片的季，播出日不晚於發佈日加容忍）：（（季, 集）, 播出日）。

    容忍與規則一同一個：發佈比 TMDB 的日期早一天的那一集，就是字幕組手上最新的那一集。
    """
    cutoff = day + RELEASE_TOLERANCE
    aired = [
        ((season.season_number, episode.episode_number), episode.air_date)
        for season in media.seasons
        if season.season_number > 0
        for episode in season.episodes
        if episode.air_date is not None and episode.air_date <= cutoff
    ]
    return max(aired, key=lambda found: (found[1], found[0])) if aired else None


def _aired(media: MediaSnapshot, season: int, episode: int) -> date | None:
    """TMDB 說這一集哪天播。沒有這一集、或 TMDB 沒填日期，都是 `None`。"""
    found = media.episode(season, episode)
    return found.air_date if found is not None else None
