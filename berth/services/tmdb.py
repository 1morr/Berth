"""精靈第 6 步：TMDB（plan §9.3 第 6 步、§8.3、brief §16.3）。

一顆按鈕。Berth 內建一把專案級憑證（Seerr 的做法，brief §20.7），所以什麼都不填也走得下去；
`settings.services.tmdb.api_key` 有值就蓋過它。「測試」打的是 `configuration`——那一支不需要
任何參數，回得出來就證明這把憑證有效。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceError
from berth.adapters.tmdb import PROJECT_CREDENTIAL
from berth.domain import StepStatus
from berth.models import SetupSettings, SetupStep, TmdbSettings
from berth.services.clients import ServiceClientFactory
from berth.services.settings import read_settings, write_settings
from berth.services.steps import StepView, message, step_views

#: 這一步唯一的那條纜繩，也是它打的端點。
TMDB_STEP = "configuration"


@dataclass(frozen=True, slots=True)
class TmdbSetupStatus:
    """`GET /api/setup/tmdb` 與「測試」的整份形狀。"""

    #: 用的是內建的專案級憑證（使用者沒有覆寫）。
    using_project_credential: bool
    steps: tuple[StepView, ...]
    skipped: bool


async def read_tmdb_status(session: AsyncSession) -> TmdbSetupStatus:
    """不連線，只回存下來的狀態。"""
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, TmdbSettings)
    return _view(setup, settings)


async def verify_tmdb(
    session: AsyncSession, factory: ServiceClientFactory, *, api_key: str
) -> TmdbSetupStatus:
    """先存再測（與其他連線表單同一個規矩）。空字串就是「用回內建的那一把」。"""
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, TmdbSettings)
    settings.api_key = api_key.strip()
    await write_settings(session, settings)

    client = factory.tmdb(credential(settings))
    try:
        configuration = await client.configuration()
    except ServiceError as exc:
        step = SetupStep(key=TMDB_STEP, status=StepStatus.FAILED, error=message(exc))
    else:
        step = SetupStep(key=TMDB_STEP, status=StepStatus.OK, detail=configuration.image_base_url)
    finally:
        await client.aclose()

    setup.tmdb.steps = [step]
    setup.tmdb.skipped = False
    await write_settings(session, setup)
    await session.commit()
    return _view(setup, settings)


async def skip_tmdb(session: AsyncSession, *, skipped: bool = True) -> TmdbSetupStatus:
    """「之後再說」（plan §9.3）。"""
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, TmdbSettings)
    setup.tmdb.skipped = skipped
    await write_settings(session, setup)
    await session.commit()
    return _view(setup, settings)


def credential(settings: TmdbSettings) -> str:
    """使用者填的蓋過內建的。之後的里程碑也從這一支拿憑證，不要各自判斷一次。"""
    return settings.api_key.strip() or PROJECT_CREDENTIAL


def _view(setup: SetupSettings, settings: TmdbSettings) -> TmdbSetupStatus:
    return TmdbSetupStatus(
        using_project_credential=not settings.api_key.strip(),
        steps=step_views(setup.tmdb.steps),
        skipped=setup.tmdb.skipped,
    )
