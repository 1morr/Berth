"""一條纜繩為什麼沒繫上：例外 → 封閉的代碼（`services.steps.failure_of`，M4 票 21）。

畫面照代碼選人話，原文收進技術細節。分類錯了，人話就說錯原因——這正是票 21 要消滅的
（TMDB 的 401 被說成「查網路」、qBittorrent 登入失敗被說成「分類衝突」）。
"""

from __future__ import annotations

import errno

import pytest

from berth.adapters.fs import PathEscapeError
from berth.adapters.http import (
    AuthFailedError,
    NotFoundError,
    ProtocolMismatchError,
    ServiceBusyError,
    ServiceError,
    ServiceNotDeployedError,
    ServiceUnavailableError,
)
from berth.adapters.qbittorrent import IpBannedError
from berth.domain import StepFailure, StepStatus
from berth.models import SetupStep
from berth.services.steps import StepFailedError, failed_step, failure_of, step_views


@pytest.mark.parametrize(
    ("error", "failure"),
    [
        (ServiceNotDeployedError("GET /: host does not resolve"), StepFailure.NOT_DEPLOYED),
        (ServiceUnavailableError("GET /: connection refused"), StepFailure.UNREACHABLE),
        (ServiceBusyError("GET /: 503 still loading"), StepFailure.STARTING),
        (AuthFailedError("GET /configuration: 401"), StepFailure.AUTH_REJECTED),
        (ProtocolMismatchError("GET /: response is not JSON"), StepFailure.PROTOCOL_MISMATCH),
        (NotFoundError("movie/1: no such title"), StepFailure.NOT_FOUND),
        (PathEscapeError("/etc is outside /data"), StepFailure.BERTH_CANNOT_WRITE),
        (ServiceError("prowlarr did not come back"), StepFailure.UNEXPECTED),
        (ValueError("anything else"), StepFailure.UNEXPECTED),
    ],
)
def test_each_classified_error_has_its_code(error: Exception, failure: StepFailure) -> None:
    assert failure_of(error) == (failure, {})


def test_a_ban_is_not_read_as_wrong_credentials() -> None:
    """`IpBannedError` 是 `AuthFailedError` 的子類：被封與帳密不對的下一步不同（brief §20.2），
    對照表的順序錯了，被封就會被說成「帳密不對」。"""
    assert failure_of(IpBannedError("auth/login: 403"))[0] is StepFailure.IP_BANNED


def test_a_file_error_names_the_path_berth_could_not_write() -> None:
    error = PermissionError(errno.EACCES, "Permission denied", "/data/torrent/complete/tv")
    assert failure_of(error) == (
        StepFailure.BERTH_CANNOT_WRITE,
        {"path": "/data/torrent/complete/tv"},
    )


def test_a_judged_failure_keeps_its_code_and_params() -> None:
    error = StepFailedError(StepFailure.PATH_NOT_VISIBLE, "/tv is not visible", path="/tv")
    step = failed_step("download_path", error)
    assert (step.status, step.failure, step.params, step.error) == (
        StepStatus.FAILED,
        StepFailure.PATH_NOT_VISIBLE,
        {"path": "/tv"},
        "/tv is not visible",
    )


def test_a_failure_stored_before_codes_existed_reads_as_unexpected() -> None:
    """票 21 之前存下的失敗沒有代碼：讀出來是 `unexpected`（畫面說「沒預料到的錯誤」，原文照樣在），
    下一次檢查就換成新的。沒失敗的沒有代碼。"""
    old = SetupStep.model_validate({"key": "category", "status": "failed", "error": "GET /: 403"})
    passed = SetupStep(key="hardlink", status=StepStatus.OK, detail="dev=69")

    views = step_views([old, passed])

    assert [view.failure for view in views] == [StepFailure.UNEXPECTED, None]
