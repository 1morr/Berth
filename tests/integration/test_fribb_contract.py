"""Fribb/anime-lists 的下載與查表（M5 票 16）。

`tests/fixtures/http/fribb/anime-list-full.excerpt.json` 是真表（約 7.5 MB）裁出的 17 筆，每筆原樣；
respx 把它當作 `LIST_URL` 的回應。時鐘是注入的，檔案修改時間用 `os.utime` 設。
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
import pytest
import respx

from berth.adapters.fribb import LIST_URL
from berth.adapters.fribb.client import (
    MAX_AGE_SECONDS,
    RETRY_SECONDS,
    HttpFribb,
    list_path,
)
from berth.adapters.http import ProtocolMismatchError, ServiceUnavailableError
from tests.conftest import FIXTURES

pytestmark = pytest.mark.asyncio

EXCERPT = (FIXTURES / "http/fribb/anime-list-full.excerpt.json").read_bytes()
DAY = 24 * 60 * 60
#: 真的現在：剛下載的檔案修改時間是真的現在，時鐘要跟它對得上。
NOW = time.time()


def at(path: Path, age: float) -> None:
    """把檔案的修改時間設成 `age` 秒前（相對於 `NOW`）。"""
    stamp = NOW - age
    os.utime(path, (stamp, stamp))


def old_copy(tmp_path: Path, age: float = 8 * DAY) -> Path:
    """一份已經下載過、內容與錄製的不同（只有一筆）的舊檔，好看出有沒有被換掉。"""
    path = list_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b'[{"type": "TV", "anilist_id": 21355, "themoviedb_id": {"tv": 1}}]')
    at(path, age)
    return path


def fribb(path: Path, now: list[float] | None = None) -> HttpFribb:
    clock = now if now is not None else [NOW]
    return HttpFribb(path, clock=lambda: clock[0])


def served(content: bytes = EXCERPT, status: int = 200) -> httpx.Response:
    return httpx.Response(status, content=content)


@respx.mock
async def test_without_a_file_it_downloads_and_looks_up_rezero(tmp_path: Path) -> None:
    route = respx.get(LIST_URL).mock(return_value=served())
    path = list_path(tmp_path)

    found = await fribb(path).lookup([21355, 100049, 108632, 119661, 163134, 189046, 164])

    assert route.call_count == 1
    assert path.read_bytes() == EXCERPT
    assert not path.with_name(path.name + ".partial").exists()
    # TMDB 把 Re:Zero 的每一輪都併在第 1 季，起點前一集是 offset
    assert {i: (e.tmdb_tv, e.tmdb_season, e.tmdb_episode_offset) for i, e in found.items()} == {
        21355: (65942, 1, None),
        100049: (65942, 0, None),  # OVA：Specials
        108632: (65942, 1, 26),
        119661: (65942, 1, 38),
        163134: (65942, 1, 50),
        189046: (65942, 1, 66),
        164: (None, None, None),
    }
    assert found[21355].type == "TV"
    assert found[100049].type == "OVA"
    assert found[21355].mal_id == 31240


@respx.mock
async def test_a_movie_has_tmdb_movie_ids_and_no_season(tmp_path: Path) -> None:
    respx.get(LIST_URL).mock(return_value=served())

    found = await fribb(list_path(tmp_path)).lookup([164])

    movie = found[164]
    assert movie.type == "MOVIE"
    assert movie.tmdb_movies == (128,)
    assert movie.tmdb_tv is None
    assert movie.tmdb_season is None


@respx.mock
async def test_ids_not_in_the_list_are_left_out(tmp_path: Path) -> None:
    respx.get(LIST_URL).mock(return_value=served())

    found = await fribb(list_path(tmp_path)).lookup([21355, 999999999])

    assert list(found) == [21355]


@respx.mock
async def test_a_fresh_file_is_used_without_asking_the_network(tmp_path: Path) -> None:
    route = respx.get(LIST_URL).mock(return_value=served())
    path = old_copy(tmp_path, age=MAX_AGE_SECONDS - 60)

    found = await fribb(path).lookup([21355])

    assert route.call_count == 0
    assert found[21355].tmdb_tv == 1  # 舊檔裡的值，不是錄製的 65942


@respx.mock
async def test_a_stale_file_is_downloaded_again(tmp_path: Path) -> None:
    route = respx.get(LIST_URL).mock(return_value=served())
    path = old_copy(tmp_path, age=8 * DAY)

    found = await fribb(path).lookup([21355])

    assert route.call_count == 1
    assert path.read_bytes() == EXCERPT
    assert found[21355].tmdb_tv == 65942
    # 換上去的檔案是新的：下一次查不再問
    await fribb(path).lookup([21355])
    assert route.call_count == 1


@respx.mock
async def test_a_failed_update_keeps_the_old_file_and_does_not_retry_for_an_hour(
    tmp_path: Path,
) -> None:
    route = respx.get(LIST_URL).mock(return_value=httpx.Response(500))
    path = old_copy(tmp_path)
    old = path.read_bytes()
    now = [NOW]
    client = fribb(path, now)

    found = await client.lookup([21355])

    assert route.call_count == 1
    assert found[21355].tmdb_tv == 1
    assert path.read_bytes() == old
    # 一小時內再查：不再試
    now[0] += RETRY_SECONDS - 1
    await client.lookup([21355])
    assert route.call_count == 1
    # 過了一小時：再試一次
    now[0] += 2
    await client.lookup([21355])
    assert route.call_count == 2


@respx.mock
async def test_the_update_after_a_failure_is_installed_when_it_works(tmp_path: Path) -> None:
    route = respx.get(LIST_URL).mock(side_effect=[httpx.Response(500), served()])
    path = old_copy(tmp_path)
    now = [NOW]
    client = fribb(path, now)
    await client.lookup([21355])

    now[0] += RETRY_SECONDS + 1
    found = await client.lookup([21355])

    assert route.call_count == 2
    assert found[21355].tmdb_tv == 65942
    assert path.read_bytes() == EXCERPT


@respx.mock
async def test_without_a_file_a_failed_download_is_unavailable(tmp_path: Path) -> None:
    respx.get(LIST_URL).mock(return_value=httpx.Response(500))
    path = list_path(tmp_path)

    with pytest.raises(ServiceUnavailableError):
        await fribb(path).lookup([21355])

    assert not path.exists()


@respx.mock
async def test_a_truncated_download_does_not_replace_the_old_file(tmp_path: Path) -> None:
    route = respx.get(LIST_URL).mock(return_value=served(EXCERPT[: len(EXCERPT) // 2]))
    path = old_copy(tmp_path)
    old = path.read_bytes()
    mtime = path.stat().st_mtime

    found = await fribb(path).lookup([21355])

    assert route.call_count == 1
    assert path.read_bytes() == old
    assert path.stat().st_mtime == mtime
    assert found[21355].tmdb_tv == 1  # 還在用舊的
    # 半張表連暫存檔都沒寫過
    assert list(path.parent.iterdir()) == [path]


@respx.mock
async def test_a_truncated_download_with_no_file_raises_and_writes_nothing(tmp_path: Path) -> None:
    respx.get(LIST_URL).mock(return_value=served(EXCERPT[: len(EXCERPT) // 2]))
    path = list_path(tmp_path)

    with pytest.raises(ServiceUnavailableError, match="not complete JSON"):
        await fribb(path).lookup([21355])

    assert not path.exists()
    assert not path.parent.exists() or list(path.parent.iterdir()) == []


@respx.mock
async def test_an_answer_that_is_not_a_list_is_a_protocol_mismatch(tmp_path: Path) -> None:
    respx.get(LIST_URL).mock(return_value=served(b"{}"))
    path = list_path(tmp_path)

    with pytest.raises(ProtocolMismatchError, match="not a list"):
        await fribb(path).lookup([21355])

    assert not path.exists()


@respx.mock
async def test_an_answer_of_the_wrong_shape_does_not_replace_the_old_file(tmp_path: Path) -> None:
    respx.get(LIST_URL).mock(return_value=served(b"{}"))
    path = old_copy(tmp_path)
    old = path.read_bytes()

    found = await fribb(path).lookup([21355])

    assert path.read_bytes() == old
    assert found[21355].tmdb_tv == 1


async def test_a_file_that_is_not_json_is_a_protocol_mismatch(tmp_path: Path) -> None:
    path = list_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"<html>")
    at(path, 60)

    with pytest.raises(ProtocolMismatchError, match="not JSON"):
        await fribb(path).lookup([21355])
