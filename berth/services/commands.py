"""命令的副作用標記（brief §14「自主權看可不可以撤銷」，M3 票 05）。

每一個 service 命令標明它的副作用等級，可逆的另外說出反向命令是哪一個。M5 的命令登錄表讀它：
可逆的 AI 通過驗證後自己做，不可逆的做成 Proposal 等人。**這裡只有標記**——不收集、不查詢，
登錄表本身在 M5 做；現在要的只是 M3 起新增的命令一出生就帶著它。

反向命令以 `"<模組>.<函式>"` 指名（相對 `berth.services`，同 brief §14 的 `issues.resolve`）：
寫成字串而不是函式物件，是因為反向命令常常定義在後面、或在另一個模組裡。名字寫錯、指到一個
沒標的函式，由 `tests/unit/test_command_marks.py` 擋下。

一支命令做好幾件事時（M5 票 04 統一）：**人按的命令照主效果標**——送單順手排的「正在下載」不讓
送單變成不可逆（`downloading.add_manual_download`）；**背景迴圈的入口照最重的副作用標**——一輪裡
排了送出去收不回來的通知就是不可逆（`sweep.sweep_once`、`rss.poll_due`）。**按得了好幾種動作的
照最重的那一種**（`issues.resolve_issue`）：分動作的等級是登錄表登記工具時的事。被
`asynccontextmanager` 包過的也是命令，標記慣例貼在最外層（`downloading.download_round`；貼在
內層也認得）。

**改設定與 Route 標 `irreversible`**（M5 票 05）：回得去，但 brief §14 列為永遠要人，而登錄表直接讀
標記決定出不出確認卡（plan §11.6）。這裡的設定是改變 Berth 怎麼運作的那幾種（服務位址與憑證、對外
網址、門檻）；個人偏好（`notify.set_mine`、`search.remember_names`）、精靈的進度與草稿
（`indexer.skip_indexers`、`jellyfin.save_bundled_libraries`）、單一 Feed 的設定、排除條件（brief
§6.10 的修正回流，全域那一層也是）照舊可逆。寫到外部服務、Berth 撤不回的（brief §16.4 物件表）
同樣是 `irreversible`。**重建 Route 已經定義的 `berth-*` 分類不算**（送單與健康迴圈都會）：那是
Route 存在的前提，不是新的東西。`settings.write_settings` 這類原語照最重的標，等級不往上傳：
呼叫它的命令照自己的效果標。
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

    #: 只讀，什麼都不改。向外部服務重抓、寫回 Berth 自己的快取（TMDB 快照）也算只讀：那一份
    #: 本來就是外部資料的抄本，不改任何決定或路徑。
    READ = "read"
    #: 改了東西，但有路回去：反向命令、或同一個命令再按一次別的選項。
    REVERSIBLE = "reversible"
    #: 做了就回不去（刪 complete 裡的檔案、移除 torrent、purge、寫到外部服務撤不回的）；
    #: 改設定與 Route 也算（見模組 docstring）。永遠要人。
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
