"""精靈第 1 步不再存帳密（M4 票 06）。

第 1 步從「建立 Berth 管理員」改成「Jellyfin 擁有者」：帳密只交給 Jellyfin（建管理員或登入、換
API key），不存下來；`settings.setup.owner` 只記是哪一個 Jellyfin 使用者。舊列的 `admin`（帳號與
介面兩組，M3 票 06c）整段拿掉，`indexer.login_password`（Berth 寫進 Prowlarr 的那一份，就是同一個
密碼）一起拿掉。

**舊列的處理**：

- 精靈已經跑完的：沒有擁有者也沒關係，`completed` 就讓門禁關著
  （`SetupSettings.owner_established`）。
  qBittorrent 與 Prowlarr 上已經設好的介面登入原封不動；Berth 之後不會再改它們，直到使用者在
  泊位上填新的一組（票 07）。
- 精靈跑到一半的：回到第 1 步，用 Jellyfin 的管理員帳密成立擁有者。套件內的那一台管理員已經
  建好時，同一組帳密就是登入（`jellyfin.claim_jellyfin`）。

降版拿掉新的鍵；舊程式讀到空的 `admin` 會回到它自己的第 1 步。

Revision ID: e8a1c4d7b293
Revises: d5c8e2a7f391
Create Date: 2026-09-28 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e8a1c4d7b293"
down_revision: str | None = "d5c8e2a7f391"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE settings SET value_json = json_remove(value_json,"
        " '$.admin', '$.indexer.login_password')"
        " WHERE key = 'setup'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE settings SET value_json = json_remove(value_json,"
        " '$.owner', '$.qbittorrent.web_ui_username', '$.qbittorrent.web_ui_password',"
        " '$.indexer.web_ui_username', '$.indexer.web_ui_password')"
        " WHERE key = 'setup'"
    )
