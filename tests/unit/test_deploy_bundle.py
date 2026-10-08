"""部署套件的 zip（M4 票 56、brief §19 E4）。

使用者拿到的是 release 上的 zip，不是 repo：compose 引用的相對路徑缺了任何一個，`docker compose up`
不會報錯——Docker 替缺的那一條建一個空目錄。缺的是 `./preseed/qbittorrent` 時，qBittorrent 沒有免密
白名單，Berth 從此進不去它（審計 P0-1）。所以這裡守的是：

- zip 裡有 compose 檔與 `.env.example`；
- compose 以**字面相對路徑**引用的每一個來源（掛載、`env_file`、頂層 `configs` / `secrets`）都在 zip
  裡，是目錄的話至少有一個檔案（zip 不存空目錄，空目錄與不存在對 Docker 是同一件事）。

`${CONFIG_ROOT}`、`${DATA_ROOT}` 展開出來的相對路徑是使用者的資料、第一次 `up` 時才建，不算。
"""

from __future__ import annotations

import shutil
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml
from deploy_bundle import LATEST_NAME, ROOT_DIR, build

from tests.unit.test_deploy_ports import DEPLOY, render

#: 兩個資料根給絕對路徑，展開之後剩下的相對路徑就只有 compose 字面寫的那幾條。
ABSOLUTE_ROOTS = {"CONFIG_ROOT": "/config-root", "DATA_ROOT": "/data-root"}


def _relative_sources(compose: Mapping[str, Any]) -> set[str]:
    sources: set[str] = set()
    for service in compose.get("services", {}).values():
        for volume in service.get("volumes", []):
            source = volume.get("source", "") if isinstance(volume, Mapping) else volume
            sources.add(str(source).split(":", 1)[0])
        env_files = service.get("env_file", [])
        for entry in [env_files] if isinstance(env_files, str) else env_files:
            sources.add(str(entry.get("path", "") if isinstance(entry, Mapping) else entry))
    for top in ("configs", "secrets"):
        for definition in (compose.get(top) or {}).values():
            sources.add(str(definition.get("file", "")))
    return {source for source in sources if source.startswith(".")}


def violations(bundle: Path) -> list[str]:
    with zipfile.ZipFile(bundle) as archive:
        names = {PurePosixPath(name) for name in archive.namelist() if not name.endswith("/")}
        root = PurePosixPath(ROOT_DIR)
        problems = [
            f"missing {required}"
            for required in ("docker-compose.yml", ".env.example")
            if root / required not in names
        ]
        if problems:
            return problems
        compose = render(archive.read(f"{ROOT_DIR}/docker-compose.yml").decode(), ABSOLUTE_ROOTS)

    for source in sorted(_relative_sources(compose)):
        target = PurePosixPath(root, *PurePosixPath(source).parts)
        if target not in names and not any(target in name.parents for name in names):
            problems.append(f"compose references {source}, which is not in the bundle")
    return problems


def test_the_bundle_holds_everything_the_compose_file_references(tmp_path: Path) -> None:
    bundle = build("1.2.3", tmp_path)

    assert bundle.name == "berth-deploy-1.2.3.zip"
    assert violations(bundle) == []


def test_the_latest_name_is_the_same_bundle(tmp_path: Path) -> None:
    bundle = build("1.2.3", tmp_path)

    assert (tmp_path / LATEST_NAME).read_bytes() == bundle.read_bytes()


def test_the_preseed_script_stays_executable(tmp_path: Path) -> None:
    with zipfile.ZipFile(build("1.2.3", tmp_path)) as archive:
        script = archive.getinfo(f"{ROOT_DIR}/preseed/qbittorrent/10-berth.sh")

    assert script.external_attr >> 16 & 0o111


# --- 規則本身的變異驗證：造一個違規證明它會紅，改一次無關的寫法證明它不會紅。 ---


@pytest.fixture
def deploy_copy(tmp_path: Path) -> Path:
    copy = tmp_path / "deploy"
    shutil.copytree(DEPLOY, copy)
    return copy


def _bundle(deploy: Path, version: str = "1.2.3") -> Path:
    return build(version, deploy.parent / "dist", deploy)


def test_a_missing_preseed_directory_is_caught(deploy_copy: Path) -> None:
    shutil.rmtree(deploy_copy / "preseed")

    assert violations(_bundle(deploy_copy)) == [
        "compose references ./preseed/qbittorrent, which is not in the bundle"
    ]


def test_an_empty_preseed_directory_is_caught(deploy_copy: Path) -> None:
    (deploy_copy / "preseed/qbittorrent/10-berth.sh").unlink()

    assert violations(_bundle(deploy_copy)) == [
        "compose references ./preseed/qbittorrent, which is not in the bundle"
    ]


def test_a_new_relative_mount_outside_the_bundle_is_caught(deploy_copy: Path) -> None:
    compose_path = deploy_copy / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    compose["services"]["berth"]["volumes"].append({"type": "bind", "source": "./extra"})
    compose_path.write_text(yaml.safe_dump(compose, allow_unicode=True), encoding="utf-8")
    (deploy_copy / "extra").mkdir()
    (deploy_copy / "extra/file").write_text("x", encoding="utf-8")

    assert violations(_bundle(deploy_copy)) == [
        "compose references ./extra, which is not in the bundle"
    ]


def test_renaming_the_preseed_script_and_the_version_is_not_a_violation(
    deploy_copy: Path,
) -> None:
    script = deploy_copy / "preseed/qbittorrent/10-berth.sh"
    script.rename(script.with_name("20-berth.sh"))

    assert violations(_bundle(deploy_copy, "2.0.0-rc1")) == []
