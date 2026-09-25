"""程序層面的行為：啟動套 migration、健康端點、前端由同一個程序提供（票 02 驗收）。"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.main import HEALTH_CHECKER_TASK, QBIT_POLLER_TASK, RSS_POLLER_TASK, create_app
from berth.models import SetupSettings


@pytest.fixture
def web_root(tmp_path: Path) -> Path:
    """假的 `pnpm -C web build` 產出。"""
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>Berth</title>", encoding="utf-8")
    (root / "assets" / "index.js").write_text("export {}", encoding="utf-8")
    return root


@pytest.fixture
def client(config: Config, web_root: Path) -> TestClient:
    return TestClient(create_app(replace(config, web_root=web_root)))


class TestStartup:
    def test_starting_on_an_empty_config_root_creates_the_database(
        self, config: Config, client: TestClient
    ) -> None:
        assert not config.database_path.exists()

        with client:
            assert config.database_path.exists()

    def test_starting_twice_over_the_same_config_root_succeeds(
        self, config: Config, client: TestClient
    ) -> None:
        with client:
            pass
        with client:
            assert client.get("/api/health").status_code == 200


class TestHealth:
    def test_health_answers_anonymously(self, client: TestClient) -> None:
        with client:
            response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_reports_the_running_version(self, client: TestClient) -> None:
        from berth.config import VERSION

        with client:
            assert client.get("/api/health").json()["version"] == VERSION

    def test_health_says_whether_the_wizard_is_done(self, client: TestClient) -> None:
        """前端要在還沒有人登入得了的時候就決定該畫精靈還是登入頁（票 07）。"""
        with client:
            assert client.get("/api/health").json()["setup_completed"] is False


class TestFrontend:
    def test_the_root_serves_the_built_index(self, client: TestClient) -> None:
        with client:
            response = client.get("/")

        assert response.status_code == 200
        assert "<title>Berth</title>" in response.text

    def test_assets_are_served(self, client: TestClient) -> None:
        with client:
            assert client.get("/assets/index.js").status_code == 200

    def test_client_side_routes_fall_back_to_the_index(self, client: TestClient) -> None:
        """`/setup` 這類路徑只有前端 router 認得，後端要回 index.html。"""
        with client:
            response = client.get("/setup")

        assert response.status_code == 200
        assert "<title>Berth</title>" in response.text

    def test_a_client_route_merely_starting_with_api_still_gets_the_index(
        self, client: TestClient
    ) -> None:
        with client:
            response = client.get("/apiary")

        assert response.status_code == 200
        assert "<title>Berth</title>" in response.text

    def test_unknown_api_paths_stay_json(self, client: TestClient) -> None:
        """否則前端 fetch 會拿到 HTML 再在 JSON.parse 炸開，錯誤訊息毫無意義。

        匿名時是 401 而不是 404：門禁在路由之前（票 07），登入後的 404 見
        `test_auth_api.py`。
        """
        with client:
            response = client.get("/api/nope")

        assert response.status_code == 401
        assert json.loads(response.text)["detail"]


class TestCompression:
    """前端的 JS 一整包七百多 KB，壓縮後約兩百（M2 票 16 audit，M3 票 06）。

    Berth 自己送靜態檔，前面不一定有代理替它壓。
    """

    @pytest.fixture
    def bundle(self, web_root: Path) -> str:
        text = "export const words = " + json.dumps(["berth"] * 2000)
        (web_root / "assets" / "bundle.js").write_text(text, encoding="utf-8")
        return text

    def test_the_frontend_bundle_is_sent_gzipped(self, client: TestClient, bundle: str) -> None:
        with client:
            response = client.get("/assets/bundle.js", headers={"Accept-Encoding": "gzip"})

        assert response.headers["content-encoding"] == "gzip"
        assert int(response.headers["content-length"]) < len(bundle) // 5
        assert response.text == bundle

    def test_a_client_that_cannot_unzip_gets_it_plain(
        self, client: TestClient, bundle: str
    ) -> None:
        with client:
            response = client.get("/assets/bundle.js", headers={"Accept-Encoding": "identity"})

        assert "content-encoding" not in response.headers
        assert response.text == bundle


class TestApiCaching:
    """`/api` 底下的回應一律 `no-store`（票 10）。

    **這不是最佳化，是正確性。** Berth 原本一個快取 header 都不送，於是瀏覽器對 `200`
    套用它自己的啟發式快取——2026-09-10 實跑當場抓到：SSE 推來「這一筆完成了」之後前端
    重問一次，拿回來的卻是幾秒前那份說「已送出」的快取，畫面因此永遠停在錯的狀態。
    """

    def test_api_responses_are_never_cached(self, client: TestClient) -> None:
        with client:
            assert client.get("/api/health").headers["cache-control"] == "no-store"

    def test_a_refusal_is_not_cached_either(self, client: TestClient) -> None:
        """401 被快取的話，登入之後那一頁還是進不去。"""
        with client:
            response = client.get("/api/jobs")

        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"

    def test_the_frontend_is_left_alone(self, client: TestClient) -> None:
        """靜態檔有自己的快取規則（檔名帶內容雜湊），門禁不碰它。"""
        with client:
            assert "cache-control" not in client.get("/index.html").headers


class TestUnitOfWork:
    """一個請求一個工作單元，**commit 在回應送出之前**（plan §1.3、票 15）。

    FastAPI 對 `yield` 相依的預設是回應送出之後才跑收尾。那樣客戶端拿到 200 的那一刻寫入
    還沒落地：接著馬上打下一支的人讀到的是舊狀態，而 commit 失敗時他手上已經是一個成功。
    2026-09-17 的 e2e 當場抓到——精靈第 2 步判定完、第 3 步緊接著就讀不到 Jellyfin 的位址。
    """

    def test_a_write_is_committed_before_its_response_starts(
        self, config: Config, web_root: Path
    ) -> None:
        app = create_app(replace(config, web_root=web_root))
        committed_at_start: list[bool] = []

        async def watching(scope: Scope, receive: Receive, send: Send) -> None:
            async def watched(message: Message) -> None:
                if message["type"] == "http.response.start":
                    committed_at_start.append(_admin_committed(config))
                await send(message)

            await app(scope, receive, watched if scope["type"] == "http" else send)

        with TestClient(watching, headers={CSRF_HEADER: "XMLHttpRequest"}) as client:
            response = client.post(
                "/api/setup/admin", json={"username": "skipper", "password": "harbour"}
            )

        assert response.status_code == 200
        assert committed_at_start == [True]


def _admin_committed(config: Config) -> bool:
    """另開一條連線讀：看得到的只有已經 commit 的東西。"""
    with closing(sqlite3.connect(config.database_path)) as db:
        row = db.execute(
            "SELECT value_json FROM settings WHERE key = ?", (SetupSettings.KEY,)
        ).fetchone()
    return row is not None and json.loads(row[0])["admin"]["username"] == "skipper"


class TestBackgroundLoops:
    """兩個背景迴圈由 lifespan 啟動與關閉（plan §3.2、票 10 驗收）。"""

    @pytest.mark.asyncio
    async def test_both_loops_run_under_the_lifespan(self, config: Config) -> None:
        app = create_app(config)

        async with app.router.lifespan_context(app):
            assert _running(HEALTH_CHECKER_TASK), "迴圈沒起來的話健康頁永遠是空的"
            assert _running(QBIT_POLLER_TASK), "迴圈沒起來的話下載列表永遠停在送單那一刻"
            assert _running(RSS_POLLER_TASK), "迴圈沒起來的話 Feed 只在按「立即輪詢」時才動"

    @pytest.mark.asyncio
    async def test_shutting_down_leaves_no_pending_task(self, config: Config) -> None:
        """關掉之後不留 pending task（票 10 驗收）。留著的話 uvicorn 會在收工時卡住。"""
        app = create_app(config)

        async with app.router.lifespan_context(app):
            pass

        assert not _running(HEALTH_CHECKER_TASK)
        assert not _running(QBIT_POLLER_TASK)
        assert not _running(RSS_POLLER_TASK)


def _running(name: str) -> list[asyncio.Task[None]]:
    return [task for task in asyncio.all_tasks() if task.get_name() == name]


class TestFrontendNotBuilt:
    def test_the_api_still_runs_without_a_frontend_build(self, config: Config) -> None:
        missing = replace(config, web_root=config.config_root / "never-built")

        with TestClient(create_app(missing)) as client:
            assert client.get("/api/health").status_code == 200
            assert client.get("/").status_code == 404
