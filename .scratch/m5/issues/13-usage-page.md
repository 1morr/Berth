# 13 — 用量頁

**Status:** done

**Blocked by:** 07

**讀:** plan §11.6〈用量記錄〉；brief §6.10「用量，不設預算」、§13；CONTEXT.md 的 AI Call；`DESIGN.md`；`dataviz` 的作圖規則

## 為什麼

使用者不設預算，但要看得到 token 消耗與快取命中率（brief §19 2026-10-24）。這一頁只讀 `ai_calls`。

## 做什麼

1. 先 `/impeccable shape`，輸出 `.scratch/m5/usage-page-shape.md`。
2. API：依日期與出處（對話、測試，M6 起加 AI 任務）彙總 `ai_calls`：輸入、輸出、快取寫入、快取讀取 tokens，呼叫數，快取命中率（讀取 ÷ 全部輸入，輸入含快取寫入與讀取）。依格式與模型分得開；快取欄位是「不知道」的呼叫不算進命中率，頁面說明有幾筆沒回報。
3. 頁面：期間切換、依日期的趨勢、依出處的明細、命中率。只給管理員看（看得到每個人的用量）。
4. 沒有任何呼叫時的空狀態講清楚怎麼開始。

## 驗收

- [x] 彙總與命中率算對，含零除與「不知道」的欄位（pytest）
- [x] `user` 拿不到這支 API（pytest）
- [x] 頁面實跑，有資料與空狀態各一張截圖（playwright）
- [x] 全部檢查、pytest、vitest 綠；DESIGN.md、progress.md 已更新

## Comments

- 2026-10-24 實作（session 紀錄在 progress.md）。shape：`.scratch/m5/usage-page-shape.md`（使用者選定設定的新分頁、明細四種、每日直條加表）。截圖：演練伺服器 `healthy`（空狀態）與新的 `usage` 情境（一個月的種子呼叫），1280 深淺兩主題、390 中英；390 寬沒有橫向捲動。截圖留在 git 忽略的 `.playwright-mcp/`（`usage-empty-1280.png`、`usage-data-1280.png`、`usage-data-1280-dark.png`、`usage-data-390-*.png`）。
- 實作時與 shape 不同的三處，已在 shape 文件以刪除線記下：圖 `aria-hidden` 不可聚焦（九十根是九十個 Tab 停留點，逐日表是等價物）；總量不縮寫；窄版的 token 欄一組一行（DESIGN.md 的 Do 條補了例外）。另 `cache_unreported` 收窄成「知道輸入、快取讀取不知道」。
- code-review 已處理：guide 重複段、種子 docstring、`failures` 改 dataclass 讓端點整份 `model_validate`、散文標籤不走 `.value wrap-anywhere`、表格 class 去重、90 天不寫死、`ORIGIN_TEXT` 型別、直條每根只算一次三段、DESIGN.md 窄版通則的例外、「算不出命中率」的文案。
- **未處理，交給票 15（UI 收尾的 critique / audit / polish）**：
  - 英文窄版的命中率欄有 `13 unreported`（`whitespace-nowrap`）時把第一欄擠窄，`claude-haiku-5-5` 會在字中間斷行（不破版、沒有橫向捲動）。
  - 輸出 tokens 通常比輸入小兩個數量級，直條最上面那一段在多數日子只有 1–2px，靠讀數列與表格讀數字。
  - 範圍外但留著的小東西（Spec 審查標為無害）：明細表每一列的「N 次沒回報」、`routes.tsx` 抽出的 `refuseNonAdmin`。
- 票 08（對話）與 M6（AI 任務）加 `AiCallOrigin` 的值時，`AiUsagePage.tsx` 的 `ORIGIN_TEXT` 與 i18n `settings.usagePage.origin.*` 要補一格（`satisfies Record<AiCallOrigin, string>` 會在型別檢查時紅）。
