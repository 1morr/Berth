"""fs adapter（plan §8.6、票 09）。

這是唯一會動 library 的模組，所以它的單元測試就是「硬鏈接與路徑逃逸」的規格：真的建檔、
真的 `link()`、真的比 inode。跑得動這一組，就代表這台機器的檔案系統撐得住 Berth 的入庫方式。
"""

from __future__ import annotations

import errno
import os
import shutil
from pathlib import Path

import pytest

from berth.adapters.fs import (
    PathEscapeError,
    ensure_directory,
    free_space,
    is_within,
    link,
    link_test,
    mount_point,
    probe_file,
    prune_empty_parents,
    remove,
    root_of,
    same_inode,
    stat,
)


def test_ensure_directory_reports_whether_it_created_one(tmp_path: Path) -> None:
    target = tmp_path / "library" / "movies"

    assert ensure_directory(target) is True
    assert ensure_directory(target) is False
    assert target.is_dir()


class TestIsWithin:
    def test_a_child_is_within_its_root(self, tmp_path: Path) -> None:
        assert is_within(tmp_path / "library" / "movies" / "a.mkv", tmp_path / "library") is True

    def test_the_root_itself_is_within_it(self, tmp_path: Path) -> None:
        assert is_within(tmp_path / "library", tmp_path / "library") is True

    def test_a_sibling_with_a_shared_prefix_is_not_within(self, tmp_path: Path) -> None:
        """`/data/library-old` 不在 `/data/library` 底下。純字串前綴比對會答錯。"""
        assert is_within(tmp_path / "library-old" / "a.mkv", tmp_path / "library") is False

    def test_a_dot_dot_escape_is_not_within(self, tmp_path: Path) -> None:
        escaping = tmp_path / "library" / ".." / "torrent" / "a.mkv"

        assert is_within(escaping, tmp_path / "library") is False


class TestStat:
    def test_reports_device_and_inode(self, tmp_path: Path) -> None:
        file = tmp_path / "a.mkv"
        file.write_bytes(b"berth")

        facts = stat(file)

        assert facts.inode == file.stat().st_ino
        assert facts.device == file.stat().st_dev

    def test_a_missing_path_raises_the_os_error(self, tmp_path: Path) -> None:
        """包成別的字串只會讓使用者看不出是哪個容器少了哪個掛載（brief §16.4）。"""
        with pytest.raises(FileNotFoundError):
            stat(tmp_path / "nowhere")


class TestFileFacts:
    """空間估算靠這兩個（brief §9.2）：**一次 `stat` 拿四個值**，不為了 `st_nlink` 再摸一次磁碟。"""

    def test_reports_the_size_and_a_lone_file_has_one_name(self, tmp_path: Path) -> None:
        path = tmp_path / "solo.mkv"
        path.write_bytes(b"berth")

        facts = stat(path)

        assert (facts.size, facts.links) == (5, 1)

    def test_a_hard_linked_file_counts_both_names(self, tmp_path: Path) -> None:
        """只有**最後一個**名字消失時那些位元組才回到檔案系統。"""
        source = tmp_path / "source.mkv"
        source.write_bytes(b"x")
        os.link(source, tmp_path / "library.mkv")

        assert stat(source).links == 2


class TestSameInode:
    def test_a_hard_link_is_the_same_inode(self, tmp_path: Path) -> None:
        source = tmp_path / "a.mkv"
        source.write_bytes(b"berth")
        target = tmp_path / "b.mkv"
        os.link(source, target)

        assert same_inode(source, target) is True

    def test_a_copy_is_not(self, tmp_path: Path) -> None:
        source = tmp_path / "a.mkv"
        source.write_bytes(b"berth")
        target = tmp_path / "b.mkv"
        shutil.copyfile(source, target)

        assert same_inode(source, target) is False


class TestLink:
    def test_links_into_an_allowed_root(self, tmp_path: Path) -> None:
        complete = tmp_path / "complete"
        library = tmp_path / "library"
        ensure_directory(complete)
        ensure_directory(library)
        source = complete / "a.mkv"
        source.write_bytes(b"berth")

        link(source, library / "a.mkv", roots=[library])

        assert same_inode(source, library / "a.mkv") is True

    def test_refuses_a_target_outside_every_root(self, tmp_path: Path) -> None:
        """寫入 library 的路徑一定要在某個 Route 的 `target_path` 底下（plan §8.6）。"""
        complete = tmp_path / "complete"
        library = tmp_path / "library"
        ensure_directory(complete)
        ensure_directory(library)
        source = complete / "a.mkv"
        source.write_bytes(b"berth")
        escaping = library / ".." / "elsewhere.mkv"

        with pytest.raises(PathEscapeError):
            link(source, escaping, roots=[library])

        assert not (tmp_path / "elsewhere.mkv").exists()

    def test_refuses_when_there_is_no_root_at_all(self, tmp_path: Path) -> None:
        """一個 Route 都還沒有的時候什麼都不准寫，而不是什麼都准。"""
        source = tmp_path / "a.mkv"
        source.write_bytes(b"berth")

        with pytest.raises(PathEscapeError):
            link(source, tmp_path / "b.mkv", roots=[])

    def test_an_existing_target_raises_the_os_error(self, tmp_path: Path) -> None:
        source = tmp_path / "a.mkv"
        source.write_bytes(b"berth")
        target = tmp_path / "b.mkv"
        target.write_bytes(b"other")

        with pytest.raises(FileExistsError):
            link(source, target, roots=[tmp_path])

    def test_creates_the_folders_the_target_needs(self, tmp_path: Path) -> None:
        """入庫的目標是算出來的檔名（`<作品>/Season 01/…`），那幾層資料夾第一次一定不存在。"""
        library = tmp_path / "library"
        ensure_directory(library)
        source = tmp_path / "a.mkv"
        source.write_bytes(b"berth")
        target = library / "Show (2022) [tmdbid-1]" / "Season 01" / "Show S01E01.mkv"

        link(source, target, roots=[library])

        assert same_inode(source, target) is True

    def test_an_escaping_target_creates_no_folders_on_the_way(self, tmp_path: Path) -> None:
        """守衛在建資料夾**之前**：擋下來的那一次不該在媒體庫外面留下空目錄。"""
        library = tmp_path / "library"
        ensure_directory(library)
        source = tmp_path / "a.mkv"
        source.write_bytes(b"berth")

        with pytest.raises(PathEscapeError):
            link(source, library / ".." / "elsewhere" / "a.mkv", roots=[library])

        assert not (tmp_path / "elsewhere").exists()

    def test_a_cross_device_link_keeps_its_errno_and_names_both_mounts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`EXDEV` 的原文只說「跨裝置」，而使用者要知道的是**哪兩個掛載**（brief §4.4）。"""
        library = tmp_path / "library"
        ensure_directory(library)
        source = tmp_path / "a.mkv"
        source.write_bytes(b"berth")

        def cross_device(source: object, target: object) -> None:
            raise OSError(errno.EXDEV, "Invalid cross-device link")

        monkeypatch.setattr(os, "link", cross_device)

        with pytest.raises(OSError) as caught:
            link(source, library / "a.mkv", roots=[library])

        assert caught.value.errno == errno.EXDEV
        message = str(caught.value)
        assert "Invalid cross-device link" in message
        assert str(mount_point(source)) in message
        assert str(mount_point(library / "a.mkv")) in message

    def test_two_separate_mounts_are_told_to_share_one_parent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """最常見的那一種：`/downloads` 與 `/media` 分開掛（brief §20.2）。"""
        library = tmp_path / "library"
        ensure_directory(library)
        source = tmp_path / "a.mkv"
        source.write_bytes(b"berth")

        def cross_device(source: object, target: object) -> None:
            raise OSError(errno.EXDEV, "Invalid cross-device link")

        def mounts(path: Path) -> Path:
            return Path("/media") if "library" in str(path) else Path("/downloads")

        monkeypatch.setattr(os, "link", cross_device)
        monkeypatch.setattr("berth.adapters.fs.mount_point", mounts)

        with pytest.raises(OSError) as caught:
            link(source, library / "a.mkv", roots=[library])

        message = str(caught.value)
        assert str(Path("/downloads")) in message
        assert str(Path("/media")) in message
        assert "mount one common parent folder" in message

    def test_one_mount_that_still_crosses_devices_is_not_told_to_share_a_parent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """mergerfs 分支、btrfs 子卷：他已經只掛一個父目錄了，那句建議會把人帶錯方向。"""
        library = tmp_path / "library"
        ensure_directory(library)
        source = tmp_path / "a.mkv"
        source.write_bytes(b"berth")

        def cross_device(source: object, target: object) -> None:
            raise OSError(errno.EXDEV, "Invalid cross-device link")

        monkeypatch.setattr(os, "link", cross_device)

        with pytest.raises(OSError) as caught:
            link(source, library / "a.mkv", roots=[library])

        message = str(caught.value)
        assert "mount one common parent folder" not in message
        assert "same underlying file system" in message

    def test_other_os_errors_pass_through_untouched(self, tmp_path: Path) -> None:
        library = tmp_path / "library"
        ensure_directory(library)

        with pytest.raises(FileNotFoundError):
            link(tmp_path / "missing.mkv", library / "a.mkv", roots=[library])


class TestMountPoint:
    def test_a_path_that_does_not_exist_yet_reports_the_mount_it_would_land_on(
        self, tmp_path: Path
    ) -> None:
        """入庫目標在鏈接之前不存在，但它會落在哪一個掛載上是已經決定了的。"""
        assert mount_point(tmp_path / "not" / "yet.mkv") == mount_point(tmp_path)

    def test_the_answer_is_a_mount(self, tmp_path: Path) -> None:
        assert os.path.ismount(mount_point(tmp_path))


class TestLinkTest:
    def test_proves_the_two_directories_share_a_file_system(self, tmp_path: Path) -> None:
        complete = tmp_path / "complete"
        library = tmp_path / "library"
        ensure_directory(complete)
        ensure_directory(library)

        facts = link_test(complete, library, roots=[library])

        assert facts.inode > 0
        assert facts.device == stat(library).device

    def test_cleans_up_both_sides(self, tmp_path: Path) -> None:
        complete = tmp_path / "complete"
        library = tmp_path / "library"
        ensure_directory(complete)
        ensure_directory(library)

        link_test(complete, library, roots=[library])

        assert list(complete.iterdir()) == []
        assert list(library.iterdir()) == []

    def test_cleans_up_when_the_link_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`EXDEV` 是最常見的失敗（brief §4.4）。留下垃圾檔會讓下一次重試也失敗。"""
        complete = tmp_path / "complete"
        library = tmp_path / "library"
        ensure_directory(complete)
        ensure_directory(library)

        def cross_device(source: object, target: object) -> None:
            raise OSError(errno.EXDEV, "Invalid cross-device link")

        monkeypatch.setattr(os, "link", cross_device)

        with pytest.raises(OSError) as caught:
            link_test(complete, library, roots=[library])

        assert caught.value.errno == errno.EXDEV
        assert list(complete.iterdir()) == []
        assert list(library.iterdir()) == []

    def test_refuses_a_target_directory_outside_every_root(self, tmp_path: Path) -> None:
        complete = tmp_path / "complete"
        library = tmp_path / "library"
        ensure_directory(complete)
        ensure_directory(library)

        with pytest.raises(PathEscapeError):
            link_test(complete, library, roots=[tmp_path / "other"])

        assert list(complete.iterdir()) == []


class TestProbeFile:
    def test_exists_inside_the_block_and_is_gone_after(self, tmp_path: Path) -> None:
        library = tmp_path / "library"
        ensure_directory(library)

        with probe_file(library, roots=[library]) as probe:
            assert probe.is_file()
            assert probe.parent == library

        assert list(library.iterdir()) == []

    def test_refuses_a_directory_outside_every_root(self, tmp_path: Path) -> None:
        with pytest.raises(PathEscapeError), probe_file(tmp_path, roots=[tmp_path / "library"]):
            pass  # pragma: no cover - 進不到這裡

    def test_survives_a_probe_that_was_already_removed(self, tmp_path: Path) -> None:
        """探測檔被別人清掉不該把檢查變成失敗——它本來就是要被刪掉的。"""
        with probe_file(tmp_path, roots=[tmp_path]) as probe:
            probe.unlink()


def test_free_space_reports_the_target_file_system(tmp_path: Path) -> None:
    assert free_space(tmp_path) == shutil.disk_usage(tmp_path).free


class TestRemove:
    """刪除也是寫入，所以它要與 `link` 同一道守衛（票 M2/04）。"""

    def test_removes_a_file_inside_an_allowed_root(self, tmp_path: Path) -> None:
        library = tmp_path / "library"
        ensure_directory(library)
        target = library / "Show" / "episode.mkv"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"x")

        assert remove(target, roots=[library]) is True
        assert not target.exists()

    def test_a_file_that_is_already_gone_reports_false(self, tmp_path: Path) -> None:
        """對帳本上早就被人刪掉的那一條，刪除不是失敗——它只是沒有事情要做。"""
        library = tmp_path / "library"
        ensure_directory(library)

        assert remove(library / "gone.mkv", roots=[library]) is False

    def test_refuses_a_path_outside_every_root(self, tmp_path: Path) -> None:
        victim = tmp_path / "elsewhere.mkv"
        victim.write_bytes(b"x")

        with pytest.raises(PathEscapeError):
            remove(victim, roots=[tmp_path / "library"])

        assert victim.exists()

    def test_refuses_when_there_is_no_root_at_all(self, tmp_path: Path) -> None:
        victim = tmp_path / "victim.mkv"
        victim.write_bytes(b"x")

        with pytest.raises(PathEscapeError):
            remove(victim, roots=[])

        assert victim.exists()

    def test_refuses_a_directory(self, tmp_path: Path) -> None:
        """刪除的單位是**一個檔案**：帳本與 job_files 記的都是檔案，而一個目錄底下可能
        有別人的東西（brief §9.1 的 `unmanaged_library_file` 永不自動刪）。"""
        library = tmp_path / "library"
        folder = library / "Show"
        folder.mkdir(parents=True)

        with pytest.raises(IsADirectoryError):
            remove(folder, roots=[library])

        assert folder.is_dir()


class TestPruneEmptyParents:
    def test_removes_the_folders_that_the_file_left_empty(self, tmp_path: Path) -> None:
        library = tmp_path / "library"
        target = library / "Show" / "Season 01" / "episode.mkv"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"x")
        remove(target, roots=[library])

        prune_empty_parents(target, root=library)

        assert library.is_dir()
        assert not (library / "Show").exists()

    def test_stops_at_the_first_folder_that_still_has_something(self, tmp_path: Path) -> None:
        library = tmp_path / "library"
        season = library / "Show" / "Season 01"
        season.mkdir(parents=True)
        (season / "kept.mkv").write_bytes(b"x")

        prune_empty_parents(season / "gone.mkv", root=library)

        assert season.is_dir()

    def test_never_removes_the_root_itself(self, tmp_path: Path) -> None:
        """媒體庫目錄是設定值，不是這一次刪除建出來的東西。"""
        library = tmp_path / "library"
        ensure_directory(library)

        prune_empty_parents(library / "episode.mkv", root=library)

        assert library.is_dir()

    def test_a_path_outside_the_root_prunes_nothing(self, tmp_path: Path) -> None:
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        prune_empty_parents(elsewhere / "file.mkv", root=tmp_path / "library")

        assert elsewhere.is_dir()


class TestRootOf:
    """守衛與「空目錄要收到哪一層」問的是同一件事，所以只算一次（M2 票 04）。"""

    def test_names_the_root_the_path_falls_under(self, tmp_path: Path) -> None:
        library, complete = tmp_path / "library", tmp_path / "complete"

        assert root_of(complete / "pack" / "a.mkv", [library, complete]) == complete

    def test_a_path_outside_every_root_raises(self, tmp_path: Path) -> None:
        with pytest.raises(PathEscapeError):
            root_of(tmp_path / "elsewhere.mkv", [tmp_path / "library"])
