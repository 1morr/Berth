"""一顆 Issue 按鈕一個命令（M5 票 04，研究 A3 的 R8）。

`resolve_issue` 以前一個函式吞全部的 `IssueAction`，只有一個標記：登錄表與確認卡分不出哪幾顆
要人。拆開之後每一顆是 `services.issues.<action>`（`adopt` 照名詞表叫 `reimport`），各自標記；
`POST /issues/{id}/resolve` 照 `action` 查 `BUTTONS` 分派。這裡守三件事：

1. 每一種 `ISSUE_ACTIONS` 上的動作都有自己的、有標記的命令。
2. 會刪東西的（`ACTION_DELETES`）一律 `irreversible`。
3. 分派表的鍵與 `ISSUE_ACTIONS` 一一對應，而且每一格叫的是**它自己的**命令——換掉那一個命令，
   分派過去的就是換上的那一個。

前兩條是靜態規則，最後做雙向變異：拿掉一個標記、把刪東西的改成可逆會紅；多一個無關的函式、
改一個不刪東西的命令的標記不紅。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from berth.domain import ACTION_DELETES, ISSUE_ACTIONS, IssueAction
from berth.services import issues
from berth.services.commands import Effect, command, mark_of
from berth.services.issues import BUTTONS, Press

#: 畫面上按得到的每一顆：`ISSUE_ACTIONS` 裡出現過的。
OFFERED = {action for actions in ISSUE_ACTIONS.values() for action in actions}

#: 不以按鈕值為名的命令：`CONTEXT.md`〈Claim〉說函式一律叫 reimport，`adopt` 只當按鈕值。
RENAMED = {IssueAction.ADOPT: "reimport"}


def command_name(action: IssueAction) -> str:
    return RENAMED.get(action, action.value)


def problems(module: Any) -> list[str]:
    """前兩條規則不成立的每一處，一行一處。空的就是守住了。"""
    found: list[str] = []
    for action in sorted(OFFERED):
        name = command_name(action)
        mark = mark_of(getattr(module, name, None))
        if mark is None:
            found.append(f"{name}: no marked command")
        elif ACTION_DELETES[action] and mark.effect is not Effect.IRREVERSIBLE:
            found.append(f"{name}: deletes but is {mark.effect}")
    return found


def test_every_action_has_a_marked_command_and_deleting_ones_are_irreversible() -> None:
    assert problems(issues) == []


def test_the_dispatch_table_covers_exactly_the_offered_actions() -> None:
    assert set(BUTTONS) == OFFERED


def stub(record: list[IssueAction] | None = None, action: IssueAction | None = None) -> Any:
    """一支新的、沒標記的 `async def`。每次一支新的：`command` 會把標記寫在函式本身上。"""

    async def standing_in(*args: Any, **kwargs: Any) -> None:
        if record is not None and action is not None:
            record.append(action)

    return standing_in


@pytest.mark.asyncio
@pytest.mark.parametrize("action", sorted(OFFERED), ids=str)
async def test_each_entry_calls_its_own_command(
    action: IssueAction, monkeypatch: pytest.MonkeyPatch
) -> None:
    pressed: list[IssueAction] = []
    for each in OFFERED:
        monkeypatch.setattr(issues, command_name(each), stub(pressed, each))

    press = Press(issue_id=1, actor="7", media="tv:1")
    # session 與 factory 只是被傳過去：替身不看它們。傳過去的參數對不對得上命令的簽名由 mypy 看。
    await BUTTONS[action](None, None, press)  # type: ignore[arg-type]
    assert pressed == [action]


# --- 雙向變異：照真的模組造一份，改它，看檢查怎麼說 -------------------------------------------


def copy_of_issues(**changes: object) -> SimpleNamespace:
    return SimpleNamespace(**{**vars(issues), **changes})


class TestTheCheckItself:
    def test_a_removed_mark_is_caught(self) -> None:
        assert problems(copy_of_issues(relink=stub())) == ["relink: no marked command"]

    def test_a_missing_command_is_caught(self) -> None:
        module = copy_of_issues()
        del module.reimport
        assert problems(module) == ["reimport: no marked command"]

    def test_a_deleting_command_marked_reversible_is_caught(self) -> None:
        softened = command(Effect.REVERSIBLE)(stub())
        assert problems(copy_of_issues(delete_orphan=softened)) == [
            "delete_orphan: deletes but is reversible"
        ]

    def test_an_unrelated_function_is_not_caught(self) -> None:
        assert problems(copy_of_issues(something_else=stub())) == []

    def test_changing_a_non_deleting_mark_is_not_caught(self) -> None:
        """可逆的改成不可逆不違反這兩條（逐支的標記是 `test_command_marks.NAMED` 的事）。"""
        hardened = command(Effect.IRREVERSIBLE)(stub())
        assert problems(copy_of_issues(relook=hardened)) == []
