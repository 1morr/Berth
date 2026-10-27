"""AI provider 的替身：不打網路，照 key 與模型名演出成功、key 被拒、模型不存在（M5 票 09）。

測試與演練伺服器（`scripts/fake_setup_server.py`）共用，所以住在 `adapters/` 而不是測試裡
（同 `adapters/notify/fake.py`）。錯誤照真的 provider 回的形狀丟，`probe` 的分類照樣走一遍。

**腳本**（M5 票 11）：`script` 給了的話，每一次模型呼叫由它回答——它看得到這一次送出去的訊息與
可用的工具（`AgentInfo.function_tools`），回一則 `ModelResponse`（文字、工具呼叫），或丟例外演出錯。
側面板是串流的，所以替身同時給串流版：把同一則回答拆成文字、工具呼叫與伺服器端工具（票 17）的
片段送出去。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    NativeToolCallPart,
    NativeToolReturnPart,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models import Model
from pydantic_ai.models.function import (
    AgentInfo,
    BuiltinToolCallsReturns,
    DeltaToolCall,
    DeltaToolCalls,
    FunctionModel,
)

from berth.adapters.ai import AiEndpoint

#: 一次模型呼叫的回答。
Script = Callable[[list[ModelMessage], AgentInfo], ModelResponse]


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
        #: 每次組模型時收到的設定，給測試斷言「用的是哪一把 key、哪個網址」。
        self.endpoints: list[AiEndpoint] = []

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
        ) -> AsyncIterator[str | DeltaToolCalls | BuiltinToolCallsReturns]:
            for index, part in enumerate(answer(messages, info).parts):
                if isinstance(part, TextPart):
                    yield part.content
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
