"""Prowlarr `config/host` 的欄位名實測（brief §20.6、§20.7；plan §9.3 第 5 步）。

回答一件事：精靈要替套件內的 Prowlarr 設 Forms 帳密時，PUT 進去的欄位到底叫什麼。
順便記錄 API key 的取得方式（config.xml）與設完之後的驗證行為。

用法：
    python scripts/experiments/prowlarr_host_config.py \\
        --base-url http://localhost:19696 --config .local/experiments/prowlarr
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from lib import Report, poll, request

USERNAME = "berth"
PASSWORD = "berth-experiment-2026"

# 精靈會碰到的欄位；不存在本身就是結果。
AUTH_KEYS = [
    "authenticationMethod",
    "authenticationRequired",
    "username",
    "password",
    "passwordConfirmation",
    "apiKey",
]


def read_api_key(config_dir: Path) -> str | None:
    """Prowlarr 首次啟動會自己產生 API key 並寫進 config.xml（plan §9.2）。"""
    config = config_dir / "config.xml"
    if not config.exists():
        return None
    match = re.search(r"<ApiKey>([^<]+)</ApiKey>", config.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--config", type=Path, required=True, help="Prowlarr 的 /config 宿主路徑")
    parser.add_argument("--out", type=Path, default=Path(".local/experiments/results"))
    args = parser.parse_args()

    report = Report(name="prowlarr-host-config", out_dir=args.out)
    base = args.base_url.rstrip("/")

    report.heading(f"Prowlarr（{base}）")
    poll(
        lambda: request(f"{base}/ping", timeout=5).ok,
        what="Prowlarr /ping 回 200",
        timeout=300,
    )
    api_key = poll(
        lambda: read_api_key(args.config),
        what="config.xml 出現 <ApiKey>",
        timeout=120,
    )
    report.record(
        "api_key_source", {"file": str(args.config / "config.xml"), "length": len(api_key)}
    )
    report.note(f"API key 從 config.xml 讀到，長度 {len(api_key)}")

    headers = {"X-Api-Key": api_key}
    status = request(f"{base}/api/v1/system/status", headers=headers).json()
    report.record(
        "system_status",
        {k: status.get(k) for k in ("version", "appName", "instanceName", "authentication")},
    )
    report.note(f"版本 {status.get('version')}，目前認證方式 {status.get('authentication')!r}")

    host = request(f"{base}/api/v1/config/host", headers=headers).json()
    report.record("config_host_fields", sorted(host.keys()))
    report.record(
        "config_host_auth_fields",
        {k: host.get(k) for k in AUTH_KEYS if k in host},
    )
    report.note(f"config/host 共 {len(host)} 個欄位")
    report.note(f"認證相關欄位：{ {k: host.get(k) for k in AUTH_KEYS if k in host} }")
    report.note(f"AUTH_KEYS 中不存在的：{[k for k in AUTH_KEYS if k not in host] or '無'}")

    # --- 設 Forms 帳密 ----------------------------------------------------
    report.heading("設定 Forms 帳密")
    payload: dict[str, Any] = dict(host)
    payload.update(
        {
            "authenticationMethod": "forms",
            "authenticationRequired": "enabled",
            "username": USERNAME,
            "password": PASSWORD,
            "passwordConfirmation": PASSWORD,
        }
    )
    put = request(
        f"{base}/api/v1/config/host/{host['id']}",
        method="PUT",
        headers=headers,
        json_body=payload,
    )
    report.record("put", {"status": put.status, "body": put.text[:300]})
    report.note(f"PUT /api/v1/config/host/{host['id']} -> {put.status}")

    # Prowlarr 改認證方式後會自己重啟，等它回來。
    time.sleep(5)
    poll(lambda: request(f"{base}/ping", timeout=5).ok, what="Prowlarr 重啟完成", timeout=180)

    after = request(f"{base}/api/v1/config/host", headers=headers)
    verify = {
        "with_api_key": after.status,
        "without_api_key": request(f"{base}/api/v1/config/host").status,
        "ping_anonymous": request(f"{base}/ping").status,
    }
    if after.ok:
        body = after.json()
        verify["authenticationMethod"] = body.get("authenticationMethod")
        verify["authenticationRequired"] = body.get("authenticationRequired")
        verify["username"] = body.get("username")
        verify["password_readback"] = body.get("password")
    report.record("verify", verify)
    report.note(str(verify))

    report.write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
