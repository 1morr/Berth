"""e2e 讀通知內文的季集（M5.6 票 11b）。

「可以看了」的內文由 `notify.describe_spans` 組：`S01E06`，同一部作品的幾筆在合併窗
（`notify.MERGE_WINDOW`，5 分鐘）內合成一則就變成 `S01E05–E06`。e2e 問的是「這一集到了沒」，
所以要把範圍展開再問；比對字串（`"S01E06" in description`）在合併時永遠對不上——那是 2026-10-24
起間歇性紅的原因（兩輪 RSS 只差幾分鐘，合不合併看 Jellyfin 反查的時序）。
"""

from __future__ import annotations

from berth.services.notify import describe_spans
from tests.e2e.harness import episodes_in, tells


def test_a_single_episode() -> None:
    assert episodes_in("S01E06") == {(1, 6)}


def test_a_merged_range_covers_the_episode() -> None:
    """合併之後第 6 集寫成 `S01E05–E06`，字串裡沒有 `S01E06`，展開成集合才有。"""
    assert "S01E06" not in "S01E05–E06"
    assert episodes_in("S01E05–E06") == {(1, 5), (1, 6)}


def test_a_second_span_in_the_same_season_leaves_the_season_out() -> None:
    assert episodes_in("S01E01–E03, E05") == {(1, 1), (1, 2), (1, 3), (1, 5)}


def test_a_second_season_writes_the_season_again() -> None:
    assert episodes_in("S01E01, S02E01–E02") == {(1, 1), (2, 1), (2, 2)}


def test_the_link_under_the_episodes_is_not_read_as_one() -> None:
    """通知的內文第二段是連結（`adapters/notify/discord`）：只讀第一段。"""
    embed = "S01E06\n\n[Open in Berth](http://127.0.0.1:28383/media/tv:285574)"
    assert episodes_in(embed) == {(1, 6)}


def test_the_product_writes_what_the_e2e_reads() -> None:
    """產品的組字改成別的格式時這裡會紅，e2e 才不會又靜靜地比對不到。"""
    spans = [(1, 1, 3), (1, 5, 5), (2, 1, 1)]
    assert episodes_in(describe_spans(spans)) == {(1, 1), (1, 2), (1, 3), (1, 5), (2, 1)}
    assert (1, 6) in episodes_in(describe_spans([(1, 5, 6)]))
    # 集號是 `f"{episode:02d}"`：三位數的長番照樣讀得到（`E100`）。
    assert episodes_in(describe_spans([(1, 99, 100)])) == {(1, 99), (1, 100)}


def test_a_merged_notice_is_told_by_its_title_and_the_episode_it_covers() -> None:
    """e2e 實際送進來的那種 embed：合併過的內文、下面一段連結。"""
    embed = {
        "title": "Ready to watch: I Want to Love You Till Your Dying Day",
        "description": "S01E05–E06\n\n[Open in Berth](http://127.0.0.1:28383/media/tv:285574)",
    }
    title = "Ready to watch: I Want to Love You Till Your Dying Day"
    assert tells(embed, title, (1, 6))
    assert not tells(embed, title, (1, 7))
    assert not tells(embed, "Ready to watch: Frieren", (1, 6))


def test_nothing_is_written_for_a_movie() -> None:
    assert episodes_in("") == set()
