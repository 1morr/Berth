"""「為什麼沒入庫」的結論分類（M5 票 10）。**規則只在這裡一份**：API 回的、agent 讀的、
之後畫面上顯示的，都是這裡算出來的那一個值，沒有人自己再推一次。

一集（或一部電影）的事實收成 `EpisodeFacts`，`conclude` 照固定順序挑一個 `WhyNot`。
一部作品整體的結論是各集裡最前面的那一個（`overall`，宣告順序就是優先序）。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from berth.domain.enums import UNDER_WAY_STATES, FeedItemStatus, JobState


class WhyNot(StrEnum):
    """一集為什麼還沒在媒體庫裡（或其實已經在了）。

    **宣告順序就是優先序**，與 `InventoryStatus` 同一個規矩：一部作品同時有好幾集各有原因時，
    整體說的是最前面那一種——需要人動手的排前面，自己會好的排後面，沒事的最後。
    """

    #: 下載完了，入庫那一步失敗（`import_failed`）。要人看那一筆。
    IMPORT_FAILED = "import_failed"
    #: 沒下載成：送單失敗、客戶端報錯、檔案不見、torrent 被移出 qBittorrent，
    #: 或 RSS 那一筆送單被拒。
    DOWNLOAD_FAILED = "download_failed"
    #: 下載完了，停在審核（`review`）等管理員。
    AWAITING_REVIEW = "awaiting_review"
    #: RSS 有這一集，但它的 RSS Series 還在待綁定：綁好之前不送。
    UNBOUND = "unbound"
    #: RSS 有這一集，被排除條件擋下，或新 Feed 第一輪選了「只追之後的」。
    EXCLUDED = "excluded"
    #: 播了，但哪裡都沒有它：沒有 Job，RSS 也沒出現過。
    NO_SOURCE = "no_source"
    #: 在路上：送單到入庫之間的哪一站（含停滯），或 RSS 綁好了、下一輪就送。
    DOWNLOADING = "downloading"
    #: 帳本有它，Jellyfin 還沒認到那個檔案（還在反查，或反查用完了）。
    JELLYFIN_PENDING = "jellyfin_pending"
    #: 還沒播，或 TMDB 還沒有播出日。
    UNAIRED = "unaired"
    #: 已入庫，Jellyfin 也找到了。
    IMPORTED = "imported"


#: 沒下載成的 Job：在你動手之前不會自己好，而且它連檔案都沒交出來（與入庫失敗分開）。
DOWNLOAD_FAILED_STATES: frozenset[JobState] = frozenset(
    {
        JobState.SUBMIT_FAILED,
        JobState.MISSING_FILES,
        JobState.CLIENT_ERROR,
        JobState.CLIENT_REMOVED,
    }
)

#: RSS 那一筆不送、而且是有人決定的：排除條件，或第一輪選了「只追之後的」。
_HELD_BACK: frozenset[FeedItemStatus] = frozenset({FeedItemStatus.EXCLUDED, FeedItemStatus.PASSED})


@dataclass(frozen=True, slots=True)
class EpisodeFacts:
    """一集（或一部電影）身上的事實。誰蓋到它由呼叫端決定，這裡只看結果。"""

    #: 帳本有正片蓋到它。
    imported: bool
    #: 蓋到它的正片裡至少一個 Jellyfin 已經認到。
    in_jellyfin: bool
    #: 蓋到它的 Job 的狀態。已入庫（`imported`）與已移除（`removed`）的在裡面也不影響結論：
    #: 已入庫的看帳本，刪掉的就是沒有了。
    jobs: frozenset[JobState]
    #: 蓋到它的 Feed Item 的狀態。上一次送單被拒的 `matched` 不在這裡，算在 `send_rejected`：
    #: 這裡的 `matched` 是下一輪就送的。
    items: frozenset[FeedItemStatus]
    #: 蓋到它的 `matched` Feed Item 裡，有一筆上一次送單被拒。
    send_rejected: bool
    aired: bool


def conclude(facts: EpisodeFacts) -> WhyNot:
    """一集的結論。順序：已入庫 → 停下來等人的 Job → 在路上的 → 沒下載成的 → RSS 那一側 → 播了沒。

    停下來等人的排在在路上的前面，與季表的「卡住」優先於「下載中」同一個規矩；沒下載成的排在
    在路上的後面：另一筆正在下載時，那一集還是會來。
    """
    if facts.imported:
        return WhyNot.IMPORTED if facts.in_jellyfin else WhyNot.JELLYFIN_PENDING
    if JobState.IMPORT_FAILED in facts.jobs:
        return WhyNot.IMPORT_FAILED
    if JobState.REVIEW in facts.jobs:
        return WhyNot.AWAITING_REVIEW
    if facts.jobs & UNDER_WAY_STATES:
        return WhyNot.DOWNLOADING
    if FeedItemStatus.MATCHED in facts.items:
        return WhyNot.DOWNLOADING
    if facts.jobs & DOWNLOAD_FAILED_STATES or facts.send_rejected:
        return WhyNot.DOWNLOAD_FAILED
    if FeedItemStatus.UNBOUND in facts.items:
        return WhyNot.UNBOUND
    if facts.items & _HELD_BACK:
        return WhyNot.EXCLUDED
    return WhyNot.NO_SOURCE if facts.aired else WhyNot.UNAIRED


def overall(conclusions: Iterable[WhyNot]) -> WhyNot | None:
    """一部作品整體的結論：各集裡最前面的那一種。一集都沒有時是 `None`。"""
    order = list(WhyNot)
    return min(conclusions, key=order.index, default=None)
