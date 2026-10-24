"""命令的副作用標記（brief §14「自主權看可不可以撤銷」，M3 票 05）。

每一個 service 命令標明它的副作用等級，可逆的另外說出反向命令是哪一個。M5 的命令登錄表讀它：
可逆的 AI 通過驗證後自己做，不可逆的做成 Proposal 等人。**這裡只有標記**——不收集、不查詢，
登錄表本身在 M5 做；現在要的只是 M3 起新增的命令一出生就帶著它。

反向命令以 `"<模組>.<函式>"` 指名（相對 `berth.services`，同 brief §14 的 `issues.resolve`）：
寫成字串而不是函式物件，是因為反向命令常常定義在後面、或在另一個模組裡。名字寫錯、指到一個
沒標的函式，由 `tests/unit/test_command_marks.py` 擋下。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypeVar

_Command = TypeVar("_Command", bound=Callable[..., Any])

_ATTRIBUTE = "__berth_command__"


class Effect(StrEnum):
    """副作用等級（brief §14）。"""

    #: 只讀，什麼都不改。
    READ = "read"
    #: 改了東西，但有路回去：反向命令、或同一個命令再按一次別的選項。
    REVERSIBLE = "reversible"
    #: 做了就回不去（刪 complete 裡的檔案、移除 torrent、purge）。永遠要人。
    IRREVERSIBLE = "irreversible"


@dataclass(frozen=True, slots=True)
class CommandMark:
    effect: Effect
    #: 撤銷它的那一個命令，`"<模組>.<函式>"`。可逆但沒有單一反向命令的
    #: （例如回去要重新規劃）是 `None`。
    inverse: str | None = None


def command(effect: Effect, *, inverse: str | None = None) -> Callable[[_Command], _Command]:
    """標上副作用等級與反向命令。函式本身原樣回傳，不包一層。"""

    def mark(function: _Command) -> _Command:
        setattr(function, _ATTRIBUTE, CommandMark(effect=effect, inverse=inverse))
        return function

    return mark


def mark_of(function: object) -> CommandMark | None:
    """一個函式的標記；沒標的是 `None`。"""
    found = getattr(function, _ATTRIBUTE, None)
    return found if isinstance(found, CommandMark) else None
