# 119 — 精靈頁 4 套件內：加站與介面登入的版面

**Status:** done

**Blocked by:** None — can start immediately

**讀:** 票 104 的 Comments；`.impeccable/critique/2026-10-19T16-59-42Z__web-src-pages-setuppage-tsx.md`；`web/src/setup/IndexerStep.tsx`（:390-395 `GAP.login.target`）；PRODUCT.md、DESIGN.md

## 為什麼

票 104 收尾的 critique 指出：頁 4 選套件內 Prowlarr 時，一屏同時要處理加站與介面登入兩件必填，約 7 個決策點；overlay 量到右欄 147% 視窗高、左欄 34%。390 寬時推薦站段落下方有大片留白。漏設登入時「還差」會把焦點送到登入區，所以不是正確性問題，是版面失衡。協調者審查（2026-10-20）建議開票。

## 做什麼

1. 先 `/impeccable layout`：讓加站與介面登入成為兩個看得出先後的區塊，平衡兩欄高度（例如登入移到左欄，或排在加站下方）。
2. `/impeccable adapt` 修 390 寬的留白。
3. 不改任何文案的事實；字數上限的閘門（`wizardCopy.test.ts`）維持綠。

## 驗收

- [x] 1280 寬頁 4 套件內沒有一欄比另一欄高出 1.5 倍視窗高（前端 e2e 量高度）
- [x] 390 寬不溢出、沒有超過一屏的空白（前端 e2e）
- [x] playwright 1280／390 截圖；`/impeccable critique` 前後分數記在 Comments
- [x] 全部檢查、vitest、前端 e2e 綠；DESIGN.md、progress.md 已更新

## Comments

**做了什麼（2026-10-20）**

- **第 1 點（layout）**：`StepFrame` 多一個 `aside`：桌機（`lg`）時接在剖面底下，那一欄不再 sticky（固定的剖面會蓋住它）。頁 4 套件內的 `ProwlarrLogin` 在桌機交給它，窄版照舊在加站之後、導覽之前——CSS 搬得動位置、搬不動 Tab 順序，所以由 `setup/useWideScreen`（`matchMedia('(min-width: 64rem)')`，量不到當窄版）決定掛在哪裡。**先後**由調度黃說：推薦站的主鍵還在（0 站、清單上有推薦站）時，登入的送出鍵是 Ghost，加了站才換成主鍵——這一條是改後 critique A 的 P2（沒沿用時兩顆黃鍵並排，看不出先做哪件），不在票面「做什麼」裡。
- **第 2 點（adapt）**：390 寬推薦站下方的「大片留白」實跑不存在：逐屏截圖時那裡只有 `mt-10` 的區塊間距；留白是 fullPage 截圖把 sticky 主鍵（`STICKY_ACTION`）畫到錯的位置，上一次 critique 也標了「待實跑確認」。版面沒改，e2e 補量溢出與最大空白。
- **第 3 點**：沒有改文案，`wizardCopy.test.ts` 綠。

**驗收第 1 條怎麼讀、量哪個狀態**

- 照字面讀成「高差 ≤ 1.5 個視窗高」的話，改前就會過（1280×720：工作面 960px、剖面 309px，差 651px＝90%），閘門擋不到任何東西。所以 e2e（`wizard.spec.ts`、`e2e/layout.ts` 的 `frameColumns`）量的是比例：**高的那一欄 < 1.5 倍矮的那一欄**。這比字面嚴，不是放寬。
- 量的是推薦站還沒跑、兩件必填同時在畫面上的狀態：改後 752／540（1.39）。登入表單打開（「改用另一組」）是 752／909，手動量過、沒有寫進 e2e（流程接著要跑推薦站，表單開著會擋住後面的步驟）。**推薦站跑完之後不量**：1947／917（2.1），撐高工作面的是逐站結果清單，不是兩件必填的分配；overlay 在這個狀態仍報 `first-viewport-column-overflow`。
- 變異驗證（手動）：`wide` 恆為 false 重 build，1280 那一條紅（Received 960、Expected < 463.5）。窄版那個變異已經由 `SetupPage.layout.test.tsx` 的單元測試編碼守著。

**截圖**：改前、改後的 1280／390 截圖在 session scratchpad 的 `probe/before`、`probe/after`、`probe/final`（a-before 已選、a2-form 表單打開、b-outcome 跑完推薦站、p390-scroll-* 逐屏）；e2e `wizard`／`wizard-390` 的 `4-indexers-one-key.png`。

**critique（雙子代理）**：**28 → 28/40**（trend 24 → 26 → 27 → 28 → 28；快照 `.impeccable/critique/2026-10-20T08-58-30Z__web-src-pages-setuppage-tsx.md`）。H8 有升有降：兩欄平衡了，但左欄「介面登入」字樣三到四次；H4 多一個不一致：介面登入在頁 2 是工作面、頁 4 桌機是剖面欄。detector CLI 0 筆。新的優先問題（不在這張票）：左欄「介面登入」四處重複（distill）、頁 1 既有卡太長（distill）、沒勾「沿用」時帳號已預填（polish）。

**驗證**：vitest 110 檔 2082 passed；前端 e2e 38 passed；pytest（見 progress.md）；`pre-commit run --all-files` 全部 Passed。

**code-review 已處理**

- Standards：`sitesFirst` 的 `some((row) => …)` 遮蔽外層的 `row` → 改名 `candidate`。
- Spec：驗收的解讀、量測狀態、390 的結論寫進這裡與 progress.md。

**code-review 未處理的發現**

- Standards（判斷）：桌機的 Tab 順序是工作面 → 導覽（含「前往下一個泊位」）→ 左欄登入，與 PRODUCT「Tab 順序符合視覺順序」有出入；窄版導覽是最後一件。前進鍵只在兩件都做完才出現，「還差」連結會把焦點送到登入，所以留著，記在 progress.md 偏差。
- Standards（判斷）：`64rem` 寫在三處（`index.css`、`useWideScreen`、測試）；Tailwind 的斷點沒有 JS 可讀的來源，改斷點時要一起改。
- Standards（判斷）：單元測試斷言 class（`sticky`、`bg-assigned`）；調度黃就是 `bg-assigned`，DESIGN.md 用它定義「主鍵」。
- Standards（判斷）：`data-frame-column` 留在正式 DOM，給 e2e 的量尺與測試找欄用。
- Spec（小）：跨過 `lg` 斷點時 `ProwlarrLogin` 換父元素、重新掛載，打到一半的表單與上一次的拒絕會丟；只在拖動視窗寬度時發生。
