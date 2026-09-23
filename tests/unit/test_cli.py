"""CLI 的 smoke 測試：`--version` 是 M0 對外承諾的第一個指令。"""

from __future__ import annotations

import json
import shutil
import subprocess
from importlib.metadata import version
from pathlib import Path

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


class TestOpenapi:
    """`berth openapi`：型別產生器的上游（票 02）。**不跑起服務**——沒有 lifespan、
    沒有資料庫、不連任何東西，所以 CI 與離線開發都產得出來。
    """

    def test_writes_the_document_to_the_given_path(self, tmp_path: Path) -> None:
        target = tmp_path / "openapi.json"

        assert main(["openapi", "--output", str(target)]) == 0

        document = json.loads(target.read_text(encoding="utf-8"))
        assert document["openapi"].startswith("3.")
        assert "/api/health" in document["paths"]
        assert "HealthDetailOut" in document["components"]["schemas"]

    def test_writes_utf8_regardless_of_the_console_encoding(self, tmp_path: Path) -> None:
        """docstring 是繁體中文，Windows 的預設編碼寫不出來（cp950）。"""
        target = tmp_path / "openapi.json"

        main(["openapi", "--output", str(target)])

        assert "精靈" in target.read_text(encoding="utf-8")

    def test_leaves_no_database_behind(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_root = tmp_path / "config"
        monkeypatch.setenv("CONFIG_ROOT", str(config_root))

        assert main(["openapi", "--output", str(tmp_path / "openapi.json")]) == 0
        assert not config_root.exists()

    def test_is_byte_for_byte_reproducible(self, tmp_path: Path) -> None:
        """CI 的過期檢查是 `git diff --exit-code`，所以同一份程式碼要產出同一串位元組。"""
        first = tmp_path / "first.json"
        second = tmp_path / "second.json"

        main(["openapi", "--output", str(first)])
        main(["openapi", "--output", str(second)])

        assert first.read_bytes() == second.read_bytes()

    def test_prints_to_stdout_without_an_output_path(
        self, capsysbinary: pytest.CaptureFixture[bytes]
    ) -> None:
        assert main(["openapi"]) == 0

        document = json.loads(capsysbinary.readouterr().out.decode("utf-8"))
        assert "/api/health" in document["paths"]


class TestBench:
    """`berth bench` 的離開碼就是 CI 的門檻（plan §4.6），所以連 CLI 這一層一起測。

    語料換成一個最小的假 repo：真的那一份由 `tests/unit/test_bench.py` 守著，
    這裡量的是「報表說有問題時，指令有沒有真的失敗」。
    """

    @pytest.fixture
    def repo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        corpus = tmp_path / "tests" / "fixtures" / "parser" / "anime"
        corpus.mkdir(parents=True)
        snapshots = tmp_path / "tests" / "fixtures" / "tmdb"
        snapshots.mkdir(parents=True)
        (snapshots / "tv-1.json").write_text(
            json.dumps(
                {"tmdb_id": 1, "kind": "tv", "title": "S", "title_en": "S", "title_original": "S"}
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr("berth.cli.REPO_ROOT", tmp_path)
        return tmp_path

    def write_fixture(self, repo: Path, *, kind: str) -> None:
        payload = {
            "id": "anime/stub",
            "source_url": "https://example.invalid/stub",
            "torrent_name": "[Group] Show - 02 [1080p]",
            "tmdb": "tv-1",
            "context": {"media": "tv:1"},
            "files": [{"path": "Show - 02.mkv", "size": 1000}],
            "expected": [{"path": "Show - 02.mkv", "kind": kind, "action": "review"}],
        }
        path = repo / "tests" / "fixtures" / "parser" / "anime" / "stub.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def write_baseline(self, repo: Path, *, auto_correct: int, auto_wrong: int) -> None:
        (repo / "tests" / "fixtures" / "parser" / "baseline.json").write_text(
            json.dumps(
                {
                    "auto_correct": auto_correct,
                    "auto_wrong": auto_wrong,
                    "extra_correct": 0,
                    "subtitle_correct": 0,
                }
            ),
            encoding="utf-8",
        )

    def test_a_clean_run_succeeds_and_prints_the_report(
        self, repo: Path, capsysbinary: pytest.CaptureFixture[bytes]
    ) -> None:
        self.write_fixture(repo, kind="video")
        self.write_baseline(repo, auto_correct=0, auto_wrong=0)

        assert main(["bench"]) == 0
        assert "auto_wrong" in capsysbinary.readouterr().out.decode("utf-8")

    def test_a_misclassified_file_fails(self, repo: Path) -> None:
        self.write_fixture(repo, kind="extra")
        self.write_baseline(repo, auto_correct=0, auto_wrong=0)

        assert main(["bench"]) == 1

    def test_falling_below_the_baseline_fails(self, repo: Path) -> None:
        self.write_fixture(repo, kind="video")
        self.write_baseline(repo, auto_correct=9, auto_wrong=0)

        assert main(["bench"]) == 1

    def test_update_baseline_writes_the_current_numbers(self, repo: Path) -> None:
        self.write_fixture(repo, kind="video")
        self.write_baseline(repo, auto_correct=9, auto_wrong=9)

        assert main(["bench", "--update-baseline"]) == 0

        written = json.loads(
            (repo / "tests" / "fixtures" / "parser" / "baseline.json").read_text(encoding="utf-8")
        )
        assert (written["auto_correct"], written["auto_wrong"]) == (0, 0)
        assert main(["bench"]) == 0


class TestRebuildLedger:
    """`berth rebuild-ledger` 的接線。反查與反解本身在 `tests/integration/test_claims.py`。"""

    def test_an_empty_install_has_nothing_to_grow_back(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """全新的資料庫（schema 由 CLI 自己升）、沒有 Route：什麼都沒有配，離開碼 0。"""
        monkeypatch.setenv("CONFIG_ROOT", str(tmp_path / "config"))
        monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))
        (tmp_path / "config").mkdir()

        assert main(["rebuild-ledger"]) == 0
        out = capsys.readouterr().out
        assert "already in the ledger: 0" in out
        assert "grown back: 0" in out
