# 92 — 簡化（前端）：同一種畫面做法收成一份，狀態色塊的內距歸位

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/simplification-audit-2026-10-13.md` 的 S7、S14、S18、S19、S25、S31；`DESIGN.md`（區塊標題 595-597、篩選列 633-635、色塊內距 556-560）；`web/src/components/controls.tsx`

## 為什麼

票 86 審計找到前端好幾處「已經有共用版本，又手寫了一份」，其中區塊標題的無障礙寫法已經分岔：`SeasonsPanel` 的計數是裸數字，螢幕閱讀器只念「3」。使用者（2026-10-13）照協調者建議要改。

## 做什麼

1. **S7**：`SectionHeading` 搬到 `components/`，審計列出的 10 處手寫區塊標題改用它。頁級 h1 不併。
2. **S14**：「服務還在啟動、每 3 秒重測」收成一個 hook，精靈與設定頁共用；相依只放穩定的 `mutate`。
3. **S18**：搜尋結果預估改用 `components/episodes.ts` 的 `seasonCode` / `episodeCode`，畫面輸出一字不變。
4. **S19**：單選篩選列收成 `components/FilterBar.tsx`，三處共用。
5. **S25**：四處小手抄改用 `Notice`、`PAGE_TITLE`、`fileName`；「讀取中」佔位抽成一個元件。
6. **S31（只做歸位）**：審計列出的 11 處 `px-2 py-1` 色塊歸到 compact（`px-1.5 py-0.5`），照協調者建議、使用者 2026-10-13 同意。約 55 處抽成類名常數的那一步不做。

## 驗收

- [ ] 每一條做完後只剩一份；S7 之後所有區塊標題的計數都有 `sr-only` 帶單位的句子，vitest 守（含 `SeasonsPanel`）
- [ ] S14 的 hook 有 vitest 守「重新 render 不會重設 3 秒計時器」，做變異驗證
- [ ] Playwright 實跑：作品頁、工作頁、媒體庫頁、RSS 頁在 1280 與 390 寬各截一張，看 S7、S19、S31 的畫面沒有走樣；**不准碰使用者的 `berth-local`**
- [ ] DESIGN.md 若因此要改（例如 `SectionHeading` 的位置）同步改；全部檢查、vitest、前端 e2e 綠；progress.md 已更新
