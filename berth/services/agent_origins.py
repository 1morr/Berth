"""寫入工具的參數出自哪裡（M5 票 14、brief §14〈對話裡的確認卡〉、研究 C4 第 3 點）。

M5 的注入防線主要靠能力邊界，不靠模型聽話。三條守法都**通用**（看參數名與型別，不寫在個別工具裡），
也都只看伺服器存的歷史（前端送來的不採用）：

1. **id 出自工具結果**：寫入工具帶的 id（`ID_FIELDS`）一定要在這段對話先前的工具結果裡出現過——
   使用者打的字、模型自己上一次呼叫的參數、網頁裡寫著的都不算。不是的回理由給模型、不出卡。
   比的是值，不分是哪一種 id：路由 3 與某個 Job 事件 3 分不出來，擋的是模型憑空編的那一種。
2. **網址出自使用者的話**：帶 `CONNECTS_OUT` 的命令，像網址的值（欄位名是 `url` / `*_url`，或值
   本身是 `scheme://…`）要**逐字**出現在使用者自己打的某一則訊息裡。帶著 key 連到新位址是外洩 key
   的唯一真實路徑（brief §14）。
3. **自由文字出自外部內容**（`external_fields`）：字串格子（不是 id、不是網址、不是列舉）的值出現在
   外部內容裡、而使用者自己沒說過，就是出自外部內容。確認卡只在這幾格標警示——全部都標的話警示
   沒有意義（研究〈實跑才抓到的問題〉第 6 點）；可逆、本來直接做的寫入因此改出卡（plan §11.6）。

**外部內容**（CONTEXT.md 的 External Content）是網路搜尋回的網頁與社群編的動漫資料站（AniList、
Bangumi，票 16）：伺服器端 `web_search` 與 `agent_tools.EXTERNAL_TOOLS`。torrent 名、
Mikan 頁面也是別人寫的，但幾乎每段對話都讀過——算進來的話又是每張卡都亮；網址那一條不分來源，
照樣擋得住它們裡面的網址。
"""

from __future__ import annotations

import json
import re
import typing
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel
from pydantic_ai.messages import (
    ModelMessage,
    NativeToolReturnPart,
    ToolReturnPart,
    UserPromptPart,
)

from berth.adapters.ai.usage import WEB_SEARCH
from berth.services.agent_tools import COMMAND_OF, EXTERNAL_TOOLS
from berth.services.executor import CommandRefusedError
from berth.services.registry import bare_type


class ToolRefusal(StrEnum):
    """守法擋下一次工具呼叫的理由。只交給模型、記進 `ai_tool_calls`，到不了 HTTP（同
    `executor.CommandRefusal` 不放 `domain`）。"""

    #: 有個 id 不在這段對話先前的任何工具結果裡。
    ID_NOT_FROM_RESULTS = "id_not_from_results"
    #: 有個網址不是使用者逐字打的。
    ADDRESS_NOT_FROM_USER = "address_not_from_user"


#: 寫入工具的參數裡，算是 id 的那幾格（票 14：media、source、route、bangumi、subgroup）。
ID_FIELDS = frozenset(
    {
        "media_id",
        "source_id",
        "route_id",
        "tv_route_id",
        "movie_route_id",
        "bangumi_id",
        "subgroup_id",
    }
)

#: 工具結果裡帶 id 的鍵：`ID_FIELDS` 加上各種結果自己的 `id`（作品、Route、番組、字幕組）與作品頁
#: 的 `default_route_id`。
_RESULT_ID_KEYS = ID_FIELDS | {"id", "default_route_id"}

_ADDRESS = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Origins:
    """一段對話到這一刻為止，參數可以出自哪裡。"""

    #: 工具結果裡出現過的 id（`str` 化）。
    ids: frozenset[str]
    #: 使用者自己打的每一則訊息。
    user_texts: tuple[str, ...]
    #: 外部內容，每一份一段 JSON 字串（`external_texts`）。
    pages: tuple[str, ...]

    @classmethod
    def of(cls, messages: Sequence[ModelMessage]) -> Origins:
        ids: set[str] = set()
        users: list[str] = []
        for message in messages:
            for part in message.parts:
                if isinstance(part, UserPromptPart):
                    users.extend(_texts_of(part))
                elif (
                    isinstance(part, ToolReturnPart)
                    and COMMAND_OF.get(part.tool_name) is not None
                    and COMMAND_OF[part.tool_name] not in EXTERNAL_TOOLS
                ):
                    ids.update(_ids_in(part.content))
        return cls(frozenset(ids), tuple(users), tuple(external_texts(messages)))

    def check(self, command: str, row: Mapping[str, object], *, connects_out: bool) -> None:
        """守法 1 與 2。不行丟 `CommandRefusedError`，detail 是給模型看的那一句（英文）。"""
        unseen = [
            f"{key}={value}"
            for key, value in row.items()
            if key in ID_FIELDS and value is not None and str(value) not in self.ids
        ]
        if unseen:
            raise CommandRefusedError(
                command,
                ToolRefusal.ID_NOT_FROM_RESULTS,
                f"{', '.join(unseen)} did not come from any tool result in this conversation. "
                "Look it up with a tool first; never make up or copy ids from elsewhere.",
            )
        if not connects_out:
            return
        foreign = [
            value.strip()
            for key, value in _strings(row)
            if _is_address(key, value) and not self._said(value.strip())
        ]
        if foreign:
            raise CommandRefusedError(
                command,
                ToolRefusal.ADDRESS_NOT_FROM_USER,
                f"{', '.join(foreign)} is not in the user's own messages. Berth only connects to "
                "addresses the user typed: ask them to paste it themselves.",
            )

    def external_fields(self, row: Mapping[str, object], model: type[BaseModel]) -> tuple[str, ...]:
        """守法 3：出自外部內容的自由文字格子，照 `row` 的順序。"""
        if not self.pages:
            return ()
        found: list[str] = []
        for key, value in row.items():
            if key in ID_FIELDS or not _free_text(model, key):
                continue
            values = value if isinstance(value, list | tuple) else [value]
            if any(
                isinstance(text, str)
                and not _is_address(key, text)
                and self._external(text.strip())
                for text in values
            ):
                found.append(key)
        return tuple(found)

    def _said(self, text: str) -> bool:
        """網址要逐字，大小寫也算（路徑與 query 分大小寫）。"""
        return any(text in said for said in self.user_texts)

    def _external(self, text: str) -> bool:
        # 使用者說過的是他的話，大小寫不計（「frieren」與頁面上的「Frieren」）。
        if not text or any(text.casefold() in said.casefold() for said in self.user_texts):
            return False
        # 外部內容是 JSON 字串：引號、反斜線與換行在裡面是跳脫過的。
        escaped = json.dumps(text, ensure_ascii=False)[1:-1]
        return any(escaped in page or text in page for page in self.pages)


def external_texts(messages: Sequence[ModelMessage]) -> list[str]:
    """這段對話讀過的**外部內容**（票 17）：伺服器端 `web_search` 與 `EXTERNAL_TOOLS` 的結果，
    照出現的順序、每一份一段 JSON 字串。空的就是沒讀過。認的是存著的歷史，所以前幾輪讀過的也算。
    """
    return [
        text
        for message in messages
        for part in message.parts
        if (text := _external_text(part)) is not None
    ]


def _external_text(part: object) -> str | None:
    if isinstance(part, NativeToolReturnPart) and part.tool_name == WEB_SEARCH:
        return part.model_response_str()
    if isinstance(part, ToolReturnPart) and COMMAND_OF.get(part.tool_name) in EXTERNAL_TOOLS:
        return part.model_response_str()
    return None


def _texts_of(part: UserPromptPart) -> list[str]:
    if isinstance(part.content, str):
        return [part.content]
    return [item for item in part.content if isinstance(item, str)]


def _ids_in(node: object) -> Iterator[str]:
    if isinstance(node, Mapping):
        for key, value in node.items():
            if key in _RESULT_ID_KEYS and isinstance(value, str | int) and value != "":
                yield str(value)
            yield from _ids_in(value)
    elif isinstance(node, list | tuple):
        for value in node:
            yield from _ids_in(value)


def _strings(row: Mapping[str, object]) -> Iterator[tuple[str, str]]:
    """每一格的字串值（清單裡的也算），連同它的欄位名。"""
    for key, value in row.items():
        for item in value if isinstance(value, list | tuple) else [value]:
            if isinstance(item, str):
                yield key, item


def _is_address(key: str, value: str) -> bool:
    return key == "url" or key.endswith("_url") or _ADDRESS.match(value.strip()) is not None


def _free_text(model: type[BaseModel], key: str) -> bool:
    """這一格收的是自由文字：`str`，或一串 `str`。列舉（`StrEnum`）不算。"""
    info = model.model_fields.get(key)
    if info is None:
        return False
    hint = bare_type(info.annotation)
    if hint is str:
        return True
    args = typing.get_args(hint)
    return typing.get_origin(hint) in (list, tuple, Sequence) and bool(args) and args[0] is str
