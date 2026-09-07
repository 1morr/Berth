"""Jellyfin adapter（plan §8.2）。介面與資料型別在這裡，實作在 `client.py` / `fake.py`。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class JellyfinPublicInfo:
    """`GET /System/Info/Public` 的回應。免憑證，精靈第 2 步靠它判定來源。"""

    server_name: str
    version: str
    startup_wizard_completed: bool


class JellyfinClient(Protocol):
    """票 06 起會擴充；本票只需要免憑證的公開資訊。"""

    @property
    def base_url(self) -> str: ...

    async def public_info(self) -> JellyfinPublicInfo: ...

    async def aclose(self) -> None: ...


__all__ = ["JellyfinClient", "JellyfinPublicInfo"]
