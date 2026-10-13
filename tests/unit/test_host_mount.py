"""既有服務的補法要印出的宿主資料夾（M4 票 63，審計 P1-6）。

compose 傳進來的是 `.env` 的 `DATA_ROOT` 原樣：補法要的是貼進**另一份** compose、`docker run` 或
Unraid 模板還指到同一個資料夾的寫法。Windows 的反斜線換成 `/`（貼進 YAML 不必管跳脫，審計實測
`C:/…:/data` 重建得起來）；相對路徑標出來——它相對於 Berth 那一份 compose 所在的資料夾，貼到別處就
指到別處。
"""

from __future__ import annotations

import pytest

from berth.services.host_mount import HostDataRoot, host_data_root


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/srv/berth/data", HostDataRoot("/srv/berth/data", relative=False)),
        ("/mnt/user/media/Berth", HostDataRoot("/mnt/user/media/Berth", relative=False)),
        (r"C:\Berth\data", HostDataRoot("C:/Berth/data", relative=False)),
        ("D:/media/berth", HostDataRoot("D:/media/berth", relative=False)),
        ("~/berth/data", HostDataRoot("~/berth/data", relative=False)),
        ("./data", HostDataRoot("./data", relative=True)),
        ("data", HostDataRoot("data", relative=True)),
        (r"..\berth\data", HostDataRoot("../berth/data", relative=True)),
        ("", HostDataRoot("", relative=False)),
    ],
)
def test_the_folder_is_written_the_way_another_compose_file_can_take_it(
    raw: str, expected: HostDataRoot
) -> None:
    assert host_data_root(raw) == expected


def test_a_trailing_slash_is_not_part_of_the_folder() -> None:
    """`/srv/berth/data/:/data` 照樣掛得上，但片段裡多一個斜線讀起來像兩個不同的資料夾。"""
    assert host_data_root("/srv/berth/data/").path == "/srv/berth/data"
    assert host_data_root("C:\\Berth\\data\\").path == "C:/Berth/data"
    assert host_data_root("/").path == "/"
