"""第一批的證據夠不夠強（M4 票 11、brief §15、plan §11.4）。

自動綁定的 RSS Series 在確認之前送來的每一集都等人看一眼（`services/plan._audit`），為的是抓規則層
看不出的季號與 offset 錯——split-cour、字幕組每一輪從 01 重數。Jellyfin 回驗抓不到它們：Jellyfin
認集數靠 Berth 取的檔名。可是季集照字面、發佈時間正好是那一集剛播的第一批，人展開也看不出要在意
什麼（2026-09-26 試跑，BLACK TORCH 四集）。這一支回答「這一份計劃是不是那一種」，是的話系統替人
確認那個 Series。

**條件逐列看，一列不符合整份就不算**：

1. Series 沒有設季號與 offset——設了就是人說過話，不是照字面。
2. 要入庫的每一列是正片（`import`）或跟著正片走的字幕；特典、留在原位、等人決定的列一出現就不算
   （這裡替它們擔保不了什麼）。至少要有一集正片。
3. **季集照字面**：對到的集號就是檔名寫的集號（`written_episode`，沒有 offset、絕對編號換算、
   重數推測），季號是發佈名或資料夾寫明的、或只寫集號而對到第一季。
4. **理由只有這幾種**（`VOUCHED`）：標題對上、年份對上、季號的字面來源、只有一季、發佈時間落在
   第一輪、TMDB 沒有片長。其餘的每一條——篇章名、絕對編號、cour、虛擬季、Series 的季號、人改過、
   任何一條壓低信心的疑點——都不在裡面，**之後新加的理由預設也不在**。
5. **播出日比對拿得到那一集的播出日而且通過**：發佈時間有、TMDB 有那一集的播出日（缺一樣，
   比對只記一筆放行，那不是「通過」）；比對擋下的列是 `review`，第 2 條已經不算。
6. **那一集剛播**：播出日落在發佈日往前 `BEHIND_LATEST`、往後 `RELEASE_TOLERANCE` 之間（與
   `publishing.just_aired` 同一個窗口）。票面的起點是「信心 high」，但只寫集號的單季作品——正是
   BLACK TORCH——解析器給的是 medium：TMDB 還沒建新的一季、字幕組沿用標題從 01 重數時，照字面讀成
   第一季是錯的，而播出日比對抓不到這個方向（發佈晚於播出是正常的，plan §11.4 ①）。「剛播」補上
   那一個方向：新一季的第 3 集發佈時，第一季的第 3 集早就播完了。

片長驗證通過或量不出隱含在第 2 條裡：它擋下的列是 `review`。

**已知盲點**：前一季短到幾集、緊接著開播 TMDB 還沒建的新一季時，新一季的第 1 集照字面讀成的舊的
第 1 集也可能在六週之內播過。那時確認的是錯的 Series，之後的集數靠播出日比對與「TMDB 沒有那一集」
接住。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from berth.domain import Confidence, MediaSnapshot, PlanAction, PlanItem
from berth.domain import ReasonCode as Code
from berth.parser.planner import episode_span, written_episode
from berth.parser.publishing import just_aired

#: 一列正片可以帶著的理由。**白名單**：沒列在這裡的理由一出現，那一列就不算照字面。
VOUCHED: frozenset[Code] = frozenset(
    {
        Code.TITLE_EXACT,
        Code.TITLE_CONTAINED,
        Code.TITLE_PARTIAL,
        Code.YEAR_MATCHES,
        Code.SEASON_FROM_RELEASE,
        Code.SEASON_FROM_FOLDER,
        Code.SINGLE_SEASON,
        # 單季作品只寫集號、剛播時解析器走的是這一條（第一輪的重數就是字面那一集）。重數到後面
        # 某一輪的那一種由第 3 條擋下：對到的集號不是檔名寫的。
        Code.PUBLISHED_IN_RUN,
        Code.RUNTIME_MISSING,
    }
)

#: 季號是寫明的：發佈名或資料夾說了第幾季。沒有的話只寫集號的那一種要對到第一季才算照字面。
_WRITTEN_SEASON: frozenset[Code] = frozenset({Code.SEASON_FROM_RELEASE, Code.SEASON_FROM_FOLDER})

#: 跟著正片走、本身不必擔保什麼的列；`skip` 不寫進媒體庫。
_ALONGSIDE: frozenset[PlanAction] = frozenset({PlanAction.SUBTITLE, PlanAction.SKIP})


def vouch_first_batch(
    torrent_name: str,
    items: Sequence[PlanItem],
    media: MediaSnapshot | None,
    published: datetime | None,
    *,
    season_hint: int | None,
    episode_offset: int | None,
) -> tuple[tuple[int, int, int], ...] | None:
    """證據夠強就回它擔保的那幾集（季, 起始集, 結束集），不夠就是 `None`。純函式。

    `items` 是過完程式檢查與 Route 政策的那一份（`services/plan._decided`）；`season_hint` 與
    `episode_offset` 是 Series 上的兩個值。
    """
    if media is None or published is None or season_hint is not None or episode_offset is not None:
        return None
    spans: list[tuple[int, int, int]] = []
    for item in items:
        if item.action in _ALONGSIDE:
            continue
        span = episode_span(item)
        if span is None or not _literal(torrent_name, item, media, published):
            return None
        spans.append(span)
    return tuple(spans) or None


def _literal(torrent_name: str, item: PlanItem, media: MediaSnapshot, published: datetime) -> bool:
    """條件 3–6：這一列照字面、理由乾淨、播出日對得上而且剛播。"""
    codes = {reason.code for reason in item.reasons}
    if item.confidence is Confidence.LOW or not codes <= VOUCHED:
        return False
    if written_episode(torrent_name, item.rel_path) != item.episode_start:
        return False
    if not codes & _WRITTEN_SEASON and item.season != _first_season(media):
        return False
    return _just_aired(item, media, published)


def _first_season(media: MediaSnapshot) -> int | None:
    regular = [season.season_number for season in media.seasons if season.season_number > 0]
    return min(regular) if regular else None


def _just_aired(item: PlanItem, media: MediaSnapshot, published: datetime) -> bool:
    """TMDB 有那一集（區間取最後一集）的播出日，而且它剛播。窗口的上緣就是播出日比對的規則一。"""
    span = episode_span(item)
    found = media.episode(span[0], span[2]) if span is not None else None
    if found is None or found.air_date is None:
        return False
    return just_aired(found.air_date, published.date())
