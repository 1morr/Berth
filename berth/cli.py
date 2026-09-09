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

import uvicorn

from berth.config import PACKAGE_NAME, VERSION, load_config

PROGRAM_NAME = PACKAGE_NAME

#: 容器內要對外可達；只想本機聽的人用 docker 的 port mapping 限制。
HOST = "0.0.0.0"

#: uvicorn 以 import string + factory 載入 app，`--reload` 才能重建它。
APP_FACTORY = "berth.main:create_app"


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


def _serve(args: argparse.Namespace) -> int:
    config = load_config()
    uvicorn.run(APP_FACTORY, factory=True, host=HOST, port=config.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
