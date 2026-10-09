"""網址 query 的值遮掉（M4 票 76）。

Mikan 的聚合 feed 只靠 `?token=` 認人，TMDB 的 v3 key 走 `?api_key=`，私有站的 passkey 各家參數名
不同——所以遮的是**每一個值**，不認參數名。
"""

from __future__ import annotations

import pytest

from berth.redact import redact_queries

MIKAN = "https://mikanani.me/RSS/MyBangumi?token=abc123secret"


class TestRedactQueries:
    def test_every_query_value_is_masked_whatever_the_parameter_is_called(self) -> None:
        text = "GET https://tracker.test/rss?uid=7&pk=deadbeef&cat=tv"

        assert redact_queries(text) == "GET https://tracker.test/rss?uid=***&pk=***&cat=***"

    def test_a_url_without_a_query_comes_out_whole(self) -> None:
        """遮的是值，不是整行：沒有 query 的網址照常能讀。"""
        text = 'HTTP Request: GET https://nyaa.si/rss/feed.xml "HTTP/1.1 200 OK"'

        assert redact_queries(text) == text

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            # HttpSession 的錯誤訊息：網址後面緊接冒號，冒號不是值的一部分。
            (
                f"GET {MIKAN}: connection refused",
                "GET https://mikanani.me/RSS/MyBangumi?token=***: connection refused",
            ),
            # httpx 的 log 與 uvicorn 的 access log：網址前後是空白或引號。
            (
                f'GET {MIKAN} "HTTP/1.1 200 OK"',
                'GET https://mikanani.me/RSS/MyBangumi?token=*** "HTTP/1.1 200 OK"',
            ),
            (f'"{MIKAN}"', '"https://mikanani.me/RSS/MyBangumi?token=***"'),
            # 只有路徑的網址（uvicorn access log）。
            ("GET /api/rss/series?media=tv:1", "GET /api/rss/series?media=***"),
            # 磁力連結的 tracker 可能帶 passkey。
            ("magnet:?xt=urn:btih:abc&tr=http%3A%2F%2Ft%2Fa%3Fpk%3Dx", "magnet:?xt=***&tr=***"),
            # 沒有等號的段落整段就是值。
            ("https://site.test/rss?deadbeef", "https://site.test/rss?***"),
            # 空的值沒有東西可遮，留著。
            ("https://site.test/rss?a=&b=1", "https://site.test/rss?a=&b=***"),
            # 值裡的冒號不是結尾：後面還有字。
            ("https://site.test/?k=ab:cd", "https://site.test/?k=***"),
            # fragment 不送到伺服器，不必遮。
            ("https://site.test/?k=v#top", "https://site.test/?k=***#top"),
        ],
    )
    def test_the_url_shapes_that_reach_a_log_line(self, text: str, expected: str) -> None:
        assert redact_queries(text) == expected

    def test_a_question_in_prose_is_left_alone(self) -> None:
        text = "is the feed reachable? no"

        assert redact_queries(text) == text

    def test_masking_twice_changes_nothing(self) -> None:
        """log 這一層與錯誤訊息那一層都會遮，同一句話可能被遮兩次。"""
        once = redact_queries(f"GET {MIKAN}")

        assert redact_queries(once) == once
