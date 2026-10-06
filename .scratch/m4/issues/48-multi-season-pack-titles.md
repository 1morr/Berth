# 48 — 「S01 + S02」「S1-S2」讀成季包，不是 S01E02

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S6 RSS 那列、§3.2 RSS 那列、改進清單 P2-6）；brief §6.3、§6.6、§6.9；plan §4.1、§4.6

## 為什麼（2026-10-06 審計，實測）

- 用一次性 RSS 連結讀 `acg.rip/.xml?term=Frieren`，「S01 + S02」與「S1-S2」兩包被標成 `S01E02`。截圖 s6-08。
- 沒有送單，所以不知道會不會影響自動綁定；要先查清楚。

## 做什麼

1. 先把那兩個標題（與同類的變體）加進 benchmark fixture，確認是紅燈。
2. 走 tdd 修發佈名解析，讀成多季合集（brief §6.6）。
3. 查清楚它對 RSS 自動綁定與送單的影響，結論寫在 Comments。

## 驗收

- [ ] fixture 先紅後綠；兩個標題讀成 S01–S02 的季包
- [ ] `berth bench` 的 `auto_wrong` 不上升（前後數字貼在 Comments）
- [ ] 對 RSS 自動綁定的影響有結論
- [ ] 全部檢查（`pre-commit run --all-files`）、test 綠燈
