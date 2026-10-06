"""頁 4 只接 Prowlarr：拿掉通用 Torznab 端點（M4 票 37、brief §19 D3）。

`settings.services.indexer` 的 `kind` 拿掉了。存著 `torznab` 的安裝，那條位址是 Jackett 之類的
Torznab 網址，Berth 現在只會把它當 Prowlarr 去連，所以連同頁 4 的結論一起清掉：

- `settings.services.indexer` 的位址與 key 清空——搜尋說「還沒接」，健康頁那一格是未設定。
- `settings.setup` 的 Prowlarr 選擇與頁 4 的纜繩清掉，頁 4 回到二選一（待處理）。介面登入那兩格
  本來就只有套件內才有，一起清掉不會丟到別人的東西。

接 Prowlarr 的安裝只少了 `kind` 這個鍵，其餘不動。

**降版不還原**：清掉的位址與 key 回不來；舊程式讀到沒有 `kind` 的設定就當成 `prowlarr`，
頁 4 一樣是待處理。

Revision ID: b4ca280eaeca
Revises: f3c9a1d6b2e8
Create Date: 2026-10-07 12:00:00.000000
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "b4ca280eaeca"
down_revision: str | None = "f3c9a1d6b2e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    rows = _settings()
    indexer = rows.get("services.indexer")
    if indexer is None:
        return
    torznab = indexer.pop("kind", "prowlarr") == "torznab"
    if torznab:
        indexer["base_url"] = ""
        indexer["api_key"] = ""
    _write("services.indexer", indexer)

    setup = rows.get("setup")
    if not torznab or setup is None:
        return
    (setup.get("choices") or {}).pop("prowlarr", None)
    part = setup.setdefault("indexer", {})
    part["steps"] = []
    part["skipped"] = False
    part["web_ui_username"] = ""
    part["web_ui_password_hash"] = ""
    _write("setup", setup)


def downgrade() -> None:
    """舊程式的 `kind` 預設就是 `prowlarr`，沒有東西要寫回去。"""


def _settings() -> dict[str, dict[str, Any]]:
    bind = op.get_bind()
    return {
        key: json.loads(value)
        for key, value in bind.execute(sa.text("SELECT key, value_json FROM settings"))
    }


def _write(key: str, value: dict[str, Any]) -> None:
    op.get_bind().execute(
        sa.text("UPDATE settings SET value_json = :value WHERE key = :key"),
        {"key": key, "value": json.dumps(value, ensure_ascii=False)},
    )
