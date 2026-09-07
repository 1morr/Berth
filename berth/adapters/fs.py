"""檔案系統（plan §8.6）。這一票只用到「把目錄準備好」。

為什麼要它：`POST /Library/VirtualFolders/Paths` 對不存在的目錄回 404（2026-09-07 對
10.11.11 實測，brief §20.7），而媒體庫目錄本來就該由 Berth 建（plan §9.1）。Berth 與
Jellyfin 把同一個宿主目錄掛在同一個容器路徑，所以 Berth 建的目錄 Jellyfin 立刻看得到。
"""

from __future__ import annotations

from pathlib import Path


def ensure_directory(path: Path) -> bool:
    """把目錄準備好，回傳「這一次是不是新建的」。

    `OSError` 直接往上丟：權限或掛載的問題要原封不動地讓精靈顯示出來，包成別的字串
    只會讓使用者看不出是哪個容器少了哪個掛載。
    """
    existed = path.is_dir()
    path.mkdir(parents=True, exist_ok=True)
    return not existed
