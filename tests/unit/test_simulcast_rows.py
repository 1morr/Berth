"""正式環境被規則一誤擋的 16 列（M5.5 票 04、brief §20.27）。

`tests/fixtures/airing/simulcast-2026-fall.json`：真的發佈名、檔名與發佈時間，TMDB 快照錄自真的
API，播出日以正式環境當時看到的為準（`tmdb_aired`，fixture 開頭說明為什麼）。走規劃時的那一條：
解析器 → 播出日比對 → 第一批的擔保，與 `services/plan` 給 RSS Series 送來的 Job 相同。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from berth.domain import FileEntry, MediaSnapshot, ParseContext, PlanAction, PlanItem
from berth.domain import ReasonCode as Code
from berth.parser import check_airing, plan, vouch_first_batch

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ROWS: list[dict[str, Any]] = json.loads(
    (FIXTURES / "airing" / "simulcast-2026-fall.json").read_text(encoding="utf-8")
)["rows"]


def snapshot(row: dict[str, Any]) -> MediaSnapshot:
    """錄下的快照，那一集的播出日換成正式環境當時的 TMDB 日期。"""
    recorded = MediaSnapshot.model_validate_json(
        (FIXTURES / "tmdb" / f"{row['tmdb']}.json").read_text(encoding="utf-8")
    )
    aired = date.fromisoformat(row["tmdb_aired"])
    seasons = tuple(
        season.model_copy(
            update={
                "episodes": tuple(
                    episode.model_copy(update={"air_date": aired})
                    if (season.season_number, episode.episode_number)
                    == (row["season"], row["episode"])
                    else episode
                    for episode in season.episodes
                )
            }
        )
        for season in recorded.seasons
    )
    return recorded.model_copy(update={"seasons": seasons})


def planned(row: dict[str, Any]) -> tuple[MediaSnapshot, datetime, tuple[PlanItem, ...]]:
    media = snapshot(row)
    at = datetime.fromisoformat(row["published_at"])
    entries = (FileEntry(rel_path=row["file"], size=500_000_000),)
    items = plan(row["torrent_name"], entries, ParseContext(media=media, published_at=at))
    return media, at, check_airing(row["torrent_name"], items, media, at, from_series=True)


@pytest.mark.parametrize("row", ROWS, ids=[row["id"] for row in ROWS])
class TestProductionRows:
    def test_read_as_in_production(self, row: dict[str, Any]) -> None:
        """前提：解析器讀出的與正式環境相同（季集、季號來源），fixture 才說得上是那一列。"""
        _, _, [item] = planned(row)

        assert (item.season, item.episode_start) == (row["season"], row["episode"])
        assert Code(row["reading"]) in {reason.code for reason in item.reasons}

    def test_passes_the_air_date_check_with_a_note(self, row: dict[str, Any]) -> None:
        _, _, [item] = planned(row)

        assert item.action is PlanAction.IMPORT
        assert item.reasons[-1].code is Code.RELEASED_AHEAD_OF_AIRING
        assert item.reasons[-1].params["aired"] == row["tmdb_aired"]

    def test_the_first_batch_vouches_for_it(self, row: dict[str, Any]) -> None:
        """哥布林、裝備仔、野生的大魔王的 Series 被這幾列卡著確認不了（研究檔 §2）。"""
        media, at, items = planned(row)
        span = (row["season"], row["episode"], row["episode"])

        assert vouch_first_batch(
            row["torrent_name"], items, media, at, season_hint=None, episode_offset=None
        ) == (span,)


def test_all_sixteen_rows_are_there() -> None:
    assert len(ROWS) == 16
