"""檔案系統（plan §8.6）。**唯一會動 library 的模組。**

兩件事在這裡，而且只在這裡：

- **硬鏈接**。`link()` 真的呼叫 `os.link`，`link_test()` 真的建檔、鏈接、比 inode 再清乾淨。
  只比 `st_dev` 不夠——同一個檔案系統掛兩次、btrfs 子卷、ZFS dataset、mergerfs 都會
  `EXDEV`，所以一定實際鏈接一次（brief §4.4）。
- **路徑逃逸**。凡是**把檔案放進去**的函式都要 `roots`（`link`、`probe_file`，以及 `link_test`
  的目標側），寫入位置不在其中任何一個底下就拒絕。呼叫端傳的是 Route 的 `target_path`，
  所以「寫進 library 的檔案一定在某個 Route 底下」在簽名上就跑不掉：沒有 `roots` 就沒有寫入。
  `ensure_directory` 是唯一的例外，它建的是 Berth 自己的根目錄（媒體庫目錄、complete 子目錄），
  那些路徑是設定值不是算出來的檔名。

`OSError` 一律往上丟：權限、掛載、跨裝置的錯誤原文（含 `errno`）正是「哪個容器少了哪個
掛載」唯一有用的證據，包成別的字串等於把它丟掉（brief §16.4）。
"""

from __future__ import annotations

import contextlib
import os
import shutil
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

#: 探測檔的檔名前綴。點開頭，Jellyfin 不會把它當成媒體。
PROBE_PREFIX = ".berth-probe-"


class PathEscapeError(Exception):
    """要寫的位置不在任何一個允許的根底下。"""


@dataclass(frozen=True, slots=True)
class PathFacts:
    """`stat` 的結果。硬鏈接檢查要的就是 `device` 與 `inode` 這一對。"""

    device: int
    inode: int


def ensure_directory(path: Path) -> bool:
    """把目錄準備好，回傳「這一次是不是新建的」。

    為什麼要它：`POST /Library/VirtualFolders/Paths` 對不存在的目錄回 404（2026-09-07 對
    10.11.11 實測，brief §20.7），而媒體庫目錄本來就該由 Berth 建（plan §9.1）。Berth 與
    Jellyfin 把同一個宿主目錄掛在同一個容器路徑，所以 Berth 建的目錄 Jellyfin 立刻看得到。
    """
    existed = path.is_dir()
    path.mkdir(parents=True, exist_ok=True)
    return not existed


def is_within(path: Path, root: Path) -> bool:
    """`path` 在 `root` 底下（或就是它）嗎。

    先正規化再比，所以 `<root>/../elsewhere` 與同前綴的兄弟目錄（`library-old` 之於
    `library`）都答 False。不解 symlink：解了會讓「掛載點是連結」的環境無故被拒。
    """
    root_parts = _normalised(root).parts
    return _normalised(path).parts[: len(root_parts)] == root_parts


def stat(path: Path) -> PathFacts:
    """這條路徑在 Berth 這個容器裡看得到嗎，看得到的話它是誰。看不到就丟 `OSError`。"""
    facts = path.stat()
    return PathFacts(device=facts.st_dev, inode=facts.st_ino)


def same_inode(a: Path, b: Path) -> bool:
    """兩條路徑是同一份資料嗎。硬鏈接成立的定義。"""
    left, right = stat(a), stat(b)
    return (left.device, left.inode) == (right.device, right.inode)


def free_space(path: Path) -> int:
    """這條路徑所在檔案系統的可用位元組。"""
    return shutil.disk_usage(path).free


def link(source: Path, target: Path, *, roots: Sequence[Path]) -> None:
    """把 `source` 硬鏈接到 `target`。`target` 不在 `roots` 底下就拒絕。

    **失敗不退回複製**（brief §4.4）：複製會讓刪除範圍與空間估算失真。
    """
    _guard(target, roots)
    os.link(source, target)


@contextmanager
def probe_file(directory: Path, *, roots: Sequence[Path]) -> Iterator[Path]:
    """在 `directory` 底下放一個探測檔，離開這個區塊就刪掉。

    「Jellyfin 看得到 Berth 剛寫的檔案嗎」要在檔案還在的時候問，所以清理不能由建立它的
    那一支順手做完（plan §9.5 的檢查三）。
    """
    probe = directory / f"{PROBE_PREFIX}{uuid.uuid4().hex[:8]}"
    _guard(probe, roots)
    probe.write_bytes(b"berth")
    try:
        yield probe
    finally:
        # 探測檔被別人清掉不該把檢查變成失敗——它本來就是要被刪掉的。
        with contextlib.suppress(FileNotFoundError):
            probe.unlink()


def link_test(source_dir: Path, target_dir: Path, *, roots: Sequence[Path]) -> PathFacts:
    """建暫存檔、鏈接、比對、清理（plan §8.6）。回傳兩邊共用的 device 與 inode。

    失敗（最常見的是 `EXDEV`）原樣往上丟，但兩邊的暫存檔一定清掉：留著會讓下一次重試
    撞上 `FileExistsError`，把真正的原因蓋掉。
    """
    # 來源側在呼叫端自己的 complete 目錄底下，所以它就是自己的根；守衛要管的是**目標**，
    # 也就是那個會多出一個檔案的 library 路徑。
    with probe_file(source_dir, roots=[source_dir]) as source:
        target = target_dir / source.name
        _guard(target, roots)
        try:
            os.link(source, target)
            facts = stat(target)
            if not same_inode(source, target):
                raise OSError(f"{source} and {target} are not the same inode after link()")
            return facts
        finally:
            with contextlib.suppress(FileNotFoundError):
                target.unlink()


def _guard(path: Path, roots: Sequence[Path]) -> None:
    if not any(is_within(path, root) for root in roots):
        listed = ", ".join(str(root) for root in roots) or "none"
        raise PathEscapeError(f"{path} is outside every Berth route target (allowed: {listed})")


def _normalised(path: Path) -> Path:
    """解掉 `.` 與 `..`，並在 Windows 上統一大小寫。不碰檔案系統。"""
    return Path(os.path.normcase(os.path.normpath(path)))


def under(root: str, rel_path: str) -> Path:
    """`<save path>/<相對路徑>`，兩邊都是**容器裡的 POSIX 路徑**（brief §20.7）。

    在 Windows 上用 `Path` 直接接會把分隔符換成反斜線，接出來的字串就不是那一條了；
    先用 `PurePosixPath` 接成一整條再交給 `Path`，兩種平台上得到的都是同一個位置。
    qBittorrent 報的 `save_path` 與 `torrents/files[].name` 都是這種路徑。
    """
    return Path(str(PurePosixPath(root) / rel_path))
