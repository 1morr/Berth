"""造 Jellyfin 命名實測用的 dummy 媒體樹（brief §20.6、§7；plan §5）。

每個檔案都是同一段 1 秒黑畫面 MKV 的複本 —— Jellyfin 會對媒體檔跑 ffprobe，
零位元組的假檔會被跳過或產生沒有媒體串流的條目，測不出命名解析的行為。
種子檔用 Jellyfin image 自己的 ffmpeg 產生，所以宿主不必先裝 ffmpeg。

用法：
    python scripts/experiments/make_media.py [--data .local/experiments/data]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

FFMPEG_IMAGE = "jellyfin/jellyfin:10.11.11"
FFMPEG = "/usr/lib/jellyfin-ffmpeg/ffmpeg"

# 一個能被解析器與播放器接受的最小 ASS。內容不重要，Jellyfin 只讀它的存在與檔名。
ASS = """[Script Info]
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, Bold, Italic, Alignment, Encoding
Style: Default,Arial,48,&H00FFFFFF,0,0,2,1

[Events]
Format: Layer, Start, End, Style, Text
Dialogue: 0,0:00:00.00,0:00:01.00,Default,berth experiment
"""

SHOW = "Berth Test Show (2020)"
SHOW_DIR = f"{SHOW} [tmdbid-1399]"
TAGS_A = "[BD][1080p][CHT+JP][Sakurato]"
TAGS_B = "[WEB][1080p][CHS][Hardsub][Lilith-Raws]"

# TMDB 對不上的作品：這才看得到 Jellyfin 自己的檔名解析器輸出什麼。
# 有 tmdbid 的那組會被 TMDB 的標題整個蓋掉，看不出方括號有沒有滲進去。
PROBE = "Qwxzyv Berth Probe (2099)"

# (相對路徑, 這個檔要回答的問題)。順序即報告順序。
VIDEOS: list[tuple[str, str]] = [
    # plan §5 的劇集模板本體：方括號 tag 與 `+` 會不會滲進劇名或集名
    (f"tv/{SHOW_DIR}/Season 01/{SHOW} - S01E01 - Winter Is Coming {TAGS_A}.mkv", "劇集模板 + tag"),
    # 同一集第二個版本，同一個季資料夾（brief §7.7）
    (f"tv/{SHOW_DIR}/Season 01/{SHOW} - S01E01 - Winter Is Coming {TAGS_B}.mkv", "同集第二版本"),
    (f"tv/{SHOW_DIR}/Season 01/{SHOW} - S01E02 - The Kingsroad {TAGS_A}.mkv", "外掛字幕的載體"),
    # 多集檔（plan §5 的 [-E{e2:02d}]）
    (
        f"tv/{SHOW_DIR}/Season 01/{SHOW} - S01E03-E04 - Lord Snow [BD][1080p][CHT][Sakurato].mkv",
        "多集檔",
    ),
    # 對照組：完全沒有 tag，用來分辨「集名被截斷」是不是 tag 造成的
    (f"tv/{SHOW_DIR}/Season 01/{SHOW} - S01E05 - The Wolf and the Lion.mkv", "無 tag 對照"),
    # Specials（brief §7.6）
    (
        f"tv/{SHOW_DIR}/Season 00/{SHOW} - S00E01 - Special One [BD][1080p][CHT][Sakurato].mkv",
        "Season 00",
    ),
    # extras：劇集層與季層各一份（brief §20.1 說兩層都可放，未證實）
    (f"tv/{SHOW_DIR}/extras/Series Level Interview.mkv", "劇集層 extras"),
    (f"tv/{SHOW_DIR}/Season 01/extras/Season Level NCOP.mkv", "季層 extras"),
    # 電影多版本 A：plan §5 的模板（檔名含 [tmdbid-…]）
    (
        "movies/Berth Movie Plan (2019) [tmdbid-27205]/"
        "Berth Movie Plan (2019) [tmdbid-27205] - [BD][2160p][CHT+JP][Sakurato].mkv",
        "電影多版本（plan §5 模板）",
    ),
    (
        "movies/Berth Movie Plan (2019) [tmdbid-27205]/"
        "Berth Movie Plan (2019) [tmdbid-27205] - [WEB][1080p][CHS][Lilith-Raws].mkv",
        "電影多版本（plan §5 模板）",
    ),
    # 電影多版本 B：brief §7.2 範例的寫法（檔名不含 [tmdbid-…]，與資料夾名不一致）
    (
        "movies/Berth Movie Brief (2019) [tmdbid-157336]/"
        "Berth Movie Brief (2019) - [BD][2160p][CHT+JP][Sakurato].mkv",
        "電影多版本（brief §7.2 範例）",
    ),
    (
        "movies/Berth Movie Brief (2019) [tmdbid-157336]/"
        "Berth Movie Brief (2019) - [WEB][1080p][CHS][Lilith-Raws].mkv",
        "電影多版本（brief §7.2 範例）",
    ),
    # 對照組：官方文件說結尾 p/i 的標籤依解析度排序
    ("movies/Berth Movie Res (2019)/Berth Movie Res (2019) - 720p.mkv", "版本排序對照"),
    ("movies/Berth Movie Res (2019)/Berth Movie Res (2019) - 2160p.mkv", "版本排序對照"),
    ("movies/Berth Movie Res (2019)/Berth Movie Res (2019) - 1080p.mkv", "版本排序對照"),
    ("movies/Berth Movie Plain (2019)/Berth Movie Plain (2019).mkv", "單版本電影"),
    ("movies/Berth Movie Plain (2019)/extras/Movie Level Behind The Scenes.mkv", "電影層 extras"),
    # TMDB 對不上的組：Series / Episode / Movie 的名稱都由檔名決定，
    # 方括號與 `+` 有沒有滲進劇名或集名，只有在這一組看得出來。
    (
        f"tv/{PROBE}/Season 01/{PROBE} - S01E01 - Winter Is Coming {TAGS_A}.mkv",
        "無 TMDB：tag 是否滲入",
    ),
    (f"tv/{PROBE}/Season 01/{PROBE} - S01E02 - The Kingsroad.mkv", "無 TMDB：無 tag 對照"),
    (
        f"movies/{PROBE} Movie/{PROBE} Movie - [BD][2160p][CHT+JP][Sakurato].mkv",
        "無 TMDB：電影版本標籤",
    ),
    (
        f"movies/{PROBE} Movie/{PROBE} Movie - [WEB][1080p][CHS][Lilith-Raws].mkv",
        "無 TMDB：電影版本標籤",
    ),
]

SUBTITLES: list[tuple[str, str]] = [
    # brief §20.1：沒有語言碼能分繁簡，繁簡放自由文字標題欄位 → 實測選單顯示什麼
    (f"tv/{SHOW_DIR}/Season 01/{SHOW} - S01E01 - Winter Is Coming {TAGS_A}.CHT.zh.ass", "CHT.zh"),
    (f"tv/{SHOW_DIR}/Season 01/{SHOW} - S01E01 - Winter Is Coming {TAGS_A}.CHS.zh.ass", "CHS.zh"),
    # 順帶回答 §20.1 標「未證實」的 zh-Hant / zh-Hans 能不能被辨識
    (f"tv/{SHOW_DIR}/Season 01/{SHOW} - S01E02 - The Kingsroad {TAGS_A}.zh-Hant.ass", "zh-Hant"),
    (f"tv/{SHOW_DIR}/Season 01/{SHOW} - S01E02 - The Kingsroad {TAGS_A}.zh-Hans.ass", "zh-Hans"),
    # default 旗標（plan §5 的 [.default]）
    (
        f"tv/{SHOW_DIR}/Season 01/{SHOW} - S01E05 - The Wolf and the Lion.CHT.default.zh.ass",
        "CHT.default.zh",
    ),
]


def make_seed(seed: Path) -> None:
    """用 Jellyfin image 的 ffmpeg 產生 1 秒 32x32 的黑畫面 MKV。"""
    if seed.exists():
        return
    seed.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{seed.parent.resolve()}:/out",
            "--entrypoint",
            FFMPEG,
            FFMPEG_IMAGE,
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=32x32:d=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-y",
            f"/out/{seed.name}",
        ],
        check=True,
        capture_output=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(".local/experiments/data"))
    args = parser.parse_args()

    root: Path = args.data.resolve()
    library = root / "library"
    if library.exists():
        shutil.rmtree(library)

    seed = root / "_seed" / "seed.mkv"
    make_seed(seed)

    for rel, _why in VIDEOS:
        target = library / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(seed, target)
    for rel, _why in SUBTITLES:
        target = library / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(ASS, encoding="utf-8")

    print(f"媒體樹：{library}")
    print(f"  影片 {len(VIDEOS)} 個、字幕 {len(SUBTITLES)} 個")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
