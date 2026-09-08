"""三個 adapter 對 `tests/fixtures/http/` 錄製回應的契約測試（plan §1.3、票 05）。

錄製來源與日期見 `tests/fixtures/http/README.md`。這裡驗的是「真服務回這個，adapter 解成那個」，
所以斷言貼著錄下來的值，不重寫一份假的 payload。
"""

from __future__ import annotations

import json
import socket
import urllib.parse

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
from berth.adapters.prowlarr import (
    DEFAULT_APP_PROFILE_ID,
    IndexerDefinition,
    IndexerRejectedError,
    ProwlarrIndexer,
)
from berth.adapters.prowlarr.client import HttpProwlarrClient
from berth.adapters.qbittorrent.client import HttpQbittorrentClient
from berth.adapters.tmdb import PROJECT_CREDENTIAL
from berth.adapters.tmdb.client import HttpTmdbClient
from berth.adapters.torznab.client import HttpTorznabClient
from berth.domain import CollectionType
from berth.services.indexer import DEFAULT_INDEXERS
from berth.services.jellyfin import MERGE_VERSIONS_REPOSITORY
from tests.conftest import read_fixture

JELLYFIN_URL = "http://jellyfin:8096"
QBITTORRENT_URL = "http://qbittorrent:8080"
PROWLARR_URL = "http://prowlarr:9696"
TORZNAB_URL = "http://jackett:9117/api/v2.0/indexers/all/results/torznab/api"
#: 契約測試不打真的 TMDB；位址是真的那一個，回應是錄下來的那一份。
TMDB_URL = "https://api.themoviedb.org/3"


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


#: 兩組錄製回應：4.4.5（Web API 2.8.5，支援下限）與 5.2.3（2.15.1）。差異本身就是要守的東西。
QBITTORRENT_RELEASES = ("4.4.5", "5.2.3")


def mock_qbittorrent_version(release: str) -> None:
    respx.get(f"{QBITTORRENT_URL}/api/v2/app/version").respond(
        200, text=read_fixture(f"http/qbittorrent/app-version.{release}.txt")
    )
    respx.get(f"{QBITTORRENT_URL}/api/v2/app/webapiVersion").respond(
        200, text=read_fixture(f"http/qbittorrent/app-webapiversion.{release}.txt")
    )


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("release", "app", "webapi"),
    [("4.4.5", "v4.4.5", "2.8.5"), ("5.2.3", "v5.2.3", "2.15.1")],
)
async def test_qbittorrent_version_without_credentials(release: str, app: str, webapi: str) -> None:
    mock_qbittorrent_version(release)

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        version = await client.version()
    finally:
        await client.aclose()

    assert version.app == app
    assert version.webapi == webapi


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize(("release", "parameter"), [("4.4.5", "paused"), ("5.2.3", "stopped")])
async def test_qbittorrent_pause_parameter_follows_the_web_api_version(
    release: str, parameter: str
) -> None:
    """送錯的那個參數會被靜默忽略，torrent 就這樣開始下載（brief §20.7）。

    版本判斷因此是必要條件而不是最佳化，所以它綁在**錄下來的版本字串**上，不是手寫的常數。
    """
    mock_qbittorrent_version(release)

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        version = await client.version()
    finally:
        await client.aclose()

    assert version.pause_parameter == parameter
    assert version.supported is True


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize("release", QBITTORRENT_RELEASES)
async def test_qbittorrent_categories_accept_both_save_path_spellings(release: str) -> None:
    """兩個版本錄到的都是 `savePath`。`save_path` 只出現在 4.4.0–4.4.1，
    而那兩版仍在支援範圍內（plan §8.1）。
    """
    respx.get(f"{QBITTORRENT_URL}/api/v2/torrents/categories").respond(
        200, text=read_fixture(f"http/qbittorrent/torrents-categories.{release}.json")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        categories = await client.categories()
    finally:
        await client.aclose()

    assert [(row.name, row.save_path) for row in categories] == [
        ("berth-exp", "/downloads/berth-exp")
    ]


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_categories_read_the_snake_case_spelling() -> None:
    """4.4.0–4.4.1 回的是 `save_path`。錄不到那兩版（image 只發到 4.4.5），所以這一條手寫。"""
    respx.get(f"{QBITTORRENT_URL}/api/v2/torrents/categories").respond(
        200, json={"berth-tv": {"name": "berth-tv", "save_path": "/data/torrent/complete/tv"}}
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        categories = await client.categories()
    finally:
        await client.aclose()

    assert categories[0].save_path == "/data/torrent/complete/tv"


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("release", "save_path", "temp_path"),
    [
        ("4.4.5", "/downloads/", "/downloads/incomplete/"),
        ("5.2.3", "/downloads", "/downloads/incomplete"),
    ],
)
async def test_qbittorrent_preferences_keep_the_recorded_values(
    release: str, save_path: str, temp_path: str
) -> None:
    """`save_path` 的尾斜線兩版不同（4.4 有、5.x 沒有）——組路徑前要正規化（brief §20.7）。"""
    respx.get(f"{QBITTORRENT_URL}/api/v2/app/preferences").respond(
        200, text=read_fixture(f"http/qbittorrent/app-preferences.{release}.json")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        preferences = await client.preferences()
    finally:
        await client.aclose()

    assert preferences["save_path"] == save_path
    assert preferences["temp_path"] == temp_path
    # 新裝的實例這三個都是 false，所以精靈第 4 步要套用的差異確實存在（brief §20.7）。
    assert preferences["temp_path_enabled"] is False
    assert preferences["auto_tmm_enabled"] is False
    assert preferences["category_changed_tmm_enabled"] is False


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_set_preferences_posts_one_json_form_field() -> None:
    """`app/setPreferences` 收的是表單裡一個叫 `json` 的欄位，不是 JSON body。"""
    route = respx.post(f"{QBITTORRENT_URL}/api/v2/app/setPreferences").respond(200, text="")

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        await client.set_preferences({"temp_path_enabled": True, "save_path": "/data"})
    finally:
        await client.aclose()

    body = urllib.parse.parse_qs(route.calls.last.request.content.decode())
    assert json.loads(body["json"][0]) == {"temp_path_enabled": True, "save_path": "/data"}


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_create_category_posts_the_camel_case_form() -> None:
    """`torrents/createCategory` 收的是表單的 `category` 與 `savePath`（brief §20.2）。

    per-category 的未完成路徑不送：Berth 只用全域的 temp path（plan §4.2）。
    """
    route = respx.post(f"{QBITTORRENT_URL}/api/v2/torrents/createCategory").respond(200, text="")

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        await client.create_category("berth-tv", "/data/torrent/complete/tv")
    finally:
        await client.aclose()

    assert urllib.parse.parse_qs(route.calls.last.request.content.decode()) == {
        "category": ["berth-tv"],
        "savePath": ["/data/torrent/complete/tv"],
    }


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
async def test_jellyfin_validate_path_confirms_it_sees_the_probe() -> None:
    """跨服務可見性：Jellyfin 看得到 Berth 剛寫的那個檔案（plan §9.5 檢查三）。

    `POST /Environment/ValidatePath` 回 204 代表看得到（`EnvironmentController.ValidatePath`，
    `IsFile=true` 時走 `File.Exists`）。
    """
    route = respx.post(f"{JELLYFIN_URL}/Environment/ValidatePath").respond(204)

    client = jellyfin_client("key")
    try:
        seen = await client.validate_path("/data/library/tv/.berth-probe-1234abcd")
    finally:
        await client.aclose()

    assert seen is True
    assert json.loads(route.calls.last.request.content) == {
        "Path": "/data/library/tv/.berth-probe-1234abcd",
        "IsFile": True,
        "ValidateWritable": False,
    }


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_validate_path_answers_no_instead_of_failing() -> None:
    """看不到那條路徑時回 **404**，而那是這一步的答案，不是連線壞了。"""
    respx.post(f"{JELLYFIN_URL}/Environment/ValidatePath").respond(404, text="")

    client = jellyfin_client("key")
    try:
        seen = await client.validate_path("/data/library/tv/.berth-probe-1234abcd")
    finally:
        await client.aclose()

    assert seen is False


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


# --- 票 08：索引站與 TMDB（plan §8.3、§8.4）---------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_schema_carries_the_ten_default_indexers() -> None:
    """精靈第 5 步預設勾的十個公開站都要在這台 Prowlarr 的定義清單裡（plan §9.3 第 5 步）。

    釘的是 `definitionName`——站名 Prowlarr 自己會改（`Anidex` 與文件寫的 `AniDex`），
    機器名不會。
    """
    respx.get(f"{PROWLARR_URL}/api/v1/indexer/schema").respond(
        200, text=read_fixture("http/prowlarr/indexer-schema.defaults.json")
    )

    client = HttpProwlarrClient(PROWLARR_URL, "key")
    try:
        definitions = await client.definitions()
    finally:
        await client.aclose()

    assert [row.definition_name for row in definitions] == list(DEFAULT_INDEXERS)
    by_name = {row.definition_name: row for row in definitions}
    assert by_name["nyaasi"].name == "Nyaa.si"
    assert by_name["nyaasi"].privacy == "public"
    # Anime Tosho 是唯一不是 public 的那一個，勾選清單靠這個欄位標示出來。
    assert by_name["animetosho-xyz"].privacy == "semiPrivate"


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_add_indexer_sends_the_definition_with_a_real_app_profile() -> None:
    """schema 給的 `appProfileId` 是 0，原樣送回去會建不起來（2026-09-08 實測）。"""
    respx.get(f"{PROWLARR_URL}/api/v1/indexer/schema").respond(
        200, text=read_fixture("http/prowlarr/indexer-schema.defaults.json")
    )
    route = respx.post(f"{PROWLARR_URL}/api/v1/indexer").respond(
        201, text=read_fixture("http/prowlarr/indexer.created.dmhy.json")
    )

    client = HttpProwlarrClient(PROWLARR_URL, "key")
    try:
        definition = next(
            row for row in await client.definitions() if row.definition_name == "dmhy"
        )
        created = await client.add_indexer(definition)
    finally:
        await client.aclose()

    sent = json.loads(route.calls.last.request.content)
    assert sent["definitionName"] == "dmhy"
    assert sent["appProfileId"] == DEFAULT_APP_PROFILE_ID
    assert (created.id, created.name, created.enabled) == (6, "dmhy", True)
    assert created.definition_name == "dmhy"


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_rejects_an_indexer_it_cannot_reach() -> None:
    """**新增之前 Prowlarr 會先連一次那個站**，連不上就 400 而且什麼都不建立。

    錄下來的這一份是 nyaa.si 從本機連出去的真實結果（2026-09-08）。
    """
    respx.post(f"{PROWLARR_URL}/api/v1/indexer").respond(
        400, text=read_fixture("http/prowlarr/indexer.rejected.nyaasi.json")
    )

    client = HttpProwlarrClient(PROWLARR_URL, "key")
    with pytest.raises(IndexerRejectedError) as failure:
        await client.add_indexer(IndexerDefinition("nyaasi", "Nyaa.si", "public", {}))
    await client.aclose()

    assert failure.value.messages[0].startswith("Query successful, but no results were returned")


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_rejects_a_second_indexer_with_the_same_name() -> None:
    """同名的第二個站被拒（`Should be unique`），所以冪等要靠呼叫端先列（實測）。"""
    respx.post(f"{PROWLARR_URL}/api/v1/indexer").respond(
        400, text=read_fixture("http/prowlarr/indexer.rejected.duplicate.json")
    )

    client = HttpProwlarrClient(PROWLARR_URL, "key")
    with pytest.raises(IndexerRejectedError) as failure:
        await client.add_indexer(IndexerDefinition("dmhy", "dmhy", "public", {}))
    await client.aclose()

    assert failure.value.messages == ("Should be unique",)


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_lists_the_indexers_that_were_added() -> None:
    respx.get(f"{PROWLARR_URL}/api/v1/indexer").respond(
        200, text=read_fixture("http/prowlarr/indexer.defaults-added.json")
    )

    client = HttpProwlarrClient(PROWLARR_URL, "key")
    try:
        indexers = await client.indexers()
    finally:
        await client.aclose()

    assert {row.definition_name for row in indexers} == {
        "acgrip",
        "dmhy",
        "mikan",
        "thepiratebay",
        "yts",
    }
    assert all(row.enabled for row in indexers)
    # `payload` 留的是原文，因為 `indexer/test` 收的就是它。
    assert indexers[0].payload["fields"]


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_host_config_round_trips_the_whole_object() -> None:
    """設帳密要把整份 `config/host` 送回去，少了 `passwordConfirmation` 會被拒（brief §20.7）。"""
    respx.get(f"{PROWLARR_URL}/api/v1/config/host").respond(
        200, text=read_fixture("http/prowlarr/config-host.json")
    )
    route = respx.put(f"{PROWLARR_URL}/api/v1/config/host/1").respond(202, json={})

    client = HttpProwlarrClient(PROWLARR_URL, "key")
    try:
        config = await client.host_config()
        await client.set_host_config(
            {
                **config,
                "authenticationMethod": "forms",
                "username": "skipper",
                "password": "harbour",
                "passwordConfirmation": "harbour",
            }
        )
    finally:
        await client.aclose()

    assert "passwordConfirmation" in config
    sent = json.loads(route.calls.last.request.content)
    assert sent["username"] == "skipper"
    assert sent["passwordConfirmation"] == "harbour"
    # 整份物件送回去：Prowlarr 用它覆寫，少送的欄位會被清掉。
    assert len(sent) == len(config)


@respx.mock
@pytest.mark.asyncio
async def test_torznab_caps_prove_the_endpoint_answers_torznab() -> None:
    """`t=caps` 一次證明位址對、key 對、而且那一端真的是 Torznab（錄自 Prowlarr 的單站網址）。"""
    route = respx.get(TORZNAB_URL).respond(200, text=read_fixture("http/torznab/caps.xml"))

    client = HttpTorznabClient(TORZNAB_URL, "the-key")
    try:
        caps = await client.caps()
    finally:
        await client.aclose()

    assert caps.server_title == "Prowlarr"
    assert caps.search_available is True
    assert caps.categories == ("TV",)
    assert dict(route.calls.last.request.url.params) == {"t": "caps", "apikey": "the-key"}


@respx.mock
@pytest.mark.asyncio
async def test_torznab_rejects_a_page_that_is_not_caps() -> None:
    respx.get(TORZNAB_URL).respond(200, text="<html><body>Jackett</body></html>")

    client = HttpTorznabClient(TORZNAB_URL, "the-key")
    with pytest.raises(ProtocolMismatchError):
        await client.caps()
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_configuration_proves_the_credential_works() -> None:
    respx.get(f"{TMDB_URL}/configuration").respond(
        200, text=read_fixture("http/tmdb/configuration.json")
    )

    client = HttpTmdbClient(PROJECT_CREDENTIAL, base_url=TMDB_URL)
    try:
        configuration = await client.configuration()
    finally:
        await client.aclose()

    assert configuration.image_base_url == "https://image.tmdb.org/t/p/"


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_read_access_token_travels_as_a_bearer_header() -> None:
    """v4 的 read access token 走標頭，不進網址——它不會落在任何一行 log 裡。"""
    route = respx.get(f"{TMDB_URL}/configuration").respond(
        200, text=read_fixture("http/tmdb/configuration.json")
    )

    client = HttpTmdbClient(PROJECT_CREDENTIAL, base_url=TMDB_URL)
    try:
        await client.configuration()
    finally:
        await client.aclose()

    assert route.calls.last.request.headers["Authorization"] == f"Bearer {PROJECT_CREDENTIAL}"
    assert "api_key" not in route.calls.last.request.url.params


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_v3_api_key_travels_as_a_query_parameter() -> None:
    """使用者貼的多半是帳號頁上那把 32 字元的 v3 key，兩種形狀都要成立（2026-09-08 實測）。"""
    route = respx.get(f"{TMDB_URL}/configuration").respond(
        200, text=read_fixture("http/tmdb/configuration.json")
    )

    client = HttpTmdbClient("dc332023c119334763ec3b21bcdd1834", base_url=TMDB_URL)
    try:
        await client.configuration()
    finally:
        await client.aclose()

    assert "Authorization" not in route.calls.last.request.headers
    assert route.calls.last.request.url.params["api_key"] == "dc332023c119334763ec3b21bcdd1834"


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_rejects_an_invalid_key() -> None:
    respx.get(f"{TMDB_URL}/configuration").respond(
        401, text=read_fixture("http/tmdb/configuration.unauthorized.json")
    )

    client = HttpTmdbClient("0000000000000000000000000000dead", base_url=TMDB_URL)
    with pytest.raises(AuthFailedError):
        await client.configuration()
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_tests_an_indexer_that_is_already_there() -> None:
    """`indexer/test` 是給**已經存在**的站用的：實測回 200 加一個空物件（2026-09-08）。

    body 是整份資源原文，所以 adapter 把 `payload` 原樣留著。
    """
    route = respx.post(f"{PROWLARR_URL}/api/v1/indexer/test").respond(200, json={})
    saved = json.loads(read_fixture("http/prowlarr/indexer.created.dmhy.json"))

    client = HttpProwlarrClient(PROWLARR_URL, "key")
    try:
        await client.test_indexer(
            ProwlarrIndexer(id=saved["id"], name=saved["name"], enabled=True, payload=saved)
        )
    finally:
        await client.aclose()

    assert json.loads(route.calls.last.request.content)["definitionName"] == "dmhy"


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_reports_a_site_that_stopped_working() -> None:
    respx.post(f"{PROWLARR_URL}/api/v1/indexer/test").respond(
        400, text=read_fixture("http/prowlarr/indexer.rejected.nyaasi.json")
    )

    client = HttpProwlarrClient(PROWLARR_URL, "key")
    with pytest.raises(IndexerRejectedError):
        await client.test_indexer(ProwlarrIndexer(id=1, name="Nyaa.si", enabled=True))
    await client.aclose()
