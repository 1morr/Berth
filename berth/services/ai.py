"""AI provider 的設定、「測試連線」與模型欄的建議（M5 票 09、plan §11.6〈provider〉）。

**key 只進不出**：讀回去的是 `has_key`，原文永遠不離開資料庫；服務的錯誤訊息若原樣貼回 key，
給畫面之前遮掉。測試連線照 Sonarr 的「Test」：測的是表單上還沒存的那一份，key 欄空著就拿這個
接口存著的那一把，但只在表單的網址與存著的相同時（M5.5 票 01，`_key_for`）。

模型欄的建議照 Open WebUI 的連線設定（brief §20.26，M5.5 票 02）：按了「取得模型」才向表單上的
端點問，問不到退回本機價目表；沒按之前只查本機表，不帶 key、不連外。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.ai import AiEndpoint, effective_base_url, normalize_base_url, probe
from berth.adapters.ai.prices import ModelPrice, known_models, price_of
from berth.domain import AiModelSource, AiProbeFailure, AiProvider, AiRefusal, AiSecret
from berth.models import AiEndpointSettings, AiSettings
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, Flag, command
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
    #: 這個端點上這個模型現在的價目；查不到是 `None`（畫面寫「未知」，不當 0）。
    price: ModelPrice | None


@dataclass(frozen=True, slots=True)
class AiView:
    enabled: bool
    provider: AiProvider
    anthropic: AiEndpointView
    openai: AiEndpointView
    has_tavily_key: bool


@dataclass(frozen=True, slots=True)
class AiForm:
    """表單上的一種接口。`api_key` 是 `None` 或空白表示沒動（存的時候留著、測試時拿存著的；
    兩者都只在網址沒改時，見 `_key_for`）。

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


@dataclass(frozen=True, slots=True)
class AiModels:
    """模型欄的建議（M5.5 票 02）。可以不選、照打。"""

    models: tuple[str, ...]
    source: AiModelSource
    #: 「取得模型」沒問到的分類；問到了、或沒按（只查本機表）是 `None`。
    failure: AiProbeFailure | None
    #: 服務回的 HTTP 狀態碼；成功或沒有回應是 `None`。
    status: int | None
    #: 服務回的原文（key 若被貼回來已遮掉）。
    detail: str


def _from_prices(provider: AiProvider, base_url: str) -> AiModels:
    models = known_models(effective_base_url(provider, base_url), provider)
    return AiModels(models, AiModelSource.PRICES, None, None, "")


def _endpoint_view(provider: AiProvider, endpoint: AiEndpointSettings) -> AiEndpointView:
    base_url = effective_base_url(provider, endpoint.base_url)
    return AiEndpointView(
        base_url=endpoint.base_url,
        model=endpoint.model,
        has_key=bool(endpoint.api_key),
        price=price_of(endpoint.model, base_url=base_url, provider=provider),
    )


def _view(settings: AiSettings) -> AiView:
    return AiView(
        enabled=settings.enabled,
        provider=settings.provider,
        anthropic=_endpoint_view(AiProvider.ANTHROPIC, settings.anthropic),
        openai=_endpoint_view(AiProvider.OPENAI, settings.openai),
        has_tavily_key=bool(settings.tavily_api_key),
    )


def _base_url(provider: AiProvider, base_url: str) -> str:
    try:
        checked = normalized_public_url(base_url)
    except PublicUrlRejectedError as exc:
        raise AiRefusedError(AiRefusal.BASE_URL_INVALID, str(exc)) from exc
    return normalize_base_url(provider, checked)


def _key_for(
    provider: AiProvider, base_url: str, typed_key: str | None, saved: AiEndpointSettings
) -> str:
    """這次用哪把 key（M5.5 票 01）。key 欄有填就用填的；空著時，表單的網址與存著的經
    `effective_base_url` 相同才用存著的那把（留空與填官方網址算同一個）。沒有能用的回空字串。

    打到一半的網址不該收到 key：存著的那把只送到存它的那個端點。`base_url` 是 `_base_url` 整理過的。
    """
    typed = (typed_key or "").strip()
    if typed:
        return typed
    same = effective_base_url(provider, base_url) == effective_base_url(provider, saved.base_url)
    return saved.api_key if same else ""


def _require_key_and_model(api_key: str, model: str) -> None:
    """開啟與測試的前提：有 key、有模型名。"""
    if not api_key:
        raise AiRefusedError(AiRefusal.KEY_MISSING)
    if not model:
        raise AiRefusedError(AiRefusal.MODEL_MISSING)


# 這四支進命令登錄表：provider 是設定（`settings`），不是身分與門禁（`Flag.INTERNAL`，M5 票 06）；
# 要不要人由 `needs_person` 管，給不給 AI 當工具是票 13、14 挑的。
@command(Effect.READ)
async def read_ai(session: AsyncSession) -> AiView:
    return _view(await read_settings(session, AiSettings))


# 改設定頁的設定；收任意 base URL，之後每次呼叫都帶著 key 連過去。用原值再存一次就回去。
@command(Effect.REVERSIBLE, inverse="ai.set_ai", flags={Flag.SETTINGS, Flag.CONNECTS_OUT})
async def set_ai(
    session: AsyncSession, *, enabled: bool, form: AiForm, tavily_api_key: str | None = None
) -> AiView:
    """存表單上那一種接口、把它設成現在用的那一種，並開或關 AI。另一種接口存著的不動。

    開啟要這個接口有 key 與模型名，否則拒絕、什麼都不存；關閉什麼都不要求。存著 key、改了網址、
    key 欄又空著時，開或關都拒絕（M5.5 票 01）：存著的那把只送到存它的端點，只守測試的話，
    先存再按就繞過去了。
    """
    base_url = _base_url(form.provider, form.base_url)
    model = form.model.strip()
    refusal: list[AiRefusedError] = []

    def change(settings: AiSettings) -> None:
        endpoint = settings.endpoint(form.provider)
        api_key = _key_for(form.provider, base_url, form.api_key, endpoint)
        if endpoint.api_key and not api_key:
            refusal.append(AiRefusedError(AiRefusal.KEY_MISSING))
            return
        if enabled:
            try:
                _require_key_and_model(api_key, model)
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
@command(Effect.IRREVERSIBLE, flags={Flag.SETTINGS})
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


# 不改 Berth 的任何狀態，所以是 READ；但它連到表單上的任意網址，key 欄空著時帶的是存著的那把
# （外洩 key 的路徑），還花使用者的 token：`CONNECTS_OUT`，`needs_person` 為真。
@command(Effect.READ, flags={Flag.CONNECTS_OUT})
async def test_ai(session: AsyncSession, factory: ServiceClientFactory, form: AiForm) -> AiTest:
    """照表單打一次最小呼叫，不存任何東西。服務回的錯誤是結果，不是拒絕。"""
    base_url = _base_url(form.provider, form.base_url)
    model = form.model.strip()
    saved = await read_settings(session, AiSettings)
    api_key = _key_for(form.provider, base_url, form.api_key, saved.endpoint(form.provider))
    _require_key_and_model(api_key, model)
    result = await probe(factory.ai(AiEndpoint(form.provider, base_url, api_key, model)))
    return AiTest(
        ok=result.failure is None,
        failure=result.failure,
        status=result.status,
        detail=result.detail.replace(api_key, _MASK),
        model=result.model,
    )


# 只讀本機價目表：不碰資料庫、不連外、不收 key，打到一半的網址也照查（認不出就照接口種類）。
@command(Effect.READ)
async def suggest_models(provider: AiProvider, base_url: str) -> AiModels:
    """沒按「取得模型」之前模型欄的建議：本機價目表照表單上的網址認出的那一家。"""
    return _from_prices(provider, normalize_base_url(provider, base_url))


# 同 `test_ai`：不改狀態，但連到表單上的任意網址，key 欄空著時帶的是存著的那把：`CONNECTS_OUT`。
@command(Effect.READ, flags={Flag.CONNECTS_OUT})
async def list_models(
    session: AsyncSession,
    factory: ServiceClientFactory,
    provider: AiProvider,
    base_url: str,
    api_key: str | None = None,
) -> AiModels:
    """向表單上的端點問它有哪些模型，不存任何東西。問不到不算拒絕：退回本機價目表，帶著原因；
    端點列出空的也退回，但沒有原因。key 的規則同測試連線（`_key_for`）。"""
    checked = _base_url(provider, base_url)
    saved = await read_settings(session, AiSettings)
    key = _key_for(provider, checked, api_key, saved.endpoint(provider))
    if not key:
        raise AiRefusedError(AiRefusal.KEY_MISSING)
    listing = await factory.ai_models(provider, checked, key).list_models()
    if listing.models:
        return AiModels(listing.models, AiModelSource.ENDPOINT, None, None, "")
    fallback = _from_prices(provider, checked)
    return AiModels(
        fallback.models,
        AiModelSource.PRICES,
        listing.failure,
        listing.status,
        listing.detail.replace(key, _MASK),
    )
