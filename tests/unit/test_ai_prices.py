"""AI 的價目表（M5 票 09、研究報告 C5）。

認得的模型有四個價與查證日期，認不得的是 `None`，不當 0。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from berth.adapters.ai.prices import price_of


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
