# 05 — plan §4〈解析器〉、§5〈命名引擎〉歸位

**Status:** ready-for-agent

**Blocked by:** 03

**讀:** `.scratch/docs-diet-2/spec.md`；plan §4、§5 全文；`berth/parser/`、`berth/naming/`、benchmark 的說明

## 為什麼

解析器的規則細節由程式與 benchmark fixture 說明，plan 這裡約 19,000 字。

## 做什麼

留下：解析的階段與每一階段的輸入輸出、信心分級怎麼對到入庫行為、命名模板的契約（Jellyfin 認得什麼）。規則清單與例子刪掉並指出 fixture 或測試。

## 驗收

- [ ] plan §4、§5 只剩標題與一行指向；`ARCHITECTURE.md` 對應的內容不超過 2,000 字
- [ ] Comments 有對照表：這張票負責的每一段 → 新位置或刪掉的理由；整段搬移附 `scripts/docs_moved_lines.py` 的輸出（遺失 0）
- [ ] 全部檢查與 `pytest tests/unit` 綠燈

## Comments
