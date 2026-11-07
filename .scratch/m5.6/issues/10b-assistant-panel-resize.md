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
- **上下限 20–40rem、預設 26rem**（`web/src/agent/panelWidth.ts` 的常數）：26 是 DESIGN.md 原本的一欄；
  20 是 390 手機寬（面板全寬時確認卡放得下的寬）；40 是 1280 開著面板時頁面還剩得下兩欄。方向鍵一步 1rem、
  `Shift` 一步 4rem；把手在面板左緣，往左＝變寬（分隔線跟著往左走）。
- **拖動不搶焦點**：pointerdown `preventDefault`，焦點只靠 Tab 進來；`touch-none` 不讓觸控拖動變成捲頁。
  寬度在放手時才寫 `localStorage`——拖動途中每一格都寫是同步 I/O，會讓拖動掉格。
- **窄版不畫把手**：沿用 `useNarrow`（`lg` 以下），390 時 `aside` 仍是 `fixed inset-0`、不套寬度。
- **沒重跑 impeccable critique／audit**：這一張照 DESIGN.md 既有設計、只加一個把手（票上寫「不新開視覺方向」），
  票 10 的 critique／audit／polish 已涵蓋面板；要的話在票 11 的驗收一起做。

驗證（2026-11-07）：

- `uv run pre-commit run --all-files`：13 個 hook 全過（prettier 先修掉 `AgentPanel.tsx` 的排版，重跑乾淨）。
- `uv run pytest`：**5804 passed、1 skipped、28 deselected**（6 分 18 秒）。
- `pnpm -C web exec vitest run`：**2458 passed**（134 檔）。
- 前端 e2e（整套 `pnpm -C web e2e`，48 個 project）：**102 passed、1 skipped、0 failed**（2.7 分）。唯一跳過的是
  `schedule` 的窄版面板那一條（既有）。前一輪 `series-offset-held-390` 在四個 worker 同時跑時逾時一次，單獨重跑與
  整輪重跑都綠。
- 截圖（不進 repo）：`web/test-results/agent-…/panel-resize-{dragged,keyboard}.png`、
  `…-agent-390/panel-resize-390.png`。390 的截圖底部那條橫向捲軸在既有測試的截圖也一樣；量到
  `documentElement.scrollWidth == innerWidth == 390`，沒有真的溢出。
