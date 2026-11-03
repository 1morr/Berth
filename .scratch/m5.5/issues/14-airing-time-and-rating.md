# 14 — 時刻與評分

**Status:** ready-for-agent

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

- [ ] 卡片顯示未來集數的放送時刻與評分；對不上的作品不顯示這兩格（測試＋playwright 實跑）
- [ ] AniList 或 Bangumi 連不上時時間表照常打開（測試）
- [ ] 兩個 adapter 有契約測試；brief §20.3 已補
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新
