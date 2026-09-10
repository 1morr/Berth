"""解析階段的純函式：分類、發佈名、結構、對應、信心（plan §4.1）。

沒有 IO，也不 import 任何會做 IO 的東西——benchmark 因此可以離線跑（plan §4）。
"""

from berth.parser.cjk import langs_in, normalize_cjk
from berth.parser.classify import SAMPLE_RATIO, classify
from berth.parser.mapping import VIRTUAL_SEASON_GAP, map_episode
from berth.parser.planner import plan
from berth.parser.release import merge_release, parse_release, tags_of
from berth.parser.structure import StructureHints, structure_hints
from berth.parser.subtitles import SubtitleMatch, match_subtitle
from berth.parser.title import MediaMatch, match_media, matches, normalize_title

__all__ = [
    "SAMPLE_RATIO",
    "VIRTUAL_SEASON_GAP",
    "MediaMatch",
    "StructureHints",
    "SubtitleMatch",
    "classify",
    "langs_in",
    "map_episode",
    "match_media",
    "match_subtitle",
    "matches",
    "merge_release",
    "normalize_cjk",
    "normalize_title",
    "parse_release",
    "plan",
    "structure_hints",
    "tags_of",
]
