# 14 — 時刻與評分

**Status:** done

**Blocked by:** 09

**讀:** spec〈範圍〉「時間表」的第二層；brief §20.3（AniList `AiringSchedule`、Bangumi）；`.scratch/m5.5/schedule-shape.md`

## 為什麼

時間表的主幹只有日期。放送時刻與評分是第二層：AniList 只給未來的精確時刻，Bangumi 補評分。

## 做什麼

1. AniList `AiringSchedule` 的 adapter：只取未來的精確時刻（官方只保證未來的資料，brief §20.3），不拿來判斷該不該入庫。
2. Bangumi 的評分 adapter（08 若已改成 Bangumi 為主幹，評分直接從主幹拿）。
3. 對到主幹的作品才顯示，**對不上就不顯示**，不猜。對應方式照 brief §20.3 的 ID 對應。
4. 結果與主幹一樣存程序內 `TtlCache`；外部來源失敗時卡片照常顯示，只少這兩格。
5. adapter 用 fixture 做契約測試；查到的端點與參數補進 brief §20.3（附來源）。

## 驗收

- [x] 卡片顯示未來集數的放送時刻與評分；對不上的作品不顯示這兩格（測試＋playwright 實跑）
- [x] AniList 或 Bangumi 連不上時時間表照常打開（測試）
- [x] 兩個 adapter 有契約測試；brief §20.3 已補
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- 2026-11-04 **對應方式改成原文名**（偏差，記在 progress.md）：票寫「照 brief §20.3 的 ID 對應」，但那份對照表（Fribb）M5 票 23d 已拿掉，產品裡沒有 TMDB↔AniList / Bangumi 的 id。實驗 `scripts/experiments/schedule_mapping.py`（`docs/research/schedule-mapping-2026-11-04.md`）：日本作品的卡片 Wikidata 只對到 46.2% / 16.1%（多半只記第一季的 id），原文名完全相同 57.0% / 51.6%，兩種都對到的 52 部 0 件不一致。採原文名（NFKC、不分大小寫、只留字母數字後相等），時刻另外要 AniList 那一筆的日本日期與 TMDB 播出日差一天以內；同名不只一部、或兩筆一樣近就不顯示。對不到的多半是續作與國產動畫。
- 「只取未來的」做在 service：adapter 抓整週（時段固定，快取才接得住），過去的那幾筆也拿來對日期，避免把隔壁那一集當成這一集；顯示時只給 `airs_at > now` 的。
- 兩個來源與 TMDB 同時抓，各自 10 秒上限；失敗或逾時的來源記 5 分鐘不再問（否則它掛著時每一次打開都要等到逾時）。快取在各自的 adapter（AniList 6 小時、每頁一份；Bangumi 1 小時）。
- 時刻 API 一律送 UTC，畫面照瀏覽器時區、24 小時制；那一刻的本地日期不是卡片那一天時前面寫星期（「週六 00:30」）。評分畫面寫「Bangumi 8.1」、人數在 `title`，念一整句「Bangumi 評分 8.1，900 人打分」（Chrome 會在 `sr-only` 前多算一個空白，所以不拆成兩段念）。
- Bangumi `/calendar` 的名字是 HTML 跳脫過的，adapter 改成還原（側面板的 `bgm.read_calendar` 也跟著拿到還原後的名字）。
- code-review 已處理：轉譯層遇到怪形狀丟 `AttributeError`（時間表接不住、整頁 500）→ AniList 與 Bangumi 都改成跳過；有分數沒人數不寫「0 人打分」；讀到頁數上限記 log；替身的時段兩端改成不含（同 AniList）；`title_key` 與 `parser/binding.title_key` 撞名 → `match_key`，評分與時刻的「同名只一部」抽出來；DESIGN.md〈時間表〉補時刻與評分。
- 2026-11-04 **評分的季別守衛**（協調者要求補）：TMDB 多季併一部、原文名是系列名，Bangumi 一季一條、第一季常用系列名，只比名字的話續作會掛上第一季的分數。評分另外要 Bangumi 條目的 `air_date` 與卡片那一季的 `seasons[].air_date` 差一天以內，任一邊沒日期就不顯示（`SEASON_START_SLACK`）。容差依數據：原文名對到唯一一筆的 48 張差距全是 0（36）或 −1 天（12，深夜檔），±0 剩 36、±1 到 ±60 都是 48，取 ±1。重量（`schedule_mapping.py`，日本作品卡片 93 張）會顯示評分的：**守衛前 46/93 = 49.5%，守衛後 46/93 = 49.5%**。這週守衛沒擋到任何一張：第二季以後的卡 17 張原文名都沒對到 Bangumi（續作條目帶季號、舊季不在放送表），它是防線。修前會紅的測試：`test_a_bangumi_entry_of_another_season_or_without_a_date_has_no_rating`。
- code-review 未處理：
  - 時刻前有 `Dot`、評分前沒有（狀態色塊前也沒有）：評分與狀態是色塊與標籤，接在後面不用分隔；照 DESIGN.md〈中點分隔〉只用在值與值之間。
  - 人數只在 `title`，觸控裝置看不到；卡片窄，桌機一欄放不下「（900 人）」。
  - `fake_setup_server.SCHEDULE_OTHERS` 從 6 欄的位置 tuple 變 7 欄（Data Clumps）：演練資料，先不包。
