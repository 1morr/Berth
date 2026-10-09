"""結構化日誌與 job 上下文（brief §16.2、plan §11.2 T1.9）。

brief §16.2 要的是「結構化，每行帶 job id」。難的不是格式而是**「每一行」**：job id 不能
靠每個呼叫端自己記得傳，那種規則第一次有人忘記就破了，而且 log 是出事之後才會去看的東西
——那時候已經來不及補。所以它是一個 `ContextVar`：進了 job 的上下文之後，那一段程式碼裡
任何模組發出的任何一行都帶著它，而寫出那一格的是 formatter 而不是呼叫端。
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

import httpx
import pytest
import respx

from berth.adapters.http import HttpSession, ProtocolMismatchError, ServiceUnavailableError
from berth.adapters.prowlarr import IndexerRejectedError
from berth.adapters.rss.client import HttpFeedFetcher
from berth.logs import JOB_FIELD, configure_logging, job_context, json_line

HASH = "4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b"


def record(message: str = "submitted", **extra: object) -> logging.LogRecord:
    """一筆 log。走真的 `Logger.makeRecord`，`extra=` 才會落在與正式路徑相同的位置。"""
    logger = logging.getLogger("berth.test")
    return logger.makeRecord(
        "berth.test", logging.INFO, __file__, 1, message, (), None, extra=extra
    )


class TestJobContext:
    def test_a_line_inside_the_context_carries_the_job_id(self) -> None:
        with job_context(HASH):
            line = json.loads(json_line(record()))

        assert line[JOB_FIELD] == HASH

    def test_a_line_outside_any_job_has_no_job_field(self) -> None:
        """健康檢查與精靈不屬於任何 Job。空字串比 `null` 糟——它讀起來像「有一個 job，
        而它的 id 是空的」。"""
        assert JOB_FIELD not in json.loads(json_line(record()))

    def test_the_context_is_restored_on_the_way_out(self) -> None:
        with job_context(HASH):
            with job_context("other"):
                inner = json.loads(json_line(record()))
            outer = json.loads(json_line(record()))

        assert inner[JOB_FIELD] == "other"
        assert outer[JOB_FIELD] == HASH

    def test_an_exception_still_restores_the_context(self) -> None:
        with pytest.raises(RuntimeError), job_context(HASH):
            raise RuntimeError("boom")

        assert JOB_FIELD not in json.loads(json_line(record()))

    @pytest.mark.asyncio
    async def test_concurrent_tasks_keep_their_own_job_id(self) -> None:
        """背景迴圈（plan §3.2）同時處理好幾個 Job，而它們共用同一個事件迴圈。

        `ContextVar` 在每個 task 各有一份，所以 poller 在 A 的上下文裡讓出控制權時，
        importer 寫的那一行不會掛上 A 的 id。**這正是不用一個全域變數的理由。**
        """

        async def emit(value: str, delay: float) -> str:
            with job_context(value):
                await asyncio.sleep(delay)
                return str(json.loads(json_line(record()))[JOB_FIELD])

        first, second = await asyncio.gather(emit("aaa", 0.02), emit("bbb", 0.0))

        assert (first, second) == ("aaa", "bbb")


class TestJsonLine:
    def test_one_json_object_per_line(self) -> None:
        line = json_line(record("job submitted"))

        assert "\n" not in line
        assert json.loads(line)["message"] == "job submitted"

    def test_carries_level_logger_and_time(self) -> None:
        line = json.loads(json_line(record()))

        assert line["level"] == "INFO"
        assert line["logger"] == "berth.test"
        # 時間要排得起來也讀得懂：與資料庫欄位同一種寫法（`models/types.UtcDateTime`）。
        assert line["time"].endswith("+00:00")

    def test_structured_extras_ride_along(self) -> None:
        """`logger.info("...", extra={"route": "tv"})` 的那幾格是結構化日誌的重點——
        維運要 grep 的是欄位，不是一句英文散文裡的一段子字串。"""
        line = json.loads(json_line(record("submitted", category="berth-tv", state="submitted")))

        assert line["category"] == "berth-tv"
        assert line["state"] == "submitted"

    def test_cjk_is_readable_rather_than_escaped(self) -> None:
        line = json_line(record("動畫"))

        assert "動畫" in line

    def test_a_traceback_is_one_field_not_extra_lines(self) -> None:
        """多行的 traceback 會把「一行一筆」的保證破掉——收成一個字串欄位。"""
        try:
            raise ValueError("no such route")
        except ValueError:
            logger = logging.getLogger("berth.test")
            failure = logger.makeRecord(
                "berth.test", logging.ERROR, __file__, 1, "boom", (), sys.exc_info()
            )

        line = json_line(failure)

        assert "\n" not in line
        assert "ValueError: no such route" in json.loads(line)["exception"]


class TestConfigureLogging:
    def test_installing_it_twice_does_not_double_every_line(self) -> None:
        """`create_app` 每次呼叫都會設定它（測試一輪裡會建幾十個 app）。"""
        root = logging.getLogger()
        before = list(root.handlers)
        try:
            configure_logging()
            once = len(root.handlers)
            configure_logging()

            assert len(root.handlers) == once
        finally:
            root.handlers = before


#: 假的 Mikan 個人 token。票 76 的起點：httpx 的 INFO log 把整條網址連 token 印進 `docker logs`。
TOKEN = "abc0token0secret"
MIKAN_FEED = f"https://mikanani.me/RSS/MyBangumi?token={TOKEN}"
PLAIN_FEED = "https://nyaa.si/rss/feed.xml"


def logged(caplog: pytest.LogCaptureFixture) -> str:
    """這一段印出來的每一行，照正式的格式（`json_line`）排好。"""
    return "\n".join(json_line(entry) for entry in caplog.records)


class TestSecretsInUrls:
    """log 與錯誤訊息裡的網址，query 的值一律遮掉（M4 票 76）。

    兩個方向都要守：秘密不見，而且**不是整行不見**——沒有 query 的網址照常完整出現。
    """

    @respx.mock
    @pytest.mark.asyncio
    async def test_a_feed_token_never_reaches_the_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        respx.get(MIKAN_FEED).respond(200, text="<rss/>")
        caplog.set_level(logging.INFO)
        fetcher = HttpFeedFetcher()
        try:
            await fetcher.fetch(MIKAN_FEED)
        finally:
            await fetcher.aclose()

        text = logged(caplog)
        assert TOKEN not in text
        # 那一行還在，只是值被遮掉：遮罩不是靠把 httpx 的 log 關掉。
        assert "https://mikanani.me/RSS/MyBangumi?token=***" in text

    @respx.mock
    @pytest.mark.asyncio
    async def test_a_url_without_a_query_is_logged_whole(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        respx.get(PLAIN_FEED).respond(200, text="<rss/>")
        caplog.set_level(logging.INFO)
        fetcher = HttpFeedFetcher()
        try:
            await fetcher.fetch(PLAIN_FEED)
        finally:
            await fetcher.aclose()

        assert f"GET {PLAIN_FEED}" in logged(caplog)

    @respx.mock
    @pytest.mark.asyncio
    async def test_a_key_sent_as_params_is_masked_too(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TMDB 的 v3 key 走 `params={"api_key": ...}`：網址是 httpx 拼出來的，呼叫端看不到。"""
        respx.get("https://api.themoviedb.org/3/configuration").respond(200, json={})
        caplog.set_level(logging.INFO)
        async with HttpSession("https://api.themoviedb.org/3") as session:
            await session.request("GET", "/configuration", params={"api_key": TOKEN})

        text = logged(caplog)
        assert TOKEN not in text
        assert "api_key=***" in text

    @respx.mock
    @pytest.mark.asyncio
    async def test_the_error_that_reaches_last_error_carries_no_token(self) -> None:
        """抓不到 Feed 時錯誤的原文寫進 `rss_feeds.last_error`，畫面與 API 都讀它。"""
        respx.get(MIKAN_FEED).mock(side_effect=httpx.ConnectError("refused"))
        fetcher = HttpFeedFetcher()
        try:
            with pytest.raises(ServiceUnavailableError) as caught:
                await fetcher.fetch(MIKAN_FEED)
        finally:
            await fetcher.aclose()

        assert TOKEN not in str(caught.value)
        assert "https://mikanani.me/RSS/MyBangumi?token=***" in str(caught.value)

    def test_extras_and_tracebacks_are_masked(self) -> None:
        """`extra={"url": ...}` 與 traceback 也是那一行的一部分。"""
        try:
            raise ValueError(f"could not read {MIKAN_FEED}")
        except ValueError:
            failure = logging.getLogger("berth.test").makeRecord(
                "berth.test",
                logging.ERROR,
                __file__,
                1,
                "boom",
                (),
                sys.exc_info(),
                extra={"url": MIKAN_FEED, "plain": PLAIN_FEED},
            )

        line = json.loads(json_line(failure))

        assert TOKEN not in json.dumps(line)
        assert line["url"] == "https://mikanani.me/RSS/MyBangumi?token=***"
        assert line["plain"] == PLAIN_FEED

    def test_the_uvicorn_access_log_is_masked(self) -> None:
        """uvicorn 的 access log 走它自己的 handler（`propagate=False`），JSON 那一層管不到。"""
        access = logging.getLogger("uvicorn.access")
        root = logging.getLogger()
        before = (list(root.handlers), list(access.filters))
        try:
            configure_logging()
            entry = access.makeRecord(
                "uvicorn.access",
                logging.INFO,
                __file__,
                1,
                '%s - "%s %s HTTP/%s" %d',
                ("127.0.0.1:5000", "GET", f"/api/rss/series?token={TOKEN}", "1.1", 200),
                None,
            )
            access.filter(entry)

            assert TOKEN not in entry.getMessage()
            assert "/api/rss/series?token=***" in entry.getMessage()
            # uvicorn 的 access formatter 把 `args` 拆成五格來用，整句換掉的話它就拆不開。
            assert isinstance(entry.args, tuple)
            assert len(entry.args) == 5

            plain = access.makeRecord(
                "uvicorn.access",
                logging.INFO,
                __file__,
                1,
                '%s - "%s %s HTTP/%s" %d',
                ("127.0.0.1:5000", "GET", "/api/health", "1.1", 200),
                None,
            )
            access.filter(plain)
            assert '"GET /api/health HTTP/1.1" 200' in plain.getMessage()
        finally:
            root.handlers, access.filters = before

    def test_a_placeholder_after_a_question_mark_still_formats(self) -> None:
        """`?a=` 在格式字串、值在 `args` 裡：先遮格式字串的話占位符變成 `***`、參數數量對不上，
        整行不見；只遮 `args` 的話認不出那一格是網址的值。"""
        error = logging.getLogger("uvicorn.error")
        root = logging.getLogger()
        before = (list(root.handlers), list(error.filters))
        try:
            configure_logging()
            entry = error.makeRecord(
                "uvicorn.error",
                logging.INFO,
                __file__,
                1,
                "GET /x?a=%s&b=%d",
                (TOKEN, 3),
                None,
            )
            error.filter(entry)

            assert entry.getMessage() == "GET /x?a=***&b=***"
        finally:
            root.handlers, error.filters = before

    def test_a_traceback_printed_by_uvicorn_is_masked(self) -> None:
        """ASGI 未處理的例外由 `uvicorn.error` 印 traceback，走的是 uvicorn 自己的 formatter。"""
        error = logging.getLogger("uvicorn.error")
        root = logging.getLogger()
        before = (list(root.handlers), list(error.filters))
        try:
            configure_logging()
            try:
                raise ValueError(f"could not read {MIKAN_FEED}")
            except ValueError:
                entry = error.makeRecord(
                    "uvicorn.error",
                    logging.ERROR,
                    __file__,
                    1,
                    "Exception in ASGI application",
                    (),
                    sys.exc_info(),
                )
            error.filter(entry)
            printed = logging.Formatter().format(entry)

            assert TOKEN not in printed
            assert "MyBangumi?token=***" in printed
        finally:
            root.handlers, error.filters = before

    def test_every_service_error_is_masked_at_construction(self) -> None:
        """`.torrent` 下載連結、`json_body` 的 `request.url` 都是直接拼進訊息的：遮在建構子，
        誰拼的都一樣。"""
        download = f"http://prowlarr:9696/1/download?apikey={TOKEN}&link=abc"

        assert str(ProtocolMismatchError(f"{download}: response is not JSON")) == (
            "http://prowlarr:9696/1/download?apikey=***&link=***: response is not JSON"
        )

    def test_prowlarr_reasons_are_masked_too(self) -> None:
        """逐條理由不經過 `args`，寫進畫面與資料庫的是它（`services/indexer.py`）。"""
        rejected = IndexerRejectedError(
            "rejected", messages=(f"Unable to connect to {MIKAN_FEED}", "no results")
        )

        assert rejected.messages == (
            "Unable to connect to https://mikanani.me/RSS/MyBangumi?token=***",
            "no results",
        )
