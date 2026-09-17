"""三個 adapter 對 `tests/fixtures/http/` 錄製回應的契約測試（plan §1.3、票 05）。

錄製來源與日期見 `tests/fixtures/http/README.md`。這裡驗的是「真服務回這個，adapter 解成那個」，
所以斷言貼著錄下來的值，不重寫一份假的 payload。
"""

from __future__ import annotations

import json
import socket
import urllib.parse
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any
from urllib.parse import parse_qsl

import httpx
import pytest
import respx

from berth.adapters.http import (
    DEFAULT_TIMEOUT_SECONDS,
    AuthFailedError,
    NotFoundError,
    ProtocolMismatchError,
    ServiceBusyError,
    ServiceNotDeployedError,
    ServiceUnavailableError,
)
from berth.adapters.jellyfin import LIBRARY_SCAN_TASK_KEY, NewLibrary, TypeOption
from berth.adapters.jellyfin.client import HttpJellyfinClient
from berth.adapters.prowlarr import (
    DEFAULT_APP_PROFILE_ID,
    IndexerDefinition,
    IndexerRejectedError,
    ProwlarrIndexer,
)
from berth.adapters.prowlarr.client import SCHEMA_TIMEOUT_SECONDS, HttpProwlarrClient
from berth.adapters.qbittorrent import (
    BERTH_TAG,
    IpBannedError,
    TorrentAdd,
    TorrentRejectedError,
)
from berth.adapters.qbittorrent.client import HttpQbittorrentClient
from berth.adapters.rate import TokenBucket
from berth.adapters.tmdb import TmdbEntry, parse_absolute_ordering
from berth.adapters.tmdb.client import RATE_PER_SECOND, HttpTmdbClient
from berth.adapters.torznab.client import HttpTorznabClient
from berth.domain import CollectionType, MediaKind, SortOrder
from berth.services.indexer import DEFAULT_INDEXERS
from tests.conftest import read_fixture

JELLYFIN_URL = "http://jellyfin:8096"
QBITTORRENT_URL = "http://qbittorrent:8080"
PROWLARR_URL = "http://prowlarr:9696"
TORZNAB_URL = "http://jackett:9117/api/v2.0/indexers/all/results/torznab/api"
#: 契約測試不打真的 TMDB；位址是真的那一個，回應是錄下來的那一份。
TMDB_URL = "https://api.themoviedb.org/3"
#: v4 read access token 的**形狀**（三段 JWT）。憑證由使用者自備（票 02b），repo 裡不留真的那一把。
V4_READ_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJiZXJ0aC10ZXN0Iiwic2NvcGVzIjpbXX0.not-a-signature"
#: v3 API key 的形狀（32 個十六進位字元）。**這一行曾經是一把真的 key**——票 08 把它當成
#: 「同形狀的假值」寫進來，而 repo 是公開的（票 03 收尾轉 public），所以它從那天起就對外可讀。
#: 秘密一律用 `0000…000n` 這種同形狀的假值，每個服務一個號碼（`tests/fixtures/http/README.md`）。
V3_API_KEY = "00000000000000000000000000000003"
#: 送單演練用的磁力連結。hash 是形狀對的假值（40 個十六進位字元）。
MAGNET = "magnet:?xt=urn:btih:4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b&dn=Berth.Test"


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
    # 這份是對真的 10.11.11 錄的，所以它同時證明版本閘門擋得住真實的舊伺服器（brief §16.4）。
    assert info.supported is False


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
@pytest.mark.parametrize(
    ("release", "fixture"),
    [
        ("4.4.5", "torrents-add.accepted.4.4.5.txt"),
        ("5.2.3", "torrents-add.accepted.5.2.3.json"),
    ],
)
async def test_qbittorrent_accepts_a_torrent_in_both_response_shapes(
    release: str, fixture: str
) -> None:
    """**成功的形狀隨版本不同**（2026-09-10 對真的 5.2.3 實測）：4.4.x 回 `Ok.`，
    5.2.3 回一份 JSON 摘要。只認 `Ok.` 的話每一次送單在 5.x 上都會被判成失敗。
    """
    mock_qbittorrent_version(release)
    route = respx.post(f"{QBITTORRENT_URL}/api/v2/torrents/add").respond(
        200, text=read_fixture(f"http/qbittorrent/{fixture}")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        await client.add_torrent(TorrentAdd(category="berth-anime", magnet=MAGNET))
    finally:
        await client.aclose()

    sent = dict(parse_qsl(route.calls.last.request.content.decode()))
    assert sent["category"] == "berth-anime"
    assert sent["tags"] == BERTH_TAG
    assert sent["contentLayout"] == "Original"
    assert sent["autoTMM"] == "true"
    assert sent["urls"] == MAGNET
    # 版本閘門：4.4.x 只認得 `paused`，5.x 只認得 `stopped`（brief §20.7）。
    assert sent["paused" if release == "4.4.5" else "stopped"] == "false"


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_pending_url_fetch_is_not_success() -> None:
    """`202` + `pending_count: 1` 是「網址收下了，之後再去抓」——而那條路徑的失敗
    永遠不會回來（brief §20.7）。Berth 自己先抓 torrent 就是為了不走它，所以真的收到
    這個形狀時要當成失敗，而不是默默把 Job 標成已送出。
    """
    mock_qbittorrent_version("5.2.3")
    respx.post(f"{QBITTORRENT_URL}/api/v2/torrents/add").respond(
        202, text=read_fixture("http/qbittorrent/torrents-add.pending.5.2.3.json")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        with pytest.raises(TorrentRejectedError, match="202"):
            await client.add_torrent(TorrentAdd(category="berth-anime", magnet=MAGNET))
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_conflict_says_what_the_status_code_means() -> None:
    """body 只有一個 `Conflict`，而它有兩種成因（2026-09-10 實測：已經有同一個 hash，
    或 category 的 save path 用不了）。畫面上那一行要說得出下一步（PRODUCT 原則 4）。
    """
    mock_qbittorrent_version("5.2.3")
    respx.post(f"{QBITTORRENT_URL}/api/v2/torrents/add").respond(
        409, text=read_fixture("http/qbittorrent/torrents-add.conflict.5.2.3.txt")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        with pytest.raises(TorrentRejectedError) as refusal:
            await client.add_torrent(TorrentAdd(category="berth-anime", magnet=MAGNET))
    finally:
        await client.aclose()

    assert "409" in str(refusal.value)
    assert "already has this torrent" in str(refusal.value)


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_rejecting_an_invalid_torrent_file_keeps_its_own_words() -> None:
    mock_qbittorrent_version("5.2.3")
    respx.post(f"{QBITTORRENT_URL}/api/v2/torrents/add").respond(
        415, text=read_fixture("http/qbittorrent/torrents-add.invalid.5.2.3.txt")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        with pytest.raises(TorrentRejectedError, match="not a valid torrent file"):
            await client.add_torrent(
                TorrentAdd(category="berth-anime", content=b"<!doctype html>", filename="x.torrent")
            )
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_uploads_a_torrent_file_as_multipart() -> None:
    """`.torrent` 走 multipart 的 `torrents` 欄位，磁力連結走表單的 `urls`——
    兩種在 `torrents/add` 上不是同一個東西。"""
    mock_qbittorrent_version("5.2.3")
    route = respx.post(f"{QBITTORRENT_URL}/api/v2/torrents/add").respond(
        200, text=read_fixture("http/qbittorrent/torrents-add.accepted.5.2.3.json")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        await client.add_torrent(
            TorrentAdd(
                category="berth-tv", content=b"d4:infod4:name5:berthee", filename="a.torrent"
            )
        )
    finally:
        await client.aclose()

    body = route.calls.last.request.content
    assert b'name="torrents"; filename="a.torrent"' in body
    assert b"d4:infod4:name5:berthee" in body
    assert b'name="urls"' not in body


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
async def test_qbittorrent_44_login_succeeds_with_the_ok_body() -> None:
    respx.post(f"{QBITTORRENT_URL}/api/v2/auth/login").respond(
        200, text=read_fixture("http/qbittorrent/auth-login.ok.4.4.5.txt")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        await client.login("admin", "adminadmin")
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_44_reports_wrong_credentials_as_a_200() -> None:
    """4.4 的失敗是 `200` + `Fails.`——狀態碼騙人，只有 body 說得出真話。"""
    respx.post(f"{QBITTORRENT_URL}/api/v2/auth/login").respond(
        200, text=read_fixture("http/qbittorrent/auth-login.fails.4.4.5.txt")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    with pytest.raises(AuthFailedError):
        await client.login("admin", "wrongwrong")
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_5x_login_succeeds_with_an_empty_204() -> None:
    """5.x 成功回 `204` 空 body，不是 4.4 的 `Ok.`（2026-09-08 對 5.2.3 實測）。

    免密白名單上的 client 也走這一條：那正是套件內的 Berth，它不需要帳密就進得去。
    把「不是 Ok.」當成失敗會讓每一套預設部署的健康檢查永遠紅著。
    """
    respx.post(f"{QBITTORRENT_URL}/api/v2/auth/login").respond(204)

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        await client.login("skipper", "harbour")
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_5x_reports_wrong_credentials_as_a_401() -> None:
    respx.post(f"{QBITTORRENT_URL}/api/v2/auth/login").respond(
        401, text=read_fixture("http/qbittorrent/auth-login.unauthorized.5.2.3.txt")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    with pytest.raises(AuthFailedError):
        await client.login("skipper", "wrongwrong")
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_login_rejects_a_reply_from_something_else() -> None:
    """「不是 `Fails.` 就是成功」會把反向代理的登入頁當成登入成功。

    位址填錯打到別的服務時，那一台很可能回 `200` 加一頁 HTML。空 body（5.x）與 `Ok.`（4.4）
    是**僅有**的兩種成功形狀，其餘的 2xx 是連到了別的東西。
    """
    respx.post(f"{QBITTORRENT_URL}/api/v2/auth/login").respond(
        200, text="<!doctype html><title>Sign in</title>"
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    with pytest.raises(ProtocolMismatchError):
        await client.login("skipper", "harbour")
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


@pytest.mark.parametrize("release", ["4.4.5", "5.2.3"])
@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_maindata_reads_the_recorded_snapshot(release: str) -> None:
    """`sync/maindata?rid=0` 的整份：三個 torrent，三種處境（2026-09-10 對兩版各錄一輪）。

    釘的是**完成判定**（brief §5.1、§20.2）：只有做種中的那一個是完成的，`metaDL` 與
    `stalledDL` 都不是。兩版都測是因為它們對「還沒完成」的 `completion_on` 講法不同——
    4.4.5 寫 `0`、5.2.3 寫 `-1`，寫成 `!= 0` 的判定會讓 5.x 上每一個剛加入的 torrent
    都被當成已完成。
    """
    respx.get(f"{QBITTORRENT_URL}/api/v2/sync/maindata", params={"rid": "0"}).respond(
        200, text=read_fixture(f"http/qbittorrent/sync-maindata.full.{release}.json")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        rows = await client.sync()
    finally:
        await client.aclose()

    assert len(rows) == 3
    complete = [row for row in rows if row.complete]
    assert [row.state for row in complete] == ["stalledUP"]
    assert complete[0].save_path == "/downloads/berth-exp"
    assert complete[0].content_path.endswith("/Berth.Poller.Test.S01.1080p.WEB-DL")
    assert complete[0].category == "berth-exp"
    assert complete[0].tags == (BERTH_TAG,)
    assert complete[0].total_size == 40120
    # 還沒完成的那幾筆 `completion_on` 兩版寫法不同（0 與 -1），但 `> 0` 對兩邊都成立。
    assert all(row.completion_on <= 0 for row in rows if not row.complete)


@pytest.mark.parametrize("release", ["4.4.5", "5.2.3"])
@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_maindata_merges_the_incremental_round(release: str) -> None:
    """增量那一輪**只帶變動的欄位**——不合併的話整份清單會塌成一堆空殼。

    實測 5.2.3 的一輪裡某個 torrent 只有 `{"num_leechs", "time_active"}`：沒有 state、
    沒有 category、沒有 name。照字面讀它會讓那一筆的 category 變成空字串，於是 poller
    當場把使用者自己的 torrent 與 Berth 的混在一起（或反過來，把自己的判成無主）。
    """
    respx.get(f"{QBITTORRENT_URL}/api/v2/sync/maindata", params={"rid": "0"}).respond(
        200, text=read_fixture(f"http/qbittorrent/sync-maindata.full.{release}.json")
    )
    respx.get(f"{QBITTORRENT_URL}/api/v2/sync/maindata", params={"rid": "1"}).respond(
        200, text=read_fixture(f"http/qbittorrent/sync-maindata.partial.{release}.json")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        first = await client.sync()
        second = await client.sync()
    finally:
        await client.aclose()

    # 增量那一輪多了一筆（腳本在兩輪之間又加了一個磁力連結）。
    assert len(second) == len(first) + 1
    assert all(row.category == "berth-exp" for row in second)
    assert all(row.state for row in second)
    # 原本就在的那幾筆保留了整份欄位，只有變動的被蓋掉。
    before = {row.hash: row for row in first}
    kept = [row for row in second if row.hash in before]
    assert kept and all(row.name == before[row.hash].name for row in kept)


@pytest.mark.parametrize("release", ["4.4.5", "5.2.3"])
@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_maindata_drops_what_the_client_removed(release: str) -> None:
    """`torrents_removed` 之後那一筆就不在清單裡了——`client_removed` 讀的就是這件事。"""
    for rid, name in ((0, "full"), (1, "partial"), (2, "removed")):
        respx.get(f"{QBITTORRENT_URL}/api/v2/sync/maindata", params={"rid": str(rid)}).respond(
            200, text=read_fixture(f"http/qbittorrent/sync-maindata.{name}.{release}.json")
        )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        await client.sync()
        after_add = {row.hash for row in await client.sync()}
        after_remove = {row.hash for row in await client.sync()}
    finally:
        await client.aclose()

    assert len(after_add - after_remove) == 1
    assert len(after_remove) == 3


@pytest.mark.parametrize("release", ["4.4.5", "5.2.3"])
@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_files_are_relative_to_the_save_path(release: str) -> None:
    """`torrents/files[].name` 含 torrent 自己的根目錄，且相對 `save_path`（brief §20.7）。

    `job_files.rel_path` 存的就是這一串，而 importer 之後拿 `save_path` 接回絕對路徑。
    """
    info_hash = "476f86e6c64ce252c09c4da40bcfee609ea827c7"
    respx.get(f"{QBITTORRENT_URL}/api/v2/torrents/files", params={"hash": info_hash}).respond(
        200, text=read_fixture(f"http/qbittorrent/torrents-files.multi.{release}.json")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        rows = await client.files(info_hash)
    finally:
        await client.aclose()

    assert [row.name for row in rows] == [
        "Berth.Poller.Test.S01.1080p.WEB-DL/Berth.Poller.Test.S01E01.1080p.WEB-DL.mkv",
        "Berth.Poller.Test.S01.1080p.WEB-DL/Subs/Berth.Poller.Test.S01E01.zh-Hant.srt",
    ]
    assert [row.size for row in rows] == [40000, 120]
    assert all(row.wanted for row in rows)


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_files_are_empty_while_metadata_is_pending() -> None:
    """`metaDL` 期間它回 `200` + `[]`，不是錯誤（實測兩版皆然）。"""
    respx.get(f"{QBITTORRENT_URL}/api/v2/torrents/files", params={"hash": "abc"}).respond(
        200, text="[]"
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        assert await client.files("abc") == ()
    finally:
        await client.aclose()


@pytest.mark.parametrize("release", ["4.4.5", "5.2.3"])
@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_tells_an_ip_ban_apart_from_wrong_credentials(release: str) -> None:
    """被封的 403 與帳密不對是兩件事（plan §8.1、T1.9 第四條）。

    2026-09-10 對兩版各實測一輪：連續 5 次帳密錯之後第 6 次回 `403` + 一句明說被封的話。
    帳密錯本身**不是** 403（4.4.5 是 200 + `Fails.`，5.2.3 是 401），所以登入端點上的
    403 只有這一個意思——而在這一票之前它被顯示成「帳密不對」，使用者會去改一組本來
    就對的密碼，再失敗五次，把封鎖時間重新算一輪。
    """
    respx.post(f"{QBITTORRENT_URL}/api/v2/auth/login").respond(
        403, text=read_fixture(f"http/qbittorrent/auth-login.banned.{release}.txt")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        with pytest.raises(IpBannedError) as banned:
            await client.login("admin", "adminadmin")
    finally:
        await client.aclose()

    # 原文照抄進訊息：使用者要看得出「這不是我打錯密碼」。
    assert "banned" in str(banned.value)
    # 仍然是 `AuthFailedError`：對「現在連不連得上」這個問題兩者的答案一樣。
    assert isinstance(banned.value, AuthFailedError)


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_ban_is_indistinguishable_on_other_endpoints() -> None:
    """被封之後 `app/version` 回的是 `403 Forbidden`——與「沒登入」一模一樣（實測）。

    所以判定只放在登入那一支。這一條釘的是**不要在別的端點上猜**：把每個 403 都說成
    「被封了」會讓真的沒登入的人收到一句與他無關的話。
    """
    respx.get(f"{QBITTORRENT_URL}/api/v2/app/version").respond(
        403, text=read_fixture("http/qbittorrent/app-version.banned.4.4.5.txt")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        with pytest.raises(AuthFailedError) as failure:
            await client.version()
    finally:
        await client.aclose()

    assert not isinstance(failure.value, IpBannedError)


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
async def test_jellyfin_runs_a_task_by_its_id() -> None:
    """排程任務用 `Id` 觸發，不是 `Key`（brief §20.7）。反查的後備靠它（brief §20.1）。"""
    route = respx.post(
        f"{JELLYFIN_URL}/ScheduledTasks/Running/dcaf151dd1af25aefe775c58e214477e"
    ).respond(204)

    client = jellyfin_client("key")
    try:
        await client.run_task("dcaf151dd1af25aefe775c58e214477e")
    finally:
        await client.aclose()

    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_items_are_asked_of_the_library_with_the_three_fields() -> None:
    """反查的兩段查詢都以媒體庫為 parent（brief §20.1）；fixture 是 12.0.0 入庫之後的原文。"""
    route = respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture("http/jellyfin/items.tv.episodes.json")
    )

    client = jellyfin_client("key")
    try:
        episodes = await client.items("4514ec850e5ad0c47b58444e17b6346c", ("Episode",))
    finally:
        await client.aclose()

    params = route.calls.last.request.url.params
    assert params["parentId"] == "4514ec850e5ad0c47b58444e17b6346c"
    assert params["recursive"] == "true"
    assert params["includeItemTypes"] == "Episode"
    assert set(params["fields"].split(",")) == {"Path", "ProviderIds", "MediaSources"}
    first = episodes[0]
    assert first.type == "Episode"
    assert first.path.endswith(
        "Season 03/The Bear (2022) - S03E01 - Tomorrow [WEB][1080p][SuccessfulCrab].mkv"
    )
    # 單一版本時，唯一的那個來源就是自己的 `Path`；多版本合併之後才會多出別的（brief §7.7）。
    assert first.source_paths == (first.path,)
    # 版本選單上的名字由 Jellyfin 算（票 14b）：單一版本時它就是整個檔名主幹。
    assert first.version_name(first.path) == (
        "The Bear (2022) - S03E01 - Tomorrow [WEB][1080p][SuccessfulCrab]"
    )


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_series_are_folders_with_a_tmdb_id_and_no_sources() -> None:
    respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture("http/jellyfin/items.tv.series.json")
    )

    client = jellyfin_client("key")
    try:
        (series,) = await client.items("4514ec850e5ad0c47b58444e17b6346c", ("Series",))
    finally:
        await client.aclose()

    assert series.type == "Series"
    assert series.path == "/data/library/tv/The Bear (2022) [tmdbid-136315]"
    assert series.tmdb_id == "136315"
    assert series.source_paths == ()


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_a_movie_is_its_own_file() -> None:
    """電影一段查詢就夠：它的檔案就是 item 自己（`services/resolver.py`）。"""
    respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture("http/jellyfin/items.movies.movie.json")
    )

    client = jellyfin_client("key")
    try:
        (movie,) = await client.items("f137a2dd21bbc1b99aa5c0f6bf02a805", ("Movie",))
    finally:
        await client.aclose()

    assert movie.tmdb_id == "872585"
    assert movie.path.endswith("Oppenheimer (2023) [tmdbid-872585] - [BD][1080p][YTS.MX].mp4")
    assert movie.path in movie.source_paths
    assert movie.version_name(movie.path) == (
        "Oppenheimer (2023) [tmdbid-872585] - [BD][1080p][YTS.MX]"
    )


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_items_without_an_items_array_is_not_jellyfin() -> None:
    respx.get(f"{JELLYFIN_URL}/Items").respond(200, json=[])

    client = jellyfin_client("key")
    try:
        with pytest.raises(ProtocolMismatchError):
            await client.items("library", ("Series",))
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_lists_its_own_library_scan_task() -> None:
    """「重新掃描媒體庫」是內建任務，`Key` 是 `RefreshLibrary`（反查的後備，brief §20.1）。"""
    respx.get(f"{JELLYFIN_URL}/ScheduledTasks").respond(
        200, text=read_fixture("http/jellyfin/scheduledtasks.merge-versions.json")
    )

    client = jellyfin_client("key")
    try:
        tasks = await client.scheduled_tasks()
    finally:
        await client.aclose()

    assert LIBRARY_SCAN_TASK_KEY in {task.key for task in tasks}


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_is_told_about_each_new_path_not_asked_to_rescan_everything() -> None:
    """路徑級的通知（brief §20.1）：一條路徑一個 `Created`，不是 `POST /Library/Refresh`。"""
    route = respx.post(f"{JELLYFIN_URL}/Library/Media/Updated").respond(204)
    episode = "/data/library/tv/Show (2024) [tmdbid-1]/Season 01/Show (2024) S01E0{}.mkv"

    client = jellyfin_client("key")
    try:
        await client.notify_paths([episode.format(1), episode.format(2)])
    finally:
        await client.aclose()

    assert json.loads(route.calls.last.request.content) == {
        "Updates": [
            {"Path": episode.format(1), "UpdateType": "Created"},
            {"Path": episode.format(2), "UpdateType": "Created"},
        ]
    }


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


# --- M1.5 票 03：替某一位使用者瀏覽媒體庫（研究 library-browsing.md §2、§3.1、§7）---------
#
# fixture 是 12.1.0 上以**只開放 TV 與 Movies 的使用者**錄的（M1.5 票 01、03，fixture README）。
# `/Items` 靜默忽略打錯的參數（brief §20.8），所以每個過濾參數要兩件事一起成立：adapter 送出去的
# 參數名與錄製那一次一字不差，而錄下來的回應看得出伺服器真的照它過濾了。

#: 受限使用者與兩個媒體庫的 id（`userviews.restricted.json`、`users.restricted.json`）。
RESTRICTED_USER = "c7c3e8c2d6d443b38cac62383fbd5716"
TV_LIBRARY = "4514ec850e5ad0c47b58444e17b6346c"
MOVIES_LIBRARY = "f137a2dd21bbc1b99aa5c0f6bf02a805"
#: 同一個 TMDB id 在他沒有權限的 Anime 裡也有一份（研究 §0）；那一份的 id 不在任何回應裡。
FORBIDDEN_FRIEREN = "8836e6e2b1400442080287739a22c85d"


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_user_views_are_the_libraries_this_user_may_open() -> None:
    route = respx.get(f"{JELLYFIN_URL}/UserViews").respond(
        200, text=read_fixture("http/jellyfin/userviews.restricted.json")
    )

    client = jellyfin_client("key")
    try:
        views = await client.user_views(RESTRICTED_USER)
    finally:
        await client.aclose()

    assert dict(route.calls.last.request.url.params) == {"userId": RESTRICTED_USER}
    # Anime 不在：這一份就是權限的權威清單（研究 §2 第 1 列）。
    assert [(view.id, view.name, view.collection_type) for view in views] == [
        (MOVIES_LIBRARY, "Movies", "movies"),
        (TV_LIBRARY, "TV", "tvshows"),
    ]


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fixture", "disabled"),
    [("users.restricted.json", False), ("users.restricted.disabled.json", True)],
)
async def test_jellyfin_policy_says_whether_the_account_is_disabled(
    fixture: str, disabled: bool
) -> None:
    """停用之後 API key 代讀照常回資料（研究 §2），「停用」只讀得出這裡。"""
    route = respx.get(f"{JELLYFIN_URL}/Users/{RESTRICTED_USER}").respond(
        200, text=read_fixture(f"http/jellyfin/{fixture}")
    )

    client = jellyfin_client("key")
    try:
        policy = await client.user_policy(RESTRICTED_USER)
    finally:
        await client.aclose()

    assert route.called
    assert policy.is_disabled is disabled


#: `items.tv.series.userdata.json` 錄製時的查詢（jellyfin-web 劇集庫的參數，研究 §7），
#: 扣掉分頁那兩格。
WALL_QUERY = {
    "userId": RESTRICTED_USER,
    "parentId": TV_LIBRARY,
    "recursive": "true",
    "includeItemTypes": "Series",
    "sortBy": "SortName",
    "sortOrder": "Ascending",
    "fields": "PrimaryImageAspectRatio,ProviderIds,Path",
    "imageTypeLimit": "1",
    "enableImageTypes": "Primary,Backdrop,Thumb",
}


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_a_library_page_is_filtered_by_the_server() -> None:
    route = respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture("http/jellyfin/items.tv.series.userdata.json")
    )

    client = jellyfin_client("key")
    try:
        page = await client.library_page(
            user_id=RESTRICTED_USER,
            library_id=TV_LIBRARY,
            item_type="Series",
            start=0,
            limit=100,
            sort_by=("SortName",),
            sort_order=SortOrder.ASCENDING,
            genres=(),
            years=(),
        )
    finally:
        await client.aclose()

    assert dict(route.calls.last.request.url.params) == {
        **WALL_QUERY,
        "startIndex": "0",
        "limit": "100",
    }
    # `includeItemTypes`：沒有它時同一位使用者拿回 24 筆，含季、集與電影（研究 §3.1）。
    assert {item.type for item in page.items} == {"Series"}
    # `parentId`：只有 TV 的作品，沒有 Movies 的電影，也沒有 Anime 那一份 Frieren。
    assert all(item.path.startswith("/media/tv/") for item in page.items)
    assert FORBIDDEN_FRIEREN not in {item.id for item in page.items}
    # `sortBy=SortName`：不帶它時（`items.tv.series.index.json`）Jellyfin 回的也是這個順序，
    # 所以這份錄製證明不了它有作用——而結果一樣，也就不必證明。別的排序鍵是票 06 的事，
    # 研究 §3.1 已逐一驗過。
    assert [item.name for item in page.items] == [
        "Alpha Show",
        "Bravo Show",
        "Frieren",
        "Hotel Show",
    ]
    assert page.total == 4
    alpha = page.items[0]
    assert (alpha.id, alpha.year, alpha.tmdb_id) == (
        "2a9857e656bbd18b7c3c3a3b4ee5eef1",
        2022,
        "1399",
    )
    # 沒有 TMDB id 的作品照樣在牆上，只是連不到 Berth 的詳情頁（票 03）。
    assert page.items[3].tmdb_id == ""


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_a_later_page_is_a_slice_of_the_whole_library() -> None:
    """`startIndex` / `limit`：第二頁恰好是整份排序結果的第 2、3 部，總數仍是整份的
    （票 03 錄製）。"""
    route = respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture("http/jellyfin/items.tv.series.page.json")
    )
    whole = json.loads(read_fixture("http/jellyfin/items.tv.series.userdata.json"))

    client = jellyfin_client("key")
    try:
        page = await client.library_page(
            user_id=RESTRICTED_USER,
            library_id=TV_LIBRARY,
            item_type="Series",
            start=1,
            limit=2,
            sort_by=("SortName",),
            sort_order=SortOrder.ASCENDING,
            genres=(),
            years=(),
        )
    finally:
        await client.aclose()

    assert dict(route.calls.last.request.url.params) == {
        **WALL_QUERY,
        "startIndex": "1",
        "limit": "2",
    }
    assert [item.id for item in page.items] == [row["Id"] for row in whole["Items"][1:3]]
    assert page.total == whole["TotalRecordCount"] == 4


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_the_index_of_a_library_is_every_title_with_only_its_poster_tag() -> None:
    """Berth 端比對用的整份清單：不分頁、不要觀看紀錄，圖只要 Primary 的 tag
    （票 04：篩選後的牆從這一份畫海報），仍然由伺服器照媒體庫與型別過濾。"""
    route = respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture("http/jellyfin/items.tv.series.index.json")
    )

    client = jellyfin_client("key")
    try:
        titles = await client.library_index(
            user_id=RESTRICTED_USER, library_id=TV_LIBRARY, item_type="Series"
        )
    finally:
        await client.aclose()

    assert dict(route.calls.last.request.url.params) == {
        "userId": RESTRICTED_USER,
        "parentId": TV_LIBRARY,
        "recursive": "true",
        "includeItemTypes": "Series",
        "fields": "ProviderIds",
        "imageTypeLimit": "1",
        "enableImageTypes": "Primary",
        "enableUserData": "false",
        "enableTotalRecordCount": "false",
    }
    assert {item.type for item in titles} == {"Series"}
    assert FORBIDDEN_FRIEREN not in {item.id for item in titles}
    # `enableUserData=false`：同一個媒體庫的牆那一份每一部都帶，這一份一部都沒有。
    rows = json.loads(read_fixture("http/jellyfin/items.tv.series.index.json"))["Items"]
    wall = json.loads(read_fixture("http/jellyfin/items.tv.series.userdata.json"))["Items"]
    assert all("UserData" in row for row in wall)
    assert not any("UserData" in row for row in rows)
    # tag 由圖的修改時間算出來，這一份是另一輪容器錄的，所以與牆那一份的值不同（fixture README）。
    assert [(item.name, item.tmdb_id, item.primary_tag) for item in titles] == [
        ("Alpha Show", "1399", "a559a2354a1a4a612c48440de5e621f6"),
        ("Bravo Show", "1396", "6db82abaab2067a1956415b245cfe1e8"),
        ("Frieren", "209867", "4b6e43fff7571a7f1e1604ce6fd214fc"),
        ("Hotel Show", "", "7b1ed5c62143ecfd6b20a6371a27dab0"),
    ]


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_a_page_without_an_items_array_is_not_jellyfin() -> None:
    respx.get(f"{JELLYFIN_URL}/Items").respond(200, json={"Nothing": []})

    client = jellyfin_client("key")
    try:
        with pytest.raises(ProtocolMismatchError):
            await client.library_page(
                user_id=RESTRICTED_USER,
                library_id=TV_LIBRARY,
                item_type="Series",
                start=0,
                limit=1,
                sort_by=("SortName",),
                sort_order=SortOrder.ASCENDING,
                genres=(),
                years=(),
            )
    finally:
        await client.aclose()


# --- M1.5 票 06：牆的排序與類型、年份篩選（研究 library-browsing.md §3）----------------
#
# 每一份錄製都是牆的查詢加上被測的那一個參數（fixture README，票 06 加錄）。判準與票 01 相同：
# 結果照那個值排或篩，**而且與名稱順序的那一份（`items.tv.series.userdata.json`）不同**——同一份
# 結果證明不了伺服器沒有把參數當成打錯字忽略掉。

#: 名稱順序的那一份牆（沒有排序、沒有篩選）。
NAME_ORDER = ["Alpha Show", "Bravo Show", "Frieren", "Hotel Show"]


def recorded_rows(fixture: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(read_fixture(f"http/jellyfin/{fixture}"))["Items"]
    return rows


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("order", "fixture", "expected"),
    [
        # 沒有評分的排在升冪最前、降冪最後（研究 §3.1）。
        (
            SortOrder.ASCENDING,
            "items.tv.series.sort-rating.ascending.json",
            ["Hotel Show", "Alpha Show", "Frieren", "Bravo Show"],
        ),
        (
            SortOrder.DESCENDING,
            "items.tv.series.sort-rating.descending.json",
            ["Bravo Show", "Frieren", "Alpha Show", "Hotel Show"],
        ),
    ],
)
async def test_jellyfin_the_wall_is_sorted_by_the_server(
    order: SortOrder, fixture: str, expected: list[str]
) -> None:
    """`sortBy` 與 `sortOrder`：兩份錄製只差 `sortOrder`，順序互為反序，也都不是名稱順序。"""
    route = respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture(f"http/jellyfin/{fixture}")
    )

    client = jellyfin_client("key")
    try:
        page = await client.library_page(
            user_id=RESTRICTED_USER,
            library_id=TV_LIBRARY,
            item_type="Series",
            start=0,
            limit=100,
            sort_by=("CommunityRating", "SortName"),
            sort_order=order,
            genres=(),
            years=(),
        )
    finally:
        await client.aclose()

    assert dict(route.calls.last.request.url.params) == {
        **WALL_QUERY,
        "sortBy": "CommunityRating,SortName",
        "sortOrder": order.value,
        "startIndex": "0",
        "limit": "100",
    }
    assert [item.name for item in page.items] == expected != NAME_ORDER
    ratings = [row.get("CommunityRating") for row in recorded_rows(fixture)]
    rated = [rating for rating in ratings if isinstance(rating, int | float)]
    assert rated == sorted(rated, reverse=order is SortOrder.DESCENDING)


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_a_film_library_sorts_with_its_own_tiebreakers() -> None:
    """電影庫的排序鍵後面接 `SortName,ProductionYear`（jellyfin-web `movies.js`）。`DatePlayed`
    只在電影庫的選單上：最近看的在前，沒看過的排最後。"""
    fixture = "items.movies.movie.sort-dateplayed.descending.json"
    route = respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture(f"http/jellyfin/{fixture}")
    )

    client = jellyfin_client("key")
    try:
        page = await client.library_page(
            user_id=RESTRICTED_USER,
            library_id=MOVIES_LIBRARY,
            item_type="Movie",
            start=0,
            limit=100,
            sort_by=("DatePlayed", "SortName", "ProductionYear"),
            sort_order=SortOrder.DESCENDING,
            genres=(),
            years=(),
        )
    finally:
        await client.aclose()

    assert dict(route.calls.last.request.url.params) == {
        **WALL_QUERY,
        "parentId": MOVIES_LIBRARY,
        "includeItemTypes": "Movie",
        "sortBy": "DatePlayed,SortName,ProductionYear",
        "sortOrder": "Descending",
        "startIndex": "0",
        "limit": "100",
    }
    # 名稱順序是 Echo、Foxtrot、Golf。
    assert [item.name for item in page.items] == ["Golf Movie", "Echo Movie", "Foxtrot Movie"]
    played = [(row.get("UserData") or {}).get("LastPlayedDate") for row in recorded_rows(fixture)]
    assert played == ["2026-05-01T12:00:00.0000000Z", "2026-04-01T12:00:00.0000000Z", None]


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_genres_are_filtered_by_the_server() -> None:
    """`genres` 以 `|` 分隔、是「或」。錄製那一台的類型寫在 NFO 裡（實驗腳本的 `TITLES`）：
    Alpha Show 是 Drama / Fantasy、Bravo Show 是 Comedy，Frieren 與 Hotel Show 兩個都不是。"""
    fixture = "items.tv.series.genres.json"
    route = respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture(f"http/jellyfin/{fixture}")
    )

    client = jellyfin_client("key")
    try:
        page = await client.library_page(
            user_id=RESTRICTED_USER,
            library_id=TV_LIBRARY,
            item_type="Series",
            start=0,
            limit=100,
            genres=("Drama", "Comedy"),
            sort_by=("SortName",),
            sort_order=SortOrder.ASCENDING,
            years=(),
        )
    finally:
        await client.aclose()

    assert dict(route.calls.last.request.url.params) == {
        **WALL_QUERY,
        "genres": "Drama|Comedy",
        "startIndex": "0",
        "limit": "100",
    }
    assert [item.name for item in page.items] == ["Alpha Show", "Bravo Show"]
    # 總數是篩過之後的，不是整個媒體庫的 4。
    assert page.total == 2


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_years_are_filtered_by_the_server() -> None:
    """`years` 以逗號分隔、是「或」。"""
    fixture = "items.tv.series.years.json"
    route = respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture(f"http/jellyfin/{fixture}")
    )

    client = jellyfin_client("key")
    try:
        page = await client.library_page(
            user_id=RESTRICTED_USER,
            library_id=TV_LIBRARY,
            item_type="Series",
            start=0,
            limit=100,
            years=(2020, 2023),
            sort_by=("SortName",),
            sort_order=SortOrder.ASCENDING,
            genres=(),
        )
    finally:
        await client.aclose()

    assert dict(route.calls.last.request.url.params) == {
        **WALL_QUERY,
        "years": "2020,2023",
        "startIndex": "0",
        "limit": "100",
    }
    assert [(item.name, item.year) for item in page.items] == [
        ("Bravo Show", 2020),
        ("Frieren", 2023),
    ]
    assert page.total == 2


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_filters_are_the_genres_and_years_of_this_library_only() -> None:
    """`/Items/Filters`（jellyfin-web 篩選面板那一支，研究 §3.2）。`parentId` 與 `includeItemTypes`
    真的有作用：Movies 才有的 Science Fiction、2018、2024，與沒有權限的 Anime 的 Mecha、2019
    都不在。
    **帶了 `parentId` 就不套權限**（研究 §2），所以媒體庫要先驗過，那是 services 的事。"""
    route = respx.get(f"{JELLYFIN_URL}/Items/Filters").respond(
        200, text=read_fixture("http/jellyfin/items-filters.tv.json")
    )

    client = jellyfin_client("key")
    try:
        filters = await client.library_filters(
            user_id=RESTRICTED_USER, library_id=TV_LIBRARY, item_type="Series"
        )
    finally:
        await client.aclose()

    assert dict(route.calls.last.request.url.params) == {
        "userId": RESTRICTED_USER,
        "parentId": TV_LIBRARY,
        "includeItemTypes": "Series",
    }
    assert filters.genres == ("Adventure", "Animation", "Comedy", "Documentary", "Drama", "Fantasy")
    assert filters.years == (2020, 2021, 2022, 2023)


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_filters_without_the_lists_are_not_jellyfin() -> None:
    respx.get(f"{JELLYFIN_URL}/Items/Filters").respond(200, json={"Nothing": []})

    client = jellyfin_client("key")
    try:
        with pytest.raises(ProtocolMismatchError):
            await client.library_filters(
                user_id=RESTRICTED_USER, library_id=TV_LIBRARY, item_type="Series"
            )
    finally:
        await client.aclose()


# --- M1.5 票 05：觀看狀態（研究 library-browsing.md §1.2、§5）-----------------------
#
# `UserData` 的欄位不是每筆都有：`PlayedPercentage` 只在看到一半或資料夾出現、`UnplayedItemCount`
# 只在資料夾、`LastPlayedDate` 只在看過之後（研究 §1.2）。牆那兩份錄製正好各缺不同的格。

#: `userplayeditems.{post,delete}.json` 錄的那一集（Bravo Show S01E02）。
BRAVO_EPISODE = "5ff804c21aa9edf479f4b827413e1eee"
#: `userplayeditems.forbidden.json` 打的那一集：Anime 裡的 Delta Mecha S01E02（實驗腳本的
#: `matrix_rows`；id 在 `items.parent-forbidden.json` 裡）。
FORBIDDEN_EPISODE = "5e51bcab9dae9b1b3bee242bcf21930e"


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_a_series_on_the_wall_reads_its_unplayed_episodes() -> None:
    respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture("http/jellyfin/items.tv.series.userdata.json")
    )

    client = jellyfin_client("key")
    try:
        page = await client.library_page(
            user_id=RESTRICTED_USER,
            library_id=TV_LIBRARY,
            item_type="Series",
            start=0,
            limit=100,
            sort_by=("SortName",),
            sort_order=SortOrder.ASCENDING,
            genres=(),
            years=(),
        )
    finally:
        await client.aclose()

    # 資料夾一定帶 `PlayedPercentage` 與 `UnplayedItemCount`：看過五集裡的一集是 20%、剩 4 集。
    assert [
        (item.name, data.played, data.played_percentage, data.unplayed_item_count)
        for item in page.items
        if (data := item.user_data) is not None
    ] == [
        ("Alpha Show", False, 20.0, 4),
        ("Bravo Show", False, 50.0, 1),
        ("Frieren", False, 0.0, 2),
        ("Hotel Show", False, 0.0, 1),
    ]


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_a_film_on_the_wall_missing_fields_read_as_zero_or_none() -> None:
    respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture("http/jellyfin/items.movies.movie.userdata.json")
    )

    client = jellyfin_client("key")
    try:
        page = await client.library_page(
            user_id=RESTRICTED_USER,
            library_id=MOVIES_LIBRARY,
            item_type="Movie",
            start=0,
            limit=100,
            sort_by=("SortName",),
            sort_order=SortOrder.ASCENDING,
            genres=(),
            years=(),
        )
    finally:
        await client.aclose()

    rows = json.loads(read_fixture("http/jellyfin/items.movies.movie.userdata.json"))["Items"]
    # 錄製裡真的缺那幾格——不是這份斷言自己想像的形狀。
    assert ["PlayedPercentage" in row["UserData"] for row in rows] == [False, True, False]
    assert not any("UnplayedItemCount" in row["UserData"] for row in rows)
    # 看過的沒有 `PlayedPercentage`（當 0）、不是資料夾的沒有 `UnplayedItemCount`（`None`）。
    assert [
        (item.name, data.played, data.played_percentage, data.unplayed_item_count)
        for item in page.items
        if (data := item.user_data) is not None
    ] == [
        ("Echo Movie", True, 0.0, None),
        ("Foxtrot Movie", False, 50.0, None),
        ("Golf Movie", True, 0.0, None),
    ]


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_the_index_carries_no_user_data() -> None:
    respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture("http/jellyfin/items.tv.series.index.json")
    )

    client = jellyfin_client("key")
    try:
        titles = await client.library_index(
            user_id=RESTRICTED_USER, library_id=TV_LIBRARY, item_type="Series"
        )
    finally:
        await client.aclose()

    assert {item.user_data for item in titles} == {None}


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("played", "method", "fixture"),
    [(True, "POST", "userplayeditems.post.json"), (False, "DELETE", "userplayeditems.delete.json")],
)
async def test_jellyfin_marking_an_item_writes_this_users_record_and_reads_it_back(
    played: bool, method: str, fixture: str
) -> None:
    route = respx.route(method=method, url=f"{JELLYFIN_URL}/UserPlayedItems/{BRAVO_EPISODE}")
    route.respond(200, text=read_fixture(f"http/jellyfin/{fixture}"))

    client = jellyfin_client("key")
    try:
        data = await client.mark_played(
            user_id=RESTRICTED_USER, item_id=BRAVO_EPISODE, played=played
        )
    finally:
        await client.aclose()

    assert dict(route.calls.last.request.url.params) == {"userId": RESTRICTED_USER}
    # 集不是資料夾：兩個方向都沒有 `UnplayedItemCount`，`DELETE` 的回應連 `LastPlayedDate` 都沒有。
    assert (data.played, data.played_percentage, data.unplayed_item_count) == (played, 0.0, None)


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["POST", "DELETE"])
async def test_jellyfin_an_item_this_user_cannot_see_is_not_found(method: str) -> None:
    """Jellyfin 自己查可見性（`GetItemById<BaseItem>(itemId, user)`，研究 §5）：無權的集回 404
    而且沒有寫入（票 01 打完立刻讀回）。那是答案，不是「接到了別的服務」。"""
    respx.route(method=method, url=f"{JELLYFIN_URL}/UserPlayedItems/{FORBIDDEN_EPISODE}").respond(
        404, text=read_fixture("http/jellyfin/userplayeditems.forbidden.json")
    )

    client = jellyfin_client("key")
    try:
        with pytest.raises(NotFoundError):
            await client.mark_played(
                user_id=RESTRICTED_USER, item_id=FORBIDDEN_EPISODE, played=method == "POST"
            )
    finally:
        await client.aclose()


# --- Jellyfin 的圖（M1.5 票 04，研究 library-browsing.md §6）----------------------


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_the_wall_carries_each_titles_primary_image_tag() -> None:
    """代理的網址要帶 DTO 的 `ImageTags.Primary`：`tag` 只是快取鍵，錯的也回圖（研究 §6）。"""
    respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture("http/jellyfin/items.tv.series.userdata.json")
    )

    client = jellyfin_client("key")
    try:
        page = await client.library_page(
            user_id=RESTRICTED_USER,
            library_id=TV_LIBRARY,
            item_type="Series",
            start=0,
            limit=100,
            sort_by=("SortName",),
            sort_order=SortOrder.ASCENDING,
            genres=(),
            years=(),
        )
    finally:
        await client.aclose()

    assert [(item.name, item.primary_tag) for item in page.items] == [
        ("Alpha Show", "f99664090dfd3223c18e80663440deac"),
        ("Bravo Show", "fa01c79f6d2ed4ceaa8ea470a7f7ac3b"),
        ("Frieren", "ae92dd1bdff3b398370c5b46b3123200"),
        ("Hotel Show", "fd9be66f6a4daa46815b2f72f256286c"),
    ]


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_an_item_without_a_primary_image_has_no_primary_tag() -> None:
    """沒有圖的 item 是 `ImageTags: {}`。錄到這個形狀的是無權媒體庫那一份（季與集沒有海報）。"""
    respx.get(f"{JELLYFIN_URL}/Items").respond(
        200, text=read_fixture("http/jellyfin/items.parent-forbidden.json")
    )

    client = jellyfin_client("key")
    try:
        page = await client.library_page(
            user_id=RESTRICTED_USER,
            library_id=TV_LIBRARY,
            item_type="Series",
            start=0,
            limit=100,
            sort_by=("SortName",),
            sort_order=SortOrder.ASCENDING,
            genres=(),
            years=(),
        )
    finally:
        await client.aclose()

    tagged: dict[str, set[bool]] = {}
    for item in page.items:
        tagged.setdefault(item.type, set()).add(bool(item.primary_tag))
    assert tagged == {"Season": {False}, "Episode": {False}, "Folder": {False}, "Series": {True}}


#: `images-primary.resized.headers.json` 錄的那一張：Alpha Show 的 Primary（票 01）。
ALPHA_SHOW = "2a9857e656bbd18b7c3c3a3b4ee5eef1"
ALPHA_PRIMARY_TAG = "f99664090dfd3223c18e80663440deac"


def recorded_image_headers(fixture: str) -> dict[str, str]:
    headers: dict[str, str] = json.loads(read_fixture(f"http/jellyfin/{fixture}"))["headers"]
    return headers


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_an_image_is_resized_by_jellyfin() -> None:
    """縮放交給 Jellyfin（`fillWidth` / `fillHeight` / `quality` / `format`），網址帶 `tag`。"""
    body = b"RIFF\x00\x00\x00\x00WEBPVP8 "
    route = respx.get(f"{JELLYFIN_URL}/Items/{ALPHA_SHOW}/Images/Primary").respond(
        200, content=body, headers=recorded_image_headers("images-primary.resized.headers.json")
    )

    client = jellyfin_client()
    try:
        image = await client.image(
            ALPHA_SHOW,
            "Primary",
            tag=ALPHA_PRIMARY_TAG,
            fill_width=342,
            fill_height=513,
            quality=90,
        )
    finally:
        await client.aclose()

    assert dict(route.calls.last.request.url.params) == {
        "tag": ALPHA_PRIMARY_TAG,
        "fillWidth": "342",
        "fillHeight": "513",
        "quality": "90",
        "format": "Webp",
    }
    assert (image.content, image.content_type) == (body, "image/webp")


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_a_missing_image_is_an_answer_not_a_mismatch() -> None:
    """沒有這張圖（或沒有這個 item）是 404（研究 §6）：卡片換成佔位，不是「接到了別的服務」。"""
    respx.get(f"{JELLYFIN_URL}/Items/{ALPHA_SHOW}/Images/Primary").respond(404)

    client = jellyfin_client()
    try:
        with pytest.raises(NotFoundError):
            await client.image(
                ALPHA_SHOW,
                "Primary",
                tag=ALPHA_PRIMARY_TAG,
                fill_width=342,
                fill_height=513,
                quality=90,
            )
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_an_image_that_is_not_an_image_is_not_jellyfin() -> None:
    """位址接到了別的服務（回一頁 HTML）時不能把它當成圖轉給瀏覽器。"""
    respx.get(f"{JELLYFIN_URL}/Items/{ALPHA_SHOW}/Images/Primary").respond(
        200, text="<html>router login</html>", headers={"Content-Type": "text/html"}
    )

    client = jellyfin_client()
    try:
        with pytest.raises(ProtocolMismatchError):
            await client.image(
                ALPHA_SHOW,
                "Primary",
                tag=ALPHA_PRIMARY_TAG,
                fill_width=342,
                fill_height=513,
                quality=90,
            )
    finally:
        await client.aclose()


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
async def test_prowlarr_schema_outlasts_a_cold_prowlarr() -> None:
    """定義清單不能用探測的 5 秒逾時（2026-09-08 票 11 的 M0 驗收實測）。

    容器剛起來的第一次呼叫，Prowlarr 要把 627 份 Cardigann 定義從 `/config` 讀進來再組出
    5.6 MB 的回應：Windows 的 9p bind mount 上量到 **9.42 秒**，同一支端點第二次只要 0.34 秒。
    5 秒的探測逾時因此讓精靈第 5 步在乾淨的部署上直接失敗，而慢的儲存（NAS）只會更糟。
    """
    route = respx.get(f"{PROWLARR_URL}/api/v1/indexer/schema").respond(
        200, text=read_fixture("http/prowlarr/indexer-schema.defaults.json")
    )

    client = HttpProwlarrClient(PROWLARR_URL, "key")
    try:
        await client.definitions()
    finally:
        await client.aclose()

    timeout = route.calls.last.request.extensions["timeout"]
    assert timeout["read"] == SCHEMA_TIMEOUT_SECONDS
    assert SCHEMA_TIMEOUT_SECONDS > DEFAULT_TIMEOUT_SECONDS


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
    assert caps.search.available is True
    assert caps.search.params == frozenset({"q"})
    # 公開站的 `tv-search` 只認關鍵字與季集，沒有 tmdbid（票 08 實測十個站都沒有）。
    assert caps.tv.params == frozenset({"q", "season", "ep"})
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

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
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

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        await client.configuration()
    finally:
        await client.aclose()

    assert route.calls.last.request.headers["Authorization"] == f"Bearer {V4_READ_TOKEN}"
    assert "api_key" not in route.calls.last.request.url.params


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_v3_api_key_travels_as_a_query_parameter() -> None:
    """使用者貼的多半是帳號頁上那把 32 字元的 v3 key，兩種形狀都要成立（2026-09-08 實測）。"""
    route = respx.get(f"{TMDB_URL}/configuration").respond(
        200, text=read_fixture("http/tmdb/configuration.json")
    )

    client = HttpTmdbClient(V3_API_KEY, base_url=TMDB_URL)
    try:
        await client.configuration()
    finally:
        await client.aclose()

    assert "Authorization" not in route.calls.last.request.headers
    assert route.calls.last.request.url.params["api_key"] == V3_API_KEY


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_trending_tv_reads_the_series_fields() -> None:
    """劇集用 `name` / `first_air_date`，電影用 `title` / `release_date`——同一支端點兩種形狀。"""
    respx.get(f"{TMDB_URL}/trending/tv/week").respond(
        200, text=read_fixture("http/tmdb/trending-tv-week.en.json")
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        entries = await client.trending(MediaKind.TV, language="en-US")
    finally:
        await client.aclose()

    assert entries[0] == TmdbEntry(
        tmdb_id=95350,
        kind=MediaKind.TV,
        title="Lanterns",
        original_title="Lanterns",
        year=2026,
        poster_path="/gpC7h43xPMEV3goYMQShfJbTtLq.jpg",
    )
    assert [entry.kind for entry in entries] == [MediaKind.TV] * 6


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_trending_movie_reads_the_movie_fields() -> None:
    respx.get(f"{TMDB_URL}/trending/movie/week").respond(
        200, text=read_fixture("http/tmdb/trending-movie-week.en.json")
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        entries = await client.trending(MediaKind.MOVIE, language="en-US")
    finally:
        await client.aclose()

    assert entries[0] == TmdbEntry(
        tmdb_id=1108427,
        kind=MediaKind.MOVIE,
        title="Moana",
        original_title="Moana",
        year=2026,
        poster_path="/gaet1xQ2nxrG0V1Ep9T20ZMNEIC.jpg",
    )


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_popular_carries_no_media_type_so_the_caller_supplies_it() -> None:
    """`{tv,movie}/popular` 的每一筆**沒有** `media_type`（trending 與 search 才有）。"""
    respx.get(f"{TMDB_URL}/tv/popular").respond(
        200, text=read_fixture("http/tmdb/tv-popular.en.json")
    )
    respx.get(f"{TMDB_URL}/movie/popular").respond(
        200, text=read_fixture("http/tmdb/movie-popular.en.json")
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        series = await client.popular(MediaKind.TV, language="en-US")
        movies = await client.popular(MediaKind.MOVIE, language="en-US")
    finally:
        await client.aclose()

    assert (series[0].tmdb_id, series[0].kind, series[0].title) == (108978, MediaKind.TV, "Reacher")
    assert (movies[0].tmdb_id, movies[0].kind) == (969681, MediaKind.MOVIE)


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_search_multi_drops_people() -> None:
    """`search/multi` 也回人物。`miyazaki` 這一查 20 筆裡 16 筆是人（2026-09-09 實測）。"""
    respx.get(f"{TMDB_URL}/search/multi").respond(
        200, text=read_fixture("http/tmdb/search-multi.miyazaki.en.json")
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        entries = await client.search("miyazaki", language="en-US")
    finally:
        await client.aclose()

    assert [(entry.kind, entry.tmdb_id) for entry in entries] == [
        (MediaKind.MOVIE, 1427106),
        (MediaKind.TV, 89764),
        (MediaKind.TV, 109113),
    ]


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_search_multi_keeps_the_original_title_next_to_the_translation() -> None:
    """顯示用標題來自 `zh-TW` 那一輪，原文標題仍然是原文（brief §7.5 的檔名用英文）。"""
    respx.get(f"{TMDB_URL}/search/multi").respond(
        200, text=read_fixture("http/tmdb/search-multi.spy-x-family.zh.json")
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        entries = await client.search("spy x family", language="zh-TW")
    finally:
        await client.aclose()

    assert [(entry.title, entry.original_title) for entry in entries] == [
        ("SPY×FAMILY 間諜家家酒", "SPY×FAMILY"),
        ("SPY×FAMILY 間諜家家酒 CODE：White", "劇場版 SPY×FAMILY CODE: White"),
    ]


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_sends_the_language_and_the_search_query() -> None:
    route = respx.get(f"{TMDB_URL}/search/multi").respond(
        200, text=read_fixture("http/tmdb/search-multi.spy-x-family.en.json")
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        await client.search("spy x family", language="zh-TW")
    finally:
        await client.aclose()

    params = route.calls.last.request.url.params
    assert params["query"] == "spy x family"
    assert params["language"] == "zh-TW"
    #: 探索頁不該回成人內容，而 TMDB 的預設就是不回；明確送出去才不必依賴那個預設。
    assert params["include_adult"] == "false"


@respx.mock
@pytest.mark.asyncio
async def test_both_credential_shapes_reach_every_tmdb_endpoint() -> None:
    """憑證的兩種形狀在**每一支**端點都送得出去，不是只有精靈打的那一支。

    `HttpTmdbClient._get` 把 `self._params` 併進每一次請求，所以這件事是結構性的——
    但「結構性」正是最容易在某一支端點手寫參數時被繞過的東西（探索頁的 `search` 就多帶了
    `query` 與 `include_adult`）。
    """
    calls: tuple[tuple[str, Callable[[HttpTmdbClient], Awaitable[object]]], ...] = (
        ("/configuration", lambda c: c.configuration()),
        ("/trending/tv/week", lambda c: c.trending(MediaKind.TV, language="en-US")),
        ("/movie/popular", lambda c: c.popular(MediaKind.MOVIE, language="en-US")),
        ("/search/multi", lambda c: c.search("x", language="en-US")),
    )
    for path, call in calls:
        respx.get(f"{TMDB_URL}{path}").respond(200, json={"images": {}, "results": []})

        v3 = HttpTmdbClient(V3_API_KEY, base_url=TMDB_URL)
        try:
            await call(v3)
        finally:
            await v3.aclose()
        request = respx.calls.last.request
        assert request.url.params["api_key"] == V3_API_KEY, path
        assert "Authorization" not in request.headers, path

        v4 = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
        try:
            await call(v4)
        finally:
            await v4.aclose()
        request = respx.calls.last.request
        assert request.headers["Authorization"] == f"Bearer {V4_READ_TOKEN}", path
        # v4 走標頭，所以憑證不會落在網址上——也就不會落在任何一行 log 或反向代理紀錄裡。
        assert "api_key" not in request.url.params, path


@respx.mock
@pytest.mark.asyncio
async def test_every_tmdb_request_goes_through_the_token_bucket() -> None:
    """速率上限在 client 裡，不是呼叫端的紀律——漏掉一支端點就等於沒有上限。"""
    respx.get(f"{TMDB_URL}/configuration").respond(
        200, text=read_fixture("http/tmdb/configuration.json")
    )
    respx.get(f"{TMDB_URL}/trending/tv/week").respond(
        200, text=read_fixture("http/tmdb/trending-tv-week.en.json")
    )
    respx.get(f"{TMDB_URL}/tv/popular").respond(
        200, text=read_fixture("http/tmdb/tv-popular.en.json")
    )
    respx.get(f"{TMDB_URL}/search/multi").respond(
        200, text=read_fixture("http/tmdb/search-multi.spy-x-family.en.json")
    )
    bucket = CountingBucket()

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL, bucket=bucket)
    try:
        await client.configuration()
        await client.trending(MediaKind.TV, language="en-US")
        await client.popular(MediaKind.TV, language="en-US")
        await client.search("spy x family", language="en-US")
    finally:
        await client.aclose()

    assert bucket.acquired == 4


def test_the_tmdb_bucket_is_one_per_process_not_one_per_client() -> None:
    """TMDB 的上限是每個 IP 的。探索頁一次開三個 feed、每個 feed 兩種語言，各配一個桶
    就等於根本沒有上限（`adapters/tmdb/client.py` 的 `_BUCKET`）。
    """
    first = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    second = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)

    assert first._bucket is second._bucket
    assert RATE_PER_SECOND == 40.0


class CountingBucket(TokenBucket):
    """真的桶，外加一個計數器。用替身的話就測不到 client 呼叫的是不是 `acquire()`。"""

    def __init__(self) -> None:
        super().__init__(rate=RATE_PER_SECOND, capacity=int(RATE_PER_SECOND))
        self.acquired = 0

    async def acquire(self) -> None:
        self.acquired += 1
        await super().acquire()


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


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_tv_detail_reads_the_season_list_and_the_absolute_group() -> None:
    """劇集詳情要回三件東西：識別欄位、季清單，以及 Absolute group 的 id（若有人建過）。

    季名原樣留著：`Specials` 與 `Hashira Training Arc` 這種篇章名是 plan §4.4 的季號來源，
    正規化成 `Season N` 就把它丟掉了。
    """
    respx.get(f"{TMDB_URL}/tv/120089").respond(
        200, text=read_fixture("http/tmdb/tv-detail.spy-x-family.en.json")
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        detail = await client.detail(MediaKind.TV, 120089, language="en-US")
    finally:
        await client.aclose()

    assert (detail.tmdb_id, detail.kind) == (120089, MediaKind.TV)
    assert (detail.title, detail.original_title) == ("SPY x FAMILY", "SPY×FAMILY")
    assert (detail.year, detail.first_air_date) == (2022, date(2022, 4, 9))
    # 劇集的片長在每一集上，不在作品上。
    assert detail.runtime is None
    assert [(row.season_number, row.name, row.episode_count) for row in detail.seasons] == [
        (0, "Specials", 3),
        (1, "Season 1", 25),
        (2, "Season 2", 12),
        (3, "Season 3", 13),
    ]
    assert detail.seasons[1].air_date == date(2022, 4, 9)
    # 五個 group 裡挑得出 `type == 2` 的那一個（brief §20.3 的 Absolute）。
    assert detail.absolute_group_id == "689a2aec017d0bc9ecc6fac8"


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_an_empty_title_falls_back_to_the_original_title() -> None:
    """`name` / `title` 是空字串時用原文標題（brief §7.5、§20.3）。

    `en` 介面的顯示用標題就是英文那一輪的這一格（M1.5 票 02），空字串會直接變成一張沒有名字的
    卡。清單與詳情各自解析一次，兩條路都要守。
    """
    respx.get(f"{TMDB_URL}/trending/tv/week").respond(
        200,
        json={
            "results": [
                {"id": 1, "media_type": "tv", "name": "", "original_name": "葬送のフリーレン"}
            ]
        },
    )
    respx.get(f"{TMDB_URL}/movie/2").respond(
        200, json={"id": 2, "title": "", "original_title": "君たちはどう生きるか"}
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        (entry,) = await client.trending(MediaKind.TV, language="en-US")
        detail = await client.detail(MediaKind.MOVIE, 2, language="en-US")
    finally:
        await client.aclose()

    assert entry.title == "葬送のフリーレン"
    assert detail.title == "君たちはどう生きるか"


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_tv_detail_collects_every_title_it_can_match_against() -> None:
    """比對用的標題集合＝英文 + 原文 + 各國別名 + 各語言翻譯，去重（plan §4.3、brief §20.3）。

    票 08 拿它逐個發搜尋，票 06 拿它認檔名裡的作品名——所以中文別名必須在裡面。
    """
    respx.get(f"{TMDB_URL}/tv/120089").respond(
        200, text=read_fixture("http/tmdb/tv-detail.spy-x-family.en.json")
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        detail = await client.detail(MediaKind.TV, 120089, language="en-US")
    finally:
        await client.aclose()

    assert detail.titles[:2] == ("SPY x FAMILY", "SPY×FAMILY")
    assert "间谍过家家" in detail.titles
    assert "스파이 패밀리" in detail.titles
    # 去重：`SPY x FAMILY` 同時是 `name`、好幾個別名與好幾份翻譯。
    assert len(detail.titles) == len(set(detail.titles))


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_movie_detail_reads_the_film_fields() -> None:
    """電影用 `title` / `release_date` / `runtime`，而且沒有季。"""
    respx.get(f"{TMDB_URL}/movie/1241982").respond(
        200, text=read_fixture("http/tmdb/movie-detail.moana-2.en.json")
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        detail = await client.detail(MediaKind.MOVIE, 1241982, language="en-US")
    finally:
        await client.aclose()

    assert (detail.tmdb_id, detail.kind, detail.title) == (1241982, MediaKind.MOVIE, "Moana 2")
    assert (detail.year, detail.first_air_date) == (2024, date(2024, 11, 21))
    assert detail.runtime == 100
    assert detail.seasons == ()
    assert detail.absolute_group_id == ""
    assert detail.overview.startswith("After receiving an unexpected call")


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_detail_sends_the_appends_each_kind_needs() -> None:
    """兩種作品的 append 不同：只有劇集有 episode groups，而兩種都要標題集合。"""
    series = respx.get(f"{TMDB_URL}/tv/120089").respond(
        200, text=read_fixture("http/tmdb/tv-detail.spy-x-family.en.json")
    )
    film = respx.get(f"{TMDB_URL}/movie/1241982").respond(
        200, text=read_fixture("http/tmdb/movie-detail.moana-2.en.json")
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        await client.detail(MediaKind.TV, 120089, language="zh-TW")
        await client.detail(MediaKind.MOVIE, 1241982, language="en-US")
    finally:
        await client.aclose()

    assert series.calls.last.request.url.params["language"] == "zh-TW"
    assert series.calls.last.request.url.params["append_to_response"] == (
        "alternative_titles,translations,episode_groups"
    )
    assert film.calls.last.request.url.params["append_to_response"] == (
        "alternative_titles,translations"
    )


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_season_reads_every_episode() -> None:
    """一季的每一集：集號、集名、播出日、片長（plan §2.2 的快照欄位）。"""
    respx.get(f"{TMDB_URL}/tv/120089/season/2").respond(
        200, text=read_fixture("http/tmdb/tv-season.spy-x-family.s02.json")
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        season = await client.season(120089, 2, language="en-US")
    finally:
        await client.aclose()

    assert (season.season_number, season.name) == (2, "Season 2")
    assert len(season.episodes) == 12
    first = season.episodes[0]
    assert (first.episode_number, first.season_number) == (1, 2)
    assert (first.name, first.runtime) == ("FOLLOW MAMA AND PAPA", 24)
    assert first.air_date == date(2023, 10, 7)


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_season_zero_is_the_specials() -> None:
    """`season_number: 0` 是 Specials（brief §20.3）。它是一季，不是一個特例分支。"""
    respx.get(f"{TMDB_URL}/tv/120089/season/0").respond(
        200, text=read_fixture("http/tmdb/tv-season.spy-x-family.s00.json")
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        season = await client.season(120089, 0, language="en-US")
    finally:
        await client.aclose()

    assert (season.season_number, season.name) == (0, "Specials")
    assert [row.episode_number for row in season.episodes] == [1, 2, 3]


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_absolute_numbers_come_from_the_order_not_the_episode_number() -> None:
    """group 裡的 `episode_number` 保留播出序的原值，絕對編號要從 0-based 的 `order` 推
    （brief §20.3，2026-09-08 實測 10 部）。

    照著 `episode_number` 讀的話 S02E01 會變成絕對第 1 集，而它其實是第 26 集。
    """
    respx.get(f"{TMDB_URL}/tv/episode_group/689a2aec017d0bc9ecc6fac8").respond(
        200, text=read_fixture("http/tmdb/tv-episode-group.spy-x-family.absolute.json")
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    try:
        ordering = await client.absolute_ordering("689a2aec017d0bc9ecc6fac8")
    finally:
        await client.aclose()

    assert ordering[(1, 1)] == 1
    assert ordering[(1, 25)] == 25
    # 第二季第一集接在第一季二十五集後面。
    assert ordering[(2, 1)] == 26


@respx.mock
@pytest.mark.asyncio
async def test_tmdb_detail_says_when_the_id_does_not_exist() -> None:
    """404 與「TMDB 壞了」是兩件事：前者重試一百次也一樣，畫面要說得出差別（票 04）。"""
    respx.get(f"{TMDB_URL}/tv/99999999").respond(
        404, text=read_fixture("http/tmdb/tv-detail.not-found.json")
    )

    client = HttpTmdbClient(V4_READ_TOKEN, base_url=TMDB_URL)
    with pytest.raises(NotFoundError):
        await client.detail(MediaKind.TV, 99999999, language="en-US")
    await client.aclose()


def test_tmdb_absolute_numbers_follow_the_order_field_even_with_gaps() -> None:
    """絕對編號是 `order + 1`，**不是這一筆在清單裡的位置**（plan §8.3、brief §20.3）。

    單一連續的 group 兩種算法看不出差別，所以這裡刻意給一份有缺號、而且沒有照順序排的
    group：照位置數會把第三筆算成 3，而它的 `order` 是 5，也就是絕對第 6 集。
    """
    ordering = parse_absolute_ordering(
        {
            "groups": [
                {
                    "order": 1,
                    "episodes": [
                        {"order": 2, "season_number": 1, "episode_number": 3},
                        {"order": 0, "season_number": 1, "episode_number": 1},
                        {"order": 5, "season_number": 2, "episode_number": 1},
                    ],
                }
            ]
        }
    )

    assert ordering == {(1, 1): 1, (1, 3): 3, (2, 1): 6}
