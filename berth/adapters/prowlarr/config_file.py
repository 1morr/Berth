"""從唯讀掛載的 Prowlarr 設定讀 API key（plan §9.2）。

Prowlarr 首次啟動就會產生 `<ApiKey>`，Berth 唯讀掛它的設定目錄，使用者不必自己抄。
用 `PROWLARR__AUTH__APIKEY` 部署的人則把同一個值也給 Berth 的環境（README 有寫）。
兩處都沒有時回空字串，精靈退回手動貼上。
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from xml.etree import ElementTree

#: Prowlarr 自己的環境變數命名（`APP__SECTION__KEY`），Berth 讀同一個名字。
API_KEY_ENV = "PROWLARR__AUTH__APIKEY"


def read_api_key(config_path: Path, environ: Mapping[str, str]) -> str:
    """環境變數優先：明確設過的值蓋過掛載進來的檔案。"""
    from_env = environ.get(API_KEY_ENV, "").strip()
    if from_env:
        return from_env
    return read_api_key_from_config(config_path)


def read_api_key_from_config(config_path: Path) -> str:
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        # 沒掛載、還沒產生、或沒有讀取權限：三種都是「讀不到」，交給精靈手動貼上。
        return ""
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return ""
    element = root.find("ApiKey")
    if element is None or element.text is None:
        return ""
    return element.text.strip()
