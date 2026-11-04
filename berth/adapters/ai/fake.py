"""AI provider 的替身：不打網路，照 key 與模型名演出成功、key 被拒、模型不存在（M5 票 09）。

測試與演練伺服器（`scripts/fake_setup_server.py`）共用，所以住在 `adapters/` 而不是測試裡
（同 `adapters/notify/fake.py`）。錯誤照真的 provider 回的形狀丟，`probe` 的分類照樣走一遍。

**腳本**（M5 票 11）：`script` 給了的話，每一次模型呼叫由它回答——它看得到這一次送出去的訊息與
可用的工具（`AgentInfo.function_tools`），回一則 `ModelResponse`（文字、工具呼叫），或丟例外演出錯。
側面板是串流的，所以替身同時給串流版：把同一則回答拆成推理（M5.5 票 16）、文字、工具呼叫與
伺服器端工具（票 17）的片段送出去。串流的回應時間是開始串流那一刻，同真的服務（pydantic-ai 的
串流回應一律用收到時的本機時鐘），腳本給的 `timestamp` 留不下來；要控制時段（DeepSeek 分尖峰離峰）
就釘時鐘（票 21c）。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable

from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    NativeToolCallPart,
    NativeToolReturnPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
)
from pydantic_ai.models import Model
from pydantic_ai.models.function import (
    AgentInfo,
    BuiltinToolCallsReturns,
    DeltaThinkingCalls,
    DeltaThinkingPart,
    DeltaToolCall,
    DeltaToolCalls,
    FunctionModel,
)

from berth.adapters.ai import AiEndpoint
from berth.adapters.ai.catalog import ModelCatalog, ModelListing
from berth.domain import AiProbeFailure, AiProvider

#: 一次模型呼叫的回答。
Script = Callable[[list[ModelMessage], AgentInfo], ModelResponse]
#: 串流的那一次開始回答之前等它（收到這一次送出去的訊息）：演一輪跑得久（M5 票 25）。
Pause = Callable[[list[ModelMessage]], Awaitable[None]]


class FakeAi:
    def __init__(
        self,
        *,
        rejected_keys: frozenset[str] = frozenset(),
        unknown_models: frozenset[str] = frozenset(),
        script: Script | None = None,
    ) -> None:
        self.rejected_keys = rejected_keys
        self.unknown_models = unknown_models
        #: 沒給就一律回「OK」（測試連線用的就是這一句）。
        self.script = script
        #: 被拒時把 key 原樣貼回錯誤訊息裡（有的服務會這樣做）。
        self.echo_key = False
        #: 每次連出去（組模型、列模型）時收到的設定，給測試斷言「用的是哪一把 key、哪個網址」。
        #: 列模型的那幾筆 `model` 是空字串。
        self.endpoints: list[AiEndpoint] = []
        #: 「取得模型」時端點列的模型（M5.5 票 02）；`None` 是這個端點沒有列模型的路由（404）。
        self.listed: tuple[str, ...] | None = ("fake-model-large", "fake-model-small")
        #: 給了的話，每一次串流的模型呼叫先等它（`Pause`）。
        self.pause: Pause | None = None

    def model(self, endpoint: AiEndpoint) -> Model:
        self.endpoints.append(endpoint)

        def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            if endpoint.api_key in self.rejected_keys:
                message = "invalid x-api-key"
                if self.echo_key:
                    message += f": {endpoint.api_key}"
                raise ModelHTTPError(
                    401,
                    endpoint.model,
                    {
                        "type": "error",
                        "error": {"type": "authentication_error", "message": message},
                    },
                )
            if endpoint.model in self.unknown_models:
                raise ModelHTTPError(
                    404,
                    endpoint.model,
                    {"error": {"message": f"The model `{endpoint.model}` does not exist"}},
                )
            if self.script is not None:
                return self.script(messages, info)
            return ModelResponse(parts=[TextPart("OK")], model_name=endpoint.model)

        async def stream(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | DeltaToolCalls | DeltaThinkingCalls | BuiltinToolCallsReturns]:
            if self.pause is not None:
                await self.pause(messages)
            for index, part in enumerate(answer(messages, info).parts):
                if isinstance(part, TextPart):
                    yield part.content
                elif isinstance(part, ThinkingPart):
                    yield {index: DeltaThinkingPart(content=part.content, signature=part.signature)}
                elif isinstance(part, ToolCallPart):
                    yield {
                        index: DeltaToolCall(
                            name=part.tool_name,
                            json_args=part.args_as_json_str(),
                            tool_call_id=part.tool_call_id,
                        )
                    }
                elif isinstance(part, NativeToolCallPart | NativeToolReturnPart):
                    # 伺服器端工具（`web_search`，票 17）整段一次送出，同真的 Anthropic 串流。
                    yield {index: part}

        return FunctionModel(answer, stream_function=stream, model_name=endpoint.model)

    def catalog(self, provider: AiProvider, base_url: str, api_key: str) -> ModelCatalog:
        self.endpoints.append(AiEndpoint(provider, base_url, api_key, ""))
        return _FakeCatalog(self, api_key)


class _FakeCatalog:
    def __init__(self, ai: FakeAi, api_key: str) -> None:
        self._ai = ai
        self._api_key = api_key

    async def list_models(self) -> ModelListing:
        if self._api_key in self._ai.rejected_keys:
            message = "invalid x-api-key"
            if self._ai.echo_key:
                message += f": {self._api_key}"
            body = {"type": "error", "error": {"type": "authentication_error", "message": message}}
            return ModelListing((), AiProbeFailure.KEY_REJECTED, 401, json.dumps(body))
        if self._ai.listed is None:
            return ModelListing((), AiProbeFailure.NOT_FOUND, 404, "404 page not found")
        return ModelListing(self._ai.listed, None, None, "")
