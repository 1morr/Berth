"""第 1 步的帳密拆成帳號與介面兩組（M3 票 06c）。

`settings.setup` 的 `admin` 原本只有一組帳密，第 3 步拿它建 Jellyfin 管理員，第 4、5 步拿它設
qBittorrent 與 Prowlarr 的介面登入。之後帳號交給 Jellyfin 就不再改，套用到兩個介面的那一組另存
在 `interface_username` / `interface_password`。**舊列抄一份過去**：兩組在交給 Jellyfin 之前本來
就相同，留空的話精靈跑到一半的舊資料重跑第 4、5 步會悄悄不設密碼（2026-09-25 使用者拍板做
migration、不在 model 上留回填）。

`SetupIndexer.login_password`（Berth 上一次寫進 Prowlarr 的密碼）不回填：空的只會讓下一次套用
多寫一次、多等 Prowlarr 重啟一次，結果相同。降版把三個鍵都拿掉，舊程式照樣讀得回來。

Revision ID: c3d8a6f1b240
Revises: f2a7c91d4e38
Create Date: 2026-09-25 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c3d8a6f1b240"
down_revision: str | None = "f2a7c91d4e38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE settings SET value_json = json_set(value_json,"
        " '$.admin.interface_username', COALESCE(json_extract(value_json, '$.admin.username'), ''),"
        " '$.admin.interface_password', COALESCE(json_extract(value_json, '$.admin.password'), ''))"
        " WHERE key = 'setup' AND json_type(value_json, '$.admin') = 'object'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE settings SET value_json = json_remove(value_json,"
        " '$.admin.interface_username', '$.admin.interface_password', '$.indexer.login_password')"
        " WHERE key = 'setup'"
    )
