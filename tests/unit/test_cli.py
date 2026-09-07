"""CLI 的 smoke 測試：`--version` 是 M0 對外承諾的第一個指令。"""

from __future__ import annotations

import shutil
import subprocess
from importlib.metadata import version

import pytest

from berth.cli import main


def test_version_flag_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert version("berth") in capsys.readouterr().out


def test_no_arguments_prints_help_and_fails(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_installed_console_script_reports_version() -> None:
    """驗收條件是 `uv run berth --version`，所以連 entry point 一起測。"""
    executable = shutil.which("berth")
    assert executable is not None, "berth console script is not installed; check [project.scripts]"

    result = subprocess.run([executable, "--version"], capture_output=True, text=True, check=True)

    assert version("berth") in result.stdout


class TestServe:
    @pytest.fixture
    def uvicorn_run(self, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
        calls: list[dict[str, object]] = []
        monkeypatch.setattr("berth.cli.uvicorn.run", lambda *args, **kwargs: calls.append(kwargs))
        return calls

    def test_serve_binds_every_interface_on_the_configured_port(
        self, uvicorn_run: list[dict[str, object]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PORT", "9111")

        assert main(["serve"]) == 0
        assert uvicorn_run[0]["host"] == "0.0.0.0"
        assert uvicorn_run[0]["port"] == 9111

    def test_serve_builds_the_app_through_the_factory(
        self, uvicorn_run: list[dict[str, object]]
    ) -> None:
        """傳 import string 而不是 app 實例，`--reload` 才有東西可以重新載入。"""
        assert main(["serve"]) == 0
        assert uvicorn_run[0]["factory"] is True

    def test_reload_is_off_unless_asked_for(self, uvicorn_run: list[dict[str, object]]) -> None:
        main(["serve"])
        main(["serve", "--reload"])

        assert uvicorn_run[0]["reload"] is False
        assert uvicorn_run[1]["reload"] is True
