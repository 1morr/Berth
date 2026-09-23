# 07 — Review Queue ⅔：低信心 Plan 逐列編輯 + 批次核准

**Status:** done

**Blocked by:** 06（佇列端點、清單元件與 `/review` 頁）

**讀:** plan §4（解析器階段與核心型別）、§5（命名引擎）、§6（plans 群組、review 群組）、§3.1（Job 狀態轉換，`review` 的出邊）；brief §6.5、§7.1–§7.4、§9.4

## 做什麼

M2 最重的一張。低信心的 Plan 停在 `review`，M1 給的是**一份唯讀的答案**；這一票讓人改得動並
套用得下去。

**前置：Plan item 的理由改成封閉集合的 code + 參數**。現在是後端拼好的句子，翻不了譯也對不了
測試。這件事要先做——它是這一票的地基，不是收尾（票 06 的列已經照這個形狀走，這裡把 Plan item
自己的理由也收進同一套）。

**端點**：`PUT /plans/{id}/items`（逐列改季集與動作）、`POST /plans/{id}/approve`、
`POST /plans/{id}/reject`，核准之後走 `apply_plan`。

**`review` 的出邊**（§3.1）要在這一票走通：核准 → `importing`；拒絕 → 該往哪去（狀態機那一節
寫死了，照它做，不要自己發明）。

**逐列能改什麼**：季、集（起訖）、動作（正片 / extra / 忽略 / Unmatched）。改完的那一列要當場
看得到它會落在哪個目標路徑——命名是純函式（plan §5），前端不重算，由後端在回應裡給。

**批次核准**：整份 Plan 一次核准是常態；逐列改過之後仍然是同一顆按鈕。

**UI 先 `/impeccable shape`**：這一頁的 Plan 表格是 M2 最密的畫面（逐列可改 + 目標路徑預覽 +
理由），而且窄版要做得完（plan §7：審核、佇列、送單在手機上要做得完）。

## 驗收

- [x] Plan item 的理由是封閉集合的 code + 參數，zh-Hant 與 en 兩份都有；後端拼句子的舊路徑刪掉
      （不留相容層）
- [x] 逐列改季集之後，那一列當場顯示新的目標路徑，且與 `apply_plan` 真的寫出來的一致
      （同一份命名函式，測試斷言兩者相同）
- [x] `PUT /plans/{id}/items` 對不合法的改動是拒絕而不是默默接受（至少：集數範圍反了、
      動作與檔案分類矛盾）
- [x] 核准 → Job 進 `importing` → 檔案真的入庫（整合測試走完整條）；拒絕 → 照 §3.1 的出邊
- [x] 批次核准與逐列改過之後的核准是同一條路徑（不是兩套）
- [x] `/review` 的 `plan` 那一類的列出現在最前面那一組（票 06 定的排序）
- [x] `user` 登入時 `/plans/{id}/items`、`approve`、`reject` 全是 403
- [x] `/impeccable shape` 產出留在 `.scratch/m2/`；窄版（390px）走得完整條審核，playwright 實跑
      附截圖或文字結果
- [x] lint、type、test 綠燈

## Comments

- 2026-09-23 code-review（Standards）：`PlanEditor` 的 `heavy` prop 名稱讀不出「置頂那幾列用粗左框」——
  **沿用**：`FileEntry` 早就用 `heavy` 表示同一件事（「這一列要人看一眼」，線變重不是變紅），換名字等於兩個詞說一件事。
- 2026-09-23 code-review（Standards）：`review_decided` 的 payload 用 `PlanStatus` 的值（`approved` / `rejected`），
  而按鈕的 enum 是 `PlanDecision`（`approve` / `reject`）——**不改**：事件是過去式的紀錄，說的是 Plan 變成了什麼狀態；
  前端的時間線以 `approved` 判斷。要換成事件自己的字面值時兩端一起改。
- 2026-09-23 code-review（Spec）：`target_exists` 的 Plan 不改那一列就核准會再撞一次、再停回 review——**不擋**：
  把媒體庫裡那個不是 Berth 鏈接的檔案移走之後原樣核准正是合法的下一步（計劃區那一句就這樣說）。
  要擋的話得先知道那個檔案還在不在，那是一次磁碟讀取，留給有 repro 的時候。
- 2026-09-23 code-review（Spec）：使用者略過的字幕，影片改回入庫時不會自動跟回來（要手動改回「字幕」）——刻意的
  （`parser.revise` 的註解）：人說略過就是略過。
- 2026-09-23 Plan 的 `summary_json` 在 audit 撤銷之後沒有重算（票 06 的 `_back_to_review` 只換 `review_reason`），
  佇列那一列的「要入庫 N 個 / 低 N」會比表格舊一格，逐列改一次就重算。沒有 repro 要修，記一行。
