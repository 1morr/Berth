"""AniList adapter 對錄製回應的契約（M5 票 16；回應是 `scripts/experiments/anime_sources.py`
2026-10-28 對 `POST https://graphql.anilist.co` 錄的）。

`tests/fixtures/http/anilist/` 的每一份是 `{request, status, headers, body}`。唯一沒錄的是
`rate-limited.docs-example.json`：故意去惹出 429 是 AniList 條款要求不要做的事，所以它是文件
（https://docs.anilist.co/guide/rate-limiting）裡的範例。

時鐘與 sleep 都是注入的：量的是「閘門決定等多久」，不是測試跑了多久。
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from berth.adapters.anilist import (
    API_URL,
    ENTRIES_QUERY,
    SEARCH_QUERY,
    SEASON_QUERY,
    AnimeRelation,
    AnimeSeason,
    parse_entry,
)
from berth.adapters.anilist.client import (
    DEFAULT_RETRY_AFTER,
    MAX_RETRY_AFTER,
    RETRIES,
    HttpAniList,
    Throttle,
)
from berth.adapters.http import ProtocolMismatchError, ServiceUnavailableError
from berth.adapters.ttl import TtlCache
from tests.conftest import read_fixture

pytestmark = pytest.mark.asyncio

REZERO = "Re:Zero kara Hajimeru Isekai Seikatsu"


class FakeTime:
    """單調時鐘 + 記錄下來的 sleep：`sleep` 把時鐘往前推，就像真的睡過去。"""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def record(name: str) -> dict[str, Any]:
    return json.loads(read_fixture(f"http/anilist/{name}.json"))  # type: ignore[no-any-return]


def recorded(name: str) -> httpx.Response:
    data = record(name)
    return httpx.Response(data["status"], json=data["body"], headers=data["headers"])


def client(fake: FakeTime, throttle: Throttle | None = None) -> HttpAniList:
    """每個測試自己的快取與閘門；要共用閘門的測試自己傳。"""
    return HttpAniList(
        throttle=throttle or Throttle(clock=fake.time, sleep=fake.sleep),
        cache=TtlCache(ttl=60, size=16, clock=fake.time),
    )


@pytest.fixture
def fake() -> FakeTime:
    return FakeTime()


@respx.mock
async def test_search_sends_the_query_and_parses_the_entries(fake: FakeTime) -> None:
    route = respx.post(API_URL).mock(return_value=recorded("search.rezero"))

    found = await client(fake).search(REZERO, limit=8)

    sent = json.loads(route.calls.last.request.content)
    assert sent == {"query": SEARCH_QUERY, "variables": {"q": REZERO, "n": 8}}
    assert record("search.rezero")["request"] == sent  # 錄的時候送的就是這個
    assert [e.id for e in found] == [21355, 100049, 119661, 108632, 163134, 189046]
    first = found[0]
    assert first.mal_id == 31240
    assert first.title.romaji == REZERO
    assert first.title.english == "Re:ZERO -Starting Life in Another World-"
    assert first.title.native == "Re:ゼロから始める異世界生活"
    assert (first.format, first.status, first.episodes) == ("TV", "FINISHED", 25)
    assert (first.season, first.season_year) == ("SPRING", 2016)
    assert first.start_date == "2016-04-04"
    assert (first.average_score, first.popularity) == (81, 633851)
    assert first.genres[:2] == ("Action", "Adventure")
    # 搜尋不問關係與季表欄位
    assert first.relations == ()
    assert first.scorers is None
    assert first.next_episode is None


@respx.mock
async def test_search_never_asks_for_more_than_one_page(fake: FakeTime) -> None:
    route = respx.post(API_URL).mock(return_value=recorded("search.rezero"))

    await client(fake).search(REZERO, limit=500)

    assert json.loads(route.calls.last.request.content)["variables"]["n"] == 50


@respx.mock
async def test_entries_keep_only_the_relations_that_point_at_anime(fake: FakeTime) -> None:
    route = respx.post(API_URL).mock(return_value=recorded("entries.rezero.0"))

    [entry] = await client(fake).entries([21355])

    sent = json.loads(route.calls.last.request.content)
    assert sent == {"query": ENTRIES_QUERY, "variables": {"ids": [21355], "n": 50}}
    assert record("entries.rezero.0")["request"] == sent
    relations = {(r.type, r.id) for r in entry.relations}
    assert ("SEQUEL", 108632) in relations
    assert ("SIDE_STORY", 100049) in relations
    assert ("SPIN_OFF", 21780) in relations
    # 錄到的 13 條裡有 4 條漫畫（SOURCE 85737 與三條 ALTERNATIVE）：下載不到，不給
    raw = record("entries.rezero.0")["body"]["data"]["Page"]["media"][0]["relations"]["edges"]
    assert len(raw) == 13
    manga = {e["node"]["id"] for e in raw if e["node"]["type"] == "MANGA"}
    assert manga == {85737, 87259, 85736, 85814}
    assert len(entry.relations) == 9
    assert not {r.id for r in entry.relations} & manga
    assert all(isinstance(r, AnimeRelation) for r in entry.relations)


@respx.mock
async def test_entries_ask_for_sorted_unique_ids(fake: FakeTime) -> None:
    route = respx.post(API_URL).mock(return_value=recorded("entries.rezero.1"))

    found = await client(fake).entries([108632, 100049, 108632])

    sent = json.loads(route.calls.last.request.content)
    assert sent["variables"]["ids"] == [100049, 108632]
    assert record("entries.rezero.1")["request"] == sent
    assert {e.id: e.format for e in found} == {100049: "OVA", 108632: "TV"}
    # 單向關係：OVA 指回 TV 本篇是 PARENT
    ova = next(e for e in found if e.id == 100049)
    assert ("PARENT", 21355) in {(r.type, r.id) for r in ova.relations}


@respx.mock
async def test_entries_without_ids_ask_nothing(fake: FakeTime) -> None:
    route = respx.post(API_URL).mock(return_value=recorded("entries.missing"))

    assert await client(fake).entries([]) == []

    assert route.call_count == 0


@respx.mock
async def test_ids_that_do_not_exist_are_just_missing(fake: FakeTime) -> None:
    respx.post(API_URL).mock(return_value=recorded("entries.missing"))

    assert await client(fake).entries([999999999]) == []


@respx.mock
async def test_the_season_carries_scorers_and_the_next_episode(fake: FakeTime) -> None:
    route = respx.post(API_URL).mock(return_value=recorded("season.fall-2026"))

    found = await client(fake).season(AnimeSeason.FALL, 2026, limit=25)

    sent = json.loads(route.calls.last.request.content)
    assert sent == {"query": SEASON_QUERY, "variables": {"s": "FALL", "y": 2026, "n": 25}}
    assert record("season.fall-2026")["request"] == sent
    assert len(found) == 25
    by_id = {e.id: e for e in found}
    # 打分人數是分數分佈十格加起來（人氣排第一的那部）
    assert by_id[195539].scorers == 19544
    assert by_id[195539].next_episode is None  # 已播完
    assert by_id[195516].next_episode == 5
    # 還沒上映的劇場版：沒有平均分，下一集是 1
    assert by_id[143103].average_score is None
    assert by_id[143103].scorers == 233
    assert by_id[143103].next_episode == 1
    raw = record("season.fall-2026")["body"]["data"]["Page"]["media"]
    for item in raw:
        total = sum(b["amount"] for b in item["stats"]["scoreDistribution"])
        assert by_id[item["id"]].scorers == total


async def test_partial_dates_keep_only_the_known_parts() -> None:
    def start(date: dict[str, Any]) -> str | None:
        return parse_entry({"id": 1, "startDate": date}).start_date

    assert start({"year": 2026, "month": 4, "day": 8}) == "2026-04-08"
    assert start({"year": 2026, "month": 4, "day": None}) == "2026-04"
    assert start({"year": 2026, "month": None, "day": None}) == "2026"
    # 沒有月卻有日：日沒有意義
    assert start({"year": 2026, "month": None, "day": 8}) == "2026"
    assert start({"year": None, "month": None, "day": None}) is None


@respx.mock
async def test_a_bad_query_names_what_anilist_said(fake: FakeTime) -> None:
    respx.post(API_URL).mock(return_value=recorded("bad-query"))

    with pytest.raises(ProtocolMismatchError, match='Unknown argument "nope"') as caught:
        await client(fake).search("x", limit=1)

    assert "400" in str(caught.value)


@respx.mock
async def test_errors_in_a_200_answer_are_not_data(fake: FakeTime) -> None:
    respx.post(API_URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"Page": {"media": []}}, "errors": [{"message": "partial"}]}
        )
    )

    with pytest.raises(ProtocolMismatchError, match="partial"):
        await client(fake).search("x", limit=1)


@respx.mock
async def test_a_server_error_is_worth_retrying_later(fake: FakeTime) -> None:
    respx.post(API_URL).mock(return_value=httpx.Response(500, text="oops"))

    with pytest.raises(ServiceUnavailableError):
        await client(fake).search("x", limit=1)


# --- 429 與閘門 ---------------------------------------------------------------------------------


@respx.mock
async def test_a_429_waits_for_retry_after_and_asks_again(fake: FakeTime) -> None:
    route = respx.post(API_URL).mock(
        side_effect=[recorded("rate-limited.docs-example"), recorded("entries.rezero.0")]
    )

    [entry] = await client(fake).entries([21355])

    assert entry.id == 21355
    assert route.call_count == 2
    assert sum(fake.slept) >= 30
    assert fake.slept[0] == pytest.approx(30)


@respx.mock
async def test_three_429s_in_a_row_give_up_after_exactly_three_requests(fake: FakeTime) -> None:
    route = respx.post(API_URL).mock(return_value=recorded("rate-limited.docs-example"))

    with pytest.raises(ServiceUnavailableError, match="Too Many Requests"):
        await client(fake).entries([21355])

    assert RETRIES == 2
    assert route.call_count == 3
    # 第一次直接送，後兩次各等一個 Retry-After
    assert sum(fake.slept) >= 60


@respx.mock
async def test_a_429_without_retry_after_waits_the_default(fake: FakeTime) -> None:
    route = respx.post(API_URL).mock(
        side_effect=[
            httpx.Response(429, json={"errors": [{"message": "x"}]}),
            recorded("search.rezero"),
        ]
    )

    await client(fake).search(REZERO, limit=8)

    assert route.call_count == 2
    assert fake.slept[0] == pytest.approx(DEFAULT_RETRY_AFTER)


@respx.mock
async def test_a_huge_retry_after_is_capped(fake: FakeTime) -> None:
    respx.post(API_URL).mock(
        side_effect=[
            httpx.Response(
                429, json={"errors": [{"message": "x"}]}, headers={"Retry-After": "3600"}
            ),
            recorded("search.rezero"),
        ]
    )

    await client(fake).search(REZERO, limit=8)

    assert fake.slept[0] == pytest.approx(MAX_RETRY_AFTER)
    assert max(fake.slept) <= MAX_RETRY_AFTER


@respx.mock
async def test_a_429_holds_back_other_callers_sharing_the_throttle(fake: FakeTime) -> None:
    throttle = Throttle(clock=fake.time, sleep=fake.sleep)
    respx.post(API_URL).mock(return_value=recorded("rate-limited.docs-example"))
    with pytest.raises(ServiceUnavailableError):
        await client(fake, throttle).entries([21355])
    respx.reset()
    route = respx.post(API_URL).mock(return_value=recorded("search.rezero"))
    blocked_until = fake.now + 30  # 最後一次 429 剛記下的封鎖
    slept_before = len(fake.slept)

    # 另一個 client（services 每次呼叫都造新的）共用同一個閘門
    await client(fake, throttle).search(REZERO, limit=8)

    assert route.call_count == 1
    assert fake.slept[slept_before:] == [pytest.approx(30)]
    assert fake.now == pytest.approx(blocked_until)


@respx.mock
async def test_two_different_questions_are_spaced_two_seconds_apart(fake: FakeTime) -> None:
    respx.post(API_URL).mock(side_effect=[recorded("search.rezero"), recorded("entries.rezero.0")])
    anilist = client(fake)

    await anilist.search(REZERO, limit=8)
    assert fake.slept == []
    await anilist.entries([21355])

    assert fake.slept == [pytest.approx(2.0)]


@respx.mock
async def test_the_same_question_twice_is_one_request(fake: FakeTime) -> None:
    route = respx.post(API_URL).mock(return_value=recorded("search.rezero"))
    anilist = client(fake)

    first = await anilist.search(REZERO, limit=8)
    second = await anilist.search(REZERO, limit=8)

    assert route.call_count == 1
    assert first == second
    assert fake.slept == []


@respx.mock
async def test_a_failed_answer_is_not_cached(fake: FakeTime) -> None:
    route = respx.post(API_URL).mock(side_effect=[recorded("bad-query"), recorded("search.rezero")])
    anilist = client(fake)

    with pytest.raises(ProtocolMismatchError):
        await anilist.search(REZERO, limit=8)
    found = await anilist.search(REZERO, limit=8)

    assert route.call_count == 2
    assert len(found) == 6
