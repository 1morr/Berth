# 05 — 核准被擋的計劃時重新比對帳本

**Status:** done

**Blocked by:** 01

**讀:** plan §11.6〈分段〉第 1 段、§11.4 的 M3 票 14 / 14b 段落；`docs/research/m5-ai-direction-2026-10-27.md` A3 的 R10；`.scratch/m3/issues/14-*.md`、`14b-*.md` 的 Comments；`berth/services/plan_review.py`（`held_proposal` 與核准路徑）

## 為什麼

被播出日比對擋下的計劃列，與 `held_proposal` 的改正，在核准時不再比對帳本，所以重複版本與 `span_clash` 會漏檢。M6 起 AI 的結果走同一條核准路徑，這個洞要先補。

## 做什麼

1. 先寫會紅的測試：被擋下的列，在核准前帳本裡已經有同一集，核准之後產生重複；或者兩列撞在同一個範圍（`span_clash`）。
2. 核准路徑在套用之前，用與規劃時同一份帳本比對。規則只有一份實作，不在核准路徑另寫一套。
3. 比對出問題時，照規劃時的行為處理（重複版本的決定、撞範圍的理由），不默默放行。

## 驗收

- [x] 重複版本與 `span_clash` 各有一條先紅後綠的測試（`test_plan_review.TestTheLedgerAtApproval` 兩條；`held_proposal` 那條路另一條 `test_series_review.TestTheCorrectedPlanItself`，三條拿掉修正時都紅）
- [x] 規劃與核准共用同一個比對函式（`plan.against_ledger` 載入 Route 與檔案清單後呼叫規劃時那一支 `_against_ledger`）
- [x] 全部檢查與 pytest 綠；progress.md 已更新

## Comments

2026-10-27 收尾。

- **核准時比的範圍**：`landing` 那一份裡**所有沒鏈接的列**都比，不只被擋下的：規劃時已經是 `import` 的列在等人的期間，帳本也可能多了另一包送的同一集。已鏈接的列不比（`_write` 也不動它們）。
- **處理照規劃時自動入庫那一份**：撞上的列略過、清路徑、多一條 `same_version` / `library_span_clash`、寫 `duplicate_of`，跟著它的字幕一起略過（`_unfollowed`），記 `duplicate_skipped`（actor `system`，同規劃）；其餘照常核准。Plan 核准後是 `SETTLED_PLANS`，那幾列出現在 Review Queue 的 `duplicate`。整份都撞上時照樣核准、importer 走到 `imported`（`test_a_held_row_clashing_with_the_library_is_skipped_on_approval`）。
- plan §6 plans / review 兩列、§11.4 延後清單同步。

code-review 已處理：`plan_review` 裡與 `plan.against_ledger` 幾乎同名的 helper 改名 `_recheck_unsettled`；plan.md 的「同一支」改成指向規劃時那一支 `_against_ledger`。

未處理的發現：
- **人改過的列也比**（判斷題，維持）：管理員把規劃時判成重複的列改回 `import`，核准時會再被判成重複、略過，要到 Review Queue 按「保留兩者」；人填的季集撞上媒體庫裡的範圍時多半不知道，「不默默放行」優先。副作用：那一列的理由裡會有兩條 `same_version`（規劃時一條、核准時一條），只是畫面上重複一行。
- **舊的 `duplicate_of` 不清**：改了季集之後不再撞帳本的列，`duplicate_of` 仍留著（`_write` 只寫不清）。action 是 `import`，`review._duplicates` 只撈 `skip`，眼前無害；但 `edit_items` 的 `_followed` 會把它當成重複版本而不跟著 Series 換。票之前就有的行為。
- 測試的 `_same_version_of` 與 `test_plan.already_in_the_library` 形狀相近（差 Tags 與結束集）；`_write` 的 `duplicates` 是選填、只有核准傳；`plan.against_ledger` 是只多載兩樣東西的薄包裝（讓 `_contents` 留在 `plan`）。判斷題，沒改。
- 待審核那一份的畫面（`read_plan` 的 `landing`）不預先比帳本，核准之後那一列才變成略過。
