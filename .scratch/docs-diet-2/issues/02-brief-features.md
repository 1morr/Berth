# 02 — brief §10–§19 歸位

**Status:** ready-for-agent

**Blocked by:** None

**讀:** `.scratch/docs-diet-2/spec.md`；brief §10–§19 全文；`docs/guide/`

## 為什麼

後半是 provider、帳號、播放、頁面、AI、RSS、部署、里程碑、延後項、決策紀錄，其中 §15、§16 最長。

## 做什麼

逐段歸位。§16〈部署與跨切面需求〉的操作說明搬到 `docs/guide/`（英文，照那裡現有的寫法）；§17〈里程碑〉換成一行指到 `docs/roadmap.md`；§19〈決策紀錄與待決問題〉裡已定的確認都在 ADR 與 `docs/decisions.md` 後，只留待決的。

## 驗收

- [ ] §10–§19 合計不超過 16,000 字；brief 全檔不超過 30,000 字
- [ ] Comments 有對照表：這張票負責的每一段 → 新位置或刪掉的理由；整段搬移附 `scripts/docs_moved_lines.py` 的輸出（遺失 0）
- [ ] 全部檢查與 `pytest tests/unit` 綠燈

## Comments
