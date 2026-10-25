"""通知裡連回 Berth 的網址＝前端真的有的那一頁、那一列（M4 票 124 的遺留，M5 票 02）。

後端組網址的地方都在 `services/deeplink.py`：`*_PAGE` 是路徑模板（`/media/{media_id}`），`*_ROW` 是
清單上那一列的錨點（`issue-{ref}`）。前端改了路由或列的 `id`，連結就靜靜變成 404 或捲不到那一列。

讀的是前端原文（同 `test_job_filters.py`）：路由在 `web/src/routes.tsx`，列的 `id` 在各自的頁面。
所以讀法本身在最後做雙向變異：改掉被連到的路由或 `id` 要讀得出來，改無關的路由或排版不能。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from berth.services import deeplink

WEB = Path(__file__).parents[2] / "web" / "src"
ROUTES_TSX = WEB / "routes.tsx"

#: 每一個 `*_ROW` 畫在哪一頁。`deeplink` 加了一個錨點就要在這裡說它在哪
#: （`test_every_row_is_placed`）。
ROW_PAGES: dict[str, Path] = {
    "REVIEW_ROW": WEB / "pages" / "ReviewPage.tsx",
    "ISSUE_ROW": WEB / "pages" / "IssuesPage.tsx",
    "SERIES_ROW": WEB / "pages" / "RssPage.tsx",
}

#: 路由的路徑：`createRoute({ path: '/media/$mediaId' })` 與設定頁的
#: `settingsRoute('/settings/…')`。
_ROUTE = re.compile(r"(?:\bpath:|\bsettingsRoute\()\s*'(?P<path>/[^']*)'")
_COMMENT = re.compile(r"/\*.*?\*/|^\s*//[^\n]*", re.S | re.M)
#: 模板裡的一個參數：後端 `{media_id}`、前端 `$mediaId`。比的是形狀，參數名兩邊各取各的。
_PARAM = re.compile(r"\{\w+\}|\$\w+")


def constants(suffix: str) -> dict[str, str]:
    return {
        name: value
        for name, value in vars(deeplink).items()
        if name.endswith(suffix) and isinstance(value, str)
    }


def shape(template: str) -> str:
    return _PARAM.sub("{}", template)


def route_shapes(source: str) -> set[str]:
    """`routes.tsx` 裡每一條路由的形狀。讀不到就是空集合，閘門照樣會紅。"""
    return {shape(found["path"]) for found in _ROUTE.finditer(_COMMENT.sub("", source))}


def has_row_id(source: str, row: str) -> bool:
    """頁面上有沒有一個元素的 `id` 是這個錨點：`` id={`issue-${issue.id}`} ``，參數換成任意運算式。
    `id={` 與樣板字串之間可以有條件（審核頁的 `entry.kind === 'row' ? … : undefined`）。"""
    literal = "".join(
        r"\$\{[^`]*?\}" if _PARAM.fullmatch(part) else re.escape(part)
        for part in re.split(r"(\{\w+\})", row)
        if part
    )
    return (
        re.search(r"(?<![\w-])id=\{[^`}]*`" + literal + "`", _COMMENT.sub("", source)) is not None
    )


@pytest.mark.parametrize("name", sorted(constants("_PAGE")))
def test_every_page_link_is_a_frontend_route(name: str) -> None:
    template = constants("_PAGE")[name]
    assert shape(template) in route_shapes(ROUTES_TSX.read_text("utf-8")), template


@pytest.mark.parametrize("name", sorted(ROW_PAGES))
def test_every_row_anchor_is_an_id_on_its_page(name: str) -> None:
    row = constants("_ROW")[name]
    assert has_row_id(ROW_PAGES[name].read_text("utf-8"), row), (row, ROW_PAGES[name].name)


def test_every_row_is_placed() -> None:
    assert set(constants("_ROW")) == set(ROW_PAGES)


def test_the_links_are_found_at_all() -> None:
    """讀法讀得到東西：上面兩條不是因為兩邊都空才過。"""
    assert len(constants("_PAGE")) >= 5
    assert len(route_shapes(ROUTES_TSX.read_text("utf-8"))) >= 15


# --- 讀法的雙向變異 -----------------------------------------------------------

ROUTES = """\
const mediaRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/media/$mediaId',
})
const healthRoute = createRoute({ getParentRoute: () => rootRoute, path: '/health' })
const tmdbSettingsRoute = settingsRoute('/settings/tmdb', TmdbSettingsPage)
"""

PAGE = """\
          <li key={issue.id} id={`issue-${issue.id}`} className="min-w-0">
"""


def test_a_renamed_linked_route_is_read() -> None:
    assert "/media/{}" in route_shapes(ROUTES)
    assert "/media/{}" not in route_shapes(ROUTES.replace("'/media/$mediaId'", "'/works/$id'"))
    assert "/media/{}" not in route_shapes(ROUTES.replace("path: '/media", "// path: '/media"))


def test_an_unrelated_route_or_layout_change_reads_the_same() -> None:
    reformatted = (
        ROUTES.replace("'/health'", "'/healthz'")
        .replace("path: '/media/$mediaId'", "/* 作品頁 */\n  path:\n    '/media/$workId'")
        .replace("settingsRoute('/settings/tmdb'", "settingsRoute(\n  '/settings/tmdb'")
    )
    assert {"/media/{}", "/settings/tmdb"} <= route_shapes(reformatted)


def test_a_renamed_row_id_is_read() -> None:
    assert has_row_id(PAGE, "issue-{ref}")
    assert not has_row_id(PAGE.replace("`issue-", "`issues-"), "issue-{ref}")
    assert not has_row_id(PAGE.replace(" id={", " data-id={"), "issue-{ref}")
    assert not has_row_id(PAGE, "{kind}-{ref}")


def test_an_unrelated_row_change_reads_the_same() -> None:
    changed = PAGE.replace("issue.id}`", "row.ref}`").replace(' className="min-w-0"', "\n")
    assert has_row_id(changed, "issue-{ref}")
    assert has_row_id(
        "id={entry.kind === 'row' ? `${entry.row.kind}-${entry.row.ref}` : undefined}",
        "{kind}-{ref}",
    )
