"""共用 fixture：一個乾淨的 CONFIG_ROOT、一個已套 migration 的資料庫。"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.config import Config, load_config
from berth.db import create_engine, create_session_factory, upgrade_to_head


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """指向空目錄的設定；`config_root` 尚未建立，讓啟動流程自己建。"""
    return load_config(
        {"CONFIG_ROOT": str(tmp_path / "config"), "DATA_ROOT": str(tmp_path / "data")}
    )


async def migrate(config: Config) -> None:
    """跑一次啟動時的資料庫準備：建 CONFIG_ROOT、套 migration、收掉 engine。"""
    config.config_root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config)
    try:
        await upgrade_to_head(engine)
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def engine(config: Config) -> AsyncIterator[AsyncEngine]:
    await migrate(config)
    engine = create_engine(config)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with create_session_factory(engine)() as session:
        yield session


FIXTURES = Path(__file__).parent / "fixtures"

#: TMDB v3 API key 的**形狀**（32 個十六進位字元），不是一把真的 key。
#: 每個服務一個號碼，號碼表在 `tests/fixtures/http/README.md`；票 08 曾經在這裡寫了一把真的。
TMDB_API_KEY = "00000000000000000000000000000003"


def read_fixture(relative: str) -> str:
    """`tests/fixtures/` 底下的錄製回應（plan §1.2）。"""
    return (FIXTURES / relative).read_text(encoding="utf-8")


def host_bash() -> str | None:
    """讀得到宿主路徑的 bash：`deploy/` 的 shell 腳本測試用它跑腳本本人。

    Windows 的 PowerShell 裡 `bash` 先解析到 WSL 的 `System32\bash.exe`，它讀不到 `C:/…` 形式的
    路徑，於是每一條腳本測試都是與腳本無關的 exit 127（票 12 記下、票 15 收掉）。所以不看
    平台，問它讀不讀得到這一個檔案：Linux 與 Git Bash 讀得到，WSL 的啟動器讀不到就略過。
    """
    bash = shutil.which("bash")
    if bash is None:
        return None
    probe = subprocess.run(
        [bash, "-c", 'test -r "$1"', "bash", Path(__file__).as_posix()],
        capture_output=True,
        check=False,
    )
    return bash if probe.returncode == 0 else None
