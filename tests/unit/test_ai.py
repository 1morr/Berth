"""AI fallback 的介面（plan §4.5、brief §6.10）。

M1 只定介面與那個什麼都不做的實作。**這一票就要定**，因為它決定了規則層的產物長什麼樣子：
`propose` 收的 `rules_plan` 與回的 Plan 是同一個型別，所以 AI 只能提案，不能發明一種
規則層表達不出來的處置（brief §6.10「AI 是 fallback 解析器與助理，不是執行者」）。
"""

from __future__ import annotations

import pytest

from berth.adapters.ai import AiPlanner, NullAiPlanner
from berth.domain import Confidence, FileEntry, FileKind, ParseContext, PlanAction, PlanItem


def rules_plan() -> tuple[PlanItem, ...]:
    return (
        PlanItem(
            rel_path="Show - 03.mkv",
            kind=FileKind.VIDEO,
            action=PlanAction.REVIEW,
            confidence=Confidence.LOW,
        ),
    )


class TestNullAiPlanner:
    def test_it_satisfies_the_interface(self) -> None:
        planner: AiPlanner = NullAiPlanner()

        assert planner is not None

    @pytest.mark.asyncio
    async def test_it_never_proposes_anything(self) -> None:
        """沒有提案時回 `None` 而不是空的 Plan：空的 Plan 是「這一包什麼都不用做」，
        而這裡要說的是「我沒有意見」，兩者的下一步不同（brief §6.10 退回 review）。
        """
        files = (FileEntry(rel_path="Show - 03.mkv", size=1),)

        proposed = await NullAiPlanner().propose(ParseContext(), files, rules_plan())

        assert proposed is None
