"""AI provider 的替身：不打網路，照 key 與模型名演出成功、key 被拒、模型不存在（M5 票 09）。

測試與演練伺服器（`scripts/fake_setup_server.py`）共用，所以住在 `adapters/` 而不是測試裡
（同 `adapters/notify/fake.py`）。錯誤照真的 provider 回的形狀丟，`probe` 的分類照樣走一遍。
"""

from __future__ import annotations

from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel

from berth.adapters.ai import AiEndpoint


class FakeAi:
    def __init__(
        self,
        *,
        rejected_keys: frozenset[str] = frozenset(),
        unknown_models: frozenset[str] = frozenset(),
    ) -> None:
        self.rejected_keys = rejected_keys
        self.unknown_models = unknown_models
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
            return ModelResponse(parts=[TextPart("OK")], model_name=endpoint.model)

        return FunctionModel(answer, model_name=endpoint.model)
