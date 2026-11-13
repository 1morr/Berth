# 06 — plan §6〈API 面〉歸位

**Status:** ready-for-agent

**Blocked by:** 03

**讀:** `.scratch/docs-diet-2/spec.md`；plan §6 全文（約 49,000 字，分小節讀）；`berth/api/`；產生的 OpenAPI

## 為什麼

API 的端點、欄位與錯誤碼已由 OpenAPI 與契約測試說明，這一節是 plan 裡最大的。

## 做什麼

留下：API 的分層與門禁規則、命令登錄表與「要不要人」的規則、錯誤的形狀與封閉集合的慣例。逐端點的說明刪掉，指到 OpenAPI 與 `tests/unit/test_openapi_contract.py`。

## 驗收

- [ ] plan §6 只剩標題與一行指向；`ARCHITECTURE.md` 對應的內容不超過 2,500 字
- [ ] Comments 有對照表：這張票負責的每一段 → 新位置或刪掉的理由；整段搬移附 `scripts/docs_moved_lines.py` 的輸出（遺失 0）
- [ ] 全部檢查與 `pytest tests/unit` 綠燈

## Comments
