"""Berth 的命令列進入點。

`--version` 與參數錯誤沿用 argparse 的慣例，直接以 `SystemExit` 結束；
`main` 的回傳值只用在有實際工作要做的路徑上。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from importlib.metadata import version

PROGRAM_NAME = "berth"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description="Self-hosted media acquisition and import coordinator.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version(PROGRAM_NAME)}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = list(sys.argv[1:] if argv is None else argv)

    if not args:
        parser.print_help(sys.stderr)
        return 2

    parser.parse_args(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
