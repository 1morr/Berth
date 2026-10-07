"""精靈第 7 步：TMDB（plan §9.3 第 7 步、§8.3、brief §16.3）。

**憑證由使用者自備，而且是必填的閘門**（票 02b）：Berth 不內建任何 provider 的 API key，
使用者要先去 themoviedb.org 申請一把貼進來，測得過才走得到第 8 步。沒有它，探索、季集快照
與命名全部停擺——所以這一步與可跳過的索引站不同級。

「測試」打的是 `configuration`——那一支不需要任何參數，回得出來就證明這把憑證有效。
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceError
from berth.domain import StepFailure, StepStatus
from berth.models import SetupSettings, SetupStep, TmdbSettings
from berth.services.clients import ServiceClientFactory
from berth.services.settings import read_settings, update_settings
from berth.services.steps import StepView, failed_step, step_views

#: 這一步唯一的那條纜繩，也是它打的端點。
TMDB_STEP = "configuration"

#: 空白的送出不必打去 TMDB 才知道不行，而它該說的是「必填」不是「401」。
#: 與其他服務回的原文一樣是英文（`SetupStep.error` 一律不翻譯）。
MISSING_CREDENTIAL = "a TMDB credential is required: paste your own API key or read access token"


@dataclass(frozen=True, slots=True)
class TmdbSetupStatus:
    """`GET /api/setup/tmdb` 與「測試」的整份形狀。"""

    #: 存著一把測過的 key。**只存測過的**（M4 票 45），所以它與 `verified` 同真同假；
    #: 0.1.0 測不過也存，那樣的舊值讀成沒有（不寫 migration，使用者拍板），下一次測過就蓋掉。
    #: 欄位留著是對外的形狀。
    api_key_present: bool
    #: 這一步的閘門：`configuration` 綠燈。前端讀這一個，不自己再導一次。
    verified: bool
    steps: tuple[StepView, ...]


async def read_tmdb_status(session: AsyncSession) -> TmdbSetupStatus:
    """不連線，只回存下來的狀態。"""
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, TmdbSettings)
    return _view(setup, settings)


async def verify_tmdb(
    session: AsyncSession, factory: ServiceClientFactory, *, api_key: str
) -> TmdbSetupStatus:
    """測過才存（M4 票 45，審計 E-6；Home Assistant 驗過才 `create_entry`）：測不過的那一把
    與它的紅燈只回給畫面，資料庫裡仍是原本的——已經有一把能用的就照舊在用（票 06i），沒有就
    還是沒有。

    原本還沒有能用的 key 時測不過也存，畫面因此多一個「已存下，沒通過驗證」的狀態，而那一把什麼都
    做不了；改一個字再按一次靠的是欄位留著使用者打的字，不靠存下來。
    """
    candidate = TmdbSettings(api_key=api_key.strip())
    step, image_base_url = await _test(factory, candidate)
    if step.status is not StepStatus.OK:
        setup = await read_settings(session, SetupSettings)
        working = _view(setup, await read_settings(session, TmdbSettings))
        return replace(working, steps=step_views([step]))

    def remember(latest: TmdbSettings) -> None:
        latest.api_key = candidate.api_key
        # 圖片基底順手存下來：它對同一把憑證是常數，而探索頁（票 03）每一張卡都要它。
        latest.image_base_url = image_base_url

    # 測試在路上時開頭讀到的那一份不整組寫回（M4 票 23）。
    settings = await update_settings(session, TmdbSettings, remember)

    def record(latest: SetupSettings) -> None:
        latest.tmdb.steps = [step]

    # 測試在路上的那幾秒裡，第 6 步可能已經寫進同一組設定（M2 票 15）。
    setup = await update_settings(session, SetupSettings, record)
    return _view(setup, settings)


async def _test(factory: ServiceClientFactory, settings: TmdbSettings) -> tuple[SetupStep, str]:
    """回這一步的結果，以及 `configuration` 給的圖片基底（失敗時是空字串）。

    基底由呼叫端寫回設定，不在這裡偷偷改 `settings`——那會讓「這支只是測一下」變成假的。
    """
    if not credential(settings):
        missing = SetupStep(
            key=TMDB_STEP,
            status=StepStatus.FAILED,
            failure=StepFailure.CREDENTIAL_MISSING,
            error=MISSING_CREDENTIAL,
        )
        return (missing, "")

    client = factory.tmdb(credential(settings))
    try:
        configuration = await client.configuration()
    except ServiceError as exc:
        # 401 是 `auth_rejected`：key 不對。畫面照代碼說，不再叫人去查網路（M4 票 21）。
        return (failed_step(TMDB_STEP, exc), "")
    else:
        base = configuration.image_base_url
        return (SetupStep(key=TMDB_STEP, status=StepStatus.OK, detail=base), base)
    finally:
        await client.aclose()


def credential(settings: TmdbSettings) -> str:
    """憑證只有一個來源。之後的里程碑也從這一支拿，不要各自判斷一次。"""
    return settings.api_key.strip()


def tmdb_verified(setup: SetupSettings) -> bool:
    """第 7 步做完了沒。步序（`services/setup.py`）與這一步自己的狀態讀同一條規則。"""
    return any(row.status is StepStatus.OK for row in setup.tmdb.steps)


def _view(setup: SetupSettings, settings: TmdbSettings) -> TmdbSetupStatus:
    verified = tmdb_verified(setup)
    return TmdbSetupStatus(
        api_key_present=verified and bool(credential(settings)),
        verified=verified,
        steps=step_views(setup.tmdb.steps),
    )
