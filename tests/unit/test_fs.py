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
    probe_file,
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
