---
target: 精靈 SetupPage
total_score: 27
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 1
target_identity: "file:C:\\Users\\Roxy\\orca\\workspaces\\MediaServer\\t103\\web\\src\\pages\\SetupPage.tsx"
target_fingerprint: "sha256:4e5ca79055cf8055f0b5b97e4801118819b7d484f5689cbc3d2ecf459645e3fb"
target_path: "C:\\Users\\Roxy\\orca\\workspaces\\MediaServer\\t103\\web\\src\\pages\\SetupPage.tsx"
timestamp: 2026-10-14T05-22-48Z
slug: web-src-pages-setuppage-tsx
---
Method: dual-agent (A: design review · B: detector)

## Design Health Score — 27/40（Acceptable；票 68 時 26）

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | 泊位板某格值換兩行時五格垂直對齊錯開 |
| 2 | Match System / Real World | 2 | 既有卡片直接丟 DATA_ROOT、/data、mergerfs；「兩種 Berth」語意不清；en「Cast off」看不出是最後一頁 |
| 3 | User Control and Freedom | 3 | — |
| 4 | Consistency and Standards | 3 | 「介面登入」已一致；頁 4 標題形狀、塗漆規則、剖面列仍有分歧 |
| 5 | Error Prevention | 3 | — |
| 6 | Recognition Rather Than Recall | 3 | 文案「頁 N」與泊位板「BTH N」兩套編號 |
| 7 | Flexibility and Efficiency | 2 | 既有路線同一台 NAS 的主機名要打三次 |
| 8 | Aesthetic and Minimalist Design | 2 | 頁 2 既有完成後「不改偏好」說 5 次；鎖定後沒選的卡仍全文 |
| 9 | Error Recovery | 3 | — |
| 10 | Help and Documentation | 3 | 說明太多而非太少 |

## Deterministic scan
CLI `detect` 0 筆。瀏覽器 overlay：頁 1/2/3 有 `nested-cards`（泊位板 panel＋label 標題列，偏誤報），頁 3 一筆 `first-viewport-column-overflow`。

## Priority Issues
- [P1] 既有分支說明重複太多，「會觸發外部程式」這唯一需要行動的副作用被淹沒（頁 2 最嚴重）。→ distill、layout
- [P2] 頁 4 既有已有站時，推薦站段只剩一顆孤立的「之後再說」。→ clarify
- [P2] 既有路線頁 2、4 位址沒有沿用頁 1 的主機。→ onboard
- [P2] 一致性最後一哩：頁 4 標題、塗漆、介面登入在重新整理前後措辭不同、頁 4 剖面無介面登入列、頁 1 剖面「不存下」與沿用矛盾。→ polish
- [P2] 指向句清楚、與完成頁標題逐字對得上，但頁 1、2、4 各重複一次且插在卡片與表單之間；完成頁停在待辦上、`.env` 在哪沒說、「容器。 第一行」多一個空格、兩顆「複製」同名。→ clarify、delight

## Persona red flags
Jordan（第一次）：卡片術語、`.env` 位置；Sam（讀屏）：既有 radio 的描述約 200 字、兩顆同名「複製」、剖面報讀順序；Casey（手機）：390 寬第一屏看不到主要動作；Mei（NAS）：「會動我什麼」散在四處。
