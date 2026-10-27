"""每個模型的價目（M5 票 09、研究報告 C5、brief §20.24〈費用〉）。

美元 / 百萬 token，四個價：輸入（沒命中快取的那部分）、輸出、快取讀、快取寫。每一列帶查證日期與
來源，價目變了改這張表。**認不得的模型回 `None`**：費用記 NULL、畫面寫「未知」，不當 0
（當 0 會讓用量頁看起來免費）。

不用 `genai_prices` 補位：它把相容閘道上的同名模型照原廠價算（brief §20.24），而一個看似精確
但其實是別家的價比「未知」更糟。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

_ANTHROPIC = "https://platform.claude.com/docs/en/about-claude/pricing"
_DEEPSEEK = "https://api-docs.deepseek.com/quick_start/pricing"


@dataclass(frozen=True, slots=True)
class ModelPrice:
    input: Decimal
    output: Decimal
    cache_read: Decimal
    #: Anthropic 是 5 分鐘快取的寫入價；沒有寫入費用的服務（DeepSeek）與輸入同價。
    cache_write: Decimal
    verified: date
    source: str


def _price(
    input_: str, output: str, cache_read: str, cache_write: str, verified: date, source: str
) -> ModelPrice:
    return ModelPrice(
        Decimal(input_),
        Decimal(output),
        Decimal(cache_read),
        Decimal(cache_write),
        verified,
        source,
    )


_CHECKED = date(2026, 10, 27)

#: 鍵是模型名稱的開頭：帶日期的版本（`claude-haiku-5-5-20261001`）照它的家族算，最長的鍵優先。
PRICES: dict[str, ModelPrice] = {
    "claude-sonnet-5-5": _price("2", "10", "0.10", "2.5", _CHECKED, _ANTHROPIC),
    "claude-haiku-5-5": _price("0.10", "0.50", "0.01", "0.125", _CHECKED, _ANTHROPIC),
    "claude-opus-5-5": _price("4", "20", "0.20", "5", _CHECKED, _ANTHROPIC),
    "claude-fable-5-1": _price("10", "50", "0.25", "12.5", _CHECKED, _ANTHROPIC),
    # DeepSeek 的尖峰價；離峰半價不折算，所以估計偏高、不會偏低。
    "deepseek-flash": _price("0.3", "1.2", "0.006", "0.3", _CHECKED, _DEEPSEEK),
    "deepseek-v4-flash": _price("0.3", "1.2", "0.006", "0.3", _CHECKED, _DEEPSEEK),
    "deepseek-v4-pro": _price("1.32", "3.96", "0.044", "1.32", _CHECKED, _DEEPSEEK),
}


def price_of(model: str) -> ModelPrice | None:
    """這個模型的價目；表上沒有是 `None`。"""
    name = model.strip().lower()
    if not name:
        return None
    matches = [key for key in PRICES if name.startswith(key)]
    return PRICES[max(matches, key=len)] if matches else None
