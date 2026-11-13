# 04 — plan §2〈資料模型〉、§3〈狀態機與背景迴圈〉歸位

**Status:** ready-for-agent

**Blocked by:** 03

**讀:** `.scratch/docs-diet-2/spec.md`；plan §2、§3 全文；`berth/models/`、`berth/pipeline/`

## 為什麼

兩節各約 24,000 字，大部分是逐欄位、逐狀態的描述，和 `berth/models/` 與狀態機的程式重複。

## 做什麼

留下：表與表之間的關係與不變量、狀態機的狀態圖與誰能改狀態、背景迴圈之間的分工。逐欄位、逐轉移的說明，找到說明它的 model、migration 或測試後刪掉。

## 驗收

- [ ] plan §2、§3 只剩標題與一行指向；`ARCHITECTURE.md` 對應的內容不超過 3,500 字
- [ ] Comments 有對照表：這張票負責的每一段 → 新位置或刪掉的理由；整段搬移附 `scripts/docs_moved_lines.py` 的輸出（遺失 0）
- [ ] 全部檢查與 `pytest tests/unit` 綠燈

## Comments
