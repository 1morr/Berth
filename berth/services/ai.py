"""AI provider 的設定與「測試連線」（M5 票 09、plan §11.6〈provider〉）。

**key 只進不出**：讀回去的是 `has_key`，原文永遠不離開資料庫；服務的錯誤訊息若原樣貼回 key，
給畫面之前遮掉。測試連線照 Sonarr 的「Test」：測的是表單上還沒存的那一份，key 欄空著就拿這個
接口存著的那一把。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.ai import AiEndpoint, normalize_base_url, probe
from berth.adapters.ai.prices import PRICES, ModelPrice, price_of
from berth.domain import AiProbeFailure, AiProvider, AiRefusal, AiSecret
from berth.models import AiEndpointSettings, AiSettings
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.deeplink import PublicUrlRejectedError, normalized_public_url
from berth.services.settings import read_settings, update_settings

#: 遮掉服務原樣貼回的 key。
_MASK = "***"


class AiRefusedError(Exception):
    def __init__(self, reason: AiRefusal, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else str(reason))
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class AiEndpointView:
    base_url: str
    model: str
    has_key: bool
    #: 這個模型的價目；價目表上沒有是 `None`（畫面寫「未知」，不當 0）。
    price: ModelPrice | None


@dataclass(frozen=True, slots=True)
class AiView:
    enabled: bool
    provider: AiProvider
    anthropic: AiEndpointView
    openai: AiEndpointView
    has_tavily_key: bool
    #: 價目表上認得的模型名，給模型欄當建議（可以不選、照打）。
    known_models: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AiForm:
    """表單上的一種接口。`api_key` 是 `None` 或空白表示沒動（存的時候留著、測試時拿存著的）。

    清掉 key 是另一個命令（`forget_ai_key`）：空欄在存檔與測試裡是同一個意思。
    """

    provider: AiProvider
    base_url: str
    model: str
    api_key: str | None = None


@dataclass(frozen=True, slots=True)
class AiTest:
    ok: bool
    failure: AiProbeFailure | None
    status: int | None
    detail: str
    model: str


def _endpoint_view(endpoint: AiEndpointSettings) -> AiEndpointView:
    return AiEndpointView(
        base_url=endpoint.base_url,
        model=endpoint.model,
        has_key=bool(endpoint.api_key),
        price=price_of(endpoint.model),
    )


def _view(settings: AiSettings) -> AiView:
    return AiView(
        enabled=settings.enabled,
        provider=settings.provider,
        anthropic=_endpoint_view(settings.anthropic),
        openai=_endpoint_view(settings.openai),
        has_tavily_key=bool(settings.tavily_api_key),
        known_models=tuple(sorted(PRICES)),
    )


def _base_url(form: AiForm) -> str:
    try:
        checked = normalized_public_url(form.base_url)
    except PublicUrlRejectedError as exc:
        raise AiRefusedError(AiRefusal.BASE_URL_INVALID, str(exc)) from exc
    return normalize_base_url(form.provider, checked)


def _complete(api_key: str, model: str) -> None:
    """開啟與測試的前提：有 key、有模型名。"""
    if not api_key:
        raise AiRefusedError(AiRefusal.KEY_MISSING)
    if not model:
        raise AiRefusedError(AiRefusal.MODEL_MISSING)


@command(Effect.READ)
async def read_ai(session: AsyncSession) -> AiView:
    return _view(await read_settings(session, AiSettings))


@command(Effect.REVERSIBLE)
async def set_ai(
    session: AsyncSession, *, enabled: bool, form: AiForm, tavily_api_key: str | None = None
) -> AiView:
    """存表單上那一種接口、把它設成現在用的那一種，並開或關 AI。另一種接口存著的不動。

    開啟要這個接口有 key 與模型名，否則拒絕、什麼都不存；關閉什麼都不要求。
    """
    base_url = _base_url(form)
    model = form.model.strip()
    refusal: list[AiRefusedError] = []

    def change(settings: AiSettings) -> None:
        endpoint = settings.endpoint(form.provider)
        api_key = (form.api_key or "").strip() or endpoint.api_key
        if enabled:
            try:
                _complete(api_key, model)
            except AiRefusedError as exc:
                refusal.append(exc)
                return
        endpoint.base_url, endpoint.model, endpoint.api_key = base_url, model, api_key
        settings.provider, settings.enabled = form.provider, enabled
        if tavily_api_key and tavily_api_key.strip():
            settings.tavily_api_key = tavily_api_key.strip()

    # key 欄空著時要看存著的那一把，所以前提在寫鎖裡判斷；被拒時寫回去的是原樣。
    saved = await update_settings(session, AiSettings, change)
    if refusal:
        raise refusal[0]
    return _view(saved)


# key 一清掉就回不來，要人重新貼一次。
@command(Effect.IRREVERSIBLE)
async def forget_ai_key(session: AsyncSession, secret: AiSecret) -> AiView:
    """清掉一把 key，其餘設定不動。清的是現在用的接口的 key 時一併關掉 AI：沒有 key 開不了。"""

    def change(settings: AiSettings) -> None:
        if secret is AiSecret.TAVILY:
            settings.tavily_api_key = ""
            return
        provider = AiProvider(secret.value)
        settings.endpoint(provider).api_key = ""
        if settings.provider is provider:
            settings.enabled = False

    return _view(await update_settings(session, AiSettings, change))


@command(Effect.READ)
async def test_ai(session: AsyncSession, factory: ServiceClientFactory, form: AiForm) -> AiTest:
    """照表單打一次最小呼叫，不存任何東西。服務回的錯誤是結果，不是拒絕。"""
    base_url = _base_url(form)
    model = form.model.strip()
    api_key = (form.api_key or "").strip()
    if not api_key:
        saved = await read_settings(session, AiSettings)
        api_key = saved.endpoint(form.provider).api_key
    _complete(api_key, model)
    result = await probe(factory.ai(AiEndpoint(form.provider, base_url, api_key, model)))
    return AiTest(
        ok=result.failure is None,
        failure=result.failure,
        status=result.status,
        detail=result.detail.replace(api_key, _MASK),
        model=result.model,
    )
