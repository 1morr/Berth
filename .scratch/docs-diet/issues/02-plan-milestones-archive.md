# 02 — plan §11 已驗收的 M0–M5 小節封存，遺留項目歸位

**Status:** ready-for-agent

**Blocked by:** 01

**讀:** `.scratch/docs-diet/spec.md`；plan §11（§11.1–§11.6 搬走，§11.7、§11.8 留）；brief §17、§18；`docs/progress.md` 里程碑表

## 為什麼

plan §11 有 432 行。M0–M5 的六節（§11.1–§11.6，約 374 行 85 KB）都已驗收，拆票後以票為準，沒人再讀。但其中有些「延後」「遺留」的項目還沒做，搬走就沒人看得到了。

## 做什麼

1. **搬**：§11.1–§11.6 全文搬到 `docs/archive/<里程碑>.md` 新的 `## plan §11` 段（§11.2b → `m1.5.md`）。
2. **留標題**：plan 每節留標題加一行「已驗收（日期），內容在 `docs/archive/mX.md`」。`berth/`、`web/` 引用 §11.1–§11.6 共 84 處，標題號碼不能變。
3. **遺留項目**：逐條掃六節裡「延後」「遺留」「之後」「M6」「不做」這類標記的項目，對 `.scratch/` 票的 `Status:` 與 `git log` 判斷做了沒有。
   - 沒做、屬於 M6 範圍的 → §11.7；其餘 → 新節 §11.9「不排里程碑」（號碼接在 §11.8 後）。
   - 每條附原出處（archive 的位置）。
   - 判不出做了沒有的不搬，列在 Comments 問使用者。
4. **改引用**：progress.md 里程碑表的「拆票前讀」欄、`CLAUDE.md`、brief §17 裡指到已封存小節的，改指 archive。舊票與 research 不改（標題那一行接住）。

## 驗收

- [ ] `scripts/docs_moved_lines.py` 對 `docs/plan.md` → `docs/archive/*.md` 跑出「遺失 0」，輸出貼 Comments（遺留項目是複製到 §11.7 / §11.9，原文也在 archive）
- [ ] 遺留清單表（項目、原出處、做了沒、證據、去處）貼 Comments
- [ ] plan §11.1–§11.6 只剩標題加一行，號碼不變
- [ ] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments
