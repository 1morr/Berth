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
timestamp: 2026-10-19T16-59-42Z
slug: web-src-pages-setuppage-tsx
---
Method: dual-agent (A: design review · B: detector)

## Design Health Score — 28/40（Acceptable；票 103 時 27）

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | 390 寬頁 4 推薦站說明下方留白 |
| 2 | Match System / Real World | 2 | 既有卡片仍直接丟 DATA_ROOT、/data、mergerfs、Web API 2.8.4 |
| 3 | User Control and Freedom | 3 | — |
| 4 | Consistency and Standards | 3 | 票 104 的六處都對齊；頁 4 已選後標題仍只是「Prowlarr」 |
| 5 | Error Prevention | 3 | 外部程式那一句獨立、貼著測試鍵 |
| 6 | Recognition Rather Than Recall | 3 | 「頁 N」與「BTH N」兩套編號 |
| 7 | Flexibility and Efficiency | 2 | 頁 2、4 位址不沿用頁 1 的主機 |
| 8 | Aesthetic and Minimalist Design | 3 | 「不改你的東西」只說一次（↑）；頁 1 既有卡片仍長 |
| 9 | Error Recovery | 3 | — |
| 10 | Help and Documentation | 3 | 說明太多而非太少 |

## Deterministic scan
CLI `detect` 0 筆（`--no-config` 亦同）。瀏覽器 overlay：頁 2、3、4 的 lede 與 hint `line-length`（已有 `max-w-prose`，65ch 對這套字體偏寬，半誤報）；頁 4 套件內 `first-viewport-column-overflow`（右欄 147% 視窗高、左欄 34%）。

## Priority Issues
- [P2] 頁 1 既有卡片太長、選之前就要讀完 → distill
- [P2] 頁 4 套件內一屏兩件必填（加站與介面登入）、決策點約 7 個 → layout
- [P2] 既有路線頁 2、4 位址不沿用頁 1 的主機（票 103 時使用者決定這一輪不做）→ onboard
- [P3] 頁 4 「沿用」沒勾時帳號已預填擁有者 → polish
- [P3] 390 寬頁 4 推薦站段落下方大片空白（待實跑確認）→ adapt

## Persona red flags
Jordan：卡片術語；Mei：主機名要打三次；Casey：頁 2 完成後要捲過選擇與探針說明才到前進鍵；Sam：既有 radio 的描述仍長。

## Minor
- 頁 2 既有做完後探針說明是現在式（「測試時…」），測試已跑完。
- 頁 3 hero 最重要的安撫「進這一頁不會動任何東西」排在最後。
- 頁 4 的 h2 在程式移焦後留一圈 focus outline（StepFrame 移焦，既有行為）。
