"""Skills：側面板的工作流程說明（M5 票 19、plan §11.6〈分段〉第 7 段）。

- **格式閘門**：`berth/skills/<name>/SKILL.md`，YAML frontmatter 照 Agent Skills 規格的 `name` /
  `description`，加 Berth 的 `tools`；其餘的鍵、資料夾裡的其他檔案一律拒絕（只能是指令）。
  每條違規造一份證明會紅，改無關的格式證明不紅。
- **漸進揭露**：instructions 只列名稱與描述，`skills.load_skill` 回全文；流程要的工具這個人在側面板
  看不到的，不列也不給載。
- **宣告的工具都是側面板的工具**：票 16 之後沒有還在等的（原本的 `PENDING` 跟著拿掉）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from berth.domain import Role
from berth.services.agent_tools import TAVILY_TOOL, TOOLS, tool_name
from berth.services.registry import commands
from berth.services.skills import (
    SKILLS_ROOT,
    Skill,
    SkillFormatError,
    SkillRefusal,
    SkillRefusedError,
    available,
    catalog,
    list_skills,
    load_skill,
    parse_skill,
    read_skills,
)

#: 第一批（票 19）。
FIRST_BATCH = {"series-mapping", "new-season-picks", "why-not-imported", "missing-episodes"}

VALID = """\
---
name: why-not-imported
description: Explain why a show or an episode is not in the library. Use when asked why.
tools:
  - why_not.explain
---

1. Call `why_not_explain` with the work's media_id.
2. Say which conclusion it reached.
"""


def write(root: Path, folder: str, text: str) -> Path:
    (root / folder).mkdir(parents=True, exist_ok=True)
    path = root / folder / "SKILL.md"
    path.write_text(text, encoding="utf-8")
    return path


class TestTheFormat:
    def test_a_well_formed_file_parses(self) -> None:
        skill = parse_skill("why-not-imported", VALID)
        assert skill == Skill(
            name="why-not-imported",
            description="Explain why a show or an episode is not in the library. "
            "Use when asked why.",
            tools=("why_not.explain",),
            body="1. Call `why_not_explain` with the work's media_id.\n"
            "2. Say which conclusion it reached.",
        )

    @pytest.mark.parametrize(
        ("broken", "complaint"),
        [
            pytest.param(VALID.removeprefix("---\n"), "frontmatter", id="no-frontmatter"),
            pytest.param(VALID.replace("---\n\n1.", "\n1."), "frontmatter", id="unclosed"),
            pytest.param(VALID.replace("tools:\n", "tools: [\n"), "YAML", id="bad-yaml"),
            pytest.param(VALID.replace("name: why-not-imported\n", ""), "name", id="no-name"),
            pytest.param(
                VALID.replace("name: why-not-imported", "name: Why_Not"), "name", id="name-case"
            ),
            pytest.param(
                VALID.replace("name: why-not-imported", "name: why-not-"), "name", id="name-hyphen"
            ),
            pytest.param(
                VALID.replace("name: why-not-imported", "name: why-not-found"),
                "folder",
                id="name-differs-from-folder",
            ),
            pytest.param(
                VALID.replace(
                    "description: Explain why a show or an episode is not in the library. "
                    "Use when asked why.",
                    "description: '  '",
                ),
                "description",
                id="blank-description",
            ),
            pytest.param(
                VALID.replace("Use when asked why.", "x" * 1024), "description", id="long"
            ),
            pytest.param(
                VALID.replace("tools:", "allowed-tools: Bash\ntools:"),
                "allowed-tools",
                id="unknown-key",
            ),
            pytest.param(
                VALID.replace("tools:\n  - why_not.explain\n", "tools: why_not.explain\n"),
                "tools",
                id="tools-not-a-list",
            ),
            pytest.param(
                VALID.replace("tools:\n  - why_not.explain\n", "tools: []\n"),
                "tools",
                id="no-tools",
            ),
            pytest.param(
                VALID.replace("  - why_not.explain\n", "  - why_not_explain\n"),
                "tools",
                id="tool-not-a-command-name",
            ),
            pytest.param(
                VALID.replace("  - why_not.explain\n", "  - why_not.explain\n  - jobs.list_jobs\n"),
                "jobs_list_jobs",
                id="declared-tool-never-mentioned",
            ),
            pytest.param(VALID.split("---\n\n")[0] + "---\n\n  \n", "body", id="empty-body"),
        ],
    )
    def test_a_broken_file_is_refused(self, broken: str, complaint: str) -> None:
        with pytest.raises(SkillFormatError, match=re.escape(complaint)):
            parse_skill("why-not-imported", broken)

    @pytest.mark.parametrize(
        "reformatted",
        [
            pytest.param(
                "---\ntools: [why_not.explain]\ndescription: >-\n  Explain why a show or an episode"
                " is not in the library.\n  Use when asked why.\nname: 'why-not-imported'\n---\n"
                "1. Call `why_not_explain` with the work's media_id.\n"
                "2. Say which conclusion it reached.\n\n\n",
                id="keys-reordered-and-quoted",
            ),
            pytest.param(VALID.replace("\n", "\r\n"), id="crlf"),
            pytest.param("\ufeff" + VALID, id="byte-order-mark"),
            pytest.param(VALID.replace("---\n\n1.", "---  \n\n1."), id="spaces-after-fence"),
            pytest.param(VALID + "\n## Notes\n\nAnything goes in the body.\n", id="longer-body"),
        ],
    )
    def test_formatting_that_does_not_matter_still_parses(self, reformatted: str) -> None:
        skill = parse_skill("why-not-imported", reformatted)
        assert skill.name == "why-not-imported"
        assert skill.tools == ("why_not.explain",)
        assert skill.description.startswith("Explain why a show")


class TestTheFolder:
    def test_each_skill_is_a_folder_with_one_file(self, tmp_path: Path) -> None:
        write(tmp_path, "why-not-imported", VALID)
        assert [skill.name for skill in read_skills(tmp_path)] == ["why-not-imported"]

    def test_anything_else_in_a_skill_folder_is_refused(self, tmp_path: Path) -> None:
        """只能是指令：Agent Skills 規格允許的 `scripts/` 與附檔，這裡都不收。"""
        write(tmp_path, "why-not-imported", VALID)
        (tmp_path / "why-not-imported" / "run.py").write_text("print('hi')\n")
        with pytest.raises(SkillFormatError, match=r"run\.py"):
            read_skills(tmp_path)

    def test_a_loose_file_beside_the_folders_is_refused(self, tmp_path: Path) -> None:
        """放錯位置的 skill 不會默默消失。"""
        write(tmp_path, "why-not-imported", VALID)
        (tmp_path / "missing-episodes.md").write_text(VALID)
        with pytest.raises(SkillFormatError, match=r"missing-episodes\.md"):
            read_skills(tmp_path)

    def test_hidden_files_are_ignored(self, tmp_path: Path) -> None:
        """macOS 的 Finder 留下的 `.DS_Store` 不能讓每一輪的 instructions 都失敗。"""
        write(tmp_path, "why-not-imported", VALID)
        (tmp_path / ".DS_Store").write_bytes(b"\0")
        (tmp_path / "why-not-imported" / ".DS_Store").write_bytes(b"\0")
        assert [skill.name for skill in read_skills(tmp_path)] == ["why-not-imported"]

    def test_a_folder_without_its_file_is_refused(self, tmp_path: Path) -> None:
        (tmp_path / "why-not-imported").mkdir()
        with pytest.raises(SkillFormatError, match=r"SKILL\.md"):
            read_skills(tmp_path)

    def test_names_are_unique_because_each_names_its_own_folder(self, tmp_path: Path) -> None:
        write(tmp_path, "why-not-imported", VALID)
        write(tmp_path, "why-not-imported-copy", VALID)
        with pytest.raises(SkillFormatError, match="folder"):
            read_skills(tmp_path)


class TestTheSkillsInTheRepo:
    """閘門套在 repo 裡的那幾份上：格式壞了，這裡（與啟動時的 `catalog`）先紅。"""

    def test_they_all_load(self) -> None:
        names = [skill.name for skill in read_skills(SKILLS_ROOT)]
        assert set(names) >= FIRST_BATCH
        assert len(names) == len(set(names))

    def test_every_declared_tool_is_a_panel_tool(self) -> None:
        """宣告了、卻不是側面板工具的：那份 skill 永遠不出現（名字寫錯也是這樣）。"""
        for skill in catalog():
            assert set(skill.tools) <= set(TOOLS), skill.name

    def test_every_tool_named_in_a_body_is_declared(self) -> None:
        """內文叫到、卻沒宣告的工具：這個人看不到它時，skill 照樣會被列出來。"""
        known = {tool_name(name): name for name in commands()}
        for skill in catalog():
            named = set(re.findall(r"`([a-z0-9_]+)`", skill.body)) & known.keys()
            assert {known[name] for name in named} <= set(skill.tools), skill.name

    def test_no_skill_needs_the_tool_that_only_comes_with_a_key(self) -> None:
        for skill in catalog():
            assert TAVILY_TOOL not in skill.tools, skill.name


class TestWhatThePanelOffers:
    def test_a_skill_shows_only_when_all_its_tools_are_there(self) -> None:
        skill = parse_skill("why-not-imported", VALID)
        assert available([skill], {"why_not.explain", "jobs.list_jobs"}) == (skill,)
        assert available([skill], {"jobs.list_jobs"}) == ()

    @pytest.mark.asyncio
    async def test_the_list_has_names_and_descriptions(self) -> None:
        listed = {entry.name: entry.description for entry in await list_skills(role=Role.ADMIN)}
        assert "why-not-imported" in listed
        assert listed["why-not-imported"]
        assert set(listed) <= FIRST_BATCH

    @pytest.mark.asyncio
    async def test_an_admin_has_every_skill_and_a_user_only_those_their_tools_allow(self) -> None:
        """一般使用者訂閱不了 Mikan 與關鍵字（`rss.*` 只給管理員），所以沒有推薦新番那一份。"""
        assert {entry.name for entry in await list_skills(role=Role.ADMIN)} == FIRST_BATCH
        listed = {entry.name for entry in await list_skills(role=Role.USER)}
        assert listed == FIRST_BATCH - {"new-season-picks"}

    @pytest.mark.asyncio
    async def test_load_skill_returns_the_whole_body(self) -> None:
        skill = next(skill for skill in catalog() if skill.name == "why-not-imported")
        loaded = await load_skill("why-not-imported", role=Role.USER)
        assert loaded.name == "why-not-imported"
        assert loaded.instructions == skill.body
        assert "`why_not_explain`" in loaded.instructions

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("name", "role"), [("no-such-skill", Role.ADMIN), ("new-season-picks", Role.USER)]
    )
    async def test_an_unknown_or_unavailable_skill_is_refused(self, name: str, role: Role) -> None:
        with pytest.raises(SkillRefusedError) as refused:
            await load_skill(name, role=role)
        assert refused.value.reason is SkillRefusal.SKILL_MISSING
