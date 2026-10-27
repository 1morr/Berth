"""AI 的價目表與一次呼叫的用量、費用（M5 票 09、11，研究報告 C5）。

認得的模型有四個價與查證日期，認不得的是 `None`，不當 0。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic_ai.usage import RequestUsage

from berth.adapters.ai.prices import cost_of, price_of
from berth.adapters.ai.usage import TokenUsage, usage_of
from berth.domain import AiProvider


def test_a_listed_model_has_its_four_prices_and_when_they_were_checked() -> None:
    price = price_of("claude-sonnet-5-5")
    assert price is not None
    # Anthropic 官方 pricing 頁（2026-10-27）：$2 / $10，快取讀 $0.10，快取寫（5 分鐘）$2.5。
    assert (price.input, price.output, price.cache_read, price.cache_write) == (
        Decimal("2"),
        Decimal("10"),
        Decimal("0.10"),
        Decimal("2.5"),
    )
    assert price.verified == date(2026, 10, 27)
    assert price.source.startswith("https://")


def test_a_dated_snapshot_name_is_priced_as_its_family() -> None:
    assert price_of("claude-haiku-5-5-20261001") == price_of("claude-haiku-5-5")


def test_the_longest_matching_name_wins() -> None:
    flash, pro = price_of("deepseek-v4-flash"), price_of("deepseek-v4-pro")
    assert flash is not None and pro is not None
    assert flash.input < pro.input


def test_an_unknown_model_has_no_price_rather_than_zero() -> None:
    assert price_of("gpt-unknown-9") is None
    assert price_of("") is None


class TestCost:
    """一次呼叫的估計費用（研究 C5）：沒命中快取的 input 照輸入價，快取讀寫各照各的價。"""

    def test_each_kind_of_token_is_priced_at_its_own_rate(self) -> None:
        # Sonnet 5.5：輸入 $2、輸出 $10、快取讀 $0.10、快取寫 $2.5（每百萬）。
        # 100 萬 input 裡 40 萬是快取讀、10 萬是快取寫，剩 50 萬照輸入價。
        usage = TokenUsage(input=1_000_000, output=200_000, cache_read=400_000, cache_write=100_000)
        assert cost_of("claude-sonnet-5-5", usage) == Decimal("1") + Decimal("2") + Decimal(
            "0.04"
        ) + Decimal("0.25")

    def test_an_unknown_cache_count_prices_all_input_as_plain_input(self) -> None:
        usage = TokenUsage(input=1_000_000, output=0, cache_read=None, cache_write=None)
        assert cost_of("claude-sonnet-5-5", usage) == Decimal("2")

    def test_an_unknown_model_has_no_cost_rather_than_zero(self) -> None:
        usage = TokenUsage(input=10, output=10, cache_read=0, cache_write=0)
        assert cost_of("some-local-model", usage) is None


class TestUsage:
    """兩種接口各自報得出哪幾格（`None` 是不知道，不當 0）。"""

    def test_anthropic_reports_both_cache_reads_and_writes(self) -> None:
        raw = RequestUsage(
            input_tokens=900, output_tokens=50, cache_read_tokens=0, cache_write_tokens=300
        )
        assert usage_of(AiProvider.ANTHROPIC, raw) == TokenUsage(900, 50, 0, 300)

    def test_chat_completions_has_no_cache_write_count(self) -> None:
        raw = RequestUsage(input_tokens=900, output_tokens=50, cache_read_tokens=600)
        assert usage_of(AiProvider.OPENAI, raw) == TokenUsage(900, 50, 600, None)
