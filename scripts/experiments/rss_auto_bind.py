"""RSS Series 自動綁定的規則門檻，對真的 Mikan 與 TMDB 量一次（M3 票 09 的驗收第 5 條）。

輸入是票 07 錄下來的 Mikan 聚合 feed（`tests/fixtures/http/mikan/rss-mybangumi.xml`，使用者
`MyBangumi` 裡的真實作品）。每一個 RSS Series 走 Berth 自己的那一條：真的抓單集頁取（番組 id,
字幕組 id）、真的抓番組頁取中文名與「放送开始」、真的打 TMDB 搜尋與讀詳情，判定用
`parser.binding.judge`——與 `services.rss._auto_bind` 同一組函式（`_clues`、`_candidates`），
只是不綁、不送單。Route 那一步不在這裡量：它看的是使用者的媒體庫設定，不是規則。

量的是「規則說有把握的有幾部、其中錯了幾部」。對錯由人看印出來的作品判斷，結果記在票 09 的
Comments 與 `docs/research/rss-sources.md` §2.8。

TMDB 憑證讀環境變數 `TMDB_API_KEY`（v3 key 或 v4 token，`.env.example` 給實驗腳本的那一個），
不印出來；資料庫是暫時目錄裡的一份新的（跑完就丟），不碰任何 Berth 環境。會 import `berth`，
要用 `uv run` 跑：

    uv run --env-file .env python scripts/experiments/rss_auto_bind.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from berth.adapters.rss.client import HttpFeedFetcher
from berth.adapters.rss.mikan import parse_feed, series_key
from berth.config import load_config
from berth.db import create_engine, create_session_factory, upgrade_to_head
from berth.models import RssSeries, TmdbSettings
from berth.parser.binding import judge, search_terms
from berth.services.clients import HttpServiceClientFactory
from berth.services.rss import _candidates, _clues, _LookupError
from berth.services.settings import write_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
FEED = REPO_ROOT / "tests" / "fixtures" / "http" / "mikan" / "rss-mybangumi.xml"


async def main() -> int:
    key = os.environ.get("TMDB_API_KEY", "")
    if not key:
        print("set TMDB_API_KEY to a TMDB v3 key or v4 token", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as root:
        config = load_config({"CONFIG_ROOT": f"{root}/config", "DATA_ROOT": f"{root}/data"})
        config.config_root.mkdir(parents=True)
        engine = create_engine(config)
        await upgrade_to_head(engine)
        try:
            async with create_session_factory(engine)() as session:
                await write_settings(session, TmdbSettings(api_key=key))
                await measure(session)
        finally:
            await engine.dispose()
    return 0


async def measure(session) -> None:  # type: ignore[no-untyped-def]  # 一次性腳本，AsyncSession
    factory = HttpServiceClientFactory()
    fetcher = HttpFeedFetcher()
    seen: set[tuple[int, int]] = set()
    confident = 0
    try:
        # 舊的先，與 `_record` 同一個順序：長出 Series 的是它第一次出現的那一筆。
        for item in reversed(parse_feed(FEED.read_bytes())):
            page = (await fetcher.fetch(item.link)).decode("utf-8", errors="replace")
            pair = series_key(page)
            if pair is None or pair in seen:
                continue
            seen.add(pair)
            series = RssSeries(
                key=f"mikan:{pair[0]}:{pair[1]}",
                mikan_bangumi_id=pair[0],
                mikan_subgroup_id=pair[1],
                title_raw=item.title,
            )
            print(f"\n== mikan {pair[0]} x {pair[1]}  {item.title}")
            try:
                clues = await _clues(fetcher, series)
                print(f"   mikan: {clues.title!r}  premiere={clues.premiere}")
                print(f"   search: {search_terms(clues)}")
                shots, missed = await _candidates(session, factory, clues)
            except _LookupError as failed:
                kind = "transient" if failed.transient else "final"
                print(f"   LOOKUP FAILED ({kind}): {failed}")
                continue
            if missed is not None:
                kind = "transient" if missed.transient else "final"
                print(f"   skipped ({kind}): {missed}")
            for shot in shots:
                aired = [(row.season_number, str(row.air_date)) for row in shot.seasons]
                print(f"   candidate {shot.kind.value}:{shot.tmdb_id} {shot.title_en!r} {aired}")
            verdict = judge(clues, shots)
            if verdict.media is not None:
                confident += 1
                shot = verdict.media
                print(f"   => BIND {shot.kind.value}:{shot.tmdb_id} {shot.title_en!r}")
                print(f"      shown as {shot.title!r}")
            else:
                print("   => PENDING")
            for reason in verdict.reasons:
                print(f"      {reason.code.value} {reason.params}")
    finally:
        await fetcher.aclose()
    print(f"\nseries: {len(seen)}  confident: {confident}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
