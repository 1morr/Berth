"""Berth 的命令列進入點。

`--version` 與參數錯誤沿用 argparse 的慣例，直接以 `SystemExit` 結束；
`main` 的回傳值只用在有實際工作要做的路徑上。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

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


def _serve(args: argparse.Namespace) -> int:
    config = load_config()
    uvicorn.run(APP_FACTORY, factory=True, host=HOST, port=config.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
