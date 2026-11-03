"""照字面的讀法：一列正片的季集就是檔名寫的那一個，中間沒有任何換算（M5.5 票 04）。

播出日比對（`parser.airing`）與第一批的擔保（`parser.first_batch`）共用這一個定義：前者對照字面的列
多容忍地上波先行，後者只替照字面的列擔保。兩邊各寫一份的話，比對放行的先行集數，擔保那一邊可能
認不出來（或反過來）。

**三個條件都要成立**：

1. **理由只有這幾種**（`VOUCHED`，白名單）：標題對上、年份對上、季號的字面來源、只有一季、發佈時間
   落在第一輪、地上波先行、TMDB 沒有片長。其餘的每一條——篇章名、絕對編號、cour、虛擬季、
   Series 的季號（`season_from_job`）、人改過、任何一條壓低信心的疑點——都不在裡面，**之後新加的
   理由預設也不在**。信心 low 也不算。
2. **集號照字面**：對到的集號就是檔名寫的集號（`written_episode`）。Series 設了 offset 時兩者不同。
3. **季號照字面**：發佈名或資料夾寫明，或只寫集號而對到第一季。

Series 上人設的季號由第 1 條擋（`season_from_job`）；offset 由第 2 條擋，只有設成 0 時照字面——那等於
人說了「檔名寫的就是 TMDB 的集號」。第一批另外要求 Series 兩個值都沒設（`vouch_first_batch`）。
"""

from __future__ import annotations

from berth.domain import Confidence, MediaSnapshot, PlanItem
from berth.domain import ReasonCode as Code
from berth.parser.planner import written_episode

#: 照字面的一列可以帶著的理由。**白名單**：沒列在這裡的理由一出現，那一列就不算照字面。
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
        # 某一輪的那一種由第 2 條擋下：對到的集號不是檔名寫的。
        Code.PUBLISHED_IN_RUN,
        # 播出日比對放行照字面的先行時記的；它只會出現在已經照字面的列上。
        Code.RELEASED_AHEAD_OF_AIRING,
        Code.RUNTIME_MISSING,
    }
)

#: 季號是寫明的：發佈名或資料夾說了第幾季。沒有的話只寫集號的那一種要對到第一季才算照字面。
WRITTEN_SEASON: frozenset[Code] = frozenset({Code.SEASON_FROM_RELEASE, Code.SEASON_FROM_FOLDER})


def is_literal(torrent_name: str, item: PlanItem, media: MediaSnapshot) -> bool:
    """這一列是不是照字面讀的（上面三個條件）。純函式。"""
    codes = {reason.code for reason in item.reasons}
    if item.confidence is Confidence.LOW or not codes <= VOUCHED:
        return False
    if written_episode(torrent_name, item.rel_path) != item.episode_start:
        return False
    return bool(codes & WRITTEN_SEASON) or item.season == _first_season(media)


def _first_season(media: MediaSnapshot) -> int | None:
    regular = [season.season_number for season in media.seasons if season.season_number > 0]
    return min(regular) if regular else None
