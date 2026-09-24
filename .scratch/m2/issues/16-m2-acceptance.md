# 16 — M2 驗收

**Status:** done

**Blocked by:** 01–15 全部

**讀:** plan §11.3（範圍與驗收那兩行）、§10；brief §9、§11、§17

## 做什麼

里程碑收尾。plan §11.3 的驗收是四條：

> 刪掉 library 後一鍵重建；對「Jellyfin 內刪除」「complete 目錄手動刪檔」「用複製取代硬鏈接」
> 三種破壞都能偵測並修復；medium 自動入庫的檔案可在佇列中一鍵撤銷；以 `user` 登入時看不到也
> 按不到審核、修正與刪除。

**e2e 要覆蓋前三條**（compose + 真服務那一套，`tests/e2e/`）。三種破壞分別對應
`library_link_missing`、`orphan_complete` / `source_missing`、`inode_mismatch`。第四條是
權限的整合測試，後端與前端各一半。

**收尾動作**（專案 CLAUDE.md）：

- `/impeccable critique`、`audit`、`polish` 各一輪，P0 / P1 當場修，其餘記進票的 Comments
- 票 01–15 的 Comments 逐條過完，分成「修掉」「延後（寫進 plan §11.4 M3 或 §11.5）」「不做」三類
- `docs/progress.md` 加 M2 的 session 紀錄與偏差；plan §11.3 與 brief 的偏差同一個 commit 改掉
- CHANGELOG

## 驗收

- [x] e2e 覆蓋三種破壞：各造一次、對帳偵測到、按動作修好，全程自動化（貼 CI run 連結與輸出）
- [x] 刪掉 library 後一鍵重建在 e2e 裡走得完（票 10 的整合測試之外，這裡是真環境）
- [x] medium 自動入庫的一筆在佇列中一鍵撤銷（e2e 或整合測試，貼輸出）
- [x] 以 `user` 登入：`/review/*`、`/issues/*`、`/files/*`、`/reconcile`、`DELETE /jobs/{hash}`、
      `POST /jobs/{hash}/reimport` 全是 403，前端看不到入口（一份把六條列齊的測試，新增 admin
      端點卻忘了加進去會紅）
- [x] `/impeccable critique`、`audit`、`polish` 各一輪，分數與處理結果記在票裡
- [x] 票 01–15 的 Comments 逐條有歸屬
- [x] `docs/progress.md`、`docs/plan.md`、`docs/design-brief.md`、CHANGELOG、README 與 repo 一致
- [x] lint、type、test、e2e 全綠（貼指令輸出）

## Comments

### 票 01–15 的 Comments 歸屬

子代理逐條對 repo 現況核過（2026-09-24），約 70 條分成四類。「已修」是後續票已經做掉的，其餘三類照票上要求。

**修掉（這一票）**

- 票 01：`test_free_space_reports_the_target_file_system` 偶發紅——改成 256 MB 內的差（兩次量測之間別的程序照樣寫磁碟）。
- 票 03：EN 的頁標題與精靈那句散文仍叫 `Library paths`，子分頁已經是 `Routes`——三處標題與一句散文改成 `Routes`（泊位板那一欄說的是路徑本身，留著）。
- 票 04：DESIGN.md「就地確認」沒記 `ConfirmPanel` 的第三種內容形狀（勾選 + 即時估算）；票 14：`.impeccable/design.json` 的牆卡片描述——`/impeccable document` 跑了一次（documenter 子代理）。就地確認改寫成「一個外殼、四種內容形狀」；牆卡片那一條**票 14 的前提有一半不對**：`MediaTile` 與 `InventoryTile` 都還在，併的是 `InventoryTile` 與集卡的外框 `Tile`，所以改成寫明三者的關係而不是換名字。兩份檔案的具名規則與 Do / Don't 逐條比對一致。

**延後**：寫進 plan §11.3 的 D 組（不排里程碑，有 repro 或使用者要求再開票）——`ROUTE_CHECKS` 手寫聯集（票 02 / 02a）、精靈兩份實作（票 03 第 17 條）、字幕指派到某一集（票 08）、`detail_json.action` 一鍵兩義（票 09）、5.x 停住的 torrent `recheck` → `start` 未實測（票 09c）、`AccountDisabledError` 名實不符（票 11）、design.json 沒有閘門（票 13）。

**已修（後續票）**：「會拒絕就要宣告」的閘門（票 02 → 02a）；其餘十種對帳檢查、`QueueRow`、五種型別的 producer（票 05 → 06、09）；design.json 的舊矛盾（票 03 → 13）；撤銷後核准重新套用、沒有 `job_hash` 的帳本列不寫事件（票 06 → 07、10）；`TEXT_LINK`（票 12 → 13）。

**不做**：其餘約 50 條——判斷題票上已結（留著的參數、兩三處的重複、命名）、刻意的行為（docstring 已寫理由）、記錄項（第一版靜綠、commit 形狀）、以及沒有 repro 的（`summary_json` 撤銷後舊一格、同集兩份同時下載完、CLI 與服務兩個程序的鎖、guessit 偶發 `TypeError`）。依全域規則「寫不出失效條件的修復不做」。

### `/impeccable critique`：34 / 40（M1 26 → M1.5 29 → M2 34）

雙代理（A 設計審查、B 偵測器 + 瀏覽器 overlay），對演練情境 `review` 的 `/review`、`/issues`、`/jobs/:hash`、Media 詳情的檔案面板，1280 與 390、zh-Hant 與 EN。快照 `.impeccable/critique/2026-09-24T02-51-46Z__web-src-pages.md`。偵測器 CLI 0 筆；overlay 34 筆裡 33 筆是誤判（`nested-cards` 是 well / hull 兩層、`—` 是無值佔位、`.label` 的大寫、海報的填滿層）。

- **[P1] EN 介面的佇列時間印成「上午10:31:36」** → 修掉：`whenText` 帶 UI 語言（`queueText.test.ts`，紅 → 綠）。
- **[P1] 佇列按完一列，焦點掉回 `body`** → 修掉：`useFocusAfterRemoval`，`/review`、`/issues`、媒體庫的「待審 / 對不到」三處，各一條測試（拿掉修正會紅，實跑過）。瀏覽器實測：鍵盤確認 S02E01 之後焦點在 S02E02 那一列、`:focus-visible`。
- **[P1] 收合的 Job 列面板還在 Tab 順序裡**（B 的 overlay）→ **誤判**：實測 Tab 從一列的 summary 直接到下一列的 summary、無障礙樹裡沒有收合的內容——Chrome 以 `content-visibility` 處理收合的 `<details>`，偵測器看到的只是幾何上的溢出。
- [P2] 同一張計劃卡上兩個同名「展開」、[P2]「改」「修正」在桌機上離檔名約 1100px、[P3] `QueueRow` 的 marker → marker 在 polish 收掉（見下），其餘兩條記在這裡不修。

### `/impeccable audit`：15 / 20（A11y 3、Perf 3、Responsive 3、Theming 3、Integrity 3）

子代理以 chrome-devtools 跑 Lighthouse（兩頁兩種裝置 Accessibility 與 Best Practices 都 100）、深淺兩主題逐節點對比（深 7.74:1、淺 5.71:1 最低，0 筆不合格）、390 無橫向捲動。P0 0、P1 2、P2 8、P3 8。

- **[P1] 390px 上黏頂的摘要列把焦點整個蓋住（2.4.11）** → 修掉：`CollapsibleRow` 的 `uncover`（焦點落在摘要列底下時捲回來；瀏覽器不捲動的那一種 `scroll-margin` 管不到），`scroll-margin` 也補到 `summary / select / input / textarea`。`CollapsibleRow.test.tsx` 紅 → 綠；瀏覽器實測 `select` 從 y 59.7（被 0–113 蓋住）變成 y 127.7。
- **[P1] 輸入框邊框對底色 2:1（1.4.11）** → 修掉：七處欄位靜止 `rule-strong`、聚焦 `ink`；DESIGN.md Inputs 與 sidecar 同步，順手更正 DESIGN.md 寫錯的 `rule-strong` 對比（深色其實 3.33–4.51:1，只有亮色 6.4:1）。
- **P2 當場修了四條**（偏離「其餘記進 Comments」：它們是這一票新寫的程式碼的缺陷或一行的事，都有測試）：`useFocusAfterRemoval` 在那一列還在時被無關的 DOM 變動觸發、把焦點拉回去（我這一票寫出來的，`useFocusAfterRemoval.test.tsx` 紅 → 綠）；刪除範圍按 Esc 收起不重設勾選（改成打開時重設）；`Checkbox` 的說明沒有 `aria-describedby`；`QueueRow` 的 `<article>` 沒有可存取名稱（`aria-labelledby` 標題，焦點落到它時念得出是哪一件）。
- **P2 沒修，記在這裡**：`RematchEntry` 與 `PlanEditor` 打開時焦點沒有送進表單；`JobDelete` 的 live region 是條件式掛載；`/review` 的 CLS 0.08–0.097（`PlanRow` 佔位不夠高）；`QueueRow`「展開」的命中區 60.7×11px（靠 2.5.8 的間距例外過）；Job 摘要列只有 audit 浮上來，對不到與重複待決沒有。
- **P3 沒修**：`/jobs` 的 h1 不是 `PAGE_TITLE`；`/review` 段標題的計數沒有 sr-only 的整句；佇列列是絕對時間、Job 頁是相對時間；送出中的鍵用 `disabled` 而不是 `aria-disabled`；`/issues` 進頁時打兩次 `GET /issues`；JS bundle 746 KB 沒有壓縮與路由拆分。

### `/impeccable polish`

收兩條設計系統漂移：`QueueRow` 的展開摘要拿掉 marker、改走 `ExpandHint`（打開之後說「收起」）；行內 `Dot` 前後的空白（`QueueRow`、對帳橫幅，原本是「…集·偵測於」）。瀏覽器實跑（`--scenario review`，1280 與 390）：marker `none`、展開前後 EXPAND / COLLAPSE、EN 時間 `9/24/2026, 10:31:36 AM`、鍵盤確認之後焦點落在下一列、390 上反向 Tab 的 `select` 露在摘要列底下（截圖 `.local/screens/m2-16/`，不進 repo）。`pnpm -C web e2e` 4 passed。

### code-review（基準 `612451f`）

**Standards**：兩條硬性違規修掉——`gate.access_of` 的 docstring 指到不存在的 `test_admin_surface.py`；sidecar 的 Input Field 描述仍說 `border-2 rule`。媒體庫子集清單的焦點補了測試。判斷題不改、記下：七處欄位的 class 字串手寫（這一輪換邊框色就改了七處，下一次再改時收成一個常量）；`whenText` 與 `Timestamp` 各自格式化時間；`test_auth_api.py` 從 unit 測試模組 import `api_endpoints`；輸入框的 `rule-strong` 規則沒有閘門。

**Spec**：e2e 的重建原本只刪一部作品的資料夾，票 10 的原文是「刪掉整個 library 目錄」——改成把 Anime 媒體庫底下的東西全部刪光（目錄本身留著：它是 Jellyfin 的媒體庫資料夾與 Route 的寫入目標）。前端那一半不是「一份列齊六條的測試」：導覽列與 admin 頁的導向在 `router.test.tsx` 列齊，頁內的按鈕（修正、刪除、重新入庫）各在 `MediaDetailPage.test.tsx` 與 `JobDetailPage.test.tsx`——頁內新增一顆 admin 按鈕而忘了擋，前端沒有測試會紅（後端那一半會：端點本身是 403）。`orphan_complete` 是額外覆蓋，不是「手動刪檔」的第二份證據。

### 驗收的證據

- **e2e 三種破壞 + 一鍵重建**：GitHub Actions [run 35955289637](https://github.com/1morr/Berth/actions/runs/35955289637)（`workflow_dispatch`，`5aa2bca`）**15 passed in 872.26s**，`test_3_m2_repair.py` 五條全過；本機三輪 15 passed（14:57–15:08），最後一輪就是推上去的版本。
- **medium 撤銷**：`uv run pytest tests/integration/test_review_api.py tests/integration/test_review.py -k Undo` → **13 passed**（`TestUndo::test_the_whole_way_through` 走 HTTP：硬鏈接沒了、帳本列沒了、Job 回 `review`、Plan `pending_review` + `audit_undone`、時間線 `audit_undone`）。
- **`user` 403 與看不到入口**：`test_auth_api.py` 74 passed（`TestWhoEachEndpointIsFor` + 檔內的雙向變異 `TestTheSurfaceCheckItself`）；`router.test.tsx` 21 passed，把「待處理」開給所有人會紅（實跑過）。
- **閘門**：ruff / ruff format / mypy（272 files）/ lint-imports（6 kept, 0 broken）綠燈，pytest **2271 passed**；eslint / tsc / prettier 綠燈，vitest **656 passed**；`pnpm -C web e2e` **4 passed**。CI [run 35955289470](https://github.com/1morr/Berth/actions/runs/35955289470)：backend、web、web-e2e、api-types、image 綠，**hygiene 紅**——critique 快照檔（工具產生）的行尾空白，本機跑 `pre-commit --all-files` 時它還沒被追蹤所以沒抓到；收尾 commit 修掉，推上去之後的那一輪見 progress.md。
