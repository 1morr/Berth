"""`scan_libraries`：請 Jellyfin 掃多大（brief §20.1，M4 票 62）。

列過的路徑只刷新它們的媒體庫；有一條沒列過就一次全庫掃描，不再另外刷新。
"""

from __future__ import annotations

import pytest

from berth.adapters.jellyfin import JellyfinItem, ScanScope, ScanTarget, lists_under, scan_libraries
from berth.adapters.jellyfin.fake import LIBRARY_SCAN_TASK, FakeJellyfinClient

pytestmark = pytest.mark.asyncio


def jellyfin() -> FakeJellyfinClient:
    client = FakeJellyfinClient(tasks=(LIBRARY_SCAN_TASK,))
    client.use_token("key")
    return client


async def test_listed_paths_refresh_each_library_once() -> None:
    client = jellyfin()

    scope = await scan_libraries(
        client,
        [
            ScanTarget(library_id="tv", listed=True),
            ScanTarget(library_id="tv", listed=True),
            ScanTarget(library_id="movies", listed=True),
        ],
    )

    assert scope is ScanScope.LIBRARY
    assert client.libraries_refreshed == ["tv", "movies"]
    assert client.tasks_run == []


async def test_one_unlisted_path_is_one_server_scan_and_nothing_else() -> None:
    """全庫掃描本來就涵蓋列過的那幾個媒體庫。"""
    client = jellyfin()

    scope = await scan_libraries(
        client,
        [ScanTarget(library_id="tv", listed=True), ScanTarget(library_id="movies", listed=False)],
    )

    assert scope is ScanScope.SERVER
    assert client.tasks_run == [LIBRARY_SCAN_TASK.id]
    assert client.libraries_refreshed == []


async def test_a_path_with_no_known_library_gets_the_server_scan() -> None:
    client = jellyfin()

    scope = await scan_libraries(client, [ScanTarget(library_id=None, listed=True)])

    assert scope is ScanScope.SERVER
    assert client.libraries_refreshed == []


async def test_nothing_to_scan_asks_for_nothing() -> None:
    client = jellyfin()

    assert await scan_libraries(client, []) is None
    assert client.tasks_run == []
    assert client.libraries_refreshed == []


async def test_a_jellyfin_without_the_scan_task_says_so() -> None:
    client = FakeJellyfinClient()
    client.use_token("key")

    assert await scan_libraries(client, [ScanTarget(library_id="tv", listed=False)]) is None


async def test_listed_means_an_item_under_the_folder_not_beside_it() -> None:
    def series(path: str) -> JellyfinItem:
        return JellyfinItem(id=path, type="Series", name="", path=path, tmdb_id="")

    assert lists_under([series("/data/library/tv/Show")], "/data/library/tv/")
    assert not lists_under([series("/data/library/tv-old/Show")], "/data/library/tv")
    assert not lists_under([series("/data/library/tv")], "/data/library/tv")
