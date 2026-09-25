# 14b — 從待審核的計劃「套用到這個 RSS Series」

**Status:** done

**Blocked by:** None — 13、14 都做完了

**讀:** plan §3.1（`review` 的逐列改與核准）、§4.4（「播出日比對」與 offset 由人改正一集時算出）、§6 files / plans 群組；brief §15（「季號與 offset」）；票 13 的 Comments

## 為什麼有這一張

票 14 做完時撞到的縫（使用者 2026-09-26 拍板另開一張）：**連載中的 split-cour**（TMDB 併成一季、字幕組第二 cour 從 01 重數、Series 的 offset 沒設）第一批現在被播出日比對的規則二**整批擋在審核裡**，一集都沒入庫。票 13 的「套用到這個 RSS Series」只能從**已入庫**的檔案發動（`POST /files/rematch` 的 `apply_to_series`，吃的是帳本那一列），停在審核的計劃列沒有這一顆——管理員只能逐列改季集再核准，一季十幾集要改十幾次。票 13 的演練情境與測試因此改成「播完一年之後才帶到」（規則二不看），繼續測已入庫那一條。

## 做什麼

- 審核中的計劃逐列改季集時，也能選「套用到這個 RSS Series」：由那一列算出季號與 offset（`parser.written_episode`，與票 13 同一個讀法），寫回 Series；同一個 Series 其餘停在審核的計劃重新規劃（管理員逐列改過的不動，同票 13），已入庫未確認的照票 13 搬。
- 被改的那一份計劃本身：改過的列照人說的；其餘列要不要跟著新的 offset 重算、還是整份重新規劃，開工時定（票 13 的規則是「人親手改的那一列清掉旗標，其餘跟著」）。
- 重新規劃之後播出日比對照常再跑一次：offset 對了就放行、自動入庫（仍在第一批裡）。
- 前端：審核頁計劃列的逐列編輯多那一格，沿用 audit 列上的元件與文案。
- 演練情境：加一個「連載中的 split-cour」（或把 `rss-split-cour` 分成兩個），playwright 走「整批擋在審核 → 改一列套用 → 其餘自動入庫」。

## 驗收

- [x] 連載中的 split-cour 第一批整批停在 `/review`（`air_date_conflict`）→ 改一列並套用到 Series → 其餘各集重新規劃後通過播出日比對、入庫（整合測試，對應 M3 驗收第五、六條同時成立）
- [x] 逐列改過的待審核計劃不被重算
- [x] 新命令或新旗標照票 05 標副作用與反向命令
- [x] playwright 對演練情境實跑，1280 與 390，附結果（`pnpm -C web e2e --project series-offset-held --project series-offset-held-390` 2 passed；截圖 `.local/screens/m3-14b/{1280,390}-{1-held,2-correcting,3-corrected,4-approved}.png`）
- [x] lint、type、test 綠燈

## Comments

2026-09-26 收尾。

- **介面**：`PUT /plans/{id}/items` 加 `apply_to_series`（只配一列，否則 422），同票 13「改一集本來就是那一支，套用只多一個旗標」的取捨；回應是整份（`PlanEditedOut`）多 `corrected: {season, episode_offset, moved, replanned, left}`，與 `POST /files/rematch` 的 `series` 同一個形狀（`SeriesCorrectedOut` 搬進 `api/schemas.py`）。`PlanRefusal` 多 `not_from_series`、`no_episode_number`。服務層是 `series_review.correct_series_from_plan`（`@command(Effect.REVERSIBLE)`，反向命令同 `correct_series`：沒有）。
- **被改的那一份（開工時定）**：人改的那一列照逐列改存下來，**那一份仍是 `pending_review` 等人核准**（逐列改從來不代替核准）；同一份裡沒有人碰過的列（不是 `set_by_user`、沒鏈接、不是重複版本）換成照新值重算的提案（`plan.held_proposal`，播出日比對照跑），同票 13「人親手改的那一列清掉旗標，其餘跟著」。Plan 的 `season_hint` / `episode_offset` 跟著改。一包多集時才看得出差別（`TestTheCorrectedPlanItself`）。
- **其餘**：同一個 Series 已入庫未確認的照票 13 搬（`_followers` / `_carry`，`edited` 可空）；停在 review、`engine ≠ user` 的重新規劃（被改的那一份自己是 `user`，自然排除），通過比對就自動入庫、仍在第一批裡；API 叫醒 importer。
- **演練情境** `rss-split-cour-airing`（第二 cour 2026-07-02 起），e2e `series-offset-held`（1280 `8510` / 390 `8511`）。README 的 e2e 表順手補上票 12、13 漏掉的兩列。
- **順手**：HEAD 上 `uv run mypy`（含 tests）有兩個票 14 留下的錯（`test_air_date_check.py`、`test_jobs_api.py`），修掉。

code-review 已處理：
- Spec 軸抓到的**鎖順序**：原本先改 Series 物件、之後的查詢把它 autoflush，SQLite 寫交易在等 Job 鎖之前就開了——另一個分頁拿著鎖要 commit 時會撞 `database locked`。改成 Series 的新值帶進 `edit_items`（`plan_review.Following`），在鎖裡與那一份同一次 commit；`held_proposal` 吃明確的季號與 offset、不先改 Series。連帶解掉「兩次 commit 不原子」。補一條鎖裡才讀得到的拒絕（`not_pending`）不寫 Series 的測試。
- Standards 軸：`_proposed(airing: bool)` 旗標參數拆成 `_stored_facts` + 兩支各自決定；前端 `onSeries` 併進 `onApplied: Said`（`shown` 決定畫不畫）；`_followers` 的條件改成先組查詢。

未處理的發現：
- **被改的那一份核准之後，跟著重算的列不在第一批裡**（`plan._audit` 只看 `auto`）：核准一整份是人看過那一份，與「還沒有人看過」不同，維持。一集一包時沒有差別。
- **`held_proposal` 不比帳本**（重複版本、範圍衝突）：與票 14 Comments 的「核准被擋的列時不再比帳本」同一個縫，要修是核准那一步再比一次，另開票。
- 守門與 offset 計算和 `correct_series` 幾乎一樣、只差例外型別；`PlanRefusal` 與 `RematchRefusal` 各有 `not_from_series` / `no_episode_number` 兩份文案；`SeriesCorrected` / `HeldSeriesCorrected` / `SeriesCorrectedOut` 三份五個欄位（判斷題，沒抽：抽出來要讓兩種拒絕型別共用一個碼）。
- 拒絕文案寫死了勾選框的標籤（與 rematch 那邊同一個既有寫法）。
- 改過之後那一份在佇列上仍說「發佈時間與換算出的集數的播出日對不上」：理由是它停下來的原因，逐列改一向不改它（`_write` 留著 `review_reason`）。
