"""十一種 Issue 的封閉集合，以及掛在它上面的兩張表（plan §2.4、brief §9.1、M2 票 05）。

`IssueType` 有兩個呼叫端：管線寫 `issue_detected` 事件時用它，對帳寫 `issues` 表時也用它。
**共用一個集合**是票 05 的驗收條件之一，而共用的代價是「加一種型別」要回答兩個問題——
它的冪等鍵取哪一欄、它按得了哪幾顆。兩張表各自涵蓋整個 enum，所以少回答一個就紅在這裡。

沒有這兩條的話：少一筆 `SUBJECT_OF` 會讓那一種每一輪對帳都開一筆新的（冪等鍵是空的），
少一筆 `ISSUE_ACTIONS` 會讓 `GET /issues` 在那一列上 `KeyError`。兩種都是執行期才知道。
"""

from __future__ import annotations

from berth.domain import ISSUE_ACTIONS, SUBJECT_OF, IssueAction, IssueSubject, IssueType

#: brief §9.1 上半張表的七種。**分的是「哪一張表列了它」，不是「今天誰在寫」**——
#: `unknown_torrent` 在這一組裡，但寫它的是 `qbit_poller`（plan §3.2）；票 09 讓對帳也走到它
#: 之後，兩個生產者寫的是同一個 `(type, subject)`，冪等鍵會把它們收成一筆。
FROM_RECONCILING = {
    IssueType.LIBRARY_LINK_MISSING,
    IssueType.SOURCE_MISSING,
    IssueType.INODE_MISMATCH,
    IssueType.ORPHAN_COMPLETE,
    IssueType.UNKNOWN_TORRENT,
    IssueType.UNMANAGED_LIBRARY_FILE,
    IssueType.JOB_WITHOUT_FILES,
}

#: M1 的 `issue_detected` 事件已經在用的那四種（plan §2.4）。
FROM_THE_PIPELINE = {
    IssueType.MISSING_FILES,
    IssueType.CLIENT_ERROR,
    IssueType.CLIENT_REMOVED,
    IssueType.JELLYFIN_ITEM_UNRESOLVED,
}


class TestTheClosedSet:
    def test_it_is_the_union_of_the_seven_and_the_four(self) -> None:
        """十一種＝對帳的七種 ∪ 管線的四種（plan §2.4，2026-09-22 定）。

        分別列一次而不是數 11：多一種而兩邊都沒登記它時，說得出少的是哪一種。
        """
        assert set(IssueType) == FROM_RECONCILING | FROM_THE_PIPELINE

    def test_the_two_halves_do_not_overlap(self) -> None:
        assert not FROM_RECONCILING & FROM_THE_PIPELINE


class TestTheIdempotencyKey:
    """`(type, subject)`，`subject` 依型別取（plan §2.4）。"""

    def test_every_type_says_which_column_its_subject_comes_from(self) -> None:
        assert set(SUBJECT_OF) == set(IssueType)

    def test_the_ones_with_a_path_use_the_path(self) -> None:
        """媒體庫少一個檔案、來源不見了、inode 對不上——單位都是那一條路徑。"""
        by_path = {kind for kind, column in SUBJECT_OF.items() if column is IssueSubject.PATH}

        assert by_path == {
            IssueType.LIBRARY_LINK_MISSING,
            IssueType.SOURCE_MISSING,
            IssueType.INODE_MISMATCH,
            IssueType.UNMANAGED_LIBRARY_FILE,
            IssueType.ORPHAN_COMPLETE,
        }

    def test_the_client_ones_use_the_job_hash(self) -> None:
        """info hash 就是 `job_hash`（plan §2.3），所以客戶端那幾種不需要第三種欄位。"""
        by_hash = {kind for kind, column in SUBJECT_OF.items() if column is IssueSubject.JOB_HASH}

        assert by_hash == {
            IssueType.UNKNOWN_TORRENT,
            IssueType.CLIENT_ERROR,
            IssueType.CLIENT_REMOVED,
            IssueType.JOB_WITHOUT_FILES,
            # 票 05 實作時改判（`SUBJECT_OF` 上寫了理由）：它有兩條偵測路徑，而其中一條
            # 手上一條路徑都沒有。
            IssueType.MISSING_FILES,
        }

    def test_giving_up_on_a_lookup_is_one_ledger_row(self) -> None:
        """同一筆 Job 的兩集各自反查、各自放棄，所以單位是帳本那一列不是 Job。"""
        by_ledger = {
            kind for kind, column in SUBJECT_OF.items() if column is IssueSubject.LEDGER_ID
        }

        assert by_ledger == {IssueType.JELLYFIN_ITEM_UNRESOLVED}


class TestWhatEachTypeCanBeResolvedWith:
    """brief §9.1 的「預設建議動作」那一欄。"""

    def test_every_type_says_what_can_be_pressed_on_it(self) -> None:
        assert set(ISSUE_ACTIONS) == set(IssueType)

    def test_the_only_type_with_actions_this_round_is_the_missing_link(self) -> None:
        """票 05 只做得出 `library_link_missing`，所以只有它按得了東西（其餘在票 09）。

        這一條是**刻意會過期的**：票 09 加第二種檢查時它要跟著改，而改它的人正好會看到
        「新的那一種也要決定按得了什麼」。
        """
        with_actions = {kind for kind, actions in ISSUE_ACTIONS.items() if actions}

        assert with_actions == {IssueType.LIBRARY_LINK_MISSING}

    def test_the_missing_link_offers_the_three_from_the_brief(self) -> None:
        """重新鏈接 / 承認刪除並清帳本 / 連 complete 一起刪，**順序就是畫面上的順序**：
        第一顆是 brief §9.1 的預設建議動作。"""
        assert ISSUE_ACTIONS[IssueType.LIBRARY_LINK_MISSING] == (
            IssueAction.RELINK,
            IssueAction.FORGET,
            IssueAction.DELETE_COMPLETE,
        )

    def test_no_type_offers_an_action_twice(self) -> None:
        for kind, actions in ISSUE_ACTIONS.items():
            assert len(set(actions)) == len(actions), kind
