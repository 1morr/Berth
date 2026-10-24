# 10 — 確認卡（Proposal）：加索引站、刪 complete

**Status:** done

**Blocked by:** 09

**讀:** plan §11.6〈對話核心〉與驗收、§2；brief §6.10「外部文字是資料」⑤、§14「接管只放開可逆的」、§9.2（刪除範圍）；CONTEXT.md 的 Proposal；M4 加索引站與刪 complete 的現有流程

## 為什麼

`irreversible` 的命令 AI 永遠不能自己做，要停在一張確認卡上，人按了才執行。M6 的接管與 M7 的 Discord 按鈕都回到同一個 `proposals` 列，所以這張把 Proposal 做成獨立的東西，不是側面板的 UI 狀態。

## 做什麼

1. **`proposals` 表**與 migration：哪個工具、輸入、誰要的、出自哪則對話、AI 的理由、狀態（等待 / 已確認 / 已拒絕 / 失效），執行結果。
2. 工具迴圈遇到 `irreversible` 的工具：不執行，建一筆 Proposal，回給模型「已提出，等人確認」，前端畫確認卡。卡上講清楚**會發生什麼**（刪哪些檔、加哪個網址），不只是工具名。
3. **確認**：以按下的那個人執行，當下重驗角色與輸入（列已經不在、索引站已存在 → 失效並說原因）。**拒絕**也記下來。結果回到對話裡（模型與卡片都看得到）。
4. 登記兩個工具：加索引站、刪 complete（走既有命令，刪除範圍照 brief §9.2）。
5. 一個「降級成 Proposal」的入口：讓之後的檢查（票 11 的網址來源）能把一次可逆呼叫改成 Proposal，而不是各自造一套。

## 驗收

- [x] 用假 provider：「加一個索引站」停在確認卡，沒按之前索引站沒加；按確認後加好（整合測試）
- [x] 「把這部的 complete 刪掉」同上，拒絕後什麼都沒刪（整合測試）
- [x] 確認時角色或輸入已不成立 → 失效並說原因（pytest）
- [x] `user` 按不到管理員的 Proposal（pytest）
- [x] 確認卡實跑（playwright 截圖）
- [x] 全部檢查、pytest、vitest 綠；CONTEXT.md、progress.md 已更新

## Comments


2026-10-24（實作 session）：

- **使用者選定**：「刪 complete」吃作品 id、只移除 torrent 加刪下載目錄的檔案（媒體庫鏈接與帳本留著）；只有提出的人按得到；按了不自動叫模型。記在 brief §19。
- **成熟產品的慣例**：工具狀態照 Vercel AI SDK 的 tool approval（`approval-requested` → 這裡的 `proposed`），但**不暫停迴圈**：AI SDK 把工具呼叫停住、等批准再接著跑，Berth 的 Proposal 要活過那一次回覆（M7 的 Discord 按鈕、M6 的背景任務），所以工具結果直接是「已提出」，按了之後另加一則 `decision`。串流不加新的 chunk 型別，沿用 `tool-output-available`（`outcome: proposed`）。
- **截圖**：本目錄的 `proposal-*-1280.png` / `-390.png`（playwright `assistant` 兩個專案）。另一個 worktree 的 e2e 佔著同一組 port，這一輪是以暫存 config 把 `assistant` 兩台搬到 9528 / 9529 跑的，spec 與情境照舊。
- **code-review（Standards × Spec）已改**：確認時重算的預覽要與卡上那一份相同，否則失效（`ToolRefusal.CHANGED`）；存下的預覽這一版讀不回來也是失效，不再被標成「確認了但內部出錯」；按卡的結果給模型時不帶外部文字（torrent 名、Prowlarr 原文），只有狀態、做成沒有與理由碼；前端補齊 `prowlarr_unchosen` / `site_unknown` / `site_not_offered` 的說法並附原文；按過的狀態不再手寫帶外框的中性色塊（`deck` 疊在 `deck` 抬頭列上會消失，改成只寫字）；`Outcome` 改讀產生的型別；`.of()` 工廠取代逐格搬欄位；`deletion.DownloadsDeleted` 改名 `JobDownloadsOutcome`（與工具那一層的同名型別分開）；`assistant.py` 指著已拆掉的 `Registry.invoke` 的兩處註解。
- **code-review 未處理**：
  - `SiteRefusal`、`DeletionRefusal` 不在 `domain/enums.py`、沒進 OpenAPI，前端 `ProposalCard.tsx` 的 `LAPSES` 以字串查表，後端改名時前端不會紅（認不得的照原樣印理由碼，不會壞）。要閘門的話可以比照 `ToolRefusal` 匯進 components；等第三個要人按的工具時一起做。
  - 加一個要人按的工具要改 `TITLES`、`CONFIRMS`、`TOOL_NAMES`、`LAPSES` 與 i18n，只有 `PREVIEWS` / `CARDS` 被 `tsc` 守（Shotgun Surgery）。同上，等下一個工具。
  - `SiteRejectedError` / `DeletionRejectedError` / `ProposalRejectedError` 的 `__init__` 與 repo 裡十幾個拒絕例外同形，沒有抽共同基底（照既有寫法）。
  - `_execute` 先 `admits` 再 `resolve`（後者也查角色）：前者是為了說出 `not_allowed` 而不是 `unknown_tool`，保留。
  - 認不得站名時 `detail` 列出最像的五個（`difflib`），票沒要求，規模小保留。
  - 刪下載的預覽含大小：還在下載的 Job，檔案大小一變，確認時就是 `changed`、要重新叫助理提一次。偏保守，等真的有人碰到再說。
  - Prowlarr 新增一站時沒帶 `baseUrl`，是不是用 `indexerUrls` 的第一個，未實測（brief §20.7 已註明）。
- **與本票無關的紅燈**：`tests/integration/test_rss_api.py::TestThePageFlow::test_add_poll_bind_and_see_the_jobs` 在開工時的 `3ed4475d` 上一樣紅：`series_finished` 以真時鐘判斷「最近一筆發佈之後 30 天沒有新的」，fixture 的發佈時間 2026-10-24 剛跨過 30 天。沒有修，記在 progress.md 的下一步。
