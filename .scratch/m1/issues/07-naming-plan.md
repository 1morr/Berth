# 07 — 命名引擎、字幕比對與 Plan 產生

**Status:** ready-for-agent

**Blocked by:** 06

**讀:** plan §4.1（match_subtitle / plan）、§4.5、§5；brief §6.7、§7.1–§7.8

## 做什麼

解析器的最後一段：外掛字幕附掛到影片、命名模板產出目標路徑、`plan()` 組出完整的 Import Plan。
做完之後 benchmark 就是拿目標路徑在比對，M1 的入庫票才有東西可以套用。

命名模板已在 M0 票 04 的實驗後**凍結**（plan §5、brief §20.6 / §20.7），本票照著實作，不重新設計。
`AiPlanner` 的介面在這一票定好（plan §4.5），M1 的實作是 `NullAiPlanner`。

## 驗收

- [ ] `naming/` 依 plan §5 的凍結模板產出相對於 Route 目標的路徑；作品資料夾、季資料夾、劇集檔、
      電影檔、外掛字幕、extras 六種各有測試
- [ ] `sanitize` 移除 `/ \ : * ? " < > |` 與控制字元、連續空白合一、去尾端 `.` 與空白、
      整體 ≤ 200 bytes（UTF-8），有邊界測試
- [ ] `episode_title` 缺 / 空 / 符合 `^Episode \d+$` 時省略，長度上限 80 字元
- [ ] 電影檔名在 ` - ` 之前與資料夾名一字不差（**含 `[tmdbid-{id}]`**），有測試釘住這條實測結論
- [ ] `match_subtitle` 依 brief §6.7 的順序附掛；語言由後綴或資料夾決定，都缺時看 `CjkHints`；
      字幕檔名用 `{影片主幹}.{SUBTOKEN}.{lang}` 且不用 `zh-Hant`（10.10 不認得）
- [ ] `plan()` 為每個影片選最佳 Candidate、產出目標路徑、處置 extras 與 unmatched
- [ ] 衝突與重複偵測（brief §6.4 第 5 點、§7.8）有測試
- [ ] `berth bench` 連目標路徑一起比對；`auto_wrong = 0`，baseline 更新
- [ ] `AiPlanner.propose(context, files, rules_plan) -> Plan | None` 介面定義完成，M1 是 `NullAiPlanner`
- [ ] lint / type / test 全綠並貼指令輸出
