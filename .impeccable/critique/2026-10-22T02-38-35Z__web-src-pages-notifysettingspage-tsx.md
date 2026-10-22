---
target: 設定 → 通知
total_score: 30
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 1
target_identity: "file:C:\\Users\\Roxy\\orca\\workspaces\\MediaServer\\t132\\web\\src\\pages\\NotifySettingsPage.tsx"
target_fingerprint: "sha256:a353e917bf650e23e0f6ff3707e4e1c520deff963dd6f3e104de3844430bb241"
target_path: "C:\\Users\\Roxy\\orca\\workspaces\\MediaServer\\t132\\web\\src\\pages\\NotifySettingsPage.tsx"
timestamp: 2026-10-22T02-38-35Z
slug: web-src-pages-notifysettingspage-tsx
---
Method: dual-agent (A: 設計審查＋audit，opus · B: 偵測器＋overlay，sonnet)

## Design Health Score：30/40（Good）；Audit 17/20

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | 系統狀態可見 | 3 | 「已儲存」與「還沒儲存」並列；測試對未存的 ID 說已送出 |
| 2 | 貼近真實世界 | 4 | 照 Discord 自己的路徑寫 |
| 3 | 使用者控制 | 3 | 網址沒有明確的清掉；草稿離頁默默丟掉 |
| 4 | 一致性 | 3 | 三處「已儲存」位置不一、欄寬不一 |
| 5 | 錯誤預防 | 2 | 沒存的 ID 照樣能按測試（P1） |
| 6 | 辨識而非回憶 | 3 | |
| 7 | 彈性與效率 | 3 | 沒有存並測試 |
| 8 | 美學與極簡 | 3 | 到不了時同一段說明出現兩次 |
| 9 | 錯誤復原 | 3 | 「補好之後按測試」帶進 P1 |
| 10 | 說明文件 | 3 | token 被拒沒提 Reset Token |

偵測器：CLI 0 條；overlay 1280 / 390 "No anti-patterns found."

## Priority Issues
- [P1] 測試鍵測的是存著的 Discord ID，不是欄位裡改過的（已修：M4 票 132，`MyHalf` 持有草稿，測試鍵說先儲存）。
- [P2] 清空網址並儲存後「已儲存」與「還沒儲存」並列（已修：「已清掉：通知不附連結。」）。
- [P2] 收件人到不了時失敗說明出現兩次、兩個 role=alert。
- [P3] 改了網址後說明仍寫「預填的是…」（協調者點名，票 124；已修：`berth.unsavedEdited`）。
- [P3] 草稿沒有未儲存標示；en 390 placeholder 截斷；「顯示」鍵對不齊；欄寬不一；token 被拒的補法。

修後：P1 由 vitest（改前紅）與實跑驗證（`aria-disabled` 與描述）。
