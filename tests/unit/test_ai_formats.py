"""每一種 `ApiFormat` 都有 adapter（`adapters.ai.formats`）：加了格式忘了接，存得進設定、一叫模型就
`KeyError`。"""

from __future__ import annotations

from berth.adapters.ai.formats import FORMATS
from berth.domain import ApiFormat


def test_every_format_has_an_adapter() -> None:
    assert set(FORMATS) == set(ApiFormat)
