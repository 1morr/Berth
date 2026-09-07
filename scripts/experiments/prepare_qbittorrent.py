"""在 qBittorrent 容器啟動前寫好設定檔，讓實驗腳本免密進得去 API。

deploy/preseed/qbittorrent/10-berth.sh 走的是 linuxserver 的 custom-cont-init.d，
「缺鍵才補」；這裡是實驗環境，直接整份寫死比較好重現 —— 容器隨時 down -v 重建，
不需要保留任何既有內容。內容以 image 的 /defaults/qBittorrent.conf 為底，
只多了子網白名單（Docker Desktop 會把發佈 port 的來源改寫成閘道，也在網段內，
所以宿主打得到；正式部署絕不能這樣開，見 plan §9.1）。

網段從 compose.yml 讀，不在這裡再寫一份 —— plan §9.2 已經決定過「避免兩處寫死」。

用法：
    python scripts/experiments/prepare_qbittorrent.py .local/experiments/qbittorrent-44
"""

from __future__ import annotations

import argparse
from pathlib import Path

COMPOSE = Path(__file__).parent / "compose.yml"

CONF = """[AutoRun]
enabled=false
program=

[LegalNotice]
Accepted=true

[Preferences]
Connection\\UPnP=false
Connection\\PortRangeMin=6881
Downloads\\SavePath=/downloads/
Downloads\\TempPath=/downloads/incomplete/
WebUI\\Address=*
WebUI\\ServerDomains=*
WebUI\\AuthSubnetWhitelistEnabled=true
WebUI\\AuthSubnetWhitelist=__SUBNET__
"""


def subnet_from_compose(compose: Path) -> str:
    """compose.yml 的 `- subnet:` 是這個網段的唯一定義處。"""
    for line in compose.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- subnet:"):
            return stripped.split(":", 1)[1].strip()
    raise SystemExit(f"{compose} 裡找不到 `- subnet:`，白名單無從得知")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config_dirs", nargs="+", type=Path)
    parser.add_argument("--compose", type=Path, default=COMPOSE)
    args = parser.parse_args()

    conf = CONF.replace("__SUBNET__", subnet_from_compose(args.compose))
    for config_dir in args.config_dirs:
        target = config_dir / "qBittorrent" / "qBittorrent.conf"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(conf, encoding="utf-8", newline="\n")
        print(f"寫入 {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
