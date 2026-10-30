# 04a — brief §19 決策紀錄改成 ADR

**Status:** ready-for-agent

**Blocked by:** 01

**讀:** `.scratch/docs-diet/spec.md`；brief §19（56 列的表加待決問題，35 KB）；`docs/agents/domain.md`；`mattpocock-skills:domain-modeling`（ADR 格式）

## 為什麼

brief 要只寫現況，但 §19 本身就是歷史：56 列「哪天、誰、決定了什麼、為什麼」。有些「為什麼」之後還用得到（下次有人想改回去時），有些已經寫進正文或被後來的決定取代。04b、04c 改寫正文時要能把「為什麼」連到 ADR，所以這張先做。

## 做什麼

1. **逐列判定**，三種去處：
   - (a) 決定仍有效，「為什麼」不明顯、以後會有人想推翻 → 寫一篇 `docs/adr/NNNN-<slug>.md`（從 0001 編），格式照 domain-modeling。
   - (b) 決定仍有效，正文已經寫清楚、理由一看就懂 → 從 §19 刪。
   - (c) 已被後來的決定取代 → 從 §19 刪。
   - 刪掉的列原文搬到 `docs/archive/<里程碑>.md` 新的 `## brief §19` 段，里程碑照列的日期。
2. **§19 留**：還沒定案的待決問題，加一份 ADR 索引（編號、標題、一句話）。§19 號碼不變（`berth/`、`web/` 引用 71 處）。
3. **正文**：(a) 類決定所在的正文章節，在決定旁連到 ADR。只加連結，正文的改寫留給 04b、04c。
4. 判斷不了該 (a) 還是 (b) 的，偏向 (a)。看不出還有沒有效的，列在 Comments 問使用者。

## 驗收

- [ ] 去處表（列、判定 a/b/c、去處、理由一句）貼 Comments，56 列都有
- [ ] `scripts/docs_moved_lines.py` 對 §19 刪掉的 (b)(c) 列 → `docs/archive/*.md` 跑出「遺失 0」，輸出貼 Comments
- [ ] 收尾 code-review 的 Spec 軸逐列對照：每個 (a) 列的決定與理由都在 ADR 裡
- [ ] `docs/adr/` 的連結都指得到檔
- [ ] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments
