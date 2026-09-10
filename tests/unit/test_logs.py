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

import pytest

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
