"""Plan Item 的理由改成封閉集合的 code + 參數（M2 票 07）。

`plan_items.reasons_json` 原本是解析器拼好的英文句子（`["the release name says season 2"]`），
之後是 `[{"code": "season_from_release", "params": {"season": 2}}]`——句子由前端照 code 挑。

**舊的句子清空，不轉換**（2026-09-23 使用者拍板）：它們只是說明，重新規劃就用新格式重算；
一份逐句型對回 code 的表只會用這一次，而對不上的那幾句一樣要丟。欄位型別不變（JSON 以 TEXT 存）。

Revision ID: b58e3d1f7a20
Revises: a71c4e08b5d2
Create Date: 2026-09-23 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b58e3d1f7a20"
down_revision: str | None = "a71c4e08b5d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 舊格式的第一個元素是字串（JSON 以 `"` 開頭）；新格式是物件（以 `{` 開頭）。
    op.execute(
        "UPDATE plan_items SET reasons_json = '[]' "
        "WHERE reasons_json IS NOT NULL AND json_type(reasons_json, '$[0]') = 'text'"
    )


def downgrade() -> None:
    # 舊的句子已經不在了；降版之後舊程式讀到的是空清單，與「還沒算過理由」同一個樣子。
    op.execute("UPDATE plan_items SET reasons_json = '[]' WHERE reasons_json IS NOT NULL")
