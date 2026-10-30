"""使用者文件的兩件事（M4 票 57）：

- `README.md`（英文）與 `README.zh-Hant.md` 段落一一對應：標題的層級一節一節相同、連出去的東西
  相同（兩份互連的那一條與同檔錨點除外）。改了一份忘了另一份，這裡紅。
- README 兩份、`docs/guide/`、`docs/development.md`、`docs/progress.md`、`docs/archive/` 裡的
  相對連結都指得到檔案，帶錨點的指得到
  那一份 Markdown 裡的標題（GitHub 的錨點算法）。
- 同一批文件裡指向部署檔的連結一律是最新 Release 的附件（`releases/latest/download/<附件名>`，
  M4 票 97）：不指 `main`（compose 不能比使用者拉到的 image 新），也不寫死版號（每次發版都要改）。
  程式碼區塊裡的 `curl` 也算；含 `<version>` 這類佔位的樣板不算。
- `.github/workflows/release.yml` 建 Release 時附上的正是這兩個附件、取自這兩個 repo 檔：
  連結指得到東西靠它。

比的是標題層級與連結目標，不是文字——翻譯換句話說、標題改措辭都不影響。
"""

from __future__ import annotations

import re
import shlex
from collections import Counter
from pathlib import Path
from typing import ClassVar

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
README_ZH = ROOT / "README.zh-Hant.md"

_FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)|<img [^>]*src=\"([^\"]+)\"|<(https?://[^>]+)>")
_HEADING = re.compile(r"^(#{1,6}) +(.+?) *$", re.MULTILINE)
_BERTH_URL = re.compile(
    r"https://(?:raw\.githubusercontent\.com|github\.com)/1morr/Berth/[^\s)>`\"']+"
)
_LATEST_DOWNLOAD = "https://github.com/1morr/Berth/releases/latest/download/"

#: Release 的部署檔附件名 → 取自 repo 的哪個檔。GitHub 會改掉開頭是 `.` 的附件名（brief §20.17），
#: 所以 `.env.example` 照 Immich 以 `example.env` 上傳。
DEPLOY_ASSETS = {
    "docker-compose.yml": "deploy/docker-compose.yml",
    "example.env": "deploy/.env.example",
}


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


def deploy_link_violations(markdown: str) -> list[str]:
    """指向部署檔（repo 的 `deploy/` 或 Release 附件）、卻不是最新 Release 那兩個附件的連結。"""
    allowed = {_LATEST_DOWNLOAD + name for name in DEPLOY_ASSETS}
    return [
        f"{url}: should be {_LATEST_DOWNLOAD}{' or '.join(DEPLOY_ASSETS)}"
        for url in _BERTH_URL.findall(markdown)
        if ("/deploy/" in url or "/download/" in url) and "<" not in url and url not in allowed
    ]


def user_docs() -> list[Path]:
    guides = sorted((ROOT / "docs" / "guide").glob("*.md"))
    archive = sorted((ROOT / "docs" / "archive").glob("*.md"))
    return [
        README,
        README_ZH,
        ROOT / "docs" / "development.md",
        ROOT / "docs" / "progress.md",
        *guides,
        *archive,
    ]


def test_the_two_readmes_match() -> None:
    english = README.read_text(encoding="utf-8")
    chinese = README_ZH.read_text(encoding="utf-8")

    assert pair_violations(english, chinese) == []
    assert README_ZH.name in links(english)
    assert README.name in links(chinese)


@pytest.mark.parametrize("path", user_docs(), ids=lambda path: path.relative_to(ROOT).as_posix())
def test_relative_links_resolve(path: Path) -> None:
    assert broken_links(path, path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("path", user_docs(), ids=lambda path: path.relative_to(ROOT).as_posix())
def test_deploy_file_links_point_at_the_latest_release(path: Path) -> None:
    assert deploy_link_violations(path.read_text(encoding="utf-8")) == []


def missing_deploy_links(markdown: str) -> set[str]:
    """`DEPLOY_ASSETS` 裡這一份沒連到的附件。"""
    linked = {url.removeprefix(_LATEST_DOWNLOAD) for url in _BERTH_URL.findall(markdown)}
    return set(DEPLOY_ASSETS) - linked


RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
_ASSET_COMMANDS = ("cp ", "gh release create ", "gh release upload ")


def release_assets(workflow: str) -> dict[str, dict[str, str]]:
    """release job 的 `gh release create` 與 `gh release upload` 各附上哪些檔。

    回 `{"create": {附件名: 取自 repo 的哪個檔}, "upload": {...}}`。

    附件是先 `cp <repo 檔> <目錄>/<附件名>` 備好的檔，在 `gh` 指令裡寫成那個路徑或 `<目錄>/*`。
    沒有 `--clobber` 的 `upload` 不算：重跑時附件已經在，同名再傳是 422（brief §20.17）。
    """
    steps = yaml.safe_load(workflow)["jobs"]["release"]["steps"]
    lines = (line.strip() for step in steps for line in step.get("run", "").splitlines())
    commands = [shlex.split(line) for line in lines if line.startswith(_ASSET_COMMANDS)]
    staged = {words[-1]: words[-2] for words in commands if words[0] == "cp"}
    result: dict[str, dict[str, str]] = {}
    for words in commands:
        if words[0] != "gh" or (words[2] == "upload" and "--clobber" not in words):
            continue
        assets = result.setdefault(words[2], {})
        for word in words[3:]:
            for path, source in staged.items():
                if word == path or (word.endswith("/*") and path.startswith(word[:-1])):
                    assets[path.rpartition("/")[2]] = source
    return result


def test_the_release_attaches_both_deploy_files() -> None:
    assets = release_assets(RELEASE_WORKFLOW.read_text(encoding="utf-8"))

    # 新建的 Release 走 create，重跑或手動先建好的走 upload：兩條路附上同樣兩個。
    assert assets == {"create": DEPLOY_ASSETS, "upload": DEPLOY_ASSETS}
    assert all((ROOT / source).is_file() for source in DEPLOY_ASSETS.values())


@pytest.mark.parametrize("readme", [README, README_ZH], ids=lambda path: path.name)
def test_the_readmes_link_both_deploy_files(readme: Path) -> None:
    assert missing_deploy_links(readme.read_text(encoding="utf-8")) == set()


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

    LATEST = "https://github.com/1morr/Berth/releases/latest/download/{name}"

    def test_a_deploy_link_into_the_repo_is_red(self) -> None:
        link = "https://raw.githubusercontent.com/1morr/Berth/main/deploy/.env.example"
        text = f"```bash\ncurl -fsSLo .env {link}\n```"

        assert deploy_link_violations(text) != []
        assert deploy_link_violations(text.replace("main", "v1.2.3")) != []

    def test_a_deploy_link_to_one_release_or_another_name_is_red(self) -> None:
        pinned = "https://github.com/1morr/Berth/releases/download/v1.2.3/docker-compose.yml"

        assert deploy_link_violations(f"[x]({pinned})") != []
        assert deploy_link_violations(f"[x]({self.LATEST.format(name='.env.example')})") != []

    def test_rewording_around_a_deploy_link_stays_green(self) -> None:
        link = self.LATEST.format(name="docker-compose.yml")

        assert deploy_link_violations(f"Get [the compose file]({link}).") == []
        assert deploy_link_violations(f"取得 <{link}>，存檔。") == []
        assert deploy_link_violations(f'```bash\ncurl -fsSLO "{link}"\n```') == []
        assert deploy_link_violations(f"```bash\ncurl -fsSLo docker-compose.yml {link}\n```") == []
        template = "https://github.com/1morr/Berth/releases/download/v<version>/docker-compose.yml"
        assert deploy_link_violations(f"`{template}`") == []
        tag_page = "https://github.com/1morr/Berth/releases/tag/v1.2.3"
        assert deploy_link_violations(f"[v1.2.3]({tag_page})") == []

    def test_a_readme_without_the_env_link_is_red(self) -> None:
        compose = self.LATEST.format(name="docker-compose.yml")
        env = self.LATEST.format(name="example.env")
        both = f"Put [the compose file]({compose}) and [example.env]({env}) in a folder."

        assert missing_deploy_links(both) == set()
        assert missing_deploy_links(both.replace(f"[example.env]({env})", "example.env")) == {
            "example.env"
        }
        assert missing_deploy_links(f"放進 [compose 檔]({compose}) 與 <{env}>。") == set()

    WORKFLOW = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    BOTH: ClassVar = {"create": DEPLOY_ASSETS, "upload": DEPLOY_ASSETS}

    def test_an_asset_under_another_name_is_red(self) -> None:
        renamed = self.WORKFLOW.replace("assets/example.env", "assets/.env.example")

        assert release_assets(self.WORKFLOW) == self.BOTH
        assert release_assets(renamed) != self.BOTH

    def test_an_asset_from_another_file_is_red(self) -> None:
        swapped = self.WORKFLOW.replace("cp deploy/.env.example", "cp .env.example")

        assert swapped != self.WORKFLOW
        assert release_assets(swapped) != self.BOTH

    def test_a_rerun_that_uploads_nothing_is_red(self) -> None:
        bare = self.WORKFLOW.replace(" assets/* --clobber", " --clobber")

        assert bare != self.WORKFLOW
        assert release_assets(bare)["upload"] == {}

    def test_a_rerun_without_clobber_is_red(self) -> None:
        strict = self.WORKFLOW.replace(" assets/* --clobber", " assets/*")

        assert strict != self.WORKFLOW
        assert "upload" not in release_assets(strict)

    def test_quoting_listing_and_renaming_the_step_stay_green(self) -> None:
        reformatted = (
            self.WORKFLOW.replace(
                "cp deploy/.env.example assets/example.env",
                "cp 'deploy/.env.example'  \"assets/example.env\"",
            )
            .replace(
                '"${flags[@]}" assets/*',
                '"${flags[@]}" assets/example.env assets/docker-compose.yml',
            )
            .replace("name: stage deploy files", "name: copy the two deploy files")
        )

        assert reformatted.count("assets/docker-compose.yml") == 2
        assert release_assets(reformatted) == self.BOTH
