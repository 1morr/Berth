"""健康檢查的四項與它們的紀錄（plan §3.2、§9.5、brief §16.2、票 10）。

驗的是票 10 的驗收：四項各自獨立、失敗說得出原因、最後成功時間留得住、服務回來就自動
變綠、Route 的結果寫回 `routes` 表。

檔案系統與第 5 步一樣是**真的**：Route 的五項檢查會真的建目錄、寫探測檔、`link()` 再比
inode（`tests/integration/arrange.py`）。
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceUnavailableError
from berth.adapters.qbittorrent import IpBannedError, QbittorrentVersion
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.domain import HealthStatus, QbittorrentStep, ServiceKind, ServiceOrigin
from berth.models import HealthSettings, IndexerSettings, QbittorrentSettings, Route
from berth.services.health import (
    CHECK_INTERVAL,
    HealthReport,
    check_health,
    check_service,
    is_due,
    overall_status,
    read_health,
)
from berth.services.routes import RouteView, build_routes
from berth.services.settings import read_settings, write_settings
from tests.integration.arrange import NOW, applied_qbittorrent, arrange, factory_for
from tests.integration.factories import FakeClientFactory

pytestmark = pytest.mark.asyncio


def statuses(report: HealthReport) -> dict[ServiceKind, HealthStatus]:
    """逐服務的判定，鍵是 `ServiceKind`。"""
    return {row.kind: row.status for row in report.services}


async def ready(session: AsyncSession, roots: dict[str, Path]) -> FakeClientFactory:
    """精靈跑完的樣子：四個泊位都接好、三條 Route 都建好而且綠燈。"""
    factory = factory_for(roots)
    await arrange(session, roots)
    status = await build_routes(session, factory, ())
    assert status.ready, "健康檢查的起點必須是三條綠燈的 Route"
    return factory


class TestAllFour:
    async def test_every_check_passes_on_a_finished_setup(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)

        report = await check_health(session, factory, now=NOW)

        assert statuses(report) == dict.fromkeys(ServiceKind, HealthStatus.OK)
        assert report.routes_status is HealthStatus.OK
        assert report.degraded is False
        assert len(report.routes) == 3

    async def test_each_service_reports_what_it_measured(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """實測值就是證據：版本號與索引站數量。"""
        factory = await ready(session, roots)

        report = await check_health(session, factory, now=NOW)
        detail = {row.kind: row.detail for row in report.services}
        library_count = {row.kind: row.library_count for row in report.services}

        assert "12.1.0" in detail[ServiceKind.JELLYFIN]
        assert "5.2.3" in detail[ServiceKind.QBITTORRENT]
        assert detail[ServiceKind.PROWLARR]
        # 媒體庫數量是給前端組句子的數字，不是英文寫死進 `detail`（票 21 驗收）。
        assert library_count[ServiceKind.JELLYFIN] == 3

    async def test_the_report_says_which_service_is_bundled(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """修正建議分兩種：套件內是「容器還在嗎」，既有是「位址與憑證對嗎」。"""
        factory = await ready(session, roots)

        report = await check_health(session, factory, now=NOW)

        assert {row.origin for row in report.services} == {ServiceOrigin.BUNDLED}

    async def test_reading_the_report_again_does_not_touch_the_services(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """健康頁載入時看的是上一輪的結果，不是又去打一次每個服務。"""
        factory = await ready(session, roots)
        await check_health(session, factory, now=NOW)
        before = factory.qbittorrent_.calls

        report = await read_health(session)

        assert factory.qbittorrent_.calls == before
        assert statuses(report) == dict.fromkeys(ServiceKind, HealthStatus.OK)


class TestOneServiceDown:
    async def test_an_unreachable_indexer_does_not_touch_the_other_three(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """索引站是唯一沒有人依賴它的那一項，所以它掛掉時另外三項必須全綠。"""
        factory = await ready(session, roots)
        factory.prowlarr_.ping_error = ServiceUnavailableError("GET /ping: connection refused")

        report = await check_health(session, factory, now=NOW)

        assert statuses(report)[ServiceKind.PROWLARR] is HealthStatus.FAILED
        assert statuses(report)[ServiceKind.JELLYFIN] is HealthStatus.OK
        assert statuses(report)[ServiceKind.QBITTORRENT] is HealthStatus.OK
        assert report.routes_status is HealthStatus.OK

    async def test_a_failure_keeps_the_service_own_words(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        factory.prowlarr_.ping_error = ServiceUnavailableError("GET /ping: connection refused")

        report = await check_health(session, factory, now=NOW)
        row = next(row for row in report.services if row.kind is ServiceKind.PROWLARR)

        assert "connection refused" in row.error

    async def test_a_down_service_makes_the_whole_thing_degraded(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        factory.prowlarr_.ping_error = ServiceUnavailableError("GET /ping: connection refused")

        report = await check_health(session, factory, now=NOW)

        assert report.degraded is True
        assert await overall_status(session) == "degraded"

    async def test_a_jellyfin_below_twelve_is_red_with_a_next_step(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """只支援 Jellyfin 12 以上（brief §16.4、§19）：那不是「連不上」而是「這台不能用」。"""
        factory = await ready(session, roots)
        factory.jellyfin_.version = "10.11.11"

        report = await check_health(session, factory, now=NOW)
        jellyfin = next(row for row in report.services if row.kind is ServiceKind.JELLYFIN)

        assert jellyfin.status is HealthStatus.FAILED
        assert jellyfin.detail == "10.11.11"
        assert "12.0" in jellyfin.error
        # 旗標而不是一句話：畫面照它說出升級的那幾件事（先備份、移除第三方插件、完整掃描）。
        assert jellyfin.unsupported is True

    async def test_jellyfin_going_down_also_reddens_the_routes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Route 的檢查三、四要問 Jellyfin，所以它掛掉時 Route 一起紅是事實不是連坐。"""
        factory = await ready(session, roots)
        factory.jellyfin_.error = ServiceUnavailableError("GET /System/Info/Public: refused")

        report = await check_health(session, factory, now=NOW)

        assert statuses(report)[ServiceKind.JELLYFIN] is HealthStatus.FAILED
        assert statuses(report)[ServiceKind.QBITTORRENT] is HealthStatus.OK
        assert report.routes_status is HealthStatus.FAILED


class TestLastSuccess:
    async def test_a_failure_keeps_the_last_time_it_worked(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「現在紅著，但五分鐘前還好好的」與「從來沒通過」是兩件事（brief §16.2）。"""
        factory = await ready(session, roots)
        await check_health(session, factory, now=NOW)
        factory.prowlarr_.ping_error = ServiceUnavailableError("refused")

        report = await check_health(session, factory, now=NOW + CHECK_INTERVAL)
        row = next(row for row in report.services if row.kind is ServiceKind.PROWLARR)

        assert row.last_ok_at == NOW
        assert row.checked_at == NOW + CHECK_INTERVAL

    async def test_consecutive_failures_are_counted(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        factory.prowlarr_.ping_error = ServiceUnavailableError("refused")

        await check_health(session, factory, now=NOW)
        report = await check_health(session, factory, now=NOW + CHECK_INTERVAL)
        row = next(row for row in report.services if row.kind is ServiceKind.PROWLARR)

        assert row.failures == 2

    async def test_a_service_that_comes_back_goes_green_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """重啟服務就好，不必重啟 Berth（票 10 驗收）。"""
        factory = await ready(session, roots)
        factory.prowlarr_.ping_error = ServiceUnavailableError("refused")
        await check_health(session, factory, now=NOW)

        factory.prowlarr_.ping_error = None
        report = await check_health(session, factory, now=NOW + CHECK_INTERVAL)
        row = next(row for row in report.services if row.kind is ServiceKind.PROWLARR)

        assert row.status is HealthStatus.OK
        assert row.failures == 0
        assert row.last_ok_at == NOW + CHECK_INTERVAL
        assert row.error == ""


class TestNotConfigured:
    async def test_a_skipped_indexer_is_unknown_rather_than_red(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """第 6 步可以跳過（plan §9.3），跳過的人不該永遠看到一盞紅燈。"""
        factory = await ready(session, roots)
        await write_settings(session, IndexerSettings())
        await session.commit()

        report = await check_health(session, factory, now=NOW)
        row = next(row for row in report.services if row.kind is ServiceKind.PROWLARR)

        assert row.status is HealthStatus.UNKNOWN
        assert row.configured is False
        assert report.degraded is False


class TestTmdb:
    """健康頁的泊位板有 TMDB 那一格（票 06e）。它不在四項檢查裡——那四項量的是
    Berth 連得上的服務，TMDB 的憑證只在精靈第 7 步測過——所以讀的是那一次的結果。"""

    async def test_the_report_carries_whether_the_tmdb_credential_was_verified(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        assert (await read_health(session)).tmdb_verified is False

        await ready(session, roots)

        assert (await read_health(session)).tmdb_verified is True


class TestQbittorrentDrift:
    async def test_a_changed_recommended_key_is_reported_as_drift(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """設定漂移不是斷線：那台服務好好的，只是有人把建議值改掉了（brief §16.3）。"""
        factory = await ready(session, roots)
        await factory.qbittorrent_.set_preferences({QbittorrentStep.AUTO_TMM_ENABLED.value: False})

        report = await check_health(session, factory, now=NOW)
        row = next(row for row in report.services if row.kind is ServiceKind.QBITTORRENT)

        assert row.status is HealthStatus.OK
        assert row.drift == (QbittorrentStep.AUTO_TMM_ENABLED.value,)

    async def test_a_service_in_agreement_reports_no_drift(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)

        report = await check_health(session, factory, now=NOW)
        row = next(row for row in report.services if row.kind is ServiceKind.QBITTORRENT)

        assert row.drift == ()

    async def test_a_web_api_below_the_floor_is_a_failure(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """低於 4.4 的 Web API 缺少 Berth 要用的端點（brief §16.4）。"""
        await ready(session, roots)
        outdated = factory_for(
            roots,
            qbittorrent=applied_qbittorrent(
                roots, version=QbittorrentVersion(app="v4.1.9", webapi="2.2.0")
            ),
        )

        report = await check_health(session, outdated, now=NOW)
        row = next(row for row in report.services if row.kind is ServiceKind.QBITTORRENT)

        assert row.status is HealthStatus.FAILED
        assert "2.8.4" in row.error


class TestRoutes:
    async def test_the_route_row_is_written_back(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """健康頁與精靈第 5 步寫的是同一個欄位（票 10 驗收）。"""
        factory = await ready(session, roots)
        factory.jellyfin_.visible_roots = ("/somewhere-else",)

        await check_health(session, factory, now=NOW)
        rows = (await session.scalars(select(Route).order_by(Route.id))).all()

        assert {row.health_status for row in rows} == {HealthStatus.FAILED}
        assert all(row.health_detail_json for row in rows)

    async def test_a_recovered_mount_turns_the_route_green_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        factory.jellyfin_.visible_roots = ("/somewhere-else",)
        await check_health(session, factory, now=NOW)

        factory.jellyfin_.visible_roots = None
        report = await check_health(session, factory, now=NOW + CHECK_INTERVAL)

        assert report.routes_status is HealthStatus.OK

    async def test_no_routes_at_all_is_unknown_not_degraded(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = factory_for(roots)
        await arrange(session, roots)

        report = await check_health(session, factory, now=NOW)

        assert report.routes_status is HealthStatus.UNKNOWN
        assert report.degraded is False


class TestRouteTimestamps:
    async def test_a_route_records_when_it_last_passed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """票 10：健康頁顯示每個 Route 的**最後成功時間**。"""
        factory = await ready(session, roots)

        report = await check_health(session, factory, now=NOW)

        assert all(route.checked_at is not None for route in report.routes)
        assert all(route.last_ok_at is not None for route in report.routes)

    async def test_a_broken_route_keeps_the_last_time_it_passed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        await check_health(session, factory, now=NOW)
        before = report_route(await read_health(session)).last_ok_at
        assert before is not None

        factory.jellyfin_.visible_roots = ("/somewhere-else",)
        await check_health(session, factory)
        route = report_route(await read_health(session))

        assert route.health is HealthStatus.FAILED
        assert route.last_ok_at == before
        assert route.checked_at is not None
        assert route.checked_at > before


def report_route(report: HealthReport) -> RouteView:
    return report.routes[0]


class TestSingleService:
    async def test_testing_one_service_leaves_the_others_alone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """設定頁的「測試連線」只重測那一個（票 10 驗收）。"""
        factory = await ready(session, roots)
        await check_health(session, factory, now=NOW)
        factory.jellyfin_.error = AuthFailedError("GET /Library/VirtualFolders: 401")

        report = await check_service(
            session, factory, ServiceKind.QBITTORRENT, now=NOW + CHECK_INTERVAL
        )

        assert statuses(report)[ServiceKind.QBITTORRENT] is HealthStatus.OK
        assert statuses(report)[ServiceKind.JELLYFIN] is HealthStatus.OK
        jellyfin = next(row for row in report.services if row.kind is ServiceKind.JELLYFIN)
        assert jellyfin.checked_at == NOW

    async def test_testing_one_service_does_not_rerun_the_route_checks(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        await check_health(session, factory, now=NOW)
        before = len(factory.qbittorrent_.created_categories)

        await check_service(session, factory, ServiceKind.QBITTORRENT, now=NOW + CHECK_INTERVAL)

        assert len(factory.qbittorrent_.created_categories) == before


class TestSchedule:
    async def test_a_snapshot_that_was_never_taken_is_due(self, session: AsyncSession) -> None:
        assert await is_due(session, now=NOW) is True

    async def test_a_fresh_snapshot_is_not_due(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        await check_health(session, factory, now=NOW)

        assert await is_due(session, now=NOW + timedelta(minutes=1)) is False

    async def test_a_snapshot_older_than_the_interval_is_due(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """紅燈要在 5 分鐘內出現（票 10 驗收），所以到期就是 5 分鐘。"""
        factory = await ready(session, roots)
        await check_health(session, factory, now=NOW)

        assert await is_due(session, now=NOW + CHECK_INTERVAL) is True


class TestStoredSnapshot:
    async def test_the_snapshot_lives_in_its_own_settings_row(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """迴圈每 5 分鐘寫一次的東西不該混進使用者設定的連線資訊（plan §3.2）。"""
        factory = await ready(session, roots)
        await check_health(session, factory, now=NOW)

        stored = await read_settings(session, HealthSettings)

        assert stored.checked_at == NOW
        assert set(stored.services) == set(ServiceKind)
        assert stored.routes is HealthStatus.OK

    async def test_an_empty_snapshot_answers_ok(self, session: AsyncSession) -> None:
        """還沒檢查過不是「降級」——降級的意思是有東西**已知**壞了。"""
        assert await overall_status(session) == "ok"


class TestIpBan:
    """被封了與帳密不對的**下一步不同**（plan §8.1、brief §20.2、票 10）。

    qBittorrent 連續 5 次登入失敗會封住來源 IP 並回 `403`；帳密不對在 4.4.5 是 `200` + `Fails.`、
    在 5.2.3 是 `401`。這一票之前兩者都變成一句「要帳密」，於是使用者去改一組本來就對的密碼，
    再失敗五次，把封鎖時間重新算一輪。
    """

    async def test_a_banned_client_says_so_instead_of_asking_for_credentials(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)
        factory = factory_for(roots)
        factory.qbittorrent_ = FakeQbittorrentClient(
            login_error=IpBannedError(
                "auth/login: Your IP address has been banned after too many failed "
                "authentication attempts."
            )
        )
        credentials = await read_settings(session, QbittorrentSettings)
        credentials.username = "admin"
        credentials.password = "adminadmin"
        await write_settings(session, credentials)
        await session.commit()

        report = await check_health(session, factory)

        qbittorrent = next(row for row in report.services if row.kind is ServiceKind.QBITTORRENT)
        assert qbittorrent.status is HealthStatus.FAILED
        assert qbittorrent.banned is True
        # 原文照舊：它自己就說了發生什麼事，而理由的翻譯是畫面的事。
        assert "banned" in qbittorrent.error

    async def test_wrong_credentials_are_still_just_wrong_credentials(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)
        factory = factory_for(roots)
        factory.qbittorrent_ = FakeQbittorrentClient(
            login_error=AuthFailedError("auth/login: rejected")
        )
        credentials = await read_settings(session, QbittorrentSettings)
        credentials.username = "admin"
        credentials.password = "wrongwrong"
        await write_settings(session, credentials)
        await session.commit()

        report = await check_health(session, factory)

        qbittorrent = next(row for row in report.services if row.kind is ServiceKind.QBITTORRENT)
        assert qbittorrent.status is HealthStatus.FAILED
        assert qbittorrent.banned is False
