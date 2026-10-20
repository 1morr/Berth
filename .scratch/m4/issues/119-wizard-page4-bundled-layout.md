# 119 — 精靈頁 4 套件內：加站與介面登入的版面

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** 票 104 的 Comments；`.impeccable/critique/2026-10-19T16-59-42Z__web-src-pages-setuppage-tsx.md`；`web/src/setup/IndexerStep.tsx`（:390-395 `GAP.login.target`）；PRODUCT.md、DESIGN.md

## 為什麼

票 104 收尾的 critique 指出：頁 4 選套件內 Prowlarr 時，一屏同時要處理加站與介面登入兩件必填，約 7 個決策點；overlay 量到右欄 147% 視窗高、左欄 34%。390 寬時推薦站段落下方有大片留白。漏設登入時「還差」會把焦點送到登入區，所以不是正確性問題，是版面失衡。協調者審查（2026-10-20）建議開票。

## 做什麼

1. 先 `/impeccable layout`：讓加站與介面登入成為兩個看得出先後的區塊，平衡兩欄高度（例如登入移到左欄，或排在加站下方）。
2. `/impeccable adapt` 修 390 寬的留白。
3. 不改任何文案的事實；字數上限的閘門（`wizardCopy.test.ts`）維持綠。

## 驗收

- [ ] 1280 寬頁 4 套件內沒有一欄比另一欄高出 1.5 倍視窗高（前端 e2e 量高度）
- [ ] 390 寬不溢出、沒有超過一屏的空白（前端 e2e）
- [ ] playwright 1280／390 截圖；`/impeccable critique` 前後分數記在 Comments
- [ ] 全部檢查、vitest、前端 e2e 綠；DESIGN.md、progress.md 已更新
