"""結構化日誌，每一行帶 job id（brief §16.2、plan §11.2 T1.9）。

Event 是使用者可見的那一層（`events` 表、Job 時間線），log 是維運的那一層——brief §16.2
明說兩者不互相取代。這一支只管後者。

**job id 不由呼叫端傳**：那種規則第一次有人忘記就破了，而 log 是出事之後才會去看的東西，
那時候已經來不及補。它是一個 `ContextVar`——進了某個 Job 的上下文之後，那一段程式碼裡
任何模組發出的任何一行都帶著它。`ContextVar` 而不是全域變數，是因為背景迴圈（plan §3.2）
會在同一個事件迴圈上同時處理好幾個 Job。

住在 `berth/` 的根而不是某一層底下：每一層都會 log，而 `logs` 只 import 同在根的 `redact`——
它在依賴圖上與 `config` 同一個位置（plan §1.3）。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from berth.redact import redact_queries

#: 這一行屬於哪一個 Job。維運 grep 的就是這個欄位名。
JOB_FIELD = "job"

#: 每一筆 `LogRecord` 本來就有的屬性。結構化的額外欄位是「不在這一份名單上的」，
#: 所以 `logger.info("...", extra={"category": ...})` 不必再登記一次。
_BUILTIN = frozenset(
    set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)
    | {"message", "asctime", "taskName", JOB_FIELD}
)

_job: ContextVar[str] = ContextVar("berth_job", default="")

#: record factory 只裝一次（它是全域的）。
_stamped = False


@contextmanager
def job_context(job_hash: str) -> Iterator[None]:
    """這一段程式碼是在處理哪一個 Job。

    離開時還原成進來時的值（不是清空）：巢狀的情況現在還沒有，但「還原」與「清空」
    在有巢狀的那一天差別很大，而那一天不會有人回來改這裡。
    """
    token = _job.set(job_hash)
    try:
        yield
    finally:
        _job.reset(token)


def current_job() -> str:
    """現在的 job id，不在任何 Job 裡就是空字串。"""
    return _job.get()


def json_line(record: logging.LogRecord) -> str:
    """一筆 `LogRecord` → 一行 JSON。

    **一筆一行**是這個格式唯一的硬條件：`docker logs | jq` 與任何 log 收集器都靠它。
    所以 traceback 收成一個字串欄位，而不是照 `logging` 的慣例印成後面幾行。

    **網址的 query 值遮掉**（M4 票 76）：httpx 的 INFO log 印整條網址，Mikan 的 token、TMDB 的
    `api_key` 就跟著進了 `docker logs`。遮在這裡而不是關掉 httpx 的 log：每一個 logger 的每一格
    都經過這裡，包括之後才加進來的。逐格遮而不是遮整行 JSON：值的範圍若吃到跳脫的引號，那一行就
    不再是 JSON。
    """
    payload: dict[str, Any] = {
        "time": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "level": record.levelname,
        "logger": record.name,
        "message": redact_queries(record.getMessage()),
    }
    job = getattr(record, JOB_FIELD, "") or current_job()
    if job:
        payload[JOB_FIELD] = job
    if record.exc_info:
        payload["exception"] = redact_queries(logging.Formatter().formatException(record.exc_info))
    # 上面那幾格是這一行的骨架，`extra=` 蓋不掉它們——`Path`、`Enum` 這類塞不進 JSON 的值
    # 交給 `default=str`，log 不該因為一個欄位就整行不見。
    payload |= {
        key: redact_queries(value) if isinstance(value, str) else value
        for key, value in record.__dict__.items()
        if key not in _BUILTIN and key not in payload
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json_line(record)


#: 不經過 root 的 JSON handler、自己印的 logger：`uvicorn.run` 的預設 `log_config` 給
#: `uvicorn.access` 與 `uvicorn` 各一個 handler 並設 `propagate=False`，`uvicorn.error` 往上傳到
#: `uvicorn` 那一個。access log 印的是請求的路徑加 query。
_SELF_PRINTING = ("uvicorn.access", "uvicorn.error")


class _RedactQueries(logging.Filter):
    """在 record 交給別人的 handler 之前把網址的 query 值遮掉。

    先遮 `args` 的每一格：uvicorn 的 access formatter 會把 `args` 拆開來用，整句換掉它就拆不開。
    `?a=` 寫在格式字串、值在 `args` 裡的話，單看一格認不出那是網址——遮完格式化出來還有沒遮到的值，
    就整句格式化好再遮、`args` 清空。**格式字串本身不先遮**：`?a=%s` 的占位符被遮成 `***`，參數數量
    對不上，那一行整個印不出來。traceback 先格式化好放進 `exc_text`，`Formatter.format` 看到有值就
    不再自己格式化一次。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                redact_queries(arg) if isinstance(arg, str) else arg for arg in record.args
            )
        message = record.getMessage()
        if (masked := redact_queries(message)) != message:
            record.msg, record.args = masked, ()
        if record.exc_info and not record.exc_text:
            record.exc_text = redact_queries(logging.Formatter().formatException(record.exc_info))
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """把 root logger 換成一行一筆 JSON。

    **冪等**：`create_app` 每次呼叫都會走這裡（測試一輪會建幾十個 app），重覆掛 handler
    的話同一行會印好幾次——而那種 log 讀起來像是同一件事真的發生了好幾次。
    """
    _stamp_records()
    for name in _SELF_PRINTING:
        logger = logging.getLogger(name)
        if not any(isinstance(found, _RedactQueries) for found in logger.filters):
            logger.addFilter(_RedactQueries())
    root = logging.getLogger()
    root.setLevel(level)
    for handler in root.handlers:
        if isinstance(handler.formatter, _JsonFormatter):
            return
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)


def _stamp_records() -> None:
    """把 job id 蓋在**每一筆 record 建立的那一刻**，而不是格式化的那一刻。

    格式化通常就在同一個呼叫堆疊上（`logging` 是同步的），但「通常」不夠：`QueueHandler`、
    pytest 的 `caplog`、任何延後輸出的 handler 都會在上下文早就結束之後才讀那一格，
    然後寫下一個空的 job id——而那正是最需要它的那幾行（送單失敗、匯入失敗）。

    record factory 是全域的，所以這件事只做一次；`extra={"job": ...}` 會因此撞上
    `logging` 自己的「不准覆寫既有屬性」而報錯，那是刻意的——job id 由上下文決定。
    """
    global _stamped
    if _stamped:
        return
    inner = logging.getLogRecordFactory()

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = inner(*args, **kwargs)
        record.job = current_job()
        return record

    logging.setLogRecordFactory(factory)
    _stamped = True


__all__ = ["JOB_FIELD", "configure_logging", "current_job", "job_context", "json_line"]
