"""工具的結果裡沒有帳密（M5 票 06，brief §6.10「外部文字是資料」④）。

結果會原樣進 prompt、進對話紀錄、畫成卡片——三處都不該出現 API key、密碼或 token。規則寫在型別上：
走訪每一條登記的結果型別（連巢狀的 model、清單與 union 裡的），欄位名看起來是帳密、或型別是
`SecretStr` 的都紅。看欄位名不看值：值是執行期才有的，型別上沒有這一格就一定送不出去。

最後一組是雙向變異：造一個含帳密欄位的結果型別會紅；名字裡只是碰巧有那幾個字母的
（`input_tokens`、`tokenizer`、`passage`）不紅。
"""

from __future__ import annotations

from itertools import pairwise
from typing import Annotated, Any, get_args, get_origin

import pytest
from pydantic import BaseModel, SecretBytes, SecretStr

from berth.services.registry import Refusal, Tool
from berth.services.tools import REGISTRY

#: 蛇形欄位名拆成字之後，出現其中任一個就是帳密。`token` 只認單數：`input_tokens` 是用量。
_SECRET_WORDS = frozenset(
    {"password", "passwd", "secret", "token", "apikey", "credential", "credentials", "cookie"}
)
#: 兩個字連著才算的（`api_key`、`private_key`、`session_id`）。
_SECRET_PAIRS = frozenset({("api", "key"), ("private", "key"), ("session", "id")})


def secret_fields(model: type[BaseModel]) -> list[str]:
    """`model` 裡看起來是帳密的欄位，`Model.field` 一行一個。"""
    found: list[str] = []
    seen: set[type[BaseModel]] = set()

    def visit(current: type[BaseModel]) -> None:
        if current in seen:
            return
        seen.add(current)
        for name, info in current.model_fields.items():
            if _looks_secret(name) or _holds_secret(info.annotation):
                found.append(f"{current.__name__}.{name}")
            for nested in _models_in(info.annotation):
                visit(nested)

    visit(model)
    return found


def _looks_secret(name: str) -> bool:
    words = [word for word in name.lower().split("_") if word]
    return any(word in _SECRET_WORDS for word in words) or any(
        pair in _SECRET_PAIRS for pair in pairwise(words)
    )


def _flatten(annotation: Any) -> list[Any]:
    origin = get_origin(annotation)
    if origin is Annotated:
        return _flatten(get_args(annotation)[0])
    if origin is not None:  # Union、`X | Y`、list、tuple 都一樣攤開參數
        return [found for arg in get_args(annotation) for found in _flatten(arg)]
    return [annotation]


def _holds_secret(annotation: Any) -> bool:
    return any(found in (SecretStr, SecretBytes) for found in _flatten(annotation))


def _models_in(annotation: Any) -> list[type[BaseModel]]:
    return [
        found
        for found in _flatten(annotation)
        if isinstance(found, type) and issubclass(found, BaseModel)
    ]


class TestTheRegistry:
    @pytest.mark.parametrize("registered", list(REGISTRY), ids=lambda found: found.name)
    def test_no_result_carries_a_credential(self, registered: Tool[Any, Any]) -> None:
        assert secret_fields(registered.result) == []

    def test_the_refusal_carries_none_either(self) -> None:
        assert secret_fields(Refusal) == []


class Inner(BaseModel):
    jellyfin_api_key: str


class Leaky(BaseModel):
    title: str
    servers: list[Inner] | None = None
    qbit: SecretStr | None = None
    feed_token: str = ""


class Usage(BaseModel):
    input_tokens: int
    tokenizer: str
    passage: str
    keyframe: int
    session_count: int


class TestTheScanItself:
    def test_a_credential_anywhere_in_the_result_is_caught(self) -> None:
        assert set(secret_fields(Leaky)) == {
            "Leaky.qbit",
            "Leaky.feed_token",
            "Inner.jellyfin_api_key",
        }

    def test_names_that_merely_contain_the_letters_pass(self) -> None:
        assert secret_fields(Usage) == []
