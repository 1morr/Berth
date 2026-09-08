# 01 — 動漫季集來源定案（TVDB 研究）

**Status:** ready-for-agent

**Blocked by:** 無 —— 可立即開工

**讀:** brief §10、§20.3、§20.6（最後一條）；plan §2.2、§4.3、§4.4

## 做什麼

brief §10 的【研究】「TVDB 作為 anime profile 的季集來源」定案。抽 10 部動漫（要涵蓋 split-cour、
連續兩季、長篇累計編號、劇場版接續正篇這幾種形態），量化字幕組實際使用的編號換算到三種來源的
失敗率：TMDB 季集、TVDB default(aired) season、TVDB absolute。以數字決定 anime profile 的季集
來源要不要換。

這張票**沒有產品程式碼**，但它決定 `media` 表的欄位與 `map_episode` 的形態，所以排在所有會碰
`media` 或解析器的票之前。採用 TVDB 的形態已在 brief §10 寫好：Media 主鍵維持 `tv:<tmdb id>`，
`media` 加 `tvdb_id` 與 `episode_source`，只有 `anime` profile 的 Route 用 TVDB 編號並要求該媒體庫
裝 TVDB 插件。

用 `mattpocock-skills:research`，輸出放 `docs/research/`。

## 驗收

- [ ] 10 部動漫的樣本清單與挑選理由寫在 `docs/research/`，每一部附三種來源的季集對照表
- [ ] 三種來源各自的換算失敗率有數字，失敗案例逐條寫出是哪一種形態造成的
- [ ] 決定寫進 brief §10（【研究】改成【決定】）並附理由；§20.6 最後一條劃掉
- [ ] 若採用 TVDB：plan §2.2 補 `media.tvdb_id` / `episode_source`、§4.3 的 `MediaSnapshot` 與 §8 補
      TVDB adapter；票 03、05、06 依此修訂並在票上註明改了什麼
- [ ] 若維持 TMDB：brief §10 寫明放棄理由與弱點對策（絕對編號換算 + review），票 03、05、06 不動
- [ ] 資料來源與查詢方式可重跑（腳本留在 `scripts/experiments/`，或在研究文件寫清楚每一支查詢）
- [ ] `docs/progress.md` 的「偏差與決定」記一行：這條研究改在 M1 票 01 做而不是拆票前
