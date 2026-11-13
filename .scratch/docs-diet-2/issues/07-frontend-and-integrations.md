# 07 — plan §7〈前端〉、§8〈外部整合細節〉歸位

**Status:** ready-for-agent

**Blocked by:** 03

**讀:** `.scratch/docs-diet-2/spec.md`；plan §7、§8 全文；`web/`、`berth/adapters/`；`docs/research/facts-*.md`

## 為什麼

§8 的外部服務行為多半是事實，該和 `docs/research/facts-*.md` 放在一起。

## 做什麼

§7 留下前端的結構、i18n 與設計系統的規則。§8 的外部服務行為併進對應的 `docs/research/facts-*.md`（接著 §20.x 編號），adapter 的契約留在 `ARCHITECTURE.md`。

## 驗收

- [ ] plan §7、§8 只剩標題與一行指向；`ARCHITECTURE.md` 對應的內容不超過 2,500 字
- [ ] Comments 有對照表：這張票負責的每一段 → 新位置或刪掉的理由；整段搬移附 `scripts/docs_moved_lines.py` 的輸出（遺失 0）
- [ ] 全部檢查與 `pytest tests/unit` 綠燈

## Comments
