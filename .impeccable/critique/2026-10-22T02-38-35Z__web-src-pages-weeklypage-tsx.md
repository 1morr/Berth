---
target: 週報
total_score: 29
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:C:\\Users\\Roxy\\orca\\workspaces\\MediaServer\\t132\\web\\src\\pages\\WeeklyPage.tsx"
target_fingerprint: "sha256:92df8a6fc235c734910f998258236e2335614f639602e8b26f11072581d9c643"
target_path: "C:\\Users\\Roxy\\orca\\workspaces\\MediaServer\\t132\\web\\src\\pages\\WeeklyPage.tsx"
timestamp: 2026-10-22T02-38-35Z
slug: web-src-pages-weeklypage-tsx
---
Method: dual-agent (A: 設計審查＋audit，opus · B: 偵測器＋overlay，sonnet)

## Design Health Score：29/40（Good）；Audit 16/20

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | 系統狀態可見 | 3 | 「產生於」用瀏覽器時區，週界用容器時區 |
| 2 | 貼近真實世界 | 3 | rematch 偏行話；「入庫 3」沒單位 |
| 3 | 使用者控制 | 3 | 沒有上一週／下一週 |
| 4 | 一致性 | 3 | 時間格式化與全站 Timestamp 不同源 |
| 5 | 錯誤預防 | 3 | 「巡檢開出的」容易被重複加總 |
| 6 | 辨識勝於回憶 | 3 | |
| 7 | 彈性與效率 | 3 | 換週要捲到最底 |
| 8 | 美學與極簡 | 3 | 空段落照樣有快照說明 |
| 9 | 錯誤復原 | 3 | 404 連結 aria-current 錯 |
| 10 | 說明文件 | 2 | 沒說一週的界線 |

偵測器：CLI 0 條；overlay 1280 / 390 "No anti-patterns found."

## Priority Issues（沒有 P0 / P1）
- [P2] 「產生於」與週界時區不同源（協調者點名，票 131）。
- [P2] 404 頁「看最新一週」帶 aria-current="page"。
- [P2] 「巡檢開出的」與 Issue 並排成同級列。
- [P2] 換週後焦點掉到 body（全站）；頁面標題全站都是 Berth（WCAG 2.4.2，全站）。
- [P3] 入庫清單排序前後端不一致（協調者點名，票 131）；歷史列沒單位；h1 沒週次；其餘打磨。
