"""命令標記的旗標與「要不要人」（M5 票 02，brief §14、plan §11.6〈分段〉第 1 段）。

「永遠要人」= `irreversible`，或帶 `connects_out` / `sends_out` / `settings` 任一個。`downloads`
不在裡面：送單受數量與磁碟閘，閘內 AI 可以自己做（brief §14「在預算與磁碟門檻內補下載」）。
"""

from __future__ import annotations

import pytest

from berth.services.commands import CommandMark, Effect, Flag, command, mark_of, needs_person


class TestNeedsPerson:
    @pytest.mark.parametrize("effect", [Effect.READ, Effect.REVERSIBLE])
    def test_a_plain_read_or_reversible_command_does_not(self, effect: Effect) -> None:
        assert needs_person(CommandMark(effect)) is False

    def test_an_irreversible_command_does(self) -> None:
        assert needs_person(CommandMark(Effect.IRREVERSIBLE)) is True

    @pytest.mark.parametrize("flag", [Flag.CONNECTS_OUT, Flag.SENDS_OUT, Flag.SETTINGS])
    def test_a_reversible_command_with_a_human_flag_does(self, flag: Flag) -> None:
        assert needs_person(CommandMark(Effect.REVERSIBLE, flags=frozenset({flag}))) is True

    def test_connecting_out_needs_a_person_even_when_only_reading(self) -> None:
        """帶著 key 連到別人給的位址就是外洩的路，讀也一樣（M5 研究 C4）。"""
        assert needs_person(CommandMark(Effect.READ, flags=frozenset({Flag.CONNECTS_OUT}))) is True

    @pytest.mark.parametrize("flag", [Flag.DOWNLOADS, Flag.INTERNAL])
    def test_downloading_or_being_internal_alone_does_not(self, flag: Flag) -> None:
        assert needs_person(CommandMark(Effect.REVERSIBLE, flags=frozenset({flag}))) is False


class TestTheDecorator:
    def test_flags_are_kept_on_the_mark(self) -> None:
        @command(Effect.REVERSIBLE, inverse="fake.undo", flags={Flag.DOWNLOADS, Flag.SETTINGS})
        async def act() -> None: ...

        assert mark_of(act) == CommandMark(
            Effect.REVERSIBLE,
            inverse="fake.undo",
            flags=frozenset({Flag.DOWNLOADS, Flag.SETTINGS}),
        )

    def test_no_flags_by_default(self) -> None:
        @command(Effect.READ)
        async def look() -> None: ...

        mark = mark_of(look)
        assert mark is not None
        assert mark.flags == frozenset()


class TestAMarkThatContradictsItself:
    """標記自己矛盾的，裝飾的那一刻就丟：載入模組就紅，不必等閘門掃到。"""

    @pytest.mark.parametrize("effect", [Effect.READ, Effect.IRREVERSIBLE])
    def test_an_inverse_on_a_command_that_is_not_reversible(self, effect: Effect) -> None:
        with pytest.raises(ValueError, match="inverse"):
            CommandMark(effect, inverse="fake.undo")

    @pytest.mark.parametrize("flag", [Flag.SENDS_OUT, Flag.DOWNLOADS, Flag.SETTINGS])
    def test_a_read_that_changes_something(self, flag: Flag) -> None:
        with pytest.raises(ValueError, match="read"):
            CommandMark(Effect.READ, flags=frozenset({flag}))

    @pytest.mark.parametrize("flag", [Flag.CONNECTS_OUT, Flag.INTERNAL])
    def test_a_read_may_connect_out_or_be_internal(self, flag: Flag) -> None:
        assert CommandMark(Effect.READ, flags=frozenset({flag})).flags == {flag}

    def test_every_flag_on_a_reversible_command_is_fine(self) -> None:
        assert len(CommandMark(Effect.REVERSIBLE, flags=frozenset(Flag)).flags) == len(Flag)

    def test_a_self_inverse_is_fine(self) -> None:
        """inverse 的第二種寫法：指向自己，同一個命令換參數回去。"""
        assert CommandMark(Effect.REVERSIBLE, inverse="fake.set").inverse == "fake.set"
