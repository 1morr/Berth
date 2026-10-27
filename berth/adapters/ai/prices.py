"""每個模型的價目與一次呼叫的估計費用（M5 票 09、21b，brief §20.24〈費用〉）。

**先問 genai-prices**（Pydantic 維護、pydantic-ai 的相依）：照 pydantic-ai 的
`iter_provider_references` 由具體到一般，先用 base URL 認服務商（Anthropic 接口打 DeepSeek 的
相容端點就照 DeepSeek 的價），網址認不得再用接口種類（`anthropic` / `openai`）；網址認得而那一家
沒有這個模型就是查不到。接口種類不能單獨當服務商：DeepSeek 的相容端點用 `anthropic` 查不到
`deepseek-flash`。都查不到再看 Berth 的
補位表（`FALLBACK`），再查不到是 `None`：費用記 NULL、畫面寫「未知」，不當 0（當 0 會讓用量頁
看起來免費）。

**價目跟著套件版本走**：用套件內附的那一份資料，不用 genai-prices 的全域 snapshot（它的
`UpdatePrices` 會換成從 GitHub 抓的），所以查價不連網、升級套件才換價。

價錢會隨時間變（DeepSeek 分尖峰離峰），所以查價帶時間：記帳用回應的時間，畫面用現在。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache

import genai_prices
from genai_prices import Usage
from genai_prices.data_snapshot import DataSnapshot
from genai_prices.types import Provider

from berth.adapters.ai.usage import TokenUsage
from berth.domain import AiProvider, PriceTable

_ANTHROPIC_WEB_SEARCH = (
    "https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool"
)


@dataclass(frozen=True, slots=True)
class PriceSource:
    """價目從哪來：genai-prices（版本、它認出的服務商名），或 Berth 補位表（那一列的查證日期）。"""

    table: PriceTable
    version: str = ""
    #: genai-prices 認出的服務商（`Deepseek`）；不叫 provider，那個詞是接口種類（`AiProvider`）。
    vendor: str = ""
    verified: date | None = None


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """美元 / 百萬 token：輸入（沒命中快取的那部分）、輸出、快取讀、快取寫。"""

    input: Decimal
    output: Decimal
    cache_read: Decimal
    #: 沒有寫入費用的服務（DeepSeek）與輸入同價（genai-prices 這樣算）。
    cache_write: Decimal
    source: PriceSource


@dataclass(frozen=True, slots=True)
class FallbackPrice:
    """補位表的一列：四個價（同 `ModelPrice`）加查證日期與來源網址。"""

    input: Decimal
    output: Decimal
    cache_read: Decimal
    cache_write: Decimal
    verified: date
    source: str


#: genai-prices 認不得、Berth 自己補的模型。鍵是模型名稱的開頭（帶日期的版本照它的家族算，最長的鍵
#: 優先）。genai-prices 0.1.13 已認得票 09 表上的全部模型，所以現在是空的；遇到它沒有的模型再加，
#: 每一列附查證日期與來源。
FALLBACK: dict[str, FallbackPrice] = {}

_MILLION = Decimal(1_000_000)
#: 畫面上的每百萬價用一千 token 的用量量出來，不碰分級價的門檻（Anthropic 的長 context 分級）。
_UNIT = 1_000


@cache
def _snapshot() -> DataSnapshot:
    """套件內附的價目（不是 `data_snapshot.get_snapshot()`：那一份會被自動更新換掉）。"""
    from genai_prices.data import providers  # 資料表很大，第一次查價才載入

    return DataSnapshot(providers=providers, from_auto_update=False)


def _genai_provider(base_url: str | None, provider: AiProvider) -> Provider | None:
    """genai-prices 裡這個端點是哪一家。

    網址比名字精確，先看網址（同 pydantic-ai 的 `iter_provider_references`）；**網址認得就是
    那一家**，那一家沒有這個模型也不退回接口種類——DeepSeek 的相容端點也收 `claude-*` 的名字，
    收的是 DeepSeek 的錢（這一點與 pydantic-ai 不同：它遇到 `LookupError` 一律退回）。網址認不得
    （自架閘道）或不知道（票 21b 之前記的呼叫）才照接口種類。
    """
    snapshot = _snapshot()
    if base_url:
        try:
            return snapshot.find_provider(None, None, base_url)
        except LookupError:
            pass
    try:
        return snapshot.find_provider(None, provider.value, None)
    except LookupError:
        return None


def _genai_vendor(model: str, base_url: str | None, provider: AiProvider) -> Provider | None:
    """有這個模型的那一家；查不到是 `None`。"""
    vendor = _genai_provider(base_url, provider)
    if vendor is None:
        return None
    try:
        _snapshot().find_provider_model(model, vendor, None, None)
    except LookupError:
        return None
    return vendor


def _fallback(model: str) -> FallbackPrice | None:
    matches = [key for key in FALLBACK if model.lower().startswith(key)]
    return FALLBACK[max(matches, key=len)] if matches else None


def _total(vendor: Provider, model: str, usage: Usage, at: datetime) -> Decimal:
    return _snapshot().calc(usage, model, vendor.id, None, at).total_price


def _plain(value: Decimal) -> Decimal:
    """`0.15000` → `0.15`、`10` 還是 `10`（`normalize()` 會變成 `1E+1`）。"""
    return Decimal(format(value.normalize(), "f"))


def price_of(
    model: str,
    *,
    base_url: str | None,
    provider: AiProvider,
    at: datetime | None = None,
) -> ModelPrice | None:
    """這個端點上這個模型在 `at`（預設現在）的價目；查不到是 `None`。

    `base_url` 是實際打的網址（官方端點也寫出來）；`None` 是不知道（票 21b 之前記的呼叫）。
    """
    name = model.strip()
    if not name:
        return None
    vendor = _genai_vendor(name, base_url, provider)
    if vendor is None:
        row = _fallback(name)
        if row is None:
            return None
        source = PriceSource(PriceTable.BERTH, verified=row.verified)
        return ModelPrice(row.input, row.output, row.cache_read, row.cache_write, source)

    when = at or datetime.now(UTC)
    per_unit = _MILLION / _UNIT

    def rate(**usage: int) -> Decimal:
        return _plain(_total(vendor, name, Usage(**usage), when) * per_unit)

    return ModelPrice(
        input=rate(input_tokens=_UNIT),
        output=rate(output_tokens=_UNIT),
        cache_read=rate(input_tokens=_UNIT, cache_read_tokens=_UNIT),
        cache_write=rate(input_tokens=_UNIT, cache_write_tokens=_UNIT),
        source=PriceSource(
            PriceTable.GENAI_PRICES, version=genai_prices.__version__, vendor=vendor.name
        ),
    )


def cost_of(
    model: str,
    usage: TokenUsage,
    *,
    base_url: str | None,
    provider: AiProvider,
    at: datetime | None = None,
) -> Decimal | None:
    """一次呼叫的估計費用（美元）；查不到價是 `None`。

    genai-prices 查得到的照它的 `calc` 算（分時段、分級價都在裡面），補位表的照四個價乘。`input`
    含快取讀寫；不知道的快取格子當作沒有：那部分照一般輸入價算，估計因此偏高、不會偏低。
    """
    name = model.strip()
    if not name:
        return None
    read, write = usage.cache_read or 0, usage.cache_write or 0
    vendor = _genai_vendor(name, base_url, provider)
    if vendor is not None:
        # 快取比 input 還多時 genai-prices 丟 `ValueError`；當作沒有沒命中的 input。
        tokens = Usage(
            input_tokens=max(usage.input, read + write),
            output_tokens=usage.output,
            cache_read_tokens=read,
            cache_write_tokens=write,
        )
        return _total(vendor, name, tokens, at or datetime.now(UTC))

    row = _fallback(name)
    if row is None:
        return None
    plain = max(usage.input - read - write, 0)
    total = (
        plain * row.input
        + usage.output * row.output
        + read * row.cache_read
        + write * row.cache_write
    )
    return total / _MILLION


def known_models(base_url: str | None, provider: AiProvider) -> tuple[str, ...]:
    """這個端點查得到價的模型名（genai-prices 認出的那一家的模型，加補位表），給模型欄當建議。"""
    names = set(FALLBACK)
    vendor = _genai_provider(base_url, provider)
    if vendor is not None:
        # `ft:` 開頭的是微調模型的前綴，不是打得出來的模型名。
        names.update(m.id for m in vendor.models if not m.deprecated and ":" not in m.id)
    return tuple(sorted(names))


#: Anthropic 官方端點的伺服器端網搜：$10 / 1,000 次（另外搜尋結果照輸入 token 算，已在 token 裡）。
#: 查證 2026-10-27，`_ANTHROPIC_WEB_SEARCH`。
WEB_SEARCH_USD = Decimal("0.01")


def web_search_cost(searches: int, *, official: bool) -> Decimal | None:
    """這幾次伺服器端網搜的費用；沒搜是 0。只有 Anthropic 官方端點的價知道，其他端點
    （DeepSeek 的相容端點、自架閘道）是 `None`：**不計進估計費用**，畫面說明（M5 票 17）。
    """
    if searches == 0:
        return Decimal(0)
    return searches * WEB_SEARCH_USD if official else None
