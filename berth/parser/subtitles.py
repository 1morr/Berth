"""外掛字幕附掛到影片（plan §4.1 的 `match_subtitle`、brief §6.7）。

字幕檔自己說不出它是第幾集——`[Group] Show - 03.tc.ass` 裡的 `03` 只有在**旁邊有一個
第三集的影片**時才有意義。所以這一層問的是配對：配到哪一個影片，以及這一個檔案是哪一種
語言。季集由配到的那個影片給（`planner`），不在這裡重算一次。

順序就是 brief §6.7：主幹相同 → 字幕資料夾裡的集號 → 對不到就是 `None`（Unmatched）。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from berth.domain import FileEntry, Lang, PlanItem, sort_langs
from berth.naming import stem
from berth.parser.cjk import langs_in
from berth.parser.release import parse_release
from berth.parser.structure import structure_hints

#: 檔名尾巴的語言後綴（brief §6.7 第 3 點）。**比詞典多幾個**：真實語料寫的是 `.Cht`
#: `.Chs` `.Jpn` `.Eng`（ISO 639-2 的寫法，`tv/gto-2026-magicstar`），而詞典那一張表
#: 是給發佈名用的——發佈名裡的 `JPN` 與 `ENG` 要求前後不是英數，後綴則整段就是它。
_LANG_SUFFIX: dict[str, tuple[Lang, ...]] = {
    "tc": (Lang.CHT,),
    "cht": (Lang.CHT,),
    "big5": (Lang.CHT,),
    "zh-hant": (Lang.CHT,),
    "zh-tw": (Lang.CHT,),
    "cn": (Lang.CHS,),
    "sc": (Lang.CHS,),
    "chs": (Lang.CHS,),
    "gb": (Lang.CHS,),
    "zh-hans": (Lang.CHS,),
    "zh-cn": (Lang.CHS,),
    "jp": (Lang.JP,),
    "jpn": (Lang.JP,),
    "ja": (Lang.JP,),
    "en": (Lang.EN,),
    "eng": (Lang.EN,),
    "jptc": (Lang.CHT, Lang.JP),
    "jpsc": (Lang.CHS, Lang.JP),
}

#: `.default` / `.forced` / `.sdh` 這類旗標（brief §20.1）。它們不是語言，但也不是主幹的一部分。
_FLAG_SUFFIX = frozenset({"default", "forced", "sdh", "cc", "hi"})


@dataclass(frozen=True, slots=True)
class SubtitleMatch:
    """一個字幕檔掛在哪一個影片上，以及它是哪一種語言。"""

    #: 影片的 `rel_path`（torrent 內），不是目標路徑——目標路徑由 `naming` 算。
    video: str
    langs: tuple[Lang, ...]
    reasons: tuple[str, ...] = ()


def match_subtitle(entry: FileEntry, videos: Sequence[PlanItem]) -> SubtitleMatch | None:
    """一個字幕檔 → 它屬於的影片（brief §6.7）。配不到時回 `None`。

    `videos` 是**已經決定季集的影片**：第二條規則要拿集號去找影片，而集號是誰的答案
    這一層不重算。
    """
    bare = _strip_langs(stem(entry.name))
    langs = _langs(entry)

    for item in videos:
        if stem(item.name) == bare:
            return SubtitleMatch(
                video=item.rel_path,
                langs=langs,
                reasons=("the subtitle and the video share a file name",),
            )

    return _by_episode(entry, videos, langs)


def _by_episode(
    entry: FileEntry, videos: Sequence[PlanItem], langs: tuple[Lang, ...]
) -> SubtitleMatch | None:
    """brief §6.7 第 2 點：字幕資料夾裡的檔名含集號 → 以集號對應影片。

    **要有那個資料夾**：字幕與影片同名是很強的證據，光有一個數字不是——一包裡任何
    帶數字的檔案都會對到某一集。語言資料夾（`繁體/`）算同一種證據：它一樣說了
    「這一格底下的東西是側掛字幕」。

    對到兩個以上的影片時不選：同一集有兩個版本時，這個字幕是誰的旁邊那一份，路徑沒有說。
    """
    structure = structure_hints(entry.rel_path)
    if not structure.subtitle_folder and structure.subtitle_lang is None:
        return None

    info = parse_release(entry.name)
    if info.episode is None:
        return None

    found = [
        item
        for item in videos
        if item.episode_start == info.episode
        and (info.season is None or item.season == info.season)
    ]
    if len(found) != 1:
        return None
    return SubtitleMatch(
        video=found[0].rel_path,
        langs=langs,
        reasons=(f"the subtitle sits in a subtitle folder and names episode {info.episode}",),
    )


def _langs(entry: FileEntry) -> tuple[Lang, ...]:
    """這一個字幕檔是哪一種語言（brief §6.7 第 3 點）。

    後綴 → 資料夾 → 檔名裡的詞典。**不看 torrent 名**：`附官方日英简繁中字幕` 說的是
    這一包有四種字幕，不是這一個檔案有四種（`tv/gto-2026-magicstar` 實測）。
    """
    if suffix := _suffix_langs(stem(entry.name)):
        return suffix
    structure = structure_hints(entry.rel_path)
    if structure.subtitle_lang is not None:
        return (structure.subtitle_lang,)
    return sort_langs(langs_in(entry.name))


def _suffix_langs(bare: str) -> tuple[Lang, ...]:
    """`….tc` / `….Cht` / `….zh-Hant`。旗標後綴（`.default`）跳過再看下一段。"""
    for segment in reversed(bare.split(".")):
        key = segment.strip().lower()
        if key in _FLAG_SUFFIX:
            continue
        return _LANG_SUFFIX.get(key, ())
    return ()


def _strip_langs(bare: str) -> str:
    """去掉尾巴的語言與旗標後綴（brief §6.7 第 1 點的「去掉語言後綴後」）。"""
    parts = bare.split(".")
    while len(parts) > 1 and (
        parts[-1].strip().lower() in _LANG_SUFFIX or parts[-1].strip().lower() in _FLAG_SUFFIX
    ):
        parts.pop()
    return ".".join(parts)
