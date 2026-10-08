"""產生部署套件的 zip（M4 票 56、brief §19 E4）。

release workflow 與本機用的是這同一支：

    uv run python scripts/deploy_bundle.py 0.2.0   # dist/berth-deploy-0.2.0.zip 與 berth-deploy.zip

zip 解壓出一個 `berth/` 目錄：compose 檔、`.env.example`、`preseed/`。只抓 compose 一個檔
不夠——它掛 `./preseed/qbittorrent`，缺了 qBittorrent 就沒有免密白名單，Berth 進不去
（審計 P0-1）。`Dockerfile` 與 `entrypoint.sh` 只給 build image 用，不放。
`tests/unit/test_deploy_bundle.py` 守著 compose 引用的每個相對路徑都在 zip 裡。

`berth-deploy.zip` 是同一份的固定名稱：README 寫死 `releases/latest/download/berth-deploy.zip`，
GitHub 把它解到最新的正式版本（預發佈與草稿不算，brief §20.17）。

輸出可重現：成員排序、時間戳固定，同一份 `deploy/` 產生同樣的位元組。
"""

from __future__ import annotations

import argparse
import shutil
import zipfile
from collections.abc import Iterator, Sequence
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent.parent / "deploy"

#: 解壓之後的目錄名；不帶版本，升級時解到同一個地方蓋過去。
ROOT_DIR = "berth"
LATEST_NAME = "berth-deploy.zip"

#: 相對於 `deploy/`；目錄整個收進去。
MEMBERS = ("docker-compose.yml", ".env.example", "preseed")

#: zip 的最早時間（1980-01-01），讓輸出與 checkout 的時間無關。
_EPOCH = (1980, 1, 1, 0, 0, 0)


def bundle_name(version: str) -> str:
    return f"berth-deploy-{version}.zip"


def _files(deploy: Path) -> Iterator[Path]:
    for member in MEMBERS:
        path = deploy / member
        if path.is_dir():
            yield from (child for child in path.rglob("*") if child.is_file())
        elif path.is_file():
            yield path


def build(version: str, out_dir: Path, deploy: Path = DEPLOY) -> Path:
    """寫出 `berth-deploy-<version>.zip` 與同內容的 `berth-deploy.zip`，回傳前者。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = out_dir / bundle_name(version)
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(_files(deploy), key=lambda p: p.relative_to(deploy).as_posix()):
            info = zipfile.ZipInfo(f"{ROOT_DIR}/{path.relative_to(deploy).as_posix()}", _EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            # Unix 權限要 create_system=3 才會被 unzip 採用；Windows 上 stat 讀不到執行位元，
            # 所以 .sh 一律 755，與 git 裡的模式相同。
            info.create_system = 3
            info.external_attr = (0o100755 if path.suffix == ".sh" else 0o100644) << 16
            archive.writestr(info, path.read_bytes())
    shutil.copyfile(bundle, out_dir / LATEST_NAME)
    return bundle


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("version", help="版本號，不含 v（0.2.0、0.2.0-rc1）")
    parser.add_argument("--out", type=Path, default=Path("dist"), help="輸出目錄（預設 dist/）")
    args = parser.parse_args(argv)
    version = str(args.version).removeprefix("v")
    print(build(version, args.out))


if __name__ == "__main__":
    main()
