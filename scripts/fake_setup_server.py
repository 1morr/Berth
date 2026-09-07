"""用 Fake adapter 起一台 Berth，讓精靈的 UI 不必真的有四個容器也能實跑驗證。

真的 API、真的資料庫、真的前端 build——只有三個外部服務換成 `adapters/*/fake.py`。
指令與情境見根目錄 README 的〈設定精靈的 Fake 後端〉。
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import uvicorn

from berth.adapters.http import AuthFailedError, ServiceNotDeployedError, ServiceUnavailableError
from berth.adapters.jellyfin import JellyfinClient, JellyfinPublicInfo
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr import ProwlarrClient, ProwlarrIndexer
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent import QbittorrentClient
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.api.deps import get_client_factory, get_setup_probes
from berth.config import load_config
from berth.main import create_app
from berth.services.setup import SetupProbes


def bundled() -> SetupProbes:
    """乾淨的 compose：三個服務都還沒被設定過。"""
    return SetupProbes(
        jellyfin=FakeJellyfinClient(),
        qbittorrent=FakeQbittorrentClient(),
        prowlarr=FakeProwlarrClient(),
        prowlarr_api_key="00000000000000000000000000000001",
    )


def mixed() -> SetupProbes:
    """NAS 的常見組合：Jellyfin 從 COMPOSE_PROFILES 拿掉、qBittorrent 已設密碼。"""
    return SetupProbes(
        jellyfin=FakeJellyfinClient(error=ServiceNotDeployedError("no such host")),
        qbittorrent=FakeQbittorrentClient(error=AuthFailedError("403")),
        prowlarr=FakeProwlarrClient(
            indexers=[ProwlarrIndexer(id=1, name="Nyaa.si", enabled=True)],
        ),
        prowlarr_api_key="00000000000000000000000000000001",
    )


def starting() -> SetupProbes:
    """容器還在啟動：qBittorrent 連不上，其餘兩個已就緒。"""
    return SetupProbes(
        jellyfin=FakeJellyfinClient(
            public_info=JellyfinPublicInfo(
                server_name="jellyfin", version="10.10.7", startup_wizard_completed=False
            )
        ),
        qbittorrent=FakeQbittorrentClient(error=ServiceUnavailableError("connection refused")),
        prowlarr=FakeProwlarrClient(),
        prowlarr_api_key="",
    )


SCENARIOS = {"bundled": bundled, "mixed": mixed, "starting": starting}


class FakeClientFactory:
    """既有服務的「測試連線」永遠連得上，用來走通表單那條路徑。

    Prowlarr 的索引站數量由情境決定：`mixed` 是使用者自己在用的那一台（有索引站，判既有），
    其餘情境是「套件內但 Berth 讀不到 key」，貼上 key 之後應該判回套件內。
    """

    def __init__(self, indexers: list[ProwlarrIndexer] | None = None) -> None:
        self._indexers = indexers or []

    def jellyfin(self, base_url: str) -> JellyfinClient:
        return FakeJellyfinClient(
            base_url=base_url,
            public_info=JellyfinPublicInfo(
                server_name="nas", version="10.10.7", startup_wizard_completed=True
            ),
        )

    def qbittorrent(self, base_url: str) -> QbittorrentClient:
        return FakeQbittorrentClient(base_url=base_url)

    def prowlarr(self, base_url: str, api_key: str) -> ProwlarrClient:
        return FakeProwlarrClient(base_url=base_url, indexers=list(self._indexers))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="bundled")
    parser.add_argument("--port", type=int, default=8484)
    parser.add_argument(
        "--config-root",
        type=Path,
        default=None,
        help="預設是一個新的暫存目錄，所以每次啟動都是乾淨環境。",
    )
    args = parser.parse_args(argv)

    config_root = args.config_root or Path(tempfile.mkdtemp(prefix="berth-fake-"))
    config = load_config({"CONFIG_ROOT": str(config_root), "DATA_ROOT": str(config_root / "data")})
    app = create_app(config)

    probes = SCENARIOS[args.scenario]()

    async def override_probes() -> AsyncIterator[SetupProbes]:
        yield probes

    in_use = [ProwlarrIndexer(id=1, name="Nyaa.si", enabled=True)]
    factory = FakeClientFactory(in_use if args.scenario == "mixed" else [])

    app.dependency_overrides[get_setup_probes] = override_probes
    app.dependency_overrides[get_client_factory] = lambda: factory

    print(f"scenario={args.scenario} config_root={config_root}", file=sys.stderr)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
