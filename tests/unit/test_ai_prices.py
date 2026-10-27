"""AI 的價目表與一次呼叫的用量、費用（M5 票 09、11，研究報告 C5）。

認得的模型有四個價與價目來源（genai-prices 或 Berth 補位表，票 21b），認不得的是 `None`，不當 0。
伺服器端網搜的次數與價（票 17）。
"""

from __future__ import annotations

import socket
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import NoReturn

import pytest
from genai_prices import data_snapshot
from pydantic_ai.messages import ModelResponse, NativeToolCallPart, TextPart
from pydantic_ai.usage import RequestUsage

from berth.adapters.ai import AiEndpoint, is_official
from berth.adapters.ai import prices as prices_module
from berth.adapters.ai.prices import (
    FALLBACK,
    FallbackPrice,
    ModelPrice,
    PriceSource,
    cost_of,
    known_models,
    price_of,
    web_search_cost,
)
from berth.adapters.ai.usage import TokenUsage, usage_of, web_searches_of
from berth.domain import AiProvider, PriceTable

#: 週三 12:00 UTC：DeepSeek 的離峰（尖峰是 UTC 01–04、06–10，genai-prices 的價目註記）。
OFF_PEAK = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
PEAK = datetime(2026, 10, 28, 2, 0, tzinfo=UTC)

ANTHROPIC = "https://api.anthropic.com"
OPENAI = "https://api.openai.com/v1"
DEEPSEEK_ANTHROPIC = "https://api.deepseek.com/anthropic"
GATEWAY = "https://llm.home.example/v1"

MILLION = 1_000_000


def _price(model: str, base_url: str | None, provider: AiProvider) -> ModelPrice | None:
    return price_of(model, base_url=base_url, provider=provider, at=OFF_PEAK)


def _cost(
    model: str,
    usage: TokenUsage,
    base_url: str | None = ANTHROPIC,
    provider: AiProvider = AiProvider.ANTHROPIC,
    at: datetime = OFF_PEAK,
) -> Decimal | None:
    return cost_of(model, usage, base_url=base_url, provider=provider, at=at)


class TestLookup:
    """先問 genai-prices（網址 → 接口種類），查不到看 Berth 補位表，再查不到是 `None`（票 21b）。"""

    def test_the_base_url_picks_the_provider_not_the_interface(self) -> None:
        # Anthropic 接口打 DeepSeek 的相容端點：照 DeepSeek 的價（協調者在 0.1.13 實測 $0.75）。
        usage = TokenUsage(input=MILLION, output=MILLION, cache_read=0, cache_write=0)
        assert _cost("deepseek-flash", usage, DEEPSEEK_ANTHROPIC) == Decimal("0.75")

    def test_time_of_day_prices_follow_the_moment_of_the_call(self) -> None:
        # DeepSeek 尖峰是離峰的兩倍：$0.3 / $1.2。
        usage = TokenUsage(input=MILLION, output=MILLION, cache_read=0, cache_write=0)
        assert _cost("deepseek-flash", usage, DEEPSEEK_ANTHROPIC, at=PEAK) == Decimal("1.5")

    def test_an_official_anthropic_model_has_four_prices_from_genai_prices(self) -> None:
        price = _price("claude-sonnet-5-5", ANTHROPIC, AiProvider.ANTHROPIC)
        assert price is not None
        # Anthropic pricing 頁：$2 / $10，快取讀 $0.10，快取寫（5 分鐘）$2.5。
        assert (price.input, price.output, price.cache_read, price.cache_write) == (
            Decimal("2"),
            Decimal("10"),
            Decimal("0.1"),
            Decimal("2.5"),
        )
        assert price.source == PriceSource(
            PriceTable.GENAI_PRICES, version="0.1.13", vendor="Anthropic"
        )

    def test_an_official_openai_model_is_priced(self) -> None:
        # gpt-5.5：$5 / $30（每百萬，不到分級門檻）。
        usage = TokenUsage(input=100_000, output=100_000, cache_read=0, cache_write=None)
        assert _cost("gpt-5.5", usage, OPENAI, AiProvider.OPENAI) == Decimal("3.5")

    def test_a_service_without_cache_writes_prices_them_as_input(self) -> None:
        price = _price("deepseek-flash", DEEPSEEK_ANTHROPIC, AiProvider.ANTHROPIC)
        assert price is not None
        assert (price.input, price.cache_write) == (Decimal("0.15"), Decimal("0.15"))

    def test_a_dated_snapshot_name_is_priced_as_its_family(self) -> None:
        dated = _price("claude-haiku-5-5-20261001", ANTHROPIC, AiProvider.ANTHROPIC)
        assert dated == _price("claude-haiku-5-5", ANTHROPIC, AiProvider.ANTHROPIC)
        assert dated is not None

    def test_an_unknown_url_falls_back_to_the_interface_kind(self) -> None:
        # 自架閘道上叫 `claude-sonnet-5-5` 的模型照 Anthropic 的價（pydantic-ai 的查價順序）。
        on_gateway = _price("claude-sonnet-5-5", GATEWAY, AiProvider.ANTHROPIC)
        assert on_gateway == _price("claude-sonnet-5-5", ANTHROPIC, AiProvider.ANTHROPIC)

    def test_a_known_url_decides_even_when_its_provider_lacks_the_model(self) -> None:
        # DeepSeek 的相容端點也收 `claude-*` 的名字，但收的是 DeepSeek 的錢：不套 Anthropic 的價。
        assert _price("claude-sonnet-5-5", DEEPSEEK_ANTHROPIC, AiProvider.ANTHROPIC) is None

    def test_the_interface_kind_alone_is_not_enough_for_another_vendor(self) -> None:
        # 不認得的網址、接口是 OpenAI：別家的模型名不照名字猜成那一家的價。
        assert _price("deepseek-flash", GATEWAY, AiProvider.OPENAI) is None

    def test_a_model_nobody_knows_has_no_price_rather_than_zero(self) -> None:
        assert _price("my-local-llm", GATEWAY, AiProvider.OPENAI) is None
        assert _price("gpt-unknown-9", OPENAI, AiProvider.OPENAI) is None
        assert _price("", ANTHROPIC, AiProvider.ANTHROPIC) is None
        usage = TokenUsage(input=10, output=10, cache_read=0, cache_write=0)
        assert _cost("my-local-llm", usage, GATEWAY, AiProvider.OPENAI) is None

    def test_berths_own_table_fills_in_what_genai_prices_does_not_know(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        checked = date(2026, 10, 28)
        monkeypatch.setitem(
            FALLBACK,
            "my-local-llm",
            FallbackPrice(Decimal("1"), Decimal("2"), Decimal("0.5"), Decimal("1"), checked, "x"),
        )
        price = _price("my-local-llm-q4", GATEWAY, AiProvider.OPENAI)
        assert price is not None
        assert (price.input, price.output) == (Decimal("1"), Decimal("2"))
        assert price.source == PriceSource(PriceTable.BERTH, verified=checked)
        usage = TokenUsage(input=MILLION, output=MILLION, cache_read=MILLION // 2, cache_write=0)
        assert _cost("my-local-llm", usage, GATEWAY, AiProvider.OPENAI) == Decimal("2.75")

    def test_genai_prices_wins_over_berths_table(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(
            FALLBACK,
            "claude-sonnet-5-5",
            FallbackPrice(Decimal("9"), Decimal("9"), Decimal("9"), Decimal("9"), date.min, "x"),
        )
        price = _price("claude-sonnet-5-5", ANTHROPIC, AiProvider.ANTHROPIC)
        assert price is not None and price.source.table is PriceTable.GENAI_PRICES


class TestNoNetwork:
    """價目跟著套件版本走：查價不連網，別人開了 genai-prices 的自動更新也不用它抓回來的價。"""

    def test_looking_up_prices_opens_no_connection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def refuse(*args: object, **kwargs: object) -> NoReturn:
            raise AssertionError(f"price lookup tried the network: {args}")

        monkeypatch.setattr(socket.socket, "connect", refuse)
        monkeypatch.setattr(socket.socket, "connect_ex", refuse)
        monkeypatch.setattr(socket, "getaddrinfo", refuse)
        # 第一次查價才載入價目：清掉快取，連載入那一次也算進來。
        prices_module._snapshot.cache_clear()
        assert "deepseek-flash" in known_models(DEEPSEEK_ANTHROPIC, AiProvider.ANTHROPIC)
        usage = TokenUsage(input=MILLION, output=MILLION, cache_read=0, cache_write=0)
        assert _cost("deepseek-flash", usage, DEEPSEEK_ANTHROPIC) == Decimal("0.75")
        assert _price("gpt-5.5", OPENAI, AiProvider.OPENAI) is not None
        assert _price("my-local-llm", GATEWAY, AiProvider.OPENAI) is None

    def test_an_auto_updated_snapshot_is_not_used(self) -> None:
        # `UpdatePrices` 換掉的是 genai-prices 的全域 snapshot；拿一份空的換上去，查價照舊。
        data_snapshot.set_custom_snapshot(
            data_snapshot.DataSnapshot(providers=[], from_auto_update=True)
        )
        try:
            assert _price("claude-sonnet-5-5", ANTHROPIC, AiProvider.ANTHROPIC) is not None
        finally:
            data_snapshot.set_custom_snapshot(None)


class TestCost:
    """一次呼叫的估計費用（研究 C5）：沒命中快取的 input 照輸入價，快取讀寫各照各的價。"""

    def test_each_kind_of_token_is_priced_at_its_own_rate(self) -> None:
        # Sonnet 5.5：輸入 $2、輸出 $10、快取讀 $0.10、快取寫 $2.5（每百萬）。
        # 100 萬 input 裡 40 萬是快取讀、10 萬是快取寫，剩 50 萬照輸入價。
        usage = TokenUsage(input=MILLION, output=200_000, cache_read=400_000, cache_write=100_000)
        assert _cost("claude-sonnet-5-5", usage) == Decimal("1") + Decimal("2") + Decimal(
            "0.04"
        ) + Decimal("0.25")

    def test_an_unknown_cache_count_prices_all_input_as_plain_input(self) -> None:
        usage = TokenUsage(input=MILLION, output=0, cache_read=None, cache_write=None)
        assert _cost("claude-sonnet-5-5", usage) == Decimal("2")

    def test_cache_counts_above_the_input_are_not_an_unknown_cost(self) -> None:
        # genai-prices 對這種用量丟 `ValueError`；當作沒有沒命中的 input，只算快取讀。
        usage = TokenUsage(input=10, output=0, cache_read=MILLION, cache_write=0)
        assert _cost("claude-sonnet-5-5", usage) == Decimal("0.1")


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


class TestWebSearches:
    """伺服器端網搜的次數與費用（M5 票 17）。"""

    def test_the_billed_count_the_service_reports_wins(self) -> None:
        # 一次 `server_tool_use` 區塊裡可能搜了好幾次；計費的是 usage 報的那個數。
        response = ModelResponse(
            parts=[NativeToolCallPart("web_search", {"query": "x"}), TextPart("ok")],
            usage=RequestUsage(details={"web_search_requests": 3}),
        )
        assert web_searches_of(response) == 3

    def test_without_a_reported_count_the_search_calls_are_counted(self) -> None:
        response = ModelResponse(
            parts=[
                NativeToolCallPart("web_search", {"query": "a"}),
                NativeToolCallPart("web_search", {"query": "b"}),
                NativeToolCallPart("code_execution", {"code": "1"}),
                TextPart("ok"),
            ]
        )
        assert web_searches_of(response) == 2

    def test_only_the_official_anthropic_endpoint_has_a_search_price(self) -> None:
        assert web_search_cost(3, official=True) == Decimal("0.03")
        assert web_search_cost(3, official=False) is None
        assert web_search_cost(0, official=False) == 0

    def test_the_official_endpoint_is_an_empty_or_the_documented_base_url(self) -> None:
        def official(provider: AiProvider, base_url: str) -> bool:
            return is_official(AiEndpoint(provider, base_url, "key", "model"))

        assert official(AiProvider.ANTHROPIC, "")
        assert official(AiProvider.ANTHROPIC, "https://api.anthropic.com/v1/")
        assert not official(AiProvider.ANTHROPIC, "https://api.deepseek.com/anthropic")
        assert official(AiProvider.OPENAI, "https://api.openai.com/v1")
        assert not official(AiProvider.OPENAI, "https://api.deepseek.com")
