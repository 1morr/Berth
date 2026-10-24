# 09b — Feed 的 Route 標成不可逆

**Status:** done

**Blocked by:** None — can start immediately（不碰票 09 的檔案）

**讀:** brief §14〈自主權看可不可以撤銷〉「改設定照字面」那一句、§19 決定紀錄的格式；`tests/unit/test_command_marks.py`（票 04 加的「改設定」與「寫到別人服務上」兩條清單）；`berth/services/rss.py` 的 `set_feed_routes`

## 為什麼

票 04 照 brief §14 的字面，把「Feed 自己的屬性（輪詢間隔、Route）」算成不是改設定，`rss.set_feed_routes` 標成 `REVERSIBLE`。使用者 2026-10-24 決定：**Feed 送到哪條 Route 要人確認**。Route 決定新集數下載到哪個資料夾、進哪個媒體庫；撤銷改得回設定，但改錯到撤銷之間已經送出的下載會進到錯的地方，收不回來。plan 也把「改 Route」點名在要確認的那一類。

輪詢間隔、排除條件、搜尋記住的名字種類維持可逆（使用者同意子 session 的判斷）。

目前登錄表裡沒有任何工具用到 `set_feed_routes`，所以這張只改標記與文件；之後誰把它登記成工具，它就會走確認卡（票 10）。

## 做什麼

1. `rss.set_feed_routes` 改標 `Effect.IRREVERSIBLE`（沒有反向命令）。
2. `test_command_marks.py` 把它加進「改設定」那一類的清單（或票 04 對應的那一條），讓它被測試守住；雙向變異：改回 `REVERSIBLE` 會紅。
3. brief §14 那一句改成：Feed 的 Route 算在「Route 的增刪」同一類、標不可逆；輪詢間隔、排除條件、搜尋記住的名字種類照舊不算。§19 加一列「2026-10-24，使用者：Feed 的 Route 要人確認」與理由。plan 若有提到 Feed Route 等級的地方一起改。
4. 若前端或其他地方依等級決定行為（例如結果卡附不附撤銷），確認沒有被這個改動弄壞。

## 驗收

- [x] `set_feed_routes` 標 `irreversible`，測試守住且雙向變異驗過（pytest）
- [x] brief §14、§19（與 plan 若有）已同步
- [x] 全部檢查、`pnpm -C web build`、pytest、vitest 綠；progress.md 已更新

## Comments

- 2026-10-24 實作：雙向變異實跑過——`set_feed_routes` 改回 `@command(Effect.REVERSIBLE)` 時 `test_command_marks.py` 1 failed；改成多行排版、改一個參數名時 16 passed。plan 沒有提到 Feed Route 的等級（§11.6〈對話核心〉本來就把 Route 整個列為 `irreversible`），沒改。登錄表沒有工具指著 `set_feed_routes`，等級只由 `registry.Tool.effect` / `.inverse` 讀，前端與 `api/gate.py` 不依等級分流，`PUT /rss/feeds/{id}/routes` 行為不變。
- code-review 未處理（不排里程碑）：①輪詢間隔、排除條件、搜尋記住的名字種類（`rss.set_feed_interval`、`rss.set_exclusions`、`search.remember_names`）沒有測試釘成 `reversible`，有人改成不可逆不會紅——票沒要求，要守時在 `test_command_marks.py` 加一條反向清單；②那條測試的變數 `settings` 其實也裝 Route 的命令，可改名 `settings_and_routes`（改動前就有）。
