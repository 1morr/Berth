"""主機名解不解得到（M4 票 30）。

套件內三台的位址是 compose 的服務名；容器不在這套 compose 裡（從 `COMPOSE_PROFILES` 拿掉）或停著，
它的名字就不在 compose 的網路上。服務頁進頁時只問這一件事——不對服務發任何請求（brief §19）。
"""

from __future__ import annotations

import asyncio
import socket
from typing import Protocol

#: 一個名字最多等多久。Docker 的內建 DNS 把不認得的名字轉給宿主的 DNS，解不到的單標籤名要等
#: 上游答完：Windows 開發機上 `jellyfin` 實測 7 秒才 gaierror（2026-10-03）。畫面不等它，
#: 晚一點加註而已。
RESOLVE_TIMEOUT_SECONDS = 10.0


class HostResolver(Protocol):
    async def resolves(self, host: str) -> bool:
        """`False` 只代表確定解不到；問不出結論時是 `True`，畫面才不會說錯「沒有起」。"""
        ...


class SystemHostResolver:
    """系統的解析器（`getaddrinfo`），與 httpx 連線時走的是同一條。"""

    async def resolves(self, host: str) -> bool:
        loop = asyncio.get_running_loop()
        try:
            async with asyncio.timeout(RESOLVE_TIMEOUT_SECONDS):
                await loop.getaddrinfo(host, None)
        except socket.gaierror:
            # 與 `http.is_dns_failure` 同一條：任何一種 gaierror 都是那個服務不在 compose 的網路上。
            return False
        except TimeoutError:
            return True
        return True
