"""服務自報的版號字串 → 可以比大小的 tuple。Jellyfin 與 Prowlarr 的版本下限共用（brief §16.4）。"""

from __future__ import annotations

from itertools import takewhile


def parse_version(version: str) -> tuple[int, ...]:
    """`12.1.0` → `(12, 1, 0)`、`2.0.5.5160` → `(2, 0, 5, 5160)`。

    認不得的片段當 0，整串認不得就是 `(0,)`——讀不出版號的一律當成太舊。
    """
    parts = []
    for chunk in version.split("."):
        digits = "".join(takewhile(str.isdigit, chunk))
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)
