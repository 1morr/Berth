# 07 — 命名引擎、字幕比對與 Plan 產生

**Status:** done

**Blocked by:** 06

**讀:** plan §4.1（match_subtitle / plan）、§4.5、§5；brief §6.7、§7.1–§7.8

## 做什麼

解析器的最後一段：外掛字幕附掛到影片、命名模板產出目標路徑、`plan()` 組出完整的 Import Plan。
做完之後 benchmark 就是拿目標路徑在比對，M1 的入庫票才有東西可以套用。

命名模板已在 M0 票 04 的實驗後**凍結**（plan §5、brief §20.6 / §20.7），本票照著實作，不重新設計。
`AiPlanner` 的介面在這一票定好（plan §4.5），M1 的實作是 `NullAiPlanner`。

## 驗收

- [x] `naming/` 依 plan §5 的凍結模板產出相對於 Route 目標的路徑；作品資料夾、季資料夾、劇集檔、
      電影檔、外掛字幕、extras 六種各有測試
- [x] `sanitize` 移除 `/ \ : * ? " < > |` 與控制字元、連續空白合一、去尾端 `.` 與空白、
      整體 ≤ 200 bytes（UTF-8），有邊界測試
- [x] `episode_title` 缺 / 空 / 符合 `^Episode \d+$` 時省略，長度上限 80 字元
- [x] 電影檔名在 ` - ` 之前與資料夾名一字不差（**含 `[tmdbid-{id}]`**），有測試釘住這條實測結論
- [x] `match_subtitle` 依 brief §6.7 的順序附掛；語言由後綴或資料夾決定，都缺時看 `CjkHints`；
      字幕檔名用 `{影片主幹}.{SUBTOKEN}.{lang}` 且不用 `zh-Hant`（10.10 不認得）
- [x] `plan()` 為每個影片選最佳 Candidate、產出目標路徑、處置 extras 與 unmatched
- [x] 衝突偵測（brief §6.4 第 5 點）有測試。**§7.8 的「與帳本既有版本重複」不在這一票**：
      帳本要到票 12 才存在，而解析器沒有 IO——理由寫進 plan §4.1，追蹤在下面的 Comments
- [x] `berth bench` 連目標路徑一起比對；`auto_wrong = 0`，baseline 更新
- [x] `AiPlanner.propose(context, files, rules_plan) -> Plan | None` 介面定義完成，M1 是 `NullAiPlanner`
- [x] lint / type / test 全綠並貼指令輸出

## Comments

**做完的樣子**：`berth bench` 連目標路徑一起比對，`auto_wrong` **0**、`auto_correct` **140**
（與票 06 相同，加上路徑之後一筆都沒掉）、`subtitle_correct` **37**（語料寫下的外掛字幕全部
掛對）、`extra_correct` **41**；review 從 98 掉到 61，剩下的 61 個全是 `movie/your-name-bdmv`
的光碟檔。878 個後端測試綠燈。

**這一票決定的四件事**（理由都在 `docs/progress.md` 的「偏差與決定」）：

1. **`naming` 移到 `parser` 之下**：`plan` 階段要產出目標路徑，而衝突偵測比的就是那條路徑。
2. **衝突改比目標路徑**，不再比（季, 集）：同一集不同 tags 的檔案本來就該並存（brief §7.7），
   简繁分軌與 1080p / 720p 同包都是常態。票 06 的 `score._duplicated` 因此刪掉。
3. **字幕的語言由字幕自己決定**，不看 torrent 名；配對的第二條規則接受語言資料夾。
4. **benchmark 多一個 `subtitle_correct` 桶**，baseline 多守 `extra_correct` 與 `subtitle_correct`
   ——字幕或 extras 整批掉出來時 `auto_wrong` 一格都不會動。

**code-review（Standards / Spec 兩軸）之後改的**：長集名會把 tags 從尾巴截掉（同一集的兩個版本
被截成同一個檔名，於是彼此衝突、一個都進不去）、長標題的電影檔名不再以資料夾名開頭（Jellyfin
會當成兩部片）、`sanitize` 的「去尾端 `.`」誤傷了 `It Didn't Have to Be Magic...` 這種集名、
`stem` 與 basename 各寫兩份、`_attach` 的死分支、`GUARDED` 的欄位名沒有測試守著、
80 字元集名上限沒有測試、`ruff format` 兩個檔案沒過。

**留給後面的票**：

- **brief §7.8 的「與帳本既有版本重複 → `duplicate`」**：帳本要到票 12 才存在，而解析器沒有 IO，
  看不到既有 Entry。這一票做完的是同一包裡的衝突（brief §6.4 第 5 點）。plan §4.1 已寫明。
- **凍結的 `folder_name` 與快照的分歧**：`naming` 現在一律從 `MediaSnapshot` 算資料夾名，
  而票 09 之後 `media.folder_name` 會是凍結的那一個字串。兩者一旦分歧，電影的多版本判定就會斷
  （檔名前綴要與資料夾名一字不差）。票 11 / 12 接上 Plan 與 importer 時要決定由哪一邊供應
  ——六種模板全部經過 `folder_name()` 與 `_series_prefix()` 兩支，換來源只動這兩支。
- **`.default` 字幕旗標**：位置已經確定（`{SUBTOKEN}.default.{lang}`），但 M1 沒有東西決定得了
  哪一軌是預設。等有字幕語言偏好設定的那一票再產生它。
- **`AiPlanner` 的實作**：M4（plan §4.5）。`services/plan.py` 的輸入壓縮、schema 驗證、快取鍵、
  預算檢查也在那時候。
