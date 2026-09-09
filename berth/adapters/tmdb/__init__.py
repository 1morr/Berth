"""TMDB adapter（plan §8.3）。M0 只用得到 `configuration`：那是「這把憑證有效」的證明。

**憑證由使用者自備**：Berth 不內建任何 provider 的 API key（brief §16.3、§20.7），唯一的來源是
`settings.services.tmdb.api_key`，取用它的地方只有 `services.tmdb.credential()`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

BASE_URL = "https://api.themoviedb.org/3"


@dataclass(frozen=True, slots=True)
class TmdbConfiguration:
    """`GET /3/configuration` 回的東西。精靈只用它證明憑證有效，M1 才用得到圖片位址。"""

    image_base_url: str


class TmdbClient(Protocol):
    async def configuration(self) -> TmdbConfiguration:
        """憑證不對時丟 `AuthFailedError`（TMDB 回 401）。"""
        ...

    async def aclose(self) -> None: ...


def credential_auth(credential: str) -> tuple[dict[str, str], dict[str, str]]:
    """憑證的兩種形狀 → 標頭與查詢參數。

    TMDB 的帳號頁同時發兩種東西，兩種都打得動 v3 端點（2026-09-08 對真 API 實測）：
    v4 的 read access token 是 JWT，走 `Authorization: Bearer`；v3 的 API key 是 32 個十六進位
    字元，走 `?api_key=`。使用者貼哪一種都該成立，所以認的是形狀而不是一個設定項。
    """
    value = credential.strip()
    if not value:
        return ({}, {})
    if value.count(".") == 2:
        return ({"Authorization": f"Bearer {value}"}, {})
    return ({}, {"api_key": value})


__all__ = ["BASE_URL", "TmdbClient", "TmdbConfiguration", "credential_auth"]
