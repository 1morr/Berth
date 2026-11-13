# 08 — plan §9〈開箱即用〉、§10〈測試策略〉歸位

**Status:** ready-for-agent

**Blocked by:** 03

**讀:** `.scratch/docs-diet-2/spec.md`；plan §9、§10 全文（§9 約 45,000 字，分小節讀）；`docs/guide/`；`docs/development.md`

## 為什麼

§9 是設定精靈與預設部署的細節，混著操作說明、事實與逐步流程。

## 做什麼

§9：給使用者的操作說明搬到 `docs/guide/`，外部服務的事實併進 `docs/research/facts-wizard.md`，精靈的步驟與健康檢查的清單由程式與測試說明的刪掉，留下精靈的設計原則與各步驟之間的契約。§10：各層測什麼留在 `ARCHITECTURE.md`，怎麼跑搬到 `docs/development.md`。

## 驗收

- [ ] plan §9、§10 只剩標題與一行指向；`ARCHITECTURE.md` 對應的內容不超過 2,500 字
- [ ] Comments 有對照表：這張票負責的每一段 → 新位置或刪掉的理由；整段搬移附 `scripts/docs_moved_lines.py` 的輸出（遺失 0）
- [ ] 全部檢查與 `pytest tests/unit` 綠燈

## Comments
