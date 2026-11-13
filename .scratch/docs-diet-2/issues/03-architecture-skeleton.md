# 03 — 建 ARCHITECTURE.md 的骨架，搬 plan §0、§1

**Status:** ready-for-agent

**Blocked by:** None

**讀:** `.scratch/docs-diet-2/spec.md`；plan §0、§1 全文；`AGENTS.md`〈架構規則〉

## 為什麼

先有骨架，後面幾張票才有地方放。

## 做什麼

建根目錄的 `ARCHITECTURE.md`：檔頭寫明寫法（只寫現況、節用標題不編號、上限 15,000 字），節是〈執行形態〉〈模組地圖〉〈依賴規則〉〈跨模組的資料與契約〉〈主要依賴〉〈測試策略〉〈風險與回寫點〉。把 plan §0〈工程慣例〉、§1〈架構總覽〉歸位；`AGENTS.md`〈架構規則〉和它重複的地方只留一處。

## 驗收

- [ ] `ARCHITECTURE.md` 存在、七個節都有標題；plan §0、§1 只剩標題與一行指向
- [ ] Comments 有對照表：這張票負責的每一段 → 新位置或刪掉的理由；整段搬移附 `scripts/docs_moved_lines.py` 的輸出（遺失 0）
- [ ] 全部檢查與 `pytest tests/unit` 綠燈

## Comments
