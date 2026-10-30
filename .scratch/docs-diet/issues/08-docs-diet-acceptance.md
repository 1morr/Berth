# 08 — docs-diet 收尾：重量、封存、評估閘門

**Status:** ready-for-agent

**Blocked by:** 01, 02, 03a, 03b, 04a, 04b, 04c, 05a, 05b, 05c, 05d, 05e, 06, 07

**讀:** `.scratch/docs-diet/spec.md`（〈量測〉）；`docs/progress.md`〈寫法與封存〉；各票的 Comments

## 為什麼

每個里程碑都有驗收票，docs-diet 也要有一張：確認目標達到，並照〈寫法與封存〉把 docs-diet 自己的紀錄封存，第一次實際跑封存流程。

## 做什麼

1. **重量**：照 spec〈量測〉的表重量一次，前後並列貼 Comments：每個檔的大小、行數；plan / brief 的歷史標記數；§20 的行數。
2. **必讀範圍**：挑一張 M6 的票（或 plan §11.7），量「CLAUDE.md + progress.md + 票 + 票指到的章節」總共多少字，貼 Comments。讀不完的話，寫明卡在哪一份，問使用者要不要再開票。
3. **評估閘門**：plan / brief 的章節大小要不要加閘門（票 07〈不做〉留下的問題）。建議與理由寫 Comments，由使用者決定；要加就另開票。
4. **封存**：docs-diet 的 session 紀錄與偏差搬到 `docs/archive/docs-diet.md`，用 `scripts/docs_moved_lines.py` 證明；里程碑表 docs-diet 那一列改成「完成，封存於…」。
5. 各票 Comments 裡沒處理的發現彙整成清單貼 Comments，問使用者要不要開票。

## 驗收

- [ ] 前後量測表貼 Comments
- [ ] 必讀範圍量測與結論貼 Comments
- [ ] 閘門評估寫了建議
- [ ] `scripts/docs_moved_lines.py` 對 docs-diet 的封存跑出「遺失 0」，輸出貼 Comments
- [ ] 全部檢查與 test 綠；commit；不 push

## Comments
