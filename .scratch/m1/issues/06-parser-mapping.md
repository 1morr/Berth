# 06 — 解析器：季集對應與信心

**Status:** ready-for-agent

**Blocked by:** 05

**讀:** plan §4.1（structure_hints / map_episode / score）、§4.3、§4.4；brief §6.4、§6.5、§6.6

## 做什麼

把 ReleaseInfo 對應到 Media 的季與集，並給出三級信心。這是 M1 最難的一段，也是 benchmark 數字
第一次真的動起來的地方。

含資料夾結構提示、brief §6.4 的比對順序、三種絕對編號換算（episode group absolute、累計集數、
air_date 虛擬季 offset）各自產一個 Candidate 並附理由，以及 brief §6.5 的信心定義與批次一致性檢查。

若票 01 決定採用 TVDB 作為 anime profile 的季集來源，本票的 `ParseContext` / `MediaSnapshot` 依
plan §4.3 修訂後的形狀實作。

## 驗收

- [ ] `structure_hints` 認得 `Season 2` / `S2` / `第二季` / `2nd Season` / `Part 2` / `Specials` /
      `SPs`，以及 `Subs/` `字幕/` 與其下的語言子資料夾
- [ ] `map_episode` 依 brief §6.4 的順序產 `Candidate`，三種絕對編號換算各自產一個並附 `strategy` 與理由
- [ ] offset 偵測（季內 `air_date` 間隔 > 180 天切虛擬季）有測試；該策略的信心至多 medium
- [ ] 上下文缺 Media 時做標題比對（正規化後比 `name` / `original_name` / alternative titles /
      translations，年份加權）
- [ ] 多集檔、合集、多季（brief §6.6）在語料裡各有涵蓋並解對
- [ ] `score` 實作 brief §6.5 的三級定義；批次一致性檢查（同模式、連續集號、數量吻合）有測試
- [ ] `berth bench`：`auto_wrong = 0`，`auto_correct` 高於票 05 的 baseline
- [ ] baseline 更新，改善的數字寫在 commit message 的 body
- [ ] anime 與 tv / movie 的數字分開報告
- [ ] lint / type / test 全綠並貼指令輸出
