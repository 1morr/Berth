# 92 — 簡化（前端）：同一種畫面做法收成一份，狀態色塊的內距歸位

**Status:** done

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

- [x] 每一條做完後只剩一份；S7 之後所有區塊標題的計數都有 `sr-only` 帶單位的句子，vitest 守（含 `SeasonsPanel`）
- [x] S14 的 hook 有 vitest 守「重新 render 不會重設 3 秒計時器」，做變異驗證
- [x] Playwright 實跑：作品頁、工作頁、媒體庫頁、RSS 頁在 1280 與 390 寬各截一張，看 S7、S19、S31 的畫面沒有走樣；**不准碰使用者的 `berth-local`**
- [x] DESIGN.md 若因此要改（例如 `SectionHeading` 的位置）同步改；全部檢查、vitest、前端 e2e 綠；progress.md 已更新

## Comments

- **驗收記錄（2026-10-13）**：vitest 94 檔 1720 條綠；`pnpm -C web e2e` 35 passed；pre-commit 全過。
  - 變異驗證：
    - `useWaitingRetest`：把 `retest` 放回相依，「重新 render 不重設計時」轉紅。拿掉 `lastRetest`，「回應快到沒畫出 busy」轉紅。
    - `SectionHeading.test.tsx` 的閘門：放進 HEAD 版的 `SeasonsPanel`，轉紅。
    - `chips.test.ts`：放進 HEAD 版的 `ItemLine`，轉紅。
    - `FilterBar.test.tsx`：key 改回 `label`，「件數更新時焦點不掉」轉紅。
  - Playwright 截圖用替身，port 8631–8633，沒碰 `berth-local`：
    - `downloads` 情境：作品頁、`/jobs`、工作詳情、媒體庫（Movies、Anime），1280 與 390 各一張。
    - `rss` 情境：`/rss` 的待綁定段，看 compact 件數塊。
    - `library` 情境（`deckhand`）：繼續觀看、下一集、觀看區的標題列。`items-center` 換成 `items-baseline` 之後，按鈕與連結的字和標題落在同一條基線上。
    - 每一張的水平捲動都是 0。
- **S14 的做法比票面多一步**：
  - 用 `useEffectEvent` 把 `retest` 從相依拿掉。
  - 相依多了 `lastRetest`（`useMutation` 的 `submittedAt`）。原因：重測的回應如果快到 React 沒畫出 `busy=true`，計時器就不會重新起算。舊的精靈寫法是靠「每次 render 都重設計時」才沒踩到這一點；精靈的既有測試抓到這個情況。
  - 設定頁的舊寫法缺同一項，這次一起補上。
- **code-review 已處理**：
  - `FilterBar` 原本拿帶件數的 `label` 當 key，SSE 一更新件數就會重建那一顆，鍵盤焦點跟著掉。改用 `value` 當 key，有測試守著。
  - `option` 改名為 `renderOption`。
  - 色塊閘門原本只認相鄰的 `px` 與 `py`，改成照字串片段配對，不管 class 的順序。
- **code-review 未處理**：
  - `ReviewPage.tsx:86-100` 是審計清單之外的另一份手寫區塊標題：計數寫在 `h2` 裡面、`pb-1.5`、標題列右側有按鈕。它已經有 `sr-only` 帶單位的句子，沒有無障礙問題。但改成 `SectionHeading` 會讓 `h2` 的可存取名稱變短，閘門也認不到它（`.label` 掛在 `span` 上）。要不要併進來，留給下一張票決定。
  - commit `11cee95` 的 subject 是 75 字元，超過 72 的上限。要改得重寫本地歷史，等使用者決定。
  - `4ae8fc2`、`7047a77` 標成 `refactor`，但裡面帶了無障礙修正：`SeasonsPanel` 念出單位、`JobDetailPage` 的段落成了有名字的 region。另外 `AwaitingReview` 從 `p` 換成 `Notice` 的 `div`。這三點都屬判斷。
  - `baseName` 換成 `fileName`：路徑以 `/` 結尾時，前者回整條路徑，後者回空字串；後者也會在 `\` 切開。帳本的 `target_path` 一定是檔案的 POSIX 路徑，所以沒有實際差別。
  - `SectionHeading` 閘門用 `<h2\b[^>]*>` 找標籤，屬性裡如果有 `>`（像 `onClick={() => …}`）就會提早截斷而漏報。目前沒有這種寫法。
  - `DownloadsPanel` 的標題列原本是 `justify-between gap-y-2`，現在是 `ms-auto`、`gap-y-1`。390 寬實測篩選列仍在同一行，沒有換行。
