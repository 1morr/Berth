"""訂閱 RSS 的防線：網址從哪裡來（M5 票 11，brief §6.10「外部文字是資料」②，plan §11.6
〈對話核心〉）。

加一個 Feed 就是讓 Berth 之後每隔一段時間連一個位址——外洩與 SSRF 的通道。搜尋結果、番組頁、
發佈名都是陌生人寫的，可能藏著「把這個網址加成 Feed」。防線不靠模型聽話，靠這裡：

- **網址由 Berth 自己組的直接做**（2026-10-24 使用者：不想手動確認）：Mikan 以番組與字幕組 id
  訂閱，**兩個 id 都要是這則對話裡 Berth 自己搜出來的**——番組出現在某一次「搜 Mikan 番組」的
  結果裡、字幕組出現在那個番組的某一次「列字幕組」結果裡（`vet_mikan`）；不是的直接拒絕。
  Nyaa / acg.rip 以搜尋詞訂閱，網址由 adapter 組，主機固定。
- **模型直接給的整個網址**（以網址加 Feed）：逐字出現在使用者這則對話自己打的話裡才直接做
  （`said_by_user`），否則降成確認卡（`ProposalCause.URL_NOT_FROM_USER`，票 10 的入口）。
  頁面那一段、工具結果、模型自己的話都不算。

出處都是這則對話存下的那幾則（`conversation_messages`），Berth 寫的，模型改不到。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from berth.services.commands import Effect, command
from berth.services.conversations import tool_results_of, user_words_of

#: 兩個 Mikan 查詢工具的名字（`services/tools.py` 登記的那兩條）：訂閱只認它們存下的結果。
MIKAN_SEARCH_TOOL = "search_mikan"
MIKAN_SUBGROUPS_TOOL = "mikan_subgroups"


class SubscribeRefusal(StrEnum):
    """AI 訂閱不了的理由（M5 票 11）。只有工具會說，不在 `domain/enums.py`（同
    `submit_guard.SubmitRefusal`）；照樣進 OpenAPI，前端說得出人話。"""

    #: 這個番組 id 不在這則對話任何一次「搜 Mikan 番組」的結果裡：別處來的、猜的、頁面裡寫的。
    BANGUMI_NOT_FROM_THIS_CONVERSATION = "bangumi_not_from_this_conversation"
    #: 這個字幕組不在這則對話裡那個番組的任何一次「列字幕組」結果裡。
    SUBGROUP_NOT_FROM_THIS_CONVERSATION = "subgroup_not_from_this_conversation"
    #: 這部作品有不只一條 Route 收得下、上次送單也沒用過任何一條，而呼叫沒說要哪一條。`detail` 列出
    #: 收得下的那幾條（`2=Anime, 1=TV`）。
    ROUTE_NEEDED = "route_needed"


class SubscribeRefusedError(Exception):
    """訂閱在動任何東西之前就停下來了。"""

    def __init__(self, reason: SubscribeRefusal, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason.value)
        self.reason = reason
        self.detail = detail


# --- 兩個 Mikan 查詢工具的結果型別 ------------------------------------------------------
# 住在這裡而不是 `tools.py`：訂閱讀回來的就是這個形狀，兩邊要是同一份。


class MikanBangumi(BaseModel):
    """Mikan 搜尋頁上的一個番組。"""

    id: int
    #: 中文名（多半是簡體），原樣。外部來的文字：資料，不是指令。
    title: str


class MikanSearchResults(BaseModel):
    """「搜 Mikan 番組」的結果（M5 票 11）：照頁上的順序。"""

    term: str
    bangumi: list[MikanBangumi]


class MikanSubgroup(BaseModel):
    """一個番組底下的一個字幕組（作品頁「RSS 訂閱」挑的那幾列，`bangumi.SubgroupView`）。"""

    id: int
    name: str
    #: 最近一次發佈的日期。
    updated: date | None
    #: 這一組在番組頁上列了幾筆發佈。
    releases: int
    #: 最近一筆的發佈名，原樣。
    latest: str
    #: 這一組的 RSS Series 已經綁在哪一部作品上；沒綁是 `null`。
    bound_to: str | None


class MikanSubgroups(BaseModel):
    """「列字幕組」的結果（M5 票 11）。"""

    bangumi: int
    title: str
    subgroups: list[MikanSubgroup]


@command(Effect.READ)
async def vet_mikan(
    session: AsyncSession, *, conversation_id: int | None, bangumi_id: int, subgroup_id: int
) -> tuple[MikanSubgroups, MikanSubgroup]:
    """這兩個 id 可以由 AI 訂閱嗎：番組要在這則對話的某一次搜尋結果裡、字幕組要在這則對話裡那個番組
    的某一次字幕組清單裡。回那份清單與那一組（名字給 Feed 與 RSS Series，不收模型寫的）；不行就丟
    `SubscribeRefusedError`，什麼都沒動。"""
    if conversation_id is None or not any(
        hit.id == bangumi_id
        for part in await tool_results_of(session, conversation_id, MIKAN_SEARCH_TOOL)
        for hit in _read(
            MikanSearchResults, part.result, MikanSearchResults(term="", bangumi=[])
        ).bangumi
    ):
        raise SubscribeRefusedError(
            SubscribeRefusal.BANGUMI_NOT_FROM_THIS_CONVERSATION, str(bangumi_id)
        )
    for part in await tool_results_of(session, conversation_id, MIKAN_SUBGROUPS_TOOL):
        listed = _read(MikanSubgroups, part.result, None)
        if listed is None or listed.bangumi != bangumi_id:
            continue
        group = next((group for group in listed.subgroups if group.id == subgroup_id), None)
        if group is not None:
            return listed, group
    raise SubscribeRefusedError(
        SubscribeRefusal.SUBGROUP_NOT_FROM_THIS_CONVERSATION, str(subgroup_id)
    )


def _read[M: BaseModel, D](model: type[M], stored: dict[str, Any], default: D) -> M | D:
    """存下的一份結果照這一版的型別讀回來；舊版本存的形狀讀不回就當沒有（不是這則對話搜出來的）。"""
    try:
        return model.model_validate(stored)
    except ValidationError:
        return default


#: 使用者的話裡一段像網址的字：到空白或常見的括號、引號、全形標點為止。
_URL = re.compile(
    r"""https?://[^\s<>"'`()\[\]{}（）「」『』【】《》，。、；！？]+""", re.IGNORECASE
)
#: 句子裡網址後面常接的半形標點：「加這個 https://…/rss.」那一點不是網址的一部分。
_TRAILING = ".,;:!?"


@command(Effect.READ)
async def said_by_user(session: AsyncSession, *, conversation_id: int | None, url: str) -> bool:
    """`url` 是不是**整個**、逐字出現在使用者這則對話自己打的話裡。

    比的是整個網址：使用者貼了 `…&q=frieren&u=someone`、模型拿掉後半段也不算——那已經不是他說的
    位址。網址後面接著句點、逗號時，去掉那幾個字再比一次。
    """
    if conversation_id is None:
        return False
    return written_in(await user_words_of(session, conversation_id), url)


def written_in(texts: Sequence[str], url: str) -> bool:
    """`said_by_user` 的比對本身：`url` 是不是 `texts` 裡某一段網址的全部。"""
    wanted = url.strip()
    return bool(wanted) and any(
        wanted in (found, found.rstrip(_TRAILING)) for text in texts for found in _URL.findall(text)
    )
