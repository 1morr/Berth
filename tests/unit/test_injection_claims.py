"""plan §11.6〈注入的防線與守它的測試〉那張表與測試對得上（M5 票 15）。

兩個方向：

- 表裡引用的每一條測試都在：Python 的寫成 `tests/...py::Class::test_name`，前端的寫成
  `web/src/...test.tsx::<it 的標題>`。測試改名或刪掉而表沒跟著改，這裡紅。
- `tests/integration/test_agent_injection.py` 的每一條都在表裡：加了新的注入測試卻沒說它守哪一條，
  這裡紅。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs" / "plan.md"
INJECTION_TESTS = "tests/integration/test_agent_injection.py"

_TITLE = "**注入的防線與守它的測試**"
_PYTHON = re.compile(r"`(tests/[^`:]+\.py)::(\w+)::(\w+)`")
_FRONTEND = re.compile(r"`(web/src/[^`:]+\.test\.tsx)::([^`]+)`")


def table(plan: str) -> str:
    """那一段之後緊接著的表（縮排的 `|` 開頭的列）。"""
    lines = plan.splitlines()
    [start] = [index for index, line in enumerate(lines) if _TITLE in line]
    rows: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip().startswith("|"):
            rows.append(line)
        elif rows:
            break
    return "\n".join(rows)


def python_claims(text: str) -> set[tuple[str, str, str]]:
    return set(_PYTHON.findall(text))


def frontend_claims(text: str) -> set[tuple[str, str]]:
    return set(_FRONTEND.findall(text))


#: 模組層的測試函式在表裡引用不了（引用要 `Class::test`）：放在這個名字底下，一定算沒列進表。
MODULE = "<module>"


def python_tests(source: str) -> set[tuple[str, str]]:
    """一份測試檔裡的測試：`Test*` 類別的 `test_*` 方法，與模組層的 `test_*` 函式（`MODULE`）。
    `async def` 也算。"""
    tests: set[tuple[str, str]] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test_"
        ):
            tests.add((MODULE, node.name))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            tests.update(
                (node.name, item.name)
                for item in node.body
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
                and item.name.startswith("test_")
            )
    return tests


def missing_python(claims: set[tuple[str, str, str]]) -> list[str]:
    missing = []
    for path, cls, name in sorted(claims):
        file = ROOT / path
        if not file.exists() or (cls, name) not in python_tests(file.read_text()):
            missing.append(f"{path}::{cls}::{name}")
    return missing


def missing_frontend(claims: set[tuple[str, str]]) -> list[str]:
    missing = []
    for path, title in sorted(claims):
        file = ROOT / path
        if not file.exists() or not re.search(
            rf"\bit\(\s*['\"]{re.escape(title)}['\"]", file.read_text()
        ):
            missing.append(f"{path}::{title}")
    return missing


def unclaimed(source: str, claims: set[tuple[str, str, str]]) -> list[str]:
    said = {(cls, name) for path, cls, name in claims if path == INJECTION_TESTS}
    return sorted(f"{cls}::{name}" for cls, name in python_tests(source) - said)


def test_every_test_the_table_cites_exists() -> None:
    text = table(PLAN.read_text())
    assert python_claims(text)
    assert frontend_claims(text)
    assert missing_python(python_claims(text)) == []
    assert missing_frontend(frontend_claims(text)) == []


def test_every_injection_test_is_in_the_table() -> None:
    claims = python_claims(table(PLAN.read_text()))
    assert unclaimed((ROOT / INJECTION_TESTS).read_text(), claims) == []


# ---------------------------------------------------------------- 規則本身


_CITED = (
    f"{INJECTION_TESTS}::TestAFeedFromOutside::"
    "test_the_users_own_feed_swapped_for_the_contents_is_refused"
)
_PLAN = f"""\
- **注入的防線與守它的測試**（票 15）：說明。

  | 防線 | 測試 |
  | --- | --- |
  | 網址 | `{_CITED}` |
  | 圖片 | `web/src/agent/Markdown.test.tsx::does not load an image the reply points at` |

下一段。`tests/integration/test_agent_api.py::TestNope::test_not_in_the_table`
"""


def test_a_renamed_test_is_caught() -> None:
    renamed = _PLAN.replace("swapped_for", "traded_for").replace("the reply", "a reply")
    text = table(renamed)
    assert missing_python(python_claims(text)) == [
        f"{INJECTION_TESTS}::TestAFeedFromOutside::"
        "test_the_users_own_feed_traded_for_the_contents_is_refused"
    ]
    assert missing_frontend(frontend_claims(text)) == [
        "web/src/agent/Markdown.test.tsx::does not load an image a reply points at"
    ]


def test_a_new_injection_test_left_out_is_caught() -> None:
    source = (
        "class TestNew:\n"
        "    def test_more(self):\n        pass\n\n"
        "    async def test_async(self):\n        pass\n\n"
        "    def helper(self):\n        pass\n\n"
        "def test_loose():\n    pass\n"
    )
    assert unclaimed(source, python_claims(table(_PLAN))) == [
        f"{MODULE}::test_loose",
        "TestNew::test_async",
        "TestNew::test_more",
    ]


def test_only_the_table_counts() -> None:
    """表後面的段落提到的測試不算宣稱。"""
    assert ("tests/integration/test_agent_api.py", "TestNope", "test_not_in_the_table") not in (
        python_claims(table(_PLAN))
    )


def test_reordering_or_respacing_the_table_changes_nothing() -> None:
    lines = _PLAN.splitlines()
    reordered = "\n".join([*lines[:4], lines[5], lines[4], *lines[6:]])
    respaced = reordered.replace(" | ", " |   ")
    text = table(respaced)
    assert missing_python(python_claims(text)) == []
    assert missing_frontend(frontend_claims(text)) == []
    assert python_claims(text) == python_claims(table(_PLAN))
