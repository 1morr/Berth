"""精靈的偵測判定轉成使用者的選擇；介面密碼只存雜湊（M4 票 15）。

2026-09-29 起「套件內 / 既有」由使用者在服務頁選（brief §16.3），`settings.setup.services`（逐服務的
偵測判定）與 `probe_started_at` 換成 `settings.setup.choices`。同日起 Berth 寫進套件內 qBittorrent /
Prowlarr 的介面密碼只存加鹽雜湊（brief §19 2026-09-29 ⑤）。

**判定怎麼轉**：

- 有結論的判定（套件內或既有）就是那時候的來源，轉成同一個來源的選擇；位址照判定上的那一條。連得上的
  測試是綠的，連不上的是紅的——使用者回到那一頁按「重新測試」或改選。
- 還在探測、逾時的沒有來源，丟掉：那一頁回到二選一。既有而連線沒解掉、也不是使用者填過的
  （例如從 `COMPOSE_PROFILES` 拿掉、還沒填位址）同樣丟掉——那是偵測猜的，使用者沒選過。

**密碼怎麼轉**：

- 套件內 qBittorrent：票 07 把 Berth 設的 WebUI 登入存在 `settings.services.qbittorrent` 的帳密
  （Berth 也拿它連）。帳號與雜湊搬到 `settings.setup.qbittorrent.web_ui_*`，帳密清空：
  Berth 連套件內那一台靠免密白名單（plan §9.2）。既有的那一台的帳密是 Berth 的連線憑證，
  照舊（brief §16.2）。
- `settings.setup.indexer.web_ui_password`（Prowlarr 的介面密碼，明文）換成 `web_ui_password_hash`。

降版把選擇轉回已釘住的判定（`configured`），雜湊丟掉：明文回不來，舊程式看到空密碼就是「還沒設過」，
在泊位上再設一次就對了。

Revision ID: f3c9a1d6b2e8
Revises: e8a1c4d7b293
Create Date: 2026-09-29 12:00:00.000000
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "f3c9a1d6b2e8"
down_revision: str | None = "e8a1c4d7b293"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: 舊的判定理由 → 新的測試理由。綠燈的那幾種收成「連上了」，Jellyfin 的兩種照舊。
_REASONS = {
    "setup_pending": "setup_pending",
    "setup_completed": "setup_completed",
    "anonymous_ok": "connected",
    "no_indexers": "connected",
    "has_indexers": "connected",
    "connected": "connected",
    "auth_required": "auth_required",
    "ip_banned": "ip_banned",
    "api_key_missing": "api_key_missing",
    "not_deployed": "not_deployed",
    "unreachable": "unreachable",
    "starting": "starting",
    "protocol_mismatch": "protocol_mismatch",
}

#: 舊程式的 `UNRESOLVED_REASONS`：還要使用者補連線資訊的那幾種。
_UNRESOLVED = frozenset(
    {
        "not_deployed",
        "unreachable",
        "starting",
        "auth_required",
        "protocol_mismatch",
        "api_key_missing",
    }
)


def upgrade() -> None:
    rows = _settings()
    setup = rows.get("setup")
    if setup is None:
        return
    probes: dict[str, dict[str, Any]] = setup.pop("services", None) or {}
    setup.pop("probe_started_at", None)
    setup["choices"] = {
        kind: choice for kind, probe in probes.items() if (choice := _choice(probe)) is not None
    }

    qbittorrent_setup = setup.setdefault("qbittorrent", {})
    # 票 06 一度把這兩格放在這裡（票 07 搬走了），殘留的明文一起丟掉。
    qbittorrent_setup.pop("web_ui_password", None)
    connection = rows.get("services.qbittorrent")
    if setup["choices"].get("qbittorrent", {}).get("origin") == "bundled" and connection:
        if connection.get("username"):
            qbittorrent_setup["web_ui_username"] = connection["username"]
            qbittorrent_setup["web_ui_password_hash"] = (
                hash_password(connection["password"]) if connection.get("password") else ""
            )
        connection["username"] = ""
        connection["password"] = ""
        _write("services.qbittorrent", connection)

    indexer_setup = setup.setdefault("indexer", {})
    plain = indexer_setup.pop("web_ui_password", "")
    if indexer_setup.get("web_ui_username"):
        indexer_setup["web_ui_password_hash"] = hash_password(plain) if plain else ""
    _write("setup", setup)


def downgrade() -> None:
    rows = _settings()
    setup = rows.get("setup")
    if setup is None:
        return
    choices: dict[str, dict[str, Any]] = setup.pop("choices", None) or {}
    setup["services"] = {kind: _probe(choice) for kind, choice in choices.items()}
    for group in ("qbittorrent", "indexer"):
        part = setup.get(group) or {}
        part.pop("web_ui_password_hash", None)
        if group == "qbittorrent":
            part.pop("web_ui_username", None)
        else:
            part["web_ui_password"] = ""
    _write("setup", setup)


def hash_password(password: str) -> str:
    """與 `services.steps.hash_password` 同一個格式，**凍結在這裡**：migration 不隨應用程式碼
    改變行為。格式要是改了，`password_matches` 仍得讀得懂這一版寫下的。"""
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def _choice(probe: dict[str, Any]) -> dict[str, Any] | None:
    origin = probe.get("origin")
    reason = _REASONS.get(probe.get("reason", ""), "unreachable")
    if origin not in ("bundled", "existing"):
        return None
    unresolved = probe.get("reason") in _UNRESOLVED
    if origin == "existing" and unresolved and not probe.get("configured"):
        return None
    return {
        "origin": origin,
        "base_url": probe.get("base_url", ""),
        "test": {
            "state": "failed" if unresolved else "ok",
            "reason": reason,
            "detail": probe.get("detail", ""),
            "checked_at": probe.get("checked_at") or datetime.now(UTC).isoformat(),
            "waiting_since": None,
        },
    }


def _probe(choice: dict[str, Any]) -> dict[str, Any]:
    test = choice.get("test") or {}
    return {
        "origin": choice["origin"],
        "reason": test.get("reason") or "connected",
        "detail": test.get("detail", ""),
        "base_url": choice.get("base_url", ""),
        "checked_at": test.get("checked_at") or datetime.now(UTC).isoformat(),
        "configured": True,
    }


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
