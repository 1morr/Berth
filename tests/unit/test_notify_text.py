"""通知的句子兩種語言並列（M4 票 123、127）：後端自己組人話的地方只有 `services.notify`，前端的
i18n 閘門管不到它，所以在這裡守——少一種語言、少一個 Issue 型別的標籤，送出那一刻才會 KeyError，
那一則就被當成組不成句子放棄。"""

from __future__ import annotations

from berth.domain import IssueType, Language
from berth.services.notify import _BY_LIBRARY, _ISSUE_LABEL, _TEXT
from berth.services.waiting import WaitingSource


def test_every_language_has_the_same_sentences() -> None:
    keys = {language: set(text) for language, text in _TEXT.items()}

    assert set(keys) == set(Language)
    assert keys[Language.EN] == keys[Language.ZH_HANT]


def test_every_issue_type_has_a_label_in_every_language() -> None:
    assert set(_ISSUE_LABEL) == set(Language)
    for labels in _ISSUE_LABEL.values():
        assert set(labels) == set(IssueType)
        assert all(label.strip() for label in labels.values())


def test_every_list_has_its_sentences() -> None:
    """「等你處理」照清單拼 key（`_part`、欄位、清單連結）：多一份清單少一句，送出那一刻才會壞。"""
    needed = {
        f"{source.value}_{suffix}"
        for source in WaitingSource
        for suffix in ("one", "many", "field", "list")
    }

    assert needed <= set(_TEXT[Language.ZH_HANT])


def test_every_kind_about_a_work_has_its_title() -> None:
    """「可以看了」與「正在下載」共用 `_render`，標題照種類取（M4 票 126）：說作品的種類多一種
    少一句，送出那一刻才會壞。"""
    for text in _TEXT.values():
        assert {kind.value for kind in _BY_LIBRARY} <= set(text)
