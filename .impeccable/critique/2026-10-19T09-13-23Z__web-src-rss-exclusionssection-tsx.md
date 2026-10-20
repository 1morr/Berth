---
target: /rss exclusions three layers
total_score: 19
max_score: 28
na_heuristics: 5,7,9
p0_count: 0
p1_count: 1
target_identity: "file:/home/user/Berth/web/src/rss/ExclusionsSection.tsx"
target_fingerprint: "sha256:a86c3e182467dbc09ac7e5042b600a60cbfc8f75905fb0ef71494b8544d9a1c8"
target_path: /home/user/Berth/web/src/rss/ExclusionsSection.tsx
timestamp: 2026-10-19T09-13-23Z
slug: web-src-rss-exclusionssection-tsx
---
Method: dual-agent (A: design review · B: detector)

範圍：/rss 排除條件三層（M4 票 113）。

Design specificity：通過（DESIGN.md 的 `.label` / `.value`、不塗漆、重橫線分組）。

| # | Heuristic | Score |
|---|---|---|
| 1 | Visibility of system status | 3 |
| 2 | Match with real world | 3 |
| 3 | User control | 3 |
| 4 | Consistency | 2 |
| 5 | Error prevention | n/a |
| 6 | Recognition | 3 |
| 7 | Flexibility | n/a |
| 8 | Minimalist | 2 |
| 9 | Error recovery | n/a |
| 10 | Help | 3 |

Detector：0 發現。

Priority issues
1. P1 兩層的空狀態「沒有排除條件。」與「合集由全域設定：目前不自動下載」矛盾 → 已改「沒有標題規則。」。
2. P2 toggle 仍叫「排除條件（N 條）」、全域叫「標題規則」→ 未改（記在票 113 Comments）。
3. P2 「改全域設定」原生錨點只捲動、不移焦點 → 未改（與 SUBSCRIBE_ANCHOR 同做法，記在 Comments）。
4. P3 內建判斷組的說明不在 accessible description → 已補 aria-describedby。
5. P3 390 寬新增 Feed 的說明偏密 → 未改。
