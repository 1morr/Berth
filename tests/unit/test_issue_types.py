"""十三種 Issue 的封閉集合，以及掛在它上面的兩張表（plan §2.4、brief §9.1、M2 票 05 / 09c）。

`IssueType` 有兩個呼叫端：管線寫 `issue_detected` 事件時用它，對帳寫 `issues` 表時也用它。
**共用一個集合**是票 05 的驗收條件之一，而共用的代價是「加一種型別」要回答兩個問題——
它的冪等鍵取哪一欄、它按得了哪幾顆。兩張表各自涵蓋整個 enum，所以少回答一個就紅在這裡。

沒有這兩條的話：少一筆 `SUBJECT_OF` 會讓那一種每一輪對帳都開一筆新的（冪等鍵是空的），
少一筆 `ISSUE_ACTIONS` 會讓 `GET /issues` 在那一列上 `KeyError`。兩種都是執行期才知道。
"""

from __future__ import annotations

from berth.domain import (
    ACTION_DELETES,
    ISSUE_ACTIONS,
    SUBJECT_OF,
    IssueAction,
    IssueSubject,
    IssueType,
)

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

#: `health_checker` 每 5 分鐘量的那兩種（M2 票 09c）。條件解除時由系統自己收掉。
FROM_HEALTH_CHECKS = {
    IssueType.LIBRARY_USES_TVDB,
    IssueType.LOW_DISK_SPACE,
}


class TestTheClosedSet:
    def test_it_is_the_union_of_the_three_producers(self) -> None:
        """十三種＝對帳的七種 ∪ 管線的四種 ∪ 健康檢查的兩種（plan §2.4）。

        分別列一次而不是數 13：多一種而三邊都沒登記它時，說得出少的是哪一種。
        """
        assert set(IssueType) == FROM_RECONCILING | FROM_THE_PIPELINE | FROM_HEALTH_CHECKS

    def test_the_three_groups_do_not_overlap(self) -> None:
        assert not FROM_RECONCILING & FROM_THE_PIPELINE
        assert not FROM_RECONCILING & FROM_HEALTH_CHECKS
        assert not FROM_THE_PIPELINE & FROM_HEALTH_CHECKS


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
            # 健康檢查那兩種也是一條路徑：TVDB 是那條 Route 的目標，磁碟是量的那個根目錄。
            IssueType.LIBRARY_USES_TVDB,
            IssueType.LOW_DISK_SPACE,
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

    def test_what_each_type_offers_this_round(self) -> None:
        """brief §9.1 那一欄，扣掉還沒做的（M2 票 09 / 09c）。

        這一條是**刻意會過期的**：票 10 補認領類的三顆時它要跟著改，而改它的人正好會看到
        「新的那一顆也要回答它會不會刪東西」（`ACTION_DELETES`）。
        """
        assert {kind: actions for kind, actions in ISSUE_ACTIONS.items() if actions} == {
            IssueType.LIBRARY_LINK_MISSING: (
                IssueAction.RELINK,
                IssueAction.FORGET,
                IssueAction.DELETE_COMPLETE,
            ),
            IssueType.SOURCE_MISSING: (IssueAction.MARK_SOURCELESS,),
            IssueType.INODE_MISMATCH: (IssueAction.REPLACE_WITH_LINK,),
            IssueType.ORPHAN_COMPLETE: (IssueAction.DELETE_ORPHAN,),
            IssueType.JOB_WITHOUT_FILES: (IssueAction.REPLAN,),
            IssueType.MISSING_FILES: (IssueAction.RECHECK, IssueAction.ACCEPT_LOSS),
            IssueType.CLIENT_ERROR: (IssueAction.RETRY,),
            IssueType.CLIENT_REMOVED: (IssueAction.RESUBMIT, IssueAction.ACCEPT_REMOVAL),
            IssueType.JELLYFIN_ITEM_UNRESOLVED: (IssueAction.RELOOK, IssueAction.RESCAN),
        }

    def test_the_health_ones_have_nothing_berth_can_press(self) -> None:
        """TVDB 插件與磁碟空間的修法在 Jellyfin 與磁碟上，不在 Berth 裡（票 09c）。

        所以它們只有「忽略」，而條件解除時由 `health_checker` 自己收掉（`resolved_by = system`）。
        """
        offered = {kind: ISSUE_ACTIONS[kind] for kind in FROM_HEALTH_CHECKS}

        assert offered == dict.fromkeys(FROM_HEALTH_CHECKS, ())

    def test_none_of_the_pipeline_actions_deletes(self) -> None:
        """「承認遺失」「承認移除」讓那一筆下載結束，但磁碟與 qBittorrent 一樣都不動（票 09c）：
        要刪東西走 Job 頁的刪除範圍，那裡四個旗標逐一說清楚。"""
        for kind in FROM_THE_PIPELINE:
            assert deleting(ISSUE_ACTIONS, kind) == [], kind

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


def deleting(table: dict[IssueType, tuple[IssueAction, ...]], kind: IssueType) -> list[IssueAction]:
    """`kind` 按得了的那幾顆裡，會刪東西的是哪幾顆。"""
    return [action for action in table[kind] if ACTION_DELETES[action]]


class TestTheUnmanagedFileIsNeverDeleted:
    """`unmanaged_library_file`：**只列出，永不自動刪**（brief §9.1，票 09 驗收）。

    服務層那一半（直接打每一顆都被擋、檔案不動）在 `tests/integration/test_issue_repairs.py`。
    """

    def test_every_action_says_whether_it_deletes(self) -> None:
        """加一顆新的而沒回答這一題，下面那一條就守不住了。"""
        assert set(ACTION_DELETES) == set(IssueAction)

    def test_none_of_its_actions_deletes(self) -> None:
        assert deleting(ISSUE_ACTIONS, IssueType.UNMANAGED_LIBRARY_FILE) == []

    def test_the_rule_turns_red_when_a_deleting_action_is_offered(self) -> None:
        """變異：票 10 替它加「認領」時手滑多給了一顆刪除。"""
        mutated = {**ISSUE_ACTIONS, IssueType.UNMANAGED_LIBRARY_FILE: (IssueAction.DELETE_ORPHAN,)}

        assert deleting(mutated, IssueType.UNMANAGED_LIBRARY_FILE) == [IssueAction.DELETE_ORPHAN]

    def test_the_rule_stays_green_for_an_action_that_does_not_delete(self) -> None:
        """變異：加一顆不刪東西的（票 10 的認領就是這種），規則不該紅。"""
        mutated = {**ISSUE_ACTIONS, IssueType.UNMANAGED_LIBRARY_FILE: (IssueAction.RELOOK,)}

        assert deleting(mutated, IssueType.UNMANAGED_LIBRARY_FILE) == []
