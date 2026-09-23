"""Berth 的命令列進入點。

`--version` 與參數錯誤沿用 argparse 的慣例，直接以 `SystemExit` 結束；
`main` 的回傳值只用在有實際工作要做的路徑上。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn

from berth.config import PACKAGE_NAME, VERSION, Config, load_config

if TYPE_CHECKING:
    from berth.services.ledger_rebuild import RebuildReport

PROGRAM_NAME = PACKAGE_NAME

#: 容器內要對外可達；只想本機聽的人用 docker 的 port mapping 限制。
HOST = "0.0.0.0"

#: uvicorn 以 import string + factory 載入 app，`--reload` 才能重建它。
APP_FACTORY = "berth.main:create_app"

#: 語料與 baseline 在 repo 裡，不在安裝後的 wheel 裡——`berth bench` 是開發指令。
REPO_ROOT = Path(__file__).resolve().parent.parent

BASELINE_NOTE = "Written by `berth bench --update-baseline`. Raising it needs a reason in the PR."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description="Self-hosted media acquisition and import coordinator.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    subcommands = parser.add_subparsers()

    serve = subcommands.add_parser("serve", help="Run the Berth server.")
    serve.add_argument(
        "--reload",
        action="store_true",
        help="Restart on source changes. Development only.",
    )
    serve.set_defaults(handler=_serve)

    openapi = subcommands.add_parser(
        "openapi",
        help="Print the OpenAPI document. Input to the frontend type generator.",
    )
    openapi.add_argument(
        "--output",
        type=Path,
        help="Write to this file instead of stdout.",
    )
    openapi.set_defaults(handler=_openapi)

    bench = subcommands.add_parser(
        "bench",
        help="Run the parser benchmark over the frozen corpus (plan 4.6).",
    )
    bench.add_argument(
        "--update-baseline",
        action="store_true",
        help="Write the current numbers to the baseline. Say why in the commit message.",
    )
    bench.set_defaults(handler=_bench)

    rebuild = subcommands.add_parser(
        "rebuild-ledger",
        help=(
            "Grow the ledger back from the library: every file the ledger does not know is"
            " matched to complete by inode and read back through the naming templates."
            " Files that do not match become unmanaged_library_file issues. Deletes nothing."
        ),
    )
    rebuild.set_defaults(handler=_rebuild_ledger)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = list(sys.argv[1:] if argv is None else argv)

    if not args:
        parser.print_help(sys.stderr)
        return 2

    parsed = parser.parse_args(args)
    handler: Callable[[argparse.Namespace], int] = parsed.handler
    return handler(parsed)


def _openapi(args: argparse.Namespace) -> int:
    """產生 OpenAPI 文件（plan §6）。**不跑起服務**：`create_app` 只組裝路由，
    lifespan 沒有執行，所以沒有資料庫、沒有連線，CI 與離線開發都產得出來。

    一律寫 UTF-8 位元組而不是交給文字串流：描述來自繁體中文 docstring，
    Windows 主控台的預設編碼（cp950）寫到一半就會炸。
    """
    # 在指令裡才 import：`berth.main` 要 686 ms，`--version` 與 `serve` 的參數解析不該付這筆。
    from berth.main import create_app

    document = create_app().openapi()
    # 尾端換行讓它是一個正常的文字檔；`ensure_ascii=False` 讓中文描述維持可讀。
    payload = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

    if args.output is None:
        sys.stdout.buffer.write(payload)
    else:
        args.output.write_bytes(payload)
    return 0


def _bench(args: argparse.Namespace) -> int:
    """解析基準測試（plan §4.6、brief §6.9）。**不連線**：語料與 TMDB 快照都在 repo 裡。

    離開碼是 CI 的門檻：分類錯、自動入錯，或掉到 baseline 以下就是 1。
    """
    from berth.services.bench import (
        dump_baseline,
        load_baseline,
        paths,
        regressions,
        render,
        run,
    )

    corpus_root, snapshot_root, baseline_path = paths(REPO_ROOT)
    report = run(corpus_root, snapshot_root)
    # 報表含中文以外的欄位也可能超出 cp950，一律以 UTF-8 位元組寫出（與 `openapi` 同理）。
    sys.stdout.buffer.write((render(report) + "\n").encode("utf-8"))

    if args.update_baseline:
        dump_baseline(baseline_path, report, note=BASELINE_NOTE)
        return 0

    problems = [*report.failures, *regressions(report, load_baseline(baseline_path))]
    for problem in problems:
        print(f"bench: {problem}", file=sys.stderr)
    return 1 if problems else 0


def _rebuild_ledger(args: argparse.Namespace) -> int:
    """`berth rebuild-ledger`（plan §11.3 決定 9、M2 票 10）。

    與服務共用同一個資料庫（WAL，服務開著也能跑），所以先把 schema 升到最新——CLI 可能比
    服務早一步跑在新版本上。**只加不減**：配不上的檔案變成 Issue，一個位元組都不刪。
    離開碼 1 是有 Route 的目標目錄或 complete 的子目錄讀不到：那幾條根本沒有比到，不能說成
    「全部配好了」。
    """
    import asyncio

    report = asyncio.run(_run_rebuild(load_config()))
    lines = [
        f"already in the ledger: {report.known}",
        f"grown back: {report.claimed}",
        *(f"unmatched ({reason.value}): {count}" for reason, count in report.unmatched.items()),
        *(f"skipped route: {line}" for line in report.skipped),
        *(f"unreadable complete: {line}" for line in report.unread_complete),
        *([f"not decided (complete unreadable): {report.undecided}"] if report.undecided else []),
    ]
    # 路徑可能是中文，與 `openapi` 同一個理由一律寫 UTF-8 位元組。
    sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8"))
    return 1 if report.skipped or report.unread_complete else 0


async def _run_rebuild(config: Config) -> RebuildReport:
    from berth.db import create_engine, create_session_factory, upgrade_to_head
    from berth.services.clients import HttpServiceClientFactory
    from berth.services.ledger_rebuild import rebuild_ledger

    engine = create_engine(config)
    try:
        await upgrade_to_head(engine)
        async with create_session_factory(engine)() as session:
            return await rebuild_ledger(session, HttpServiceClientFactory())
    finally:
        await engine.dispose()


def _serve(args: argparse.Namespace) -> int:
    config = load_config()
    uvicorn.run(APP_FACTORY, factory=True, host=HOST, port=config.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
