"""精靈的頁由狀態導出（plan §9.3〈續行與跳過〉，M4 票 15）：`services.setup._current_step`
是純函式。

頁序：Jellyfin（擁有者）→ qBittorrent → 媒體庫與路徑 → Prowlarr 與索引站 → TMDB → 完成。
"""

from __future__ import annotations

from datetime import UTC, datetime

from berth.domain import (
    PROWLARR_LOGIN_STEP,
    ConnectionReason,
    ConnectionState,
    JellyfinStep,
    QbittorrentStep,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import (
    ServiceChoice,
    ServiceTest,
    SetupLibrary,
    SetupOwner,
    SetupSettings,
    SetupStep,
)
from berth.services.jellyfin import libraries_built
from berth.services.setup import (
    STEP_COMPLETE,
    STEP_INDEXER,
    STEP_JELLYFIN,
    STEP_QBITTORRENT,
    STEP_ROUTES,
    STEP_TMDB,
    _current_step,
)

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def chosen(origin: ServiceOrigin) -> ServiceChoice:
    return ServiceChoice(
        origin=origin,
        base_url="http://x",
        test=ServiceTest(
            state=ConnectionState.OK, reason=ConnectionReason.CONNECTED, checked_at=NOW
        ),
    )


def ok(*keys: str) -> list[SetupStep]:
    return [SetupStep(key=key, status=StepStatus.OK) for key in keys]


def finished(**origins: ServiceOrigin) -> SetupSettings:
    """每一頁都做完的狀態；`origins` 改某個服務的來源（預設全是套件內）。"""
    setup = SetupSettings(owner=SetupOwner(jellyfin_user_id="u1", name="skipper"))
    setup.choices = {
        kind: chosen(origins.get(kind.value, ServiceOrigin.BUNDLED)) for kind in ServiceKind
    }
    setup.jellyfin.steps = ok(*(step.value for step in JellyfinStep))
    setup.qbittorrent.steps = ok(*(step.value for step in QbittorrentStep))
    setup.indexer.steps = ok("nyaasi", PROWLARR_LOGIN_STEP)
    setup.tmdb.steps = ok("configuration")
    return setup


def test_a_clean_install_is_on_the_jellyfin_page() -> None:
    assert _current_step(SetupSettings(), berthed=False) == STEP_JELLYFIN


def test_everything_done_is_the_complete_page() -> None:
    assert _current_step(finished(), berthed=True) == STEP_COMPLETE


def test_no_owner_is_the_jellyfin_page_whatever_else_is_there() -> None:
    setup = finished()
    setup.owner = SetupOwner()

    assert _current_step(setup, berthed=True) == STEP_JELLYFIN


def test_an_unchosen_qbittorrent_holds_page_two() -> None:
    """還沒選就沒有做完，就算步驟都在（舊資料、或選擇被 migration 丟掉）。"""
    setup = finished()
    setup.choices = {k: v for k, v in setup.choices.items() if k is not ServiceKind.QBITTORRENT}

    assert _current_step(setup, berthed=True) == STEP_QBITTORRENT


def test_a_bundled_qbittorrent_needs_its_login_but_an_existing_one_does_not() -> None:
    bundled = finished()
    bundled.qbittorrent.steps = ok(
        *(step.value for step in QbittorrentStep if step is not QbittorrentStep.PASSWORD)
    )
    assert _current_step(bundled, berthed=True) == STEP_QBITTORRENT

    # 既有的那一台沒有偏好的纜繩（M4 票 22）：按「確認」只記密碼那一條 `skipped`，它就是做完了。
    existing = finished(qbittorrent=ServiceOrigin.EXISTING)
    existing.qbittorrent.steps = [
        SetupStep(key=QbittorrentStep.PASSWORD.value, status=StepStatus.SKIPPED)
    ]
    assert _current_step(existing, berthed=True) == STEP_COMPLETE
    # 還沒按就還沒做完。
    existing.qbittorrent.steps = []
    assert _current_step(existing, berthed=True) == STEP_QBITTORRENT


def test_page_three_holds_until_it_is_berthed() -> None:
    assert _current_step(finished(), berthed=False) == STEP_ROUTES


def snapshot(*rows: tuple[str, str]) -> list[SetupLibrary]:
    """Jellyfin 報的媒體庫（名稱、路徑）。"""
    return [
        SetupLibrary(name=name, item_id=name, collection_type="movies", locations=[path])
        for name, path in rows
    ]


def test_the_bundled_list_is_built_once_jellyfin_has_every_row() -> None:
    """看快照、不看「建媒體庫那一步」（M4 票 24）：重裝的 Berth 從沒跑過那一步。"""
    setup = finished()
    setup.jellyfin.steps = [row for row in setup.jellyfin.steps if row.key != "libraries"]
    setup.jellyfin.libraries = snapshot(
        ("Movies", "/data/library/movies"),
        ("TV", "/data/library/tv"),
        ("動畫", "/data/library/anime"),
    )

    # 「Anime」在 Jellyfin 被改了名，資料夾還是它的：照樣算建好了。
    assert libraries_built(setup, "/data/library") is True


def test_a_row_jellyfin_does_not_have_holds_the_list() -> None:
    setup = finished()
    setup.jellyfin.libraries = snapshot(
        ("Movies", "/data/library/movies"), ("TV", "/data/library/tv")
    )

    assert libraries_built(setup, "/data/library") is False


def test_an_existing_jellyfin_has_no_libraries_to_build() -> None:
    setup = finished(jellyfin=ServiceOrigin.EXISTING)

    assert libraries_built(setup, "/data/library") is True


def test_page_four_can_be_skipped_but_not_left_with_only_a_login() -> None:
    only_login = finished()
    only_login.indexer.steps = ok(PROWLARR_LOGIN_STEP)
    skipped = finished()
    skipped.indexer.steps = []
    skipped.indexer.skipped = True

    assert _current_step(only_login, berthed=True) == STEP_INDEXER
    assert _current_step(skipped, berthed=True) == STEP_COMPLETE


def test_a_bundled_prowlarr_needs_its_login_but_an_existing_one_does_not() -> None:
    bundled = finished()
    bundled.indexer.steps = ok("nyaasi")
    existing = finished(prowlarr=ServiceOrigin.EXISTING)
    existing.indexer.steps = ok("prowlarr")

    assert _current_step(bundled, berthed=True) == STEP_INDEXER
    assert _current_step(existing, berthed=True) == STEP_COMPLETE


def test_tmdb_is_a_gate() -> None:
    setup = finished()
    setup.tmdb.steps = []

    assert _current_step(setup, berthed=True) == STEP_TMDB


def test_the_page_order() -> None:
    assert (
        STEP_JELLYFIN,
        STEP_QBITTORRENT,
        STEP_ROUTES,
        STEP_INDEXER,
        STEP_TMDB,
        STEP_COMPLETE,
    ) == (
        1,
        2,
        3,
        4,
        5,
        6,
    )
