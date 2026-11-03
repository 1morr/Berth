# 08 — 時間表資料源實驗

**Status:** ready-for-agent

**Blocked by:** None (can start immediately；可與 07 平行)

**讀:** spec〈範圍〉「時間表」的資料那一條；brief §20.3〈放送時間表的來源〉、§10；`docs/development.md`（`TMDB_API_KEY`）；skill `mattpocock-skills:prototype`

## 為什麼

時間表預定以 TMDB 為主幹（有作品 id、海報、zh-TW），但 discover 的條件與它對當季新番的覆蓋率還沒實測（brief §20.3）。09 用哪個來源當主幹要看這個結果。

## 做什麼

1. 寫 `scripts/experiments/schedule_sources.py`（保留，下次換季重量；plan §10）：
   - 用 TMDB discover（或 `tv/on_the_air`）列當季動畫，條件可調。
   - 抓 Bangumi 的放送表，當作「當季新番」的對照。
   - 比對兩邊（標題、Bangumi 與 TMDB 的對應），算 TMDB 列得出的比例，並列出漏掉的作品。
2. **判定**：覆蓋率九成以上，09 照 TMDB 為主幹；**低於九成就改以 Bangumi 為主幹**、再對 TMDB，並同輪改 spec〈範圍〉與 09 的「做什麼」。
3. 結論、discover 參數、覆蓋率數字與來源寫回 brief §20.3。

## 驗收

- [ ] 實驗腳本在 `scripts/experiments/`，跑得起來，輸出貼在 Comments
- [ ] brief §20.3 有覆蓋率、漏掉的作品、discover 參數與主幹的決定（附來源）
- [ ] 主幹改成 Bangumi 時，spec 與票 09 已跟著改
- [ ] 全部檢查綠；progress.md 已更新
