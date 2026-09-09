"""錄 `tests/fixtures/tmdb/` 的快照（plan §4.6、票 05）。

benchmark 是離線的：解析器只吃 `MediaSnapshot`，所以語料要用的每一部作品都先錄一份快照
凍在 repo 裡，測試不打外部（plan §10）。

**錄的是產品自己的路徑**：這支開一個暫時的資料庫、把憑證寫進去、呼叫 `refresh_media`，
再把 `media.tmdb_snapshot_json` 原樣寫出去。手工組一份 JSON 只會證明它與想像一致；
這樣錄下來的形狀與 Berth 執行時存進資料庫的那一份是同一個。

用法（憑證只給開發用的腳本，產品不讀它——票 02b）：

    uv run --env-file .env python scripts/record_tmdb_snapshots.py

已存在的快照預設跳過（「錄一次即凍結」）；`--force` 重錄全部。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from berth.config import load_config
from berth.db import create_engine, create_session_factory, upgrade_to_head
from berth.models import Media, TmdbSettings
from berth.services.bench import load_corpus, paths
from berth.services.clients import HttpServiceClientFactory
from berth.services.media import refresh_media
from berth.services.settings import write_settings

CORPUS, SNAPSHOTS, _BASELINE = paths(Path(__file__).resolve().parent.parent)

#: 與實驗腳本同一個變數名（`.env.example`）。Berth 本身不讀它。
CREDENTIAL_ENV = "TMDB_API_KEY"


def wanted() -> dict[str, str]:
    """語料指到的每一份快照：`tv-209867` → `tv:209867`。

    語料怎麼讀由 `services/bench` 說了算——這裡再刻一份的話，語料目錄或欄位一改就要動兩處。
    """
    return {fixture.tmdb: fixture.context_media for fixture in load_corpus(CORPUS)}


async def record(credential: str, *, force: bool) -> int:
    targets = wanted()
    missing = {
        name: media_id
        for name, media_id in targets.items()
        if force or not (SNAPSHOTS / f"{name}.json").exists()
    }
    if not missing:
        print(f"{len(targets)} snapshots already frozen; nothing to record.")
        return 0

    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        config = load_config({"CONFIG_ROOT": str(root / "config"), "DATA_ROOT": str(root / "data")})
        config.config_root.mkdir(parents=True, exist_ok=True)
        engine = create_engine(config)
        try:
            await upgrade_to_head(engine)
            async with create_session_factory(engine)() as session:
                await write_settings(session, TmdbSettings(api_key=credential))
                await session.commit()
                factory = HttpServiceClientFactory()
                for name, media_id in missing.items():
                    view = await refresh_media(session, factory, media_id)
                    if view.problem is not None:
                        print(f"{name}: {view.problem} {view.detail}", file=sys.stderr)
                        return 1
                    row = await session.get(Media, media_id)
                    assert row is not None and row.tmdb_snapshot_json is not None
                    payload = json.dumps(row.tmdb_snapshot_json, ensure_ascii=False, indent=1)
                    (SNAPSHOTS / f"{name}.json").write_text(payload + "\n", encoding="utf-8")
                    seasons = len(view.seasons)
                    print(f"{name}: {view.title_en} ({view.year}) — {seasons} seasons")
        finally:
            await engine.dispose()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-record snapshots that exist.")
    args = parser.parse_args(argv)

    credential = os.environ.get(CREDENTIAL_ENV, "").strip()
    if not credential:
        print(f"{CREDENTIAL_ENV} is not set; see .env.example.", file=sys.stderr)
        return 2
    return asyncio.run(record(credential, force=args.force))


if __name__ == "__main__":
    raise SystemExit(main())
