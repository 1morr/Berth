"""第一層：檔案分類（plan §4.1、brief §6.2）。

輸入是**整包**檔案而不是一個路徑，因為三條規則裡有兩條要看鄰居：`sample` 比的是同目錄
最大的影片，`disc` 看的是整包有沒有 `BDMV/` 結構。逐檔的簽名做不到這兩件事。

第一階段沒有 mediainfo，所以「檔名像正片但時長 90 秒 → 降為 extra」那條（brief §6.2）
不在這裡；分類器留著可以被修正的形狀（回傳新的 `FileEntry`，不改輸入）。
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from berth.domain import FileEntry, FileKind
from berth.naming import extension

_BY_EXTENSION: dict[str, FileKind] = {
    **dict.fromkeys(
        (".mkv", ".mp4", ".avi", ".ts", ".m2ts", ".wmv", ".flv", ".webm"), FileKind.VIDEO
    ),
    **dict.fromkeys((".ass", ".ssa", ".srt", ".sup", ".sub", ".idx", ".vtt"), FileKind.SUBTITLE),
    **dict.fromkeys((".ttf", ".otf", ".ttc"), FileKind.FONT),
    **dict.fromkeys((".flac", ".mp3", ".m4a", ".aac", ".ogg", ".wav"), FileKind.AUDIO),
    **dict.fromkeys((".jpg", ".jpeg", ".png", ".webp", ".bmp"), FileKind.IMAGE),
    **dict.fromkeys((".zip", ".rar", ".7z"), FileKind.ARCHIVE),
}

#: 光碟結構。任何一個檔案落在這兩個目錄底下，**整包**都是 disc——一張 BD 的
#: `CERTIFICATE/` 與 `BDMV/` 是同一件東西的兩半，只標其中一半沒有意義（brief §6.2）。
_DISC_DIRS = frozenset({"BDMV", "VIDEO_TS"})

#: extras 資料夾。Jellyfin 認得的那一串（brief §20.1）加上字幕組與 BD 包的慣例
#: （`SPs/`、`Bonus/`、`NCOP&NCED/`、`PV/`、`CM/`）。比對前先小寫。
_EXTRA_DIRS = frozenset(
    {
        "extras",
        "extra",
        "behind the scenes",
        "deleted scenes",
        "interviews",
        "scenes",
        "shorts",
        "featurettes",
        "clips",
        "trailers",
        "theme-music",
        "backdrops",
        "bonus",
        "menu",
        "menus",
        "pv",
        "cm",
        "ncop&nced",
        "nc",
    }
)

#: extras 關鍵字（brief §6.2）。`OP` / `ED` 只在**沒有集號**時算——`OP` 後面接數字的是
#: 第 N 個片頭，仍然是特典；但 `Title - OP01` 這種寫法與正片集號長得太像，交給資料夾判。
_EXTRA_TOKENS = re.compile(
    r"(?<![A-Za-z0-9])(?:NCOP|NCED|PV|CM|Menu|Preview|Trailer|Making|Interview)(?![A-Za-z0-9])"
    r"|特典|映像特典|預告|预告|花絮",
    re.IGNORECASE,
)

#: 無集號的 `OP` / `ED`。分開一條是因為它要求後面**不接數字**。
_BARE_OPENING = re.compile(r"(?<![A-Za-z0-9])(?:OP|ED)(?![A-Za-z0-9])")

#: `SPs/` 裡帶 SP 編號的是特典本體（可能對得到 TMDB season 0），不是 extra（brief §6.2）。
_SP_NUMBERED = re.compile(r"(?<![A-Za-z0-9])SP\s*[\[\]._-]*\s*[0-9]{1,2}(?![0-9])", re.IGNORECASE)

_SAMPLE = re.compile(r"(?<![A-Za-z0-9])sample(?![A-Za-z0-9])", re.IGNORECASE)

#: sample 的大小門檻：同目錄最大影片的一成（brief §6.2、plan §4.1）。
SAMPLE_RATIO = 0.1


def classify(files: Sequence[FileEntry]) -> tuple[FileEntry, ...]:
    """替每個檔案填上 `kind`。回新的 entry，不改輸入。"""
    if _is_disc(files):
        return tuple(entry.model_copy(update={"kind": FileKind.DISC}) for entry in files)

    biggest = _biggest_video_per_directory(files)
    torrent_biggest = max(biggest.values(), default=0)
    return tuple(
        entry.model_copy(
            update={"kind": _kind_of(entry, _reference_video(entry, biggest, torrent_biggest))}
        )
        for entry in files
    )


def _reference_video(entry: FileEntry, biggest: dict[str, int], torrent_biggest: int) -> int:
    """拿來比大小的那個「正片」有多大。

    先看同目錄（brief §6.2 的原文），同目錄只有它自己時退回整包最大的那一個——真實發佈
    幾乎都把 sample 放在自己的 `Sample/` 資料夾裡，照字面只比同目錄的話那條規則永遠不成立
    （plan §4.1 已同步改成這樣）。
    """
    same_directory = biggest.get(entry.directory, 0)
    return torrent_biggest if same_directory <= entry.size else same_directory


def _is_disc(files: Sequence[FileEntry]) -> bool:
    return any(
        segment in _DISC_DIRS for entry in files for segment in entry.rel_path.split("/")[:-1]
    )


def _kind_of(entry: FileEntry, reference_video: int) -> FileKind:
    kind = _BY_EXTENSION.get(extension(entry.name), FileKind.OTHER)
    if kind is not FileKind.VIDEO:
        return kind
    if _is_sample(entry, reference_video):
        return FileKind.SAMPLE
    if _is_extra(entry):
        return FileKind.EXTRA
    return FileKind.VIDEO


def _is_sample(entry: FileEntry, reference_video: int) -> bool:
    """檔名含 sample **而且**遠小於正片（brief §6.2）。

    兩個條件缺一不可：`Sample Man (2019).mkv` 是一部片，而一個沒有 `sample` 字樣的小檔
    可能是真的短片。整包只有它一個影片時 `reference_video` 就是它自己，比例是 1，
    判不成 sample——這是對的，孤零零一個檔案沒有東西可以說它「小」。
    """
    return bool(_SAMPLE.search(entry.name)) and entry.size < reference_video * SAMPLE_RATIO


def _is_extra(entry: FileEntry) -> bool:
    directories = [segment.lower() for segment in entry.directory.split("/")]
    if any(directory in _EXTRA_DIRS for directory in directories):
        return True
    if any(directory in ("sps", "sp", "specials") for directory in directories):
        # `SPs/` 裡的東西預設是特典本體，只有沒有 SP 編號的才是 extra（brief §6.2）。
        return not _SP_NUMBERED.search(entry.name)
    if _EXTRA_TOKENS.search(entry.name):
        return True
    return bool(_BARE_OPENING.search(entry.name))


def _biggest_video_per_directory(files: Sequence[FileEntry]) -> dict[str, int]:
    biggest: dict[str, int] = {}
    for entry in files:
        if _BY_EXTENSION.get(extension(entry.name)) is not FileKind.VIDEO:
            continue
        biggest[entry.directory] = max(biggest.get(entry.directory, 0), entry.size)
    return biggest
