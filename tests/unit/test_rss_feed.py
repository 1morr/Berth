"""三站共用的那一點（`berth/adapters/rss/__init__.py`、`feed.py`，M3 票 11）。"""

from __future__ import annotations

import pytest

from berth.adapters.rss import approx_bytes


class TestApproxBytes:
    """三站的大小寫法（研究檔 §2.4、§3.1）：只當顯示用的近似值。"""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("240.5 MiB", int(240.5 * 1024**2)),
            ("1.3 GiB", int(1.3 * 1024**3)),
            ("518.65 MB", int(518.65 * 1000**2)),
            ("5.79 GB", int(5.79 * 1000**3)),
            ("812 Bytes", 812),
            ("1 Byte", 1),
        ],
    )
    def test_binary_and_decimal_units(self, text: str, expected: int) -> None:
        assert approx_bytes(text) == expected

    @pytest.mark.parametrize("text", ["", "big", "12 parsecs"])
    def test_what_it_cannot_read_is_none(self, text: str) -> None:
        assert approx_bytes(text) is None
