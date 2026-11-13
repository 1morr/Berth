# 01 — brief §0–§9 歸位

**Status:** ready-for-agent

**Blocked by:** None

**讀:** `.scratch/docs-diet-2/spec.md`；brief §0–§9 全文

## 為什麼

brief 的前半是產品定位、路徑模型、管線、解析策略、命名、資料模型、刪除與修復，混著實作細節與歷史。

## 做什麼

逐段歸位（spec〈範圍〉的五個去處）。§6〈解析與比對策略〉的規則細節多半已由 `berth/parser/` 與 benchmark 說明，留下「信心分級與自動入庫的門檻」這類產品決定。

## 驗收

- [ ] §0–§9 合計不超過 12,000 字
- [ ] Comments 有對照表：這張票負責的每一段 → 新位置或刪掉的理由；整段搬移附 `scripts/docs_moved_lines.py` 的輸出（遺失 0）
- [ ] 全部檢查與 `pytest tests/unit` 綠燈

## Comments
