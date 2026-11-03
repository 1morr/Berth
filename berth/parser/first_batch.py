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
3. **照字面**（`parser.literal.is_literal`，與播出日比對放行先行同一個定義）：對到的集號就是檔名寫的
   集號（`written_episode`，沒有 offset、絕對編號換算、重數推測），季號是發佈名或資料夾寫明的、
   或只寫集號而對到第一季。
   **3b. 或是寫明季號的累計編號**（M5.5 票 05，brief §15）：理由是 `absolute_cumulative`、
   季號是發佈名或資料夾寫明的、檔名集號正好等於前面各季集數加對到的集號（夜櫻 40 → 前面 27 集
   + S02E13）。季號與累加換算互相印證，讀法是確定的。只寫集號的絕對編號（季號是換算推出來的）、
   `absolute_group`、重數推測都不算。這一種的理由白名單另有一份（`_CUMULATIVE`），不含地上波先行。
4. **理由只有這幾種**（第 3 條的 `VOUCHED`，在 `parser.literal`；3b 看自己的 `_CUMULATIVE`）：
   標題對上、年份對上、季號的字面來源、只有一季、發佈時間落在第一輪、地上波先行
   （`released_ahead_of_airing`）、TMDB 沒有片長。其餘的每一條——篇章名、絕對編號、cour、虛擬季、
   Series 的季號、人改過、任何一條壓低信心的疑點——都不在裡面，**之後新加的理由預設也不在**。
5. **播出日比對拿得到那一集的播出日而且通過**：發佈時間有、TMDB 有那一集的播出日（缺一樣，
   比對只記一筆放行，那不是「通過」）；比對擋下的列是 `review`，第 2 條已經不算。
6. **那一集剛播**：播出日落在發佈日往前 `BEHIND_LATEST`、往後 `RELEASE_TOLERANCE` 加
   `SIMULCAST_LEAD` 之間（`publishing.just_aired(literal=True)`，上緣與播出日比對放行照字面的列
   相同；M5.5 票 04 前是兩天，地上波先行的第一批因此擔保不了）。累計編號（3b）與推測虛擬季用
   兩天的那一個窗口：有換算的讀法，播出日比對也只容忍兩天。
   票面的起點是「信心 high」，但只寫集號的單季作品——正是 BLACK TORCH——解析器給的是 medium：
   TMDB 還沒建新的一季、字幕組沿用標題從 01 重數時，照字面讀成第一季是錯的，而播出日比對抓不到
   這個方向（發佈晚於播出是正常的，plan §11.4 ①）。「剛播」補上那一個方向：
   新一季的第 3 集發佈時，第一季的第 3 集早就播完了。

片長驗證通過或量不出隱含在第 2 條裡：它擋下的列是 `review`。

**已知盲點**：前一季短到幾集、緊接著開播 TMDB 還沒建的新一季時，新一季的第 1 集照字面讀成的舊的
第 1 集也可能在六週之內播過。那時確認的是錯的 Series，之後的集數靠播出日比對與「TMDB 沒有那一集」
接住。

**已知盲點（3b）**：字幕組與 TMDB 的前幾季集數差一集時（總集篇只有一邊算），換算仍落在寫明的那一季、
晚一週也在 `BEHIND_LATEST` 之內，擔保的會差一集（brief §15）。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from berth.domain import Confidence, MediaSnapshot, PlanAction, PlanItem
from berth.domain import ReasonCode as Code
from berth.parser.literal import WRITTEN_SEASON, is_literal
from berth.parser.planner import episode_span, written_episode
from berth.parser.publishing import just_aired

#: 跟著正片走、本身不必擔保什麼的列；`skip` 不寫進媒體庫。
_ALONGSIDE: frozenset[PlanAction] = frozenset({PlanAction.SUBTITLE, PlanAction.SKIP})

#: 累計編號那一種讀法可以帶著的理由（條件 3b）。**白名單**，同 `VOUCHED`：其他絕對編號
#: （`absolute_group`）、疑點、地上波先行（只記在照字面的列上）都不在。
_CUMULATIVE: frozenset[Code] = frozenset(
    {
        Code.ABSOLUTE_CUMULATIVE,
        Code.TITLE_EXACT,
        Code.TITLE_CONTAINED,
        Code.TITLE_PARTIAL,
        Code.YEAR_MATCHES,
        *WRITTEN_SEASON,
        Code.RUNTIME_MISSING,
    }
)


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
        if span is None or not _vouched(torrent_name, item, media, published):
            return None
        spans.append(span)
    return tuple(spans) or None


def _vouched(torrent_name: str, item: PlanItem, media: MediaSnapshot, published: datetime) -> bool:
    """條件 3–6：這一列照字面或是寫明季號的累計編號、理由乾淨、播出日對得上而且剛播。"""
    if is_literal(torrent_name, item, media):
        return _just_aired(item, media, published, literal=True)
    return _counted_from_first_season(torrent_name, item, media) and _just_aired(
        item, media, published, literal=False
    )


def _counted_from_first_season(torrent_name: str, item: PlanItem, media: MediaSnapshot) -> bool:
    """條件 3b：季號寫明、集號從第一季一路數下來，檔名集號正好是前面各季集數加對到的集號。"""
    codes = {reason.code for reason in item.reasons}
    if item.confidence is Confidence.LOW or not codes <= _CUMULATIVE:
        return False
    if Code.ABSOLUTE_CUMULATIVE not in codes or item.season is None or item.episode_start is None:
        return False
    # 寫明的季號就是換算落到的那一季，兩者互相印證。解析器只在相同時產生這種讀法，這裡自己再守一次。
    # 參數從資料庫讀回時可能是字串。
    written = {str(r.params.get("season")) for r in item.reasons if r.code in WRITTEN_SEASON}
    if written != {str(item.season)}:
        return False
    before = sum(
        season.length for season in media.seasons if 0 < season.season_number < item.season
    )
    return written_episode(torrent_name, item.rel_path) == before + item.episode_start


def _just_aired(
    item: PlanItem, media: MediaSnapshot, published: datetime, *, literal: bool
) -> bool:
    """TMDB 有那一集（區間取最後一集）的播出日，而且它剛播。照字面的列上緣是播出日比對放行它的那一個
    （`RELEASE_TOLERANCE` 加 `SIMULCAST_LEAD`），累計編號的維持 `RELEASE_TOLERANCE`。"""
    span = episode_span(item)
    found = media.episode(span[0], span[2]) if span is not None else None
    if found is None or found.air_date is None:
        return False
    return just_aired(found.air_date, published.date(), literal=literal)
