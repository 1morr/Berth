"""使用者文件的兩件事（M4 票 57）：

- `README.md`（英文）與 `README.zh-Hant.md` 段落一一對應：標題的層級一節一節相同、連出去的東西
  相同（兩份互連的那一條與同檔錨點除外）。改了一份忘了另一份，這裡紅。
- README 兩份、`docs/guide/`、`docs/development.md` 裡的相對連結都指得到檔案，帶錨點的指得到
  那一份 Markdown 裡的標題（GitHub 的錨點算法）。

比的是標題層級與連結目標，不是文字——翻譯換句話說、標題改措辭都不影響。
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
README_ZH = ROOT / "README.zh-Hant.md"

_FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)|<img [^>]*src=\"([^\"]+)\"|<(https?://[^>]+)>")
_HEADING = re.compile(r"^(#{1,6}) +(.+?) *$", re.MULTILINE)


def _prose(markdown: str) -> str:
    """去掉程式碼區塊：裡面的 `# 註解` 與 `[x](y)` 不是標題也不是連結。"""
    return _FENCE.sub("", markdown)


def links(markdown: str) -> list[str]:
    """一份 Markdown 裡的連結與圖片目標，程式碼區塊裡的不算。"""
    matches = _LINK.finditer(_prose(markdown))
    return [next(group for group in match.groups() if group) for match in matches]


def heading_levels(markdown: str) -> list[int]:
    """標題一個接一個的層級（`#` 的個數），程式碼區塊裡的不算。"""
    return [len(marks) for marks, _ in _HEADING.findall(_prose(markdown))]


def anchors(markdown: str) -> set[str]:
    """GitHub 替每個標題產生的錨點：小寫、去掉標點、空白換成 `-`，重複的加 `-1`、`-2`。"""
    seen: Counter[str] = Counter()
    result = set()
    for _, heading in _HEADING.findall(_prose(markdown)):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        result.add(slug if not seen[slug] else f"{slug}-{seen[slug]}")
        seen[slug] += 1
    return result


def _outward(markdown: str) -> Counter[str]:
    """連出這一份的目標：同檔錨點與兩份互連的那一條不算。"""
    return Counter(
        target
        for target in links(markdown)
        if not target.startswith("#") and target not in {README.name, README_ZH.name}
    )


def pair_violations(english: str, chinese: str) -> list[str]:
    """兩份 README 對不上的地方。"""
    problems = []
    english_levels, chinese_levels = heading_levels(english), heading_levels(chinese)
    if english_levels != chinese_levels:
        problems.append(
            f"heading levels differ: README.md {english_levels}, README.zh-Hant.md {chinese_levels}"
        )
    english_links, chinese_links = _outward(english), _outward(chinese)
    for target in sorted((english_links - chinese_links) + (chinese_links - english_links)):
        problems.append(f"link only in one README: {target}")
    return problems


def broken_links(path: Path, markdown: str) -> list[str]:
    """`path` 裡指不到東西的相對連結。"""
    problems = []
    for target in links(markdown):
        if re.match(r"[a-z]+:", target):
            continue
        file_part, _, anchor = target.partition("#")
        destination = (path.parent / file_part).resolve() if file_part else path
        if not destination.exists():
            problems.append(f"{path.name}: {target} (no such file)")
        elif (
            anchor
            and destination.suffix == ".md"
            and anchor not in anchors(destination.read_text(encoding="utf-8"))
        ):
            problems.append(f"{path.name}: {target} (no such heading)")
    return problems


def user_docs() -> list[Path]:
    guides = sorted((ROOT / "docs" / "guide").glob("*.md"))
    return [README, README_ZH, ROOT / "docs" / "development.md", *guides]


def test_the_two_readmes_match() -> None:
    english = README.read_text(encoding="utf-8")
    chinese = README_ZH.read_text(encoding="utf-8")

    assert pair_violations(english, chinese) == []
    assert README_ZH.name in links(english)
    assert README.name in links(chinese)


@pytest.mark.parametrize("path", user_docs(), ids=lambda path: path.relative_to(ROOT).as_posix())
def test_relative_links_resolve(path: Path) -> None:
    assert broken_links(path, path.read_text(encoding="utf-8")) == []


class TestTheGatesThemselves:
    """兩道檢查各自紅得起來，也不被無關的改動弄紅。"""

    ENGLISH = (
        "# A\n\n[中文](README.zh-Hant.md)\n\n## Install\n\nSee [guide](docs/guide/x.md).\n\n"
        "## Status\n\n[up](#install)\n"
    )
    CHINESE = (
        "# A\n\n[English](README.md)\n\n## 安裝\n\n見[指南](docs/guide/x.md)。\n\n"
        "## 現況\n\n[上](#安裝)\n"
    )

    def test_matching_pair_passes(self) -> None:
        assert pair_violations(self.ENGLISH, self.CHINESE) == []

    def test_a_section_missing_from_one_side_is_red(self) -> None:
        shorter = self.CHINESE.replace("## 現況\n\n[上](#安裝)\n", "")
        assert pair_violations(self.ENGLISH, shorter) != []

    def test_a_subsection_on_one_side_only_is_red(self) -> None:
        deeper = self.CHINESE.replace("## 現況\n", "## 現況\n\n### 已知問題\n")
        assert pair_violations(self.ENGLISH, deeper) != []

    def test_a_link_missing_from_one_side_is_red(self) -> None:
        unlinked = self.CHINESE.replace("見[指南](docs/guide/x.md)。", "見指南。")
        assert pair_violations(self.ENGLISH, unlinked) != []

    def test_rewording_and_renaming_headings_stays_green(self) -> None:
        reworded = self.CHINESE.replace("## 安裝", "## 怎麼裝").replace(
            "見[指南]", "請看[這份指南]"
        )
        assert pair_violations(self.ENGLISH, reworded) == []

    def test_headings_inside_code_blocks_do_not_count(self) -> None:
        commented = self.CHINESE.replace("## 安裝\n", "## 安裝\n\n```bash\n## 這是註解\n```\n")
        assert pair_violations(self.ENGLISH, commented) == []

    def test_a_missing_file_or_heading_is_red(self, tmp_path: Path) -> None:
        guide = tmp_path / "guide.md"
        guide.write_text("# Guide\n\n## What an existing service needs\n", encoding="utf-8")
        page = tmp_path / "page.md"

        assert broken_links(page, "[x](missing.md)") != []
        assert broken_links(page, "[x](guide.md#no-such-heading)") != []
        assert broken_links(page, "[x](guide.md#what-an-existing-service-needs)") == []

    def test_links_in_code_blocks_and_absolute_urls_are_ignored(self, tmp_path: Path) -> None:
        page = tmp_path / "page.md"
        text = (
            "```\n[x](nowhere.md)\n```\n\n<https://example.com/a>\n\n[y](https://example.com/b)\n"
        )

        assert broken_links(page, text) == []

    def test_anchors_follow_github(self) -> None:
        text = (
            "## Status & known limitations\n\n## `berth rebuild-ledger`\n\n"
            "## 現況與已知限制\n\n## Status & known limitations\n"
        )

        assert anchors(text) == {
            "status--known-limitations",
            "berth-rebuild-ledger",
            "現況與已知限制",
            "status--known-limitations-1",
        }
