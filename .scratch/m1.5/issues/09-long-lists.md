# 09 — 季表、檔案清單與下載列不再整份攤開

**Status:** done

**Blocked by:** 08

**讀:** plan §11.2b（M1 帶過來的 critique 那一段）；`.scratch/m1.5/media-detail-shape.md`；`.scratch/m1/jobs-shape.md`；
`.impeccable/critique/2026-09-17T06-17-18Z__web-src-pages.md`；progress.md 裡票 15 的 audit 那一行（季表效能）

## 做什麼

票 15 的 critique 與 audit 量到的長清單問題，交給 M1.5 跟著詳情頁的新版面一起定（plan §11.2b）：

- **季表收起時仍渲染整張集表**：1213 集的作品（名偵探柯南，TMDB 併成一季）開頁就多幾千個節點。
- **一季展開之後只能捲回頂端收起**。
- **不能只看缺集**：季表知道缺哪幾集，但要自己一列一列找。
- **「檔案與版本」逐檔列出**：葬送的芙莉蓮那一筆展開後 9,000 px 以上。
- **下載列展開後的計劃逐檔列出**（`/jobs`），同一個問題。

版面照票 08 的 shape 往裡填。下載列那一半不在詳情頁上、其實不受票 08 影響；排在這裡是為了讓兩份清單用同一種
收合方式。

## 驗收

- [x] 季表收起的季不渲染集列（附 1213 集作品開頁時的 DOM 節點數，前後對照）
      —— 名偵探柯南（TMDB 現在是一季 1216 集 + 35 個特別篇）開頁 **10,147 → 119 個節點**；展開 S01 之後 9,861 個，
      收起又回到 119。
- [x] 展開的一季不必捲回頂端就能收起
      —— 摘要列展開時黏在畫面頂端（捲到第 600 列時量到 `top = 0`，四種寬度 × 主題都是），底端另有一顆「收起 S01」；
      兩條路收起之後，摘要列若在畫面上方就捲回來（量到 `top = 669 / 610`），從底端那一顆收起時焦點回到摘要列。
- [x] 可以只看缺集，狀態說得出「這一季沒有缺集」
      —— 工具列一顆「只看缺集」（`aria-pressed`）+ 一行 `aria-live`「共缺 N 集 / 這部作品沒有缺集」；每季摘要多一格
      「缺 N 集 / 沒有缺集」，展開的集表只留缺的那幾列，沒有就一句「這一季沒有缺集。」。缺只算 `missing`
      （卡住、下載中、未播出都不算，使用者拍板）。
- [x] 「檔案與版本」與下載列展開的計劃不再逐檔攤開（附芙莉蓮那一筆展開後的頁面高度，前後對照），
      逐檔資訊仍然拿得到
      —— 兩份都**依決定分組**（使用者拍板）。下載列那一筆展開：**5,394 → 707 px（1280）、8,513 → 928 px（390）**，
      39 個檔案收成兩行（待確認的 S00 11 個排最前、S01 28 個）。「檔案與版本」預設看到的是兩組（190 / 276 px），
      組的那一行就說得出帳本與 Jellyfin（「帳本對得上 · Jellyfin 已收錄 28」）。**逐檔那一列本身沒有變**
      （拍板時說「沿用現在的樣子」），所以展開一組之後的高度與以前展開一季相同（2,824 / 5,118 px）——
      要再壓縮的話是另一張票，記在下面的 Comments。
- [x] 前端測試涵蓋收合、只看缺集、摘要與展開
      —— `MediaDetailPage.test.tsx`（收起不渲染集列、底端收起 + 焦點、缺集計數與只留缺的那幾列、沒有缺集、
      沒有季時不畫工具列、檔案分組與摘要、需要人的組排最前、電影不分組）、`JobPlan.test.tsx`（39 個檔案收成兩行、
      展開才逐檔、需要人的組排最前）、`episodes.test.ts` 與 `rowGroups.test.ts`（集數範圍與分組的純函式）。
- [x] playwright 實跑：1280 / 390 × 深淺兩主題，頁面層級橫向捲動 0，附結果；鍵盤可完成
      —— 對演練情境 `long-lists`（真的 TMDB、39 個檔案真的入庫）跑四種組合：頁面層級橫向捲動**全部 0**（季表展開、
      只看缺集、檔案組、下載列各量一次），新文字對比最低 **7.74:1（深）/ 5.71:1（淺）**，console 只有登入前
      `/api/auth/me` 的 401（既有行為）。鍵盤：Space 切「只看缺集」、Tab 到季摘要、Enter 收合、Tab 一下到「收起 S00」、
      Enter 之後焦點回到摘要列（`:focus-visible` 為真），下一個 Tab 是下一季。截圖在 `.playwright-mcp/t09-*.png`（不進版控）。
- [x] lint / type / test 全綠並貼指令輸出
      —— `uv run ruff check .`（All checks passed）、`uv run ruff format --check .`（303 files already formatted）、
      `uv run mypy`（no issues in 217 source files）、`uv run lint-imports`（6 kept, 0 broken）、
      `uv run pytest -q`（1550 passed, 4 deselected）、`pnpm -C web typecheck` / `lint` / `format:check` 無輸出即通過、
      `pnpm -C web test`（418 passed）。

## Comments

- **code-review 這一輪是主對話自己做的**：兩軸的子代理連開四次都被 API 擋下（`400 Invalid schema for function 'Artifact'`，
  與任務無關），所以 Standards 與 Spec 兩軸由主對話逐條走。抓到並修掉三條：
  1. 發佈名「換掉檔案系統不收的字元」與 e2e 的 `info_name` 各算一份 —— 改成 import `tests.e2e.payload.info_name`
     （那一支的 docstring 本來就寫著「兩邊才不會各算一份」）。
  2. `CollapsibleRow` 自己寫了第二份「展開 / 收起」的文案與樣式 —— 改回共用 `ExpandHint`，它多收一個 `open`
     （`CollapsibleRow` 不能用 `group-open:`：計劃的組長在下載列那個帶 `group` 的 `<details>` 裡，會跟著外層亮）。
  3. `FilesPanel` 的 Jellyfin 計數繞了一層 `PRESENCE_COUNT` 對照表 —— 直接用 `${kind}Count` 組 i18n 鍵。
- **留著、沒有做的**（要做是另一張票）：
  - 展開一組之後的逐檔列仍是三行（處置 · 季集 · Tags / 目標路徑 / 帳本 · Jellyfin），芙莉蓮 28 個檔案 2,824 / 5,118 px。
    組的摘要已經說過的東西（處置、帳本「對得上」、Jellyfin「已收錄」）可以從逐檔列拿掉、目標路徑只留檔名，
    高度大約再省一半。**拍板時說的是「逐檔那一列沿用現在的樣子」**，所以這一輪沒有動它。
  - 「只看缺集」不寫進網址（重整或從 `/jobs` 回來會回到全部）。目前沒有需求要分享這個狀態。
  - 收起的段落不渲染內容，所以瀏覽器的頁內搜尋（Ctrl+F）找不到收起的集名與路徑。這是「收起時不渲染」的代價，
    shape §6 已寫明。
