# 09b — Feed 的 Route 標成不可逆

**Status:** ready-for-agent

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

- [ ] `set_feed_routes` 標 `irreversible`，測試守住且雙向變異驗過（pytest）
- [ ] brief §14、§19（與 plan 若有）已同步
- [ ] 全部檢查、`pnpm -C web build`、pytest、vitest 綠；progress.md 已更新

## Comments
