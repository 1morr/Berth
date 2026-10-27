"""Bangumi adapter 對錄製回應的契約（M5 票 16；回應是 `scripts/experiments/anime_sources.py`
2026-10-28 對 `GET https://api.bgm.tv/calendar` 錄的）。

`tests/fixtures/http/bgm/calendar.json` 是 `{status, headers, body}`；七天、112 部，
有的條目沒有 `rank`、沒有 `rating`。
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from berth.adapters.bgm import API_URL, USER_AGENT, CalendarItem
from berth.adapters.bgm.client import HttpBgm
from berth.adapters.http import ProtocolMismatchError
from berth.adapters.ttl import TtlCache
from tests.conftest import read_fixture

pytestmark = pytest.mark.asyncio

CALENDAR = f"{API_URL}/calendar"


def recorded() -> httpx.Response:
    data: dict[str, Any] = json.loads(read_fixture("http/bgm/calendar.json"))
    return httpx.Response(data["status"], json=data["body"], headers=data["headers"])


def client() -> HttpBgm:
    return HttpBgm(cache=TtlCache(ttl=60, size=2))


@respx.mock
async def test_the_calendar_is_flattened_with_its_weekdays() -> None:
    respx.get(CALENDAR).mock(return_value=recorded())

    items = await client().calendar()

    assert len(items) == 112
    assert all(isinstance(item, CalendarItem) for item in items)
    assert [item.weekday for item in items] == sorted(item.weekday for item in items)
    counts = {day: sum(1 for i in items if i.weekday == day) for day in range(1, 8)}
    assert counts == {1: 14, 2: 10, 3: 13, 4: 11, 5: 14, 6: 22, 7: 28}


@respx.mock
async def test_an_item_with_a_score_has_votes_and_a_rank() -> None:
    respx.get(CALENDAR).mock(return_value=recorded())

    items = {item.id: item for item in await client().calendar()}

    item = items[418229]
    assert item.name == "魔法少女育成計画 restart"
    assert item.name_cn == "魔法少女育成计划 restart"
    assert item.air_date == "2026-10-05"
    assert item.weekday == 1
    assert item.score == 6.2
    assert item.votes == 136
    assert item.rank == 5681


@respx.mock
async def test_missing_rank_and_score_are_none_not_zero() -> None:
    respx.get(CALENDAR).mock(return_value=recorded())

    items = {item.id: item for item in await client().calendar()}

    # 有分數、沒排名
    assert items[390200].score == 3.6
    assert items[390200].votes == 8
    assert items[390200].rank is None
    # 連 `rating` 都沒有，名字的中文版也是空字串
    assert items[498559].score is None
    assert items[498559].votes == 0
    assert items[498559].rank is None
    assert items[498559].name == "Electro Andes"
    assert items[498559].name_cn == ""
    raw = json.loads(read_fixture("http/bgm/calendar.json"))["body"]
    no_rating = {i["id"] for day in raw for i in day["items"] if not i.get("rating")}
    assert no_rating
    assert all(items[i].score is None and items[i].votes == 0 for i in no_rating)


@respx.mock
async def test_the_user_agent_names_the_developer_and_the_repo() -> None:
    route = respx.get(CALENDAR).mock(return_value=recorded())

    await client().calendar()

    sent = route.calls.last.request.headers["User-Agent"]
    assert sent == USER_AGENT
    assert "1morr/berth/" in sent
    assert "https://github.com/1morr/Berth" in sent
    assert "python-httpx" not in sent


@respx.mock
async def test_the_second_call_is_served_from_the_cache() -> None:
    route = respx.get(CALENDAR).mock(return_value=recorded())
    bgm = client()

    first = await bgm.calendar()
    second = await bgm.calendar()

    assert route.call_count == 1
    assert first == second
    # 給出去的是副本：呼叫端改它不會動到快取
    first.clear()
    assert len(await bgm.calendar()) == 112


@respx.mock
async def test_an_answer_that_is_not_a_list_is_a_protocol_mismatch() -> None:
    respx.get(CALENDAR).mock(return_value=httpx.Response(200, json={"title": "Not Found"}))

    with pytest.raises(ProtocolMismatchError, match="not a list"):
        await client().calendar()
