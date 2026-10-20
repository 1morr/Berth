---
target: 精靈 SetupPage
total_score: 28
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/home/user/Berth/web/src/pages/SetupPage.tsx"
target_fingerprint: "sha256:b99d3fab30668e81a03387a493a37a6cfc3849b20d87f2e925162482309af7d6"
target_path: /home/user/Berth/web/src/pages/SetupPage.tsx
timestamp: 2026-10-20T08-58-30Z
slug: web-src-pages-setuppage-tsx
---
Method: dual-agent (A: design review · B: detector)

## Design Health Score — 28/40（Acceptable；票 104 時 28）

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | 左欄登入狀態卡與剖面「介面登入」列重複報同一件事 |
| 2 | Match System / Real World | 2 | 頁 1、2 既有卡仍丟 DATA_ROOT、/data、mergerfs、Web API 2.8.4 |
| 3 | User Control and Freedom | 3 | — |
| 4 | Consistency and Standards | 3 | 介面登入頁 2 在工作面、頁 4 桌機在剖面欄 |
| 5 | Error Prevention | 3 | 加站在飛時登入 held；版面原本沒說先加站（之後以「一屏一顆調度黃」處理） |
| 6 | Recognition Rather Than Recall | 3 | 「還差」連結跨欄接得上；「頁 N / BTH N」兩套編號 |
| 7 | Flexibility and Efficiency | 2 | 既有路線頁 2、4 位址不沿用頁 1 的主機 |
| 8 | Aesthetic and Minimalist Design | 3 | 兩欄平衡（↑）；左欄「介面登入」字樣三到四次（↓） |
| 9 | Error Recovery | 3 | — |
| 10 | Help and Documentation | 3 | 說明偏多；登入說明「必填。」與「必填」標重複 |

## Deterministic scan
CLI `detect` 0 筆。overlay：頁 4 套件內已選（1280、390）、登入表單打開（1280、390）0 筆；按「測試推薦站」之後 1280 有 `first-viewport-column-overflow`（工作面 1947px 對剖面 917px，來自推薦站結果清單）。

## Priority Issues
- [P2] 頁 4 套件內沒沿用時兩件必填沒有先後編碼（兩顆黃鍵並排）→ layout（本票已處理：加站前登入送出鍵改 Ghost）
- [P2] 左欄「介面登入」四處重複（剖面列、h3、legend、狀態卡）；頁 2 同 → distill
- [P2] 頁 1 既有卡太長 → distill
- [P3] 剖面欄只放讀的契約多了 `aside` 例外，要記進 DESIGN.md → document（本票已記）
- [P3] 「沿用」沒勾時帳號已預填；h2 移焦後留 focus outline → polish

## Persona red flags
Jordan：既有卡術語、沒沿用時不知先後；Casey：Tab 從工作面導覽跳回左欄登入（可接受，前提是視覺說出登入是第二件）；Mei：主機名打三次；Sam：無。

## Minor
- 加站結果出來後左欄不 sticky，捲到下半段左欄全空（有意取捨）。
- 390 寬整頁截圖「之後再說」下方的空白是 sticky 主鍵在 fullPage 截圖錯位，逐屏截圖正常。
