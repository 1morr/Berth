"""精靈第 6 步：TMDB（plan §9.3 第 6 步、§8.3、brief §16.3）。

**憑證由使用者自備，而且是必填的閘門**（票 02b）：Berth 不內建任何 provider 的 API key，
使用者要先去 themoviedb.org 申請一把貼進來，測得過才走得到第 7 步。沒有它，探索、季集快照
與命名全部停擺——所以這一步與可跳過的索引站不同級。

「測試」打的是 `configuration`——那一支不需要任何參數，回得出來就證明這把憑證有效。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceError
from berth.domain import StepStatus
from berth.models import SetupSettings, SetupStep, TmdbSettings
from berth.services.clients import ServiceClientFactory
from berth.services.settings import read_settings, write_settings
from berth.services.steps import StepView, message, step_views

#: 這一步唯一的那條纜繩，也是它打的端點。
TMDB_STEP = "configuration"

#: 空白的送出不必打去 TMDB 才知道不行，而它該說的是「必填」不是「401」。
#: 與其他服務回的原文一樣是英文（`SetupStep.error` 一律不翻譯）。
MISSING_CREDENTIAL = "a TMDB credential is required: paste your own API key or read access token"


@dataclass(frozen=True, slots=True)
class TmdbSetupStatus:
    """`GET /api/setup/tmdb` 與「測試」的整份形狀。"""

    #: 使用者的 key 已經存下來了。存下來不等於測得過——測不過也存（見 `verify_tmdb`）。
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
    """先存再測（與其他連線表單同一個規矩）：測不過也存，使用者才能改一個字再按一次。"""
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, TmdbSettings)
    settings.api_key = api_key.strip()
    await write_settings(session, settings)

    setup.tmdb.steps = [await _test(factory, settings)]
    await write_settings(session, setup)
    await session.commit()
    return _view(setup, settings)


async def _test(factory: ServiceClientFactory, settings: TmdbSettings) -> SetupStep:
    if not credential(settings):
        return SetupStep(key=TMDB_STEP, status=StepStatus.FAILED, error=MISSING_CREDENTIAL)

    client = factory.tmdb(credential(settings))
    try:
        configuration = await client.configuration()
    except ServiceError as exc:
        return SetupStep(key=TMDB_STEP, status=StepStatus.FAILED, error=message(exc))
    else:
        return SetupStep(key=TMDB_STEP, status=StepStatus.OK, detail=configuration.image_base_url)
    finally:
        await client.aclose()


def credential(settings: TmdbSettings) -> str:
    """憑證只有一個來源。之後的里程碑也從這一支拿，不要各自判斷一次。"""
    return settings.api_key.strip()


def tmdb_verified(setup: SetupSettings) -> bool:
    """第 6 步做完了沒。步序（`services/setup.py`）與這一步自己的狀態讀同一條規則。"""
    return any(row.status is StepStatus.OK for row in setup.tmdb.steps)


def _view(setup: SetupSettings, settings: TmdbSettings) -> TmdbSetupStatus:
    return TmdbSetupStatus(
        api_key_present=bool(credential(settings)),
        verified=tmdb_verified(setup),
        steps=step_views(setup.tmdb.steps),
    )
