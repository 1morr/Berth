"""送單確認卡逐列標出作品已經有的集（M5 票 28，使用者 2026-10-30）。

由伺服器算、不靠模型說：提出卡片時經執行器讀這部作品（Jellyfin 照提出卡片的那個人打開），每一列的
發佈照結果表的同一個預估蓋到哪幾集，其中帳本有或 Jellyfin 已有的記進 `preview.held`。場景是確認卡
測試那一台（`test_agent_cards.py`）：SPY×FAMILY 第 1 季的替身只有第 1、25 集。
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.jellyfin import ITEM_EPISODE, ITEM_SERIES, JellyfinItem
from berth.config import Config
from berth.domain import PlanAction
from berth.models import LedgerEntry
from tests.integration.factories import FakeClientFactory
from tests.integration.test_agent_api import Script, chat
from tests.integration.test_agent_cards import (
    CALL,
    berth_services,
    card,
    cards,
    in_db,
    rows,
    running_berth,
    script,
)
from tests.integration.test_media import SPY_ID

__all__ = ["script"]  # pytest 的 fixture

SPY_SERIES = "5" * 32


@pytest.fixture
def factory(roots: dict[str, Path], script: Script) -> FakeClientFactory:
    """Jellyfin 的 TV 媒體庫有 SPY×FAMILY，其中一集的播出日是 TMDB 的第 25 集（2022-12-24）。"""
    made = berth_services(roots, script)
    fake = made.jellyfin_
    [tv] = [row.locations[0] for row in fake.libraries_ if row.name == "TV"]
    fake.items_ = [
        *fake.items_,
        JellyfinItem(SPY_SERIES, ITEM_SERIES, "SPY x FAMILY", f"{tv}/SPY", "120089"),
        JellyfinItem(
            "6" * 32,
            ITEM_EPISODE,
            "FIRST CONTACT",
            f"{tv}/SPY/Season 01/S01E25.mkv",
            "",
            series_id=SPY_SERIES,
            season=1,
            episode_start=25,
            premiere_date=date(2022, 12, 24),
        ),
    ]
    return made


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    roots["incomplete"].mkdir(parents=True, exist_ok=True)
    yield from running_berth(config, tmp_path, roots, factory)


def imported_first_episode(client: TestClient) -> None:
    """帳本有第 1 集（作品頁先讀過一次：帳本的 `media_id` 要那一列在）。"""
    assert client.get(f"/api/media/{SPY_ID}").status_code == 200

    async def write(session: AsyncSession) -> None:
        session.add(
            LedgerEntry(
                source_rel_path="SPY/01.mkv",
                source_abs_path="/data/complete/SPY/01.mkv",
                source_dev="1",
                target_path="/data/media/tv/SPY/Season 01/S01E01.mkv",
                target_inode="2",
                media_id=SPY_ID,
                action=PlanAction.IMPORT,
                season=1,
                episode_start=1,
            )
        )
        await session.commit()

    in_db(client, write)


def held(proposal: dict[str, Any]) -> list[list[tuple[int, int]]]:
    return [
        [(episode["season"], episode["episode"]) for episode in row]
        for row in proposal["preview"]["held"]
    ]


class TestTheCardSaysWhatYouHave:
    def test_each_row_lists_the_episodes_already_in_the_ledger_or_jellyfin(
        self, client: TestClient, script: Script
    ) -> None:
        imported_first_episode(client)
        script.steps = [card(rows(client, 1, 25, 2))]

        chat(client, "Download SPY×FAMILY 1, 25 and 2.")

        [proposal] = cards(client)
        assert proposal["tool_call_id"] == CALL
        assert held(proposal) == [[(1, 1)], [(1, 25)], []]

    def test_a_card_with_nothing_held_says_nothing(
        self, client: TestClient, script: Script
    ) -> None:
        script.steps = [card(rows(client, 2))]

        chat(client, "Download SPY×FAMILY 2.")

        [proposal] = cards(client)
        assert proposal["preview"]["held"] == []
