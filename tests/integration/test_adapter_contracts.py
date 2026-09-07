"""三個 adapter 對 `tests/fixtures/http/` 錄製回應的契約測試（plan §1.3、票 05）。

錄製來源與日期見 `tests/fixtures/http/README.md`。這裡驗的是「真服務回這個，adapter 解成那個」，
所以斷言貼著錄下來的值，不重寫一份假的 payload。
"""

from __future__ import annotations

import json
import socket

import httpx
import pytest
import respx

from berth.adapters.http import (
    AuthFailedError,
    ProtocolMismatchError,
    ServiceBusyError,
    ServiceNotDeployedError,
    ServiceUnavailableError,
)
from berth.adapters.jellyfin import NewLibrary, TypeOption
from berth.adapters.jellyfin.client import HttpJellyfinClient
from berth.adapters.prowlarr.client import HttpProwlarrClient
from berth.adapters.qbittorrent.client import HttpQbittorrentClient
from berth.domain import CollectionType
from berth.services.jellyfin import MERGE_VERSIONS_REPOSITORY
from tests.conftest import read_fixture

JELLYFIN_URL = "http://jellyfin:8096"
QBITTORRENT_URL = "http://qbittorrent:8080"
PROWLARR_URL = "http://prowlarr:9696"


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_public_info_before_startup_wizard() -> None:
    respx.get(f"{JELLYFIN_URL}/System/Info/Public").respond(
        200, text=read_fixture("http/jellyfin/system-info-public.setup-pending.json")
    )

    client = HttpJellyfinClient(JELLYFIN_URL)
    try:
        info = await client.public_info()
    finally:
        await client.aclose()

    assert info.startup_wizard_completed is False
    assert info.version == "10.11.11"


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_public_info_after_startup_wizard() -> None:
    respx.get(f"{JELLYFIN_URL}/System/Info/Public").respond(
        200, text=read_fixture("http/jellyfin/system-info-public.configured.json")
    )

    client = HttpJellyfinClient(JELLYFIN_URL)
    try:
        info = await client.public_info()
    finally:
        await client.aclose()

    assert info.startup_wizard_completed is True


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_rejects_a_payload_from_something_else() -> None:
    respx.get(f"{JELLYFIN_URL}/System/Info/Public").respond(200, json={"hello": "world"})

    client = HttpJellyfinClient(JELLYFIN_URL)
    with pytest.raises(ProtocolMismatchError):
        await client.public_info()
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_version_without_credentials() -> None:
    respx.get(f"{QBITTORRENT_URL}/api/v2/app/version").respond(
        200, text=read_fixture("http/qbittorrent/app-version.txt")
    )
    respx.get(f"{QBITTORRENT_URL}/api/v2/app/webapiVersion").respond(
        200, text=read_fixture("http/qbittorrent/app-webapiversion.txt")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        version = await client.version()
    finally:
        await client.aclose()

    assert version.app == "v5.2.3"
    assert version.webapi == "2.15.1"


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_forbidden_maps_to_auth_failed() -> None:
    respx.get(f"{QBITTORRENT_URL}/api/v2/app/version").respond(
        403, text=read_fixture("http/qbittorrent/app-version.forbidden.txt")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    with pytest.raises(AuthFailedError):
        await client.version()
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_sends_referer_matching_the_base_url() -> None:
    """CSRF：送了 `Referer` 就必須與 Host 一致，不一致回 401（brief §20.7）。"""
    route = respx.get(f"{QBITTORRENT_URL}/api/v2/app/version").respond(200, text="v5.2.3")
    respx.get(f"{QBITTORRENT_URL}/api/v2/app/webapiVersion").respond(200, text="2.15.1")

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        await client.version()
    finally:
        await client.aclose()

    assert route.calls.last.request.headers["Referer"] == QBITTORRENT_URL


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_ping_is_anonymous() -> None:
    respx.get(f"{PROWLARR_URL}/ping").respond(200, text=read_fixture("http/prowlarr/ping.json"))

    client = HttpProwlarrClient(PROWLARR_URL)
    try:
        await client.ping()
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_indexers_empty_on_a_fresh_install() -> None:
    respx.get(f"{PROWLARR_URL}/api/v1/indexer").respond(
        200, text=read_fixture("http/prowlarr/indexer.empty.json")
    )

    client = HttpProwlarrClient(PROWLARR_URL, "key")
    try:
        assert await client.indexers() == []
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_indexers_parsed_from_a_configured_install() -> None:
    route = respx.get(f"{PROWLARR_URL}/api/v1/indexer").respond(
        200, text=read_fixture("http/prowlarr/indexer.configured.json")
    )

    client = HttpProwlarrClient(PROWLARR_URL, "the-key")
    try:
        indexers = await client.indexers()
    finally:
        await client.aclose()

    assert [(row.id, row.name, row.enabled) for row in indexers] == [(1, "Nyaa.si", True)]
    assert route.calls.last.request.headers["X-Api-Key"] == "the-key"


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_without_api_key_maps_to_auth_failed() -> None:
    respx.get(f"{PROWLARR_URL}/api/v1/indexer").respond(401)

    client = HttpProwlarrClient(PROWLARR_URL)
    with pytest.raises(AuthFailedError):
        await client.indexers()
    await client.aclose()


@pytest.mark.asyncio
async def test_unresolvable_host_is_not_deployed(monkeypatch: pytest.MonkeyPatch) -> None:
    """主機名解不到 = 服務不在 compose 裡，不是「還沒起來」（plan §9.3 第 2 步）。

    這條不走 respx：它會把 side effect 例外的 `__cause__` 換成自己的 Route 物件，
    而分類靠的正是 `__cause__` 鏈。真實鏈是 httpx.ConnectError → httpcore → socket.gaierror。
    """
    chained = httpx.ConnectError("nodename nor servname provided")
    chained.__cause__ = socket.gaierror(-2, "Name or service not known")

    async def raise_dns_failure(*_args: object, **_kwargs: object) -> httpx.Response:
        raise chained

    monkeypatch.setattr(httpx.AsyncClient, "request", raise_dns_failure)

    client = HttpJellyfinClient(JELLYFIN_URL)
    with pytest.raises(ServiceNotDeployedError):
        await client.public_info()
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_connection_refused_is_unavailable() -> None:
    respx.get(f"{JELLYFIN_URL}/System/Info/Public").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    client = HttpJellyfinClient(JELLYFIN_URL)
    with pytest.raises(ServiceUnavailableError):
        await client.public_info()
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_timeout_is_unavailable() -> None:
    respx.get(f"{JELLYFIN_URL}/System/Info/Public").mock(
        side_effect=httpx.ConnectTimeout("timed out")
    )

    client = HttpJellyfinClient(JELLYFIN_URL)
    with pytest.raises(ServiceUnavailableError):
        await client.public_info()
    await client.aclose()


# --- Jellyfin：精靈第 3 步用到的端點（plan §9.4、§9.5、票 06）---


def jellyfin_client(token: str = "") -> HttpJellyfinClient:
    return HttpJellyfinClient(JELLYFIN_URL, token=token)


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_libraries_parsed_with_their_paths_and_fetchers() -> None:
    """一庫多路徑與 `TypeOptions[].MetadataFetchers` 都要讀得出來（plan §8.2）。"""
    respx.get(f"{JELLYFIN_URL}/Library/VirtualFolders").respond(
        200, text=read_fixture("http/jellyfin/library-virtualfolders.json")
    )

    client = jellyfin_client("key")
    try:
        libraries = await client.libraries()
    finally:
        await client.aclose()

    by_name = {library.name: library for library in libraries}
    assert by_name["Movies"].collection_type == "movies"
    assert by_name["Movies"].locations == ("/data/library/movies",)
    assert by_name["TV"].item_id
    # 使用者自己的媒體庫：兩條路徑，而且掛了 TVDB 插件（brief §16.4 的警告來源）。
    assert by_name["Films"].locations == ("/data/library/films", "/data/nas-films")
    assert by_name["Films"].type_options[0].metadata_fetchers == ("TheTVDB", "TheMovieDb")
    assert [option.type for option in by_name["TV"].type_options] == ["Series", "Season", "Episode"]


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_available_options_are_fetcher_names() -> None:
    """`AvailableOptions` 回 `{Name, Type}` 物件，媒體庫本身回字串陣列——兩種都要接。

    這兩份是**裝了 TVDB 插件之後**錄的：插件會替每個型別多掛幾個 fetcher，正好證明
    「圖片 fetcher 不能寫死」——同一台伺服器裝了什麼，清單就不一樣（brief §20.7）。
    """
    respx.get(f"{JELLYFIN_URL}/Libraries/AvailableOptions").respond(
        200, text=read_fixture("http/jellyfin/libraries-availableoptions.tvshows.with-tvdb.json")
    )

    client = jellyfin_client("key")
    try:
        options = await client.available_type_options(CollectionType.TVSHOWS)
    finally:
        await client.aclose()

    assert [option.type for option in options] == ["Series", "Season", "Episode"]
    assert options[0].metadata_fetchers == (
        "TheMovieDb",
        "The Open Movie Database",
        "Missing Episode Fetcher",
        "TheTVDB",
    )
    assert options[0].image_fetchers == ("TheMovieDb", "TheTVDB")


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_movie_available_options() -> None:
    respx.get(f"{JELLYFIN_URL}/Libraries/AvailableOptions").respond(
        200, text=read_fixture("http/jellyfin/libraries-availableoptions.movies.with-tvdb.json")
    )

    client = jellyfin_client("key")
    try:
        options = await client.available_type_options(CollectionType.MOVIES)
    finally:
        await client.aclose()

    assert [option.type for option in options] == ["Movie"]
    assert options[0].image_fetchers == (
        "TheMovieDb",
        "TheTVDB",
        "The Open Movie Database",
        "Embedded Image Extractor",
        "Screen Grabber",
    )


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_create_library_wraps_the_options_one_level() -> None:
    """直接送 `LibraryOptions` 一樣回 204，但整份設定會被靜默丟掉（brief §20.7）。"""
    route = respx.post(f"{JELLYFIN_URL}/Library/VirtualFolders").respond(204)

    client = jellyfin_client()
    try:
        await client.create_library(
            NewLibrary(
                name="TV",
                collection_type=CollectionType.TVSHOWS,
                path="/data/library/tv",
                type_options=(
                    TypeOption(
                        type="Series",
                        metadata_fetchers=("TheMovieDb",),
                        image_fetchers=("TheMovieDb",),
                    ),
                ),
                preferred_metadata_language="zh-TW",
                metadata_country_code="TW",
            )
        )
    finally:
        await client.aclose()

    request = route.calls.last.request
    assert dict(request.url.params) == {
        "name": "TV",
        "collectionType": "tvshows",
        "paths": "/data/library/tv",
        "refreshLibrary": "false",
    }
    options = json.loads(request.content)["LibraryOptions"]
    assert options["PathInfos"] == [{"Path": "/data/library/tv"}]
    # 票 06 驗收的三個選項。
    assert options["EnableRealtimeMonitor"] is False
    assert options["SeasonZeroDisplayName"] == "Specials"
    assert options["PreferredMetadataLanguage"] == "zh-TW"
    assert options["MetadataCountryCode"] == "TW"
    assert options["TypeOptions"] == [
        {
            "Type": "Series",
            "MetadataFetchers": ["TheMovieDb"],
            "MetadataFetcherOrder": ["TheMovieDb"],
            "ImageFetchers": ["TheMovieDb"],
            "ImageFetcherOrder": ["TheMovieDb"],
        }
    ]


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_add_library_path_never_refreshes() -> None:
    """既有媒體庫加一條路徑，不觸發掃描（plan §9.5）。"""
    route = respx.post(f"{JELLYFIN_URL}/Library/VirtualFolders/Paths").respond(204)

    client = jellyfin_client("key")
    try:
        await client.add_library_path("Films", "/data/library/films")
    finally:
        await client.aclose()

    request = route.calls.last.request
    assert dict(request.url.params) == {"refreshLibrary": "false"}
    assert json.loads(request.content) == {
        "Name": "Films",
        "Path": "/data/library/films",
        "PathInfo": {"Path": "/data/library/films"},
    }


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_api_keys_are_read_back_after_creating_one() -> None:
    """`POST /Auth/Keys` 回 204 而且不回傳 key，只能再列一次（brief §20.7）。"""
    created = respx.post(f"{JELLYFIN_URL}/Auth/Keys").respond(204)
    respx.get(f"{JELLYFIN_URL}/Auth/Keys").respond(
        200, text=read_fixture("http/jellyfin/auth-keys.berth.json")
    )

    client = jellyfin_client("key")
    try:
        await client.create_api_key("Berth")
        keys = await client.api_keys()
    finally:
        await client.aclose()

    assert dict(created.calls.last.request.url.params) == {"app": "Berth"}
    assert [key.app_name for key in keys] == ["Berth"]
    assert keys[0].access_token == "00000000000000000000000000000001"


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_authenticate_reports_the_administrator_flag() -> None:
    """票 07 的角色判定用同一個欄位（plan §11.1 T0.5）。"""
    route = respx.post(f"{JELLYFIN_URL}/Users/AuthenticateByName").respond(
        200, text=read_fixture("http/jellyfin/authenticate-by-name.json")
    )

    client = jellyfin_client()
    try:
        auth = await client.authenticate("skipper", "harbour-2026")
    finally:
        await client.aclose()

    assert json.loads(route.calls.last.request.content) == {
        "Username": "skipper",
        "Pw": "harbour-2026",
    }
    assert auth.token == "00000000000000000000000000000002"
    assert auth.is_administrator is True
    assert auth.user_id
    assert auth.server_id


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_merge_tasks_are_found_by_key_and_used_by_id() -> None:
    """觸發要用 `Id`，`Key` 只是找得到它的依據（brief §20.7）。"""
    respx.get(f"{JELLYFIN_URL}/ScheduledTasks").respond(
        200, text=read_fixture("http/jellyfin/scheduledtasks.merge-versions.json")
    )

    client = jellyfin_client("key")
    try:
        tasks = await client.scheduled_tasks()
    finally:
        await client.aclose()

    by_key = {task.key: task for task in tasks}
    assert by_key["MergeMoviesTask"].id == "fd957c84b0cfc2380becf2893e4b76fc"
    assert by_key["MergeEpisodesTask"].id == "dcaf151dd1af25aefe775c58e214477e"
    assert by_key["MergeMoviesTask"].name == "Merge All Movies"


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_repositories_round_trip() -> None:
    """`POST /Repositories` 是整份覆寫，所以要先讀再合併（plan §9.4 第 8 步）。

    這份是 Berth 加完之後錄的，所以它同時證明「重按不會加第二次」認得出自己加的那一筆。
    """
    respx.get(f"{JELLYFIN_URL}/Repositories").respond(
        200, text=read_fixture("http/jellyfin/repositories.with-merge-versions.json")
    )
    route = respx.post(f"{JELLYFIN_URL}/Repositories").respond(204)

    client = jellyfin_client("key")
    try:
        existing = await client.repositories()
        await client.set_repositories(existing)
    finally:
        await client.aclose()

    assert [repo.name for repo in existing] == ["Jellyfin Stable", "danieladov"]
    assert any(repo.url == MERGE_VERSIONS_REPOSITORY.url for repo in existing)
    assert json.loads(route.calls.last.request.content) == [
        {
            "Name": "Jellyfin Stable",
            "Url": "https://repo.jellyfin.org/files/plugin/manifest.json",
            "Enabled": True,
        },
        {"Name": "danieladov", "Url": MERGE_VERSIONS_REPOSITORY.url, "Enabled": True},
    ]


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_package_versions_read_the_manifest_casing() -> None:
    """`/Packages` 是 manifest 的原文轉發，鍵是 camelCase 而不是 Jellyfin 的 PascalCase。"""
    respx.get(f"{JELLYFIN_URL}/Packages").respond(
        200, text=read_fixture("http/jellyfin/packages.merge-versions.json")
    )

    client = jellyfin_client("key")
    try:
        versions = await client.package_versions("Merge Versions")
        missing = await client.package_versions("Nothing")
    finally:
        await client.aclose()

    assert versions[:2] == ("10.11.0.1", "10.10.0.5")
    assert missing == ()


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_plugin_ids_are_compared_without_hyphens() -> None:
    respx.get(f"{JELLYFIN_URL}/Plugins").respond(
        200, text=read_fixture("http/jellyfin/plugins.merge-versions-installed.json")
    )

    client = jellyfin_client("key")
    try:
        plugins = await client.plugins()
    finally:
        await client.aclose()

    by_id = {plugin.id: plugin for plugin in plugins}
    assert by_id["f21bbed83a974d8b88b248aaa65427cb"].name == "Merge Versions"
    assert by_id["f21bbed83a974d8b88b248aaa65427cb"].version == "10.11.0.1"


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_still_loading_is_not_a_failure() -> None:
    """重啟後管理員 API 有一段時間回 503；那是「還沒好」不是「壞了」（brief §20.7）。"""
    respx.get(f"{JELLYFIN_URL}/ScheduledTasks").respond(503, text="Jellyfin server is loading")

    client = jellyfin_client("key")
    with pytest.raises(ServiceBusyError):
        await client.scheduled_tasks()
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_token_travels_in_the_mediabrowser_header() -> None:
    """登入 token 與 API key 同一個標頭形狀（實測 10.11.11）。"""
    route = respx.get(f"{JELLYFIN_URL}/System/Info/Public").respond(
        200, text=read_fixture("http/jellyfin/system-info-public.setup-pending.json")
    )

    client = jellyfin_client()
    try:
        await client.public_info()
        anonymous = route.calls.last.request.headers["Authorization"]
        client.use_token("the-key")
        await client.public_info()
    finally:
        await client.aclose()

    assert 'Token="' not in anonymous
    assert 'Client="Berth"' in anonymous
    assert 'Token="the-key"' in route.calls.last.request.headers["Authorization"]
