# 10b — 助理側面板可拖拉調整寬度

**Status:** done

**Blocked by:** 10

**讀:** `DESIGN.md`、`PRODUCT.md`；票 10 的 Comments（確認卡在桌機與 390 的收尾）；`web/src/agent/` 的側面板元件

## 為什麼

使用者（2026-11-07）要求助理的側面板可以自己拖寬窄：13 列的確認卡在桌機上要看得下更多列，讀程式碼與長發佈名時也想把面板拉寬；同時不能讓窄螢幕壞掉。這是 M5.6 UI 收尾（票 10）之後追加的一張，排在驗收（票 11）之前，讓里程碑的 UI 一次收乾淨。

## 做什麼

1. **拖拉把手**：側面板與主內容之間加一個可拖動的分隔把手（滑鼠拖曳），寬度即時跟著走。上下限照 `DESIGN.md` 的版面節奏定，寫在常數旁；超出範圍夾住，不是自由數字。
2. **鍵盤**：把手可聚焦（`tabindex`／`role="separator"`＋`aria-orientation="vertical"`），左右方向鍵調整寬度（一次一個步進、`Shift` 加大步進）；`aria-label` 走 i18n，zh-Hant 與 en 並列。
3. **記住寬度**：關掉再開要回到上次的寬度。存在哪在這裡定（建議瀏覽器端的 `localStorage`：這是每人每台裝置的顯示偏好，不是伺服器端設定；用伺服器端設定要多一輪 API 與 migration）。決定與理由寫進本票 Comments。
4. **窄螢幕**：390px 時側面板是全寬、不畫把手（拖了也沒有意義）；桌機才有。斷點照 `DESIGN.md` 既有的。
5. **鍵盤與讀屏**：拖動時不搶焦點、不改變頁面捲動；把手有清楚的 hover／focus 樣式。
6. 照 `DESIGN.md` 既有設計，不新開視覺方向；這一張不動確認卡的內容結構。

## 驗收

- [x] 桌機可拖動側面板，寬度有上下限，拖到邊界會夾住（vitest）
- [x] 把手可用鍵盤操作（左右方向鍵、`Shift` 大步進），`aria-label` 兩種語言都有（vitest）
- [x] 寬度會記住，重新載入後仍是上次的寬度（vitest）
- [x] 390px 不畫把手、面板全寬（playwright 截圖）
- [x] playwright 實跑桌機與 390，附截圖；鍵盤操作也實跑一次
- [x] 全部檢查、vitest、前端 e2e 綠；progress.md 已更新

## Comments

- 2026-11-07 協調者：使用者要求；排在票 10 之後、票 11 之前。側面板寬度不影響模型行為，所以 S1–S8 的驗收重跑不受影響。

### 2026-11-07 實作

- **寬度存在 `localStorage`**（`berth.agent.width`，單位 rem）：每人每台裝置的顯示偏好，不是伺服器端設定——
  走伺服器要多一輪 API 與 migration，而換裝置、換瀏覽器本來就該各自一份。壞掉的值、私密視窗讀不到
  （`localStorage` 拋錯）都回到預設，拖動照常。
- **上下限 24–40rem、預設 26rem**（`web/src/agent/panelWidth.ts` 的常數）：26 是 DESIGN.md 原本的一欄；
  24（384px）挨著 390 的手機寬（24.4rem）——票 10 量到那裡 Route 下拉 330px 加左右各 1rem 內距是 362px，
  再窄這張卡就擠；40 是 1280 開著面板時頁面還剩得下兩欄，`lg` 的 1024 也在 e2e 量過沒有橫向捲動。
  方向鍵一步 1rem、`Shift` 一步 4rem；把手在面板左緣，往左＝變寬（分隔線跟著往左走）。
- **不引入可拖拉分隔的套件**：`react-resizable-panels` 這類會接手整個兩欄版面（自己算尺寸、自己存寬度），
  而這裡的兩欄已經有桌機 `sticky`、窄版 `fixed` dialog 與 container query 的分工，套件進來要重排 `AppShell`；
  單一分隔的 pointer capture 與鍵盤處理約 40 行（全域 CLAUDE.md〈設計與實作〉的取捨）。
- **拖動不搶焦點**：pointerdown `preventDefault`，焦點只靠 Tab 進來；`touch-none` 不讓觸控拖動變成捲頁。
  寬度在放手時才寫 `localStorage`——拖動途中每一格都寫是同步 I/O，會讓拖動掉格。
- **窄版不畫把手**：沿用 `useNarrow`（`lg` 以下），390 時 `aside` 仍是 `fixed inset-0`、不套寬度。
- **impeccable critique／audit／polish**：使用者 2026-11-07 要求 10b 也要過同一道閘門（票 10 之後追加的票，
  否則驗收只有 vitest 與 playwright 截圖）；結果與處理記在下面那一節。

### 2026-11-07 code-review（兩軸，對象 `8f9c3870...HEAD`）

- **Standards 軸抓到一條硬性違規**：把手命中區只有 8px，`DESIGN.md`〈命中面積〉要 24×24 px。改成外層 `w-6`（24px）、
  內層置中的 2px 線（平常透明、hover／聚焦換 `ink`），DESIGN.md 同輪改。
- **修掉的**：預設寬度兩個來源（inline style 恆勝、`lg:w-[26rem]` 是死碼，拿掉 class）；常數旁「20 是 390 手機寬」
  算錯（390px 是 24.4rem，而且窄版不畫把手），改成 24rem 並寫出依據；`dragTo` 沒看 `event.buttons`，
  漏收 `pointerup`（在視窗外放手）之後 hover 會接著拖，現在收掉那次拖動並寫下寬度。
- **Spec 軸指出的證據偏弱已補**：e2e 的 px 斷言改成從根字級算（不再硬寫 416／64）；補最窄（24rem）與最寬
  （40rem、1024 窗寬）兩端夾住與沒有橫向捲動的實跑截圖。
- **沒修（記在這裡）**：沒有任何功能缺漏；focus 的證據從「`:focus-visible` 選擇器命中」加上截圖（截圖看得到那一圈雙環）。

### 2026-11-07 impeccable critique／polish／audit

- **critique（dual-agent：A 設計審查、B 偵測器＋瀏覽器證據）**：**28/40**（需改善帶）。快照
  `.impeccable/critique/2026-11-07T10-46-31Z__web-src-agent-agentpanel-tsx.md`。偵測器 CLI 與 overlay
  （1280、390 各一次，注入成功）都 **0 findings**，沒有 false positive。這個 slug 上一次（2026-10-27）沒有分數，
  這次是第一次有分數的 critique。
- **polish 修掉的**
  - P1 可發現性：把手靜止時完全透明。中段加三道 12×2px 的握把刻記（`ink-dim`，hover／聚焦轉 `ink`，`aria-hidden`），
    沿用站上的線語彙，不加文字。
  - P1 拖動回饋：拖動或聚焦時抬頭列多一格 `.value` 寬度讀數（`26 rem`；拉到底就停住，看得出上下限）；
    雙擊把手回 `26rem`；`aria-valuetext` 補單位與「用左右方向鍵調整」（zh-Hant／en 並列）。DESIGN.md 同輪改。
  - P3 語意：`aria-valuetext` 讓讀屏聽到單位與操作方式；focus 時刻記轉 `ink` 加上全站雙環，與 hover 分得開。
- **沒修（記在這裡，不擴大改動）**
  - P2 上限不看視窗：1024 寬拖到 40rem 頁面剩 384px（e2e 量過零橫向捲動，頁首換列變高）。使用者選了維持 40rem；
    要改 `min(40rem, 60vw)` 的話在驗收票決定。
  - P2 命中區越界 12px：24px 命中區以分隔線為中心，往頁面那半落在頁面 `px-6` 的邊距裡；往面板內移會蓋到
    面板自己的 `px-4` 內容（前 8px），所以留著。
  - Esc 在把手上會收掉整個面板：維持（`Esc` 是面板的逃生口，桌面面板本來就是這樣收）。
  - 40rem 時抬頭列變空曠、平板直向（`lg` 以下）沒有拖寬能力、確認卡貼底決策列在 24／40rem 都壓到列上：
    前兩者是設計取捨，第三屬票 10 的範圍。
- **audit（a11y 為主：程式碼＋既有 playwright 證據）**：**18/20**（A11y 4、Performance 3、Theming 4、Responsive 3、
  Implementation Integrity 4）。
  - 對比（由 token 算，oklch→sRGB）：握把刻記 `ink-dim` 對面板 `hull` 深 **7.76:1**／淺 **6.42:1**（非文字要 3:1）；
    hover／focus `ink` 14.22:1／14.95:1；寬度讀數 `ink-dim` 在 `deck` 6.57:1／7.21:1（正文要 4.5:1）；焦點環 `ink`
    14:1 以上。
  - 焦點環：全域 `[tabindex]:focus-visible`（2px、offset 2）；e2e 斷言 `:focus-visible` 命中，截圖看得到雙環。
  - live region：新增的東西都不是 live region——讀數是視覺回饋，讀屏走聚焦 separator 的 `aria-valuenow`／
    `aria-valuetext`，拖動時不會每一格朗讀；票 10 確認卡那個常駐 `role="status"` 沒動。
  - ARIA：`role="separator"`、`aria-orientation="vertical"`、`aria-label` 兩語、`aria-valuenow/min/max`（rem）、
    `aria-valuetext`、`tabIndex=0`；窄版整個不渲染（不是渲染一個無用的）。
  - 390：`fixed inset-0`、`role="dialog" aria-modal`、背景 `inert`、沒有把手、零橫向捲動（e2e 斷言＋截圖）。
  - 觸控：`touch-none`＋pointer events（含 pointer capture）；沒有實機觸控可驗，留在票上。
  - 效能：拖動每次 pointermove 都 setState（面板重繪）；這次沒量到掉格，長對話若要更省可先把寬度寫進 CSS 變數、
    放手才 setState——記在票上，不在這張做。
  - 扣分的兩項：命中區越界的邊角情境（同 critique P2）、Responsive 的上限不看視窗。

驗證（2026-11-07）：

- `uv run pre-commit run --all-files`：13 個 hook 全過（prettier 先修掉 `AgentPanel.tsx` 的排版，重跑乾淨）。
- `uv run pytest`：**5804 passed、1 skipped、28 deselected**（6 分 18 秒）。
- `pnpm -C web exec vitest run`：**2460 passed**（134 檔）。
- 前端 e2e（整套 `pnpm -C web e2e`，48 個 project）：**102 passed、1 skipped、0 failed**（2.6 分）。唯一跳過的是
  `schedule` 的窄版面板那一條（既有）。`series-offset-held-390` 在四個 worker 同時跑時逾時過兩次，單獨重跑與整輪
  重跑都綠——與這張票無關（那個 project 不開面板）。
- 截圖（不進 repo）：`web/test-results/agent-…/panel-resize-{dragged,keyboard}.png`、
  `…-agent-390/panel-resize-390.png`。390 的截圖底部那條橫向捲軸在既有測試的截圖也一樣；量到
  `documentElement.scrollWidth == innerWidth == 390`，沒有真的溢出。
