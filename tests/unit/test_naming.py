"""命名引擎的純函式（plan §5）。

模板在 M0 票 04 的實驗後**凍結**，所以這裡的期望值不是從程式推出來的，而是抄自 plan §5
與那次實測的結論。本票只用得到作品資料夾那一格；其餘五種模板由票 07 補上。
"""

from __future__ import annotations

from datetime import date

from berth.domain import MediaKind, MediaSnapshot
from berth.naming import folder_name, sanitize


def snapshot(**overrides: object) -> MediaSnapshot:
    defaults: dict[str, object] = {
        "tmdb_id": 120089,
        "kind": MediaKind.TV,
        "title": "SPY×FAMILY 間諜家家酒",
        "title_en": "SPY x FAMILY",
        "title_original": "SPY×FAMILY",
        "year": 2022,
        "first_air_date": date(2022, 4, 9),
    }
    return MediaSnapshot(**{**defaults, **overrides})  # type: ignore[arg-type]


class TestFolderName:
    def test_it_follows_the_frozen_template(self) -> None:
        """`{title} ({year}) [tmdbid-{id}]`（plan §5）。"""
        assert folder_name(snapshot()) == "SPY x FAMILY (2022) [tmdbid-120089]"

    def test_a_film_uses_the_same_template(self) -> None:
        """電影與劇集的資料夾名是同一個模板，差別只在檔名（brief §7.1、§7.2）。"""
        card = snapshot(
            tmdb_id=1241982,
            kind=MediaKind.MOVIE,
            title="海洋奇緣2",
            title_en="Moana 2",
            title_original="Moana 2",
            year=2024,
        )

        assert folder_name(card) == "Moana 2 (2024) [tmdbid-1241982]"


class TestSanitize:
    """plan §5 的 `sanitize`。

    完整的六種模板是票 07 的事，但**這一票就把 `folder_name` 凍結進資料庫**——
    `Mission: Impossible` 這種標題現在被寫成非法路徑的話，票 07 補規則時已經改不掉了。
    """

    def test_it_removes_the_characters_windows_refuses(self) -> None:
        assert sanitize(r'a/b\c:d*e?f"g<h>i|j') == "abcdefghij"

    def test_a_real_title_with_a_colon_survives(self) -> None:
        """`Mission: Impossible` 是這條規則存在的理由。"""
        card = snapshot(tmdb_id=575265, title_en="Mission: Impossible - The Final Reckoning")

        assert folder_name(card) == (
            "Mission Impossible - The Final Reckoning (2022) [tmdbid-575265]"
        )

    def test_it_drops_control_characters(self) -> None:
        assert sanitize("a\u0000b\tc\nd") == "a b c d"

    def test_it_collapses_runs_of_whitespace(self) -> None:
        assert sanitize("a   b \t c") == "a b c"

    def test_it_strips_trailing_dots_and_spaces(self) -> None:
        """Windows 的目錄名不能以 `.` 或空白結尾——建得起來也開不了。"""
        assert sanitize("Dr. Strangelove. . ") == "Dr. Strangelove"

    def test_it_keeps_the_name_within_two_hundred_bytes(self) -> None:
        """上限算的是 UTF-8 **位元組**，不是字元：中文一個字三個位元組。"""
        long_name = sanitize("間諜家家酒" * 40)

        assert len(long_name.encode("utf-8")) <= 200
        # 不從一個字的中間切開——切出半個位元組的話那不是一個字串。
        assert long_name == long_name.encode("utf-8").decode("utf-8")

    def test_it_does_not_cut_a_name_that_already_fits(self) -> None:
        assert sanitize("SPY x FAMILY (2022) [tmdbid-120089]") == (
            "SPY x FAMILY (2022) [tmdbid-120089]"
        )

    def test_a_name_that_sanitizes_to_nothing_is_still_identifiable(self) -> None:
        """全部是非法字元的標題不能變成空字串——空的資料夾名建不出目錄。"""
        card = snapshot(title_en="///", title_original="///")

        assert folder_name(card) == "(2022) [tmdbid-120089]".strip()
