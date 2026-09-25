"""解析階段的純函式：分類、發佈名、結構、對應、信心（plan §4.1）。

沒有 IO，也不 import 任何會做 IO 的東西——benchmark 因此可以離線跑（plan §4）。
"""

from berth.parser.airing import BEHIND_LATEST, HELD_BY_AIRING, RELEASE_TOLERANCE, check_airing
from berth.parser.cjk import langs_in, normalize_cjk
from berth.parser.classify import SAMPLE_RATIO, SHORT_FEATURE, classify, kind_by_extension
from berth.parser.mapping import VIRTUAL_SEASON_GAP, map_episode
from berth.parser.planner import episode_span, plan, promote, revise, written_episode
from berth.parser.release import merge_release, parse_release, tags_of
from berth.parser.runtime import HELD_BY_RUNTIME, RUNTIME_RATIO, RUNTIME_SLACK, check_runtime
from berth.parser.structure import StructureHints, structure_hints
from berth.parser.subtitles import SubtitleMatch, match_subtitle
from berth.parser.title import MediaMatch, match_media, matches, mentions, normalize_title

__all__ = [
    "BEHIND_LATEST",
    "HELD_BY_AIRING",
    "HELD_BY_RUNTIME",
    "RELEASE_TOLERANCE",
    "RUNTIME_RATIO",
    "RUNTIME_SLACK",
    "SAMPLE_RATIO",
    "SHORT_FEATURE",
    "VIRTUAL_SEASON_GAP",
    "MediaMatch",
    "StructureHints",
    "SubtitleMatch",
    "check_airing",
    "check_runtime",
    "classify",
    "episode_span",
    "kind_by_extension",
    "langs_in",
    "map_episode",
    "match_media",
    "match_subtitle",
    "matches",
    "mentions",
    "merge_release",
    "normalize_cjk",
    "normalize_title",
    "parse_release",
    "plan",
    "promote",
    "revise",
    "structure_hints",
    "tags_of",
    "written_episode",
]
