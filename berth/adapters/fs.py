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
import errno
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
    """`stat` 的結果。硬鏈接檢查要的就是 `device` 與 `inode` 這一對。

    `size` 與 `links` 是刪除範圍的空間估算要的（brief §9.2）：**一次 `stat` 拿四個值**，
    而不是為了 `st_nlink` 再摸一次磁碟——那會讓同一個檔案的四個數字來自兩個不同的時刻。
    `links` 是這份資料現在有幾個名字，只有最後一個消失時那些位元組才回到檔案系統。
    """

    device: int
    inode: int
    size: int
    links: int


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
    return PathFacts(
        device=facts.st_dev, inode=facts.st_ino, size=facts.st_size, links=facts.st_nlink
    )


def same_inode(a: Path, b: Path) -> bool:
    """兩條路徑是同一份資料嗎。硬鏈接成立的定義。"""
    left, right = stat(a), stat(b)
    return (left.device, left.inode) == (right.device, right.inode)


def free_space(path: Path) -> int:
    """這條路徑所在檔案系統的可用位元組。"""
    return shutil.disk_usage(path).free


def remove(path: Path, *, roots: Sequence[Path]) -> bool:
    """刪掉一個檔案。真的刪了回 `True`，本來就不在回 `False`。

    **刪除也是寫入**，所以它與 `link` 走同一道守衛：要刪的位置不在 `roots` 底下就拒絕。
    呼叫端傳的是 Route 的目標（刪 library 鏈接）或 complete root（刪來源），所以「Berth 只
    刪得掉自己放進去的那幾層」在簽名上就跑不掉。

    **單位是一個檔案**：目錄一律拒絕（`IsADirectoryError`）。帳本與 `job_files` 記的都是
    檔案，而一個目錄底下可能有 Berth 不知道的東西——brief §9.1 的 `unmanaged_library_file`
    說的就是那些，它們永不自動刪。空掉的目錄由 `prune_empty_parents` 收。

    **不在了不是失敗**：帳本上那一條可能早就被人在 Jellyfin 或檔案總管裡刪掉了（brief §9.5
    的 `library_link_missing` 就是這件事），而刪除要做的事本來就已經成立。
    """
    _guard(path, roots)
    if path.is_dir():
        raise IsADirectoryError(errno.EISDIR, "refusing to remove a folder", str(path))
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def remove_tree(path: Path, *, roots: Sequence[Path]) -> bool:
    """刪掉一整個目錄（或單一檔案），回傳「真的刪了什麼沒有」（M2 票 09 的 `orphan_complete`）。

    **只有一個呼叫端，而它的單位本來就是一整棵**：complete 底下一個 torrent 的內容根，
    qBittorrent 與 Berth 都不認得它（brief §9.1）。`remove` 刻意不刪目錄，理由是目錄底下可能
    有 Berth 不知道的東西——這裡正是使用者看過那一句、按了確認之後才走得到的那一條。

    守衛比 `remove` 多一道：**根本身不刪**。`roots` 傳的是每一條 Route 的 complete 子目錄，
    刪掉它等於刪掉那一條 Route 之後每一筆下載的落點。
    """
    root = root_of(path, roots)
    if _normalised(path) == _normalised(root):
        raise PathEscapeError(f"refusing to remove the root {root} itself")
    if not path.exists():
        return False
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def prune_empty_parents(path: Path, *, root: Path) -> None:
    """把 `path` 留下的空目錄一層層收掉，收到 `root` 為止（不含 `root` 自己）。

    刪掉一季裡最後一集之後留著 `Show/Season 01/` 兩層空目錄，Jellyfin 的牆上那部作品就還在
    ——畫面說刪掉了，媒體庫說沒有。`root` 本身不碰：媒體庫目錄與 complete root 是設定值，
    不是這一次刪除建出來的東西。

    **只刪空的**：`rmdir` 對非空目錄丟 `OSError`，遇到第一個就停——那底下還有別人的檔案。
    """
    current = path.parent
    while is_within(current, root) and _normalised(current) != _normalised(root):
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def link(source: Path, target: Path, *, roots: Sequence[Path]) -> None:
    """把 `source` 硬鏈接到 `target`。`target` 不在 `roots` 底下就拒絕。

    目標那幾層資料夾順手建好：入庫的目標是算出來的檔名（`<作品>/Season 01/…`，plan §5），
    第一次一定不存在。**守衛在建資料夾之前**，所以被擋下來的那一次不會在媒體庫外面留下
    空目錄——建資料夾也是一次寫入。

    **失敗不退回複製**（brief §4.4）：複製會讓刪除範圍與空間估算失真。
    """
    _guard(target, roots)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
        # 仍是同一個 `errno` 的 `OSError`，只多說一件事：兩邊各自落在哪一個掛載上。系統原文只說
        # 「跨裝置」，而使用者要改的是 compose 裡的哪兩行 volume（brief §16.4）。
        reason = exc.strerror or "Invalid cross-device link"
        source_mount, target_mount = mount_point(source), mount_point(target)
        if source_mount != target_mount:
            where = (
                f"the source is on the mount at {source_mount} and the target is on the mount "
                f"at {target_mount}; a hard link cannot cross mounts, so mount one common "
                "parent folder into Berth, qBittorrent and Jellyfin at the same path instead of "
                "separate download and library folders"
            )
        else:
            # 同一個掛載底下仍然 `EXDEV`：mergerfs 的分支、btrfs 子卷、ZFS dataset 都會這樣
            # （brief §4.4、§20.2）。這時候叫人「掛同一個父目錄」是錯的建議——他已經這樣掛了。
            where = (
                f"both paths are under the mount at {source_mount}, but the file system behind "
                "it splits them (mergerfs branches, btrfs subvolumes and ZFS datasets do this); "
                "put the download and library folders on the same underlying file system"
            )
        raise OSError(errno.EXDEV, f"{reason}: {where}", str(source), None, str(target)) from exc


def replace_link(source: Path, target: Path, *, roots: Sequence[Path]) -> None:
    """讓 `target` 這個名字改指 `source`，**一步換過去**（M2 票 08 的「取代舊版」）。

    同一條路徑上舊的換新的：先拆再鏈的話中間有一段那一集不存在，而鏈接失敗時舊的已經沒了。
    所以先在同一個資料夾裡鏈一個臨時名字，再 `Path.replace`（`os.replace`）蓋過去——同一個
    檔案系統上的 rename 是原子的，任何時刻那個名字底下都是一個完整的檔案。失敗時臨時名字
    收掉，舊的不動。
    臨時名字點開頭（同 `PROBE_PREFIX`），Jellyfin 不會在那一瞬間把它當成媒體。
    """
    _guard(target, roots)
    staged = target.with_name(f"{PROBE_PREFIX}{uuid.uuid4().hex}{target.suffix}")
    link(source, staged, roots=roots)
    try:
        staged.replace(target)
    except OSError:
        with contextlib.suppress(OSError):
            staged.unlink()
        raise


def mount_point(path: Path) -> Path:
    """這條路徑落在哪一個掛載上。

    **還不存在的路徑也答得出來**：入庫目標在鏈接之前一定不存在，但它會落在哪個掛載上，
    由它最近那個存在的祖先決定。不解 symlink，理由與 `is_within` 相同。
    """
    current = path.absolute()
    while not current.exists() and current != current.parent:
        current = current.parent
    while not os.path.ismount(current) and current != current.parent:
        current = current.parent
    return current


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


def root_of(path: Path, roots: Sequence[Path]) -> Path:
    """`path` 落在 `roots` 的哪一個底下。都不在就丟 `PathEscapeError`。

    守衛與「收掉空目錄要收到哪一層」問的是同一件事，所以只算一次：`remove` 之後呼叫端拿著
    這個答案去 `prune_empty_parents`，不必自己再走一次 `is_within`。
    """
    for root in roots:
        if is_within(path, root):
            return root
    listed = ", ".join(str(root) for root in roots) or "none"
    raise PathEscapeError(f"{path} is outside every Berth route target (allowed: {listed})")


def top_level_under(path: Path, roots: Sequence[Path]) -> Path | None:
    """`path` 落在 `roots` 的哪一個底下的**第一層**那一項。都不在就是 `None`。

    complete 的一個 torrent 就是 `<complete>/<route-slug>/` 底下的一項（brief §4.1）：多檔的
    是一個目錄，單檔的就是那個檔案。qBittorrent 報的 `content_path`、帳本的來源都比這一層深，
    「這一項有沒有主」要先把它們收到這一層再比。
    """
    for root in roots:
        if not is_within(path, root):
            continue
        parts = _normalised(path).parts[len(_normalised(root).parts) :]
        return root / parts[0] if parts else None
    return None


def path_key(path: Path | str) -> str:
    """比兩條路徑是不是同一條時用的鍵。

    帳本記的是容器裡的 POSIX 字串（`models/ledger.py`），走訪目錄拿到的是這台機器的 `Path`：
    同一個檔案，兩種寫法。逐字比的話每一個入庫的檔案都會被當成不認得的。規則與 `is_within`
    同一份（`.` 與 `..`、Windows 的大小寫與分隔符）。
    """
    return str(_normalised(Path(path)))


def _guard(path: Path, roots: Sequence[Path]) -> None:
    root_of(path, roots)


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
