# 30 — 精靈導覽：上一頁回到上一步、重新整理留在原頁、手機首屏、套件內卡片先查主機名

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-qa-2026-10-01.md`（第 23、24 條與「兩條決定」第二條）；brief §19（每個服務手動選擇）；
plan §9.3〈前端的導覽〉；`web/src/setup/navigation.ts`；`PRODUCT.md`、`DESIGN.md`；先跑 `/impeccable shape`

## 為什麼（2026-10-01 精靈實測）

- **瀏覽器「上一頁」直接離開精靈（兩邊，實測證實）。** 精靈步驟不進 history（`web/src/pages/SetupPage.tsx:108-131`）。
  NN/g 的精靈準則要求可以回上一步。截圖 B3-03、E10-06。
- **回頭看某一頁時重新整理，被帶回目前這一步；已完成的頁重新整理被推到下一頁（實測證實）。** 截圖 B3-01。
- **手機寬度的首屏被泊位板和底部固定列佔掉（全新，實測證實）。** 390 寬沒有橫向溢出，但一進頁幾乎只看到泊位板
  （`web/src/setup/BerthBoard.tsx`）。截圖 B11-08、B11-09。
- **只有 Berth 時「套件內」照常列出（使用者 2026-10-01 決定）。** 選了才說主機名解不到。決定：進頁只做主機名解析
  （`jellyfin`、`qbittorrent`、`prowlarr`），不對服務發請求；解不到的卡片直接寫「這套 compose 沒有起 X」並附加回
  `COMPOSE_PROFILES` 的指令；**不預選、不停用**。brief §19「每個服務手動選擇、選之前不發請求」不變。截圖 E9-01、E9-02。

## 做什麼

1. 目前看的步驟放進 URL（例如 `/setup?step=3`），上一頁／下一頁在「≤ 後端頁」的範圍內移動；超出時回到後端頁。重新整理
   留在 URL 指的那一頁。
2. 手機寬度的泊位板收成一列摘要（可展開），首屏先看到這一頁要做的事。依 `/impeccable shape` 的結果定。
3. 新增一支唯讀 API（或併進 `GET /setup/status`）回三個套件內主機名能不能解析；服務頁的套件內卡片據此加註與補法。
4. progress.md「偏差與決定」記第 3 點（只查 DNS 不算「選之前發請求」）。

## 驗收

- [ ] vitest：URL 的 step 與畫面一致；瀏覽器上一頁回到上一步、不離開精靈；超過後端頁的 step 被拉回
- [ ] 整合測試：主機名解不到的服務標為不在 compose；解得到的不標（雙向）；過程沒有對服務發 HTTP 請求
- [ ] vitest：套件內卡片的加註與補法；卡片仍可選
- [ ] playwright：390 寬首屏截圖、上一頁、重新整理；只有 Berth 時頁 1 的卡片加註。附截圖
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
