"""以網址加 Feed 的那一道：網址是不是使用者自己打的（M5 票 11，brief §6.10「外部文字是資料」②）。"""

from __future__ import annotations

import pytest

from berth.services.subscribe_guard import written_in

FEED = "https://nyaa.si/?page=rss&q=frieren&c=1_0&f=0"


@pytest.mark.parametrize(
    "said",
    [
        FEED,
        f"Add this feed: {FEED}",
        f"加這個 {FEED}。",
        f"Add {FEED}.",
        f"({FEED})",
        f"「{FEED}」好嗎",
        f"first line\n{FEED}\nthanks",
    ],
)
def test_the_whole_url_written_by_the_user_counts(said: str) -> None:
    assert written_in([said], FEED)


@pytest.mark.parametrize(
    "said",
    [
        # 使用者貼的比較長：模型拿掉後半段，那已經不是他說的位址。
        f"{FEED}&u=someone",
        # 使用者貼的比較短：模型自己接上了一段。
        "https://nyaa.si/?page=rss&q=frieren",
        "subscribe to frieren on nyaa",
        "",
    ],
)
def test_anything_else_does_not(said: str) -> None:
    assert not written_in([said], FEED)


def test_any_of_the_users_lines_in_the_conversation_counts() -> None:
    assert written_in(["hi", f"use {FEED}", "thanks"], FEED)


def test_an_empty_url_is_never_written() -> None:
    assert not written_in([FEED], "  ")
