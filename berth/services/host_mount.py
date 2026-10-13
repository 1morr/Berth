"""Berth 的 `/data` 在宿主上是哪個資料夾：既有服務的掛載補法印出它（M4 票 63，審計 P1-6）。

既有的 qBittorrent 與 Jellyfin 要把**同一個**宿主資料夾掛在 `/data`（brief §16.4）。原本補法是
`${DATA_ROOT}:/data`，使用者得自己去 Berth 的 `.env` 找值；compose 現在把那個值原樣傳進來
（`Config.host_data_root`），這裡把它換成貼得進另一份 compose、`docker run` 與 Unraid 模板的寫法。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: `C:/…`：反斜線已經換掉之後的 Windows 磁碟機路徑。
_DRIVE = re.compile(r"^[A-Za-z]:/")


@dataclass(frozen=True, slots=True)
class HostDataRoot:
    """`.env` 的 `DATA_ROOT`，照補法要的寫法。"""

    #: Windows 的反斜線換成 `/`（貼進 YAML 不必跳脫，Docker Desktop 照收，審計 S2 實測）、拿掉結尾的
    #: 斜線。compose 沒傳進來是空字串：補法照舊印 `${DATA_ROOT}`，說去哪裡找值。
    path: str
    #: 相對路徑：它相對於 Berth 那一份 compose 所在的資料夾，貼到別處就指到別處——補法說要換成
    #: 絕對路徑。`~` 開頭不算：同一個帳號在哪一份 compose 裡展開都是同一個家目錄。
    relative: bool


def host_data_root(raw: str) -> HostDataRoot:
    path = raw.strip().replace("\\", "/")
    trimmed = path.rstrip("/")
    # 根目錄本身（`/`、`C:/`）的斜線是它的一部分。
    if trimmed and not re.fullmatch(r"[A-Za-z]:", trimmed):
        path = trimmed
    relative = bool(path) and not (path.startswith(("/", "~")) or _DRIVE.match(path))
    return HostDataRoot(path=path, relative=relative)
