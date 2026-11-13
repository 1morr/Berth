# 09 — 換掉引用、刪掉 plan、加上限

**Status:** ready-for-agent

**Blocked by:** 01, 02, 03, 04, 05, 06, 07, 08

**讀:** `.scratch/docs-diet-2/spec.md`；plan 剩下的全部；各票 Comments 的對照表；`tests/unit/test_doc_ratchets.py`、`test_reading_budget.py`；`AGENTS.md`

## 為什麼

plan 的內容都歸位之後，程式碼裡兩千多處 `plan §x.y` 才能換掉。

## 做什麼

1. plan §12〈風險與回寫點〉歸位，確認每一節只剩標題與指向。
2. 把各票的對照表併成一份「舊節號 → 新位置」，寫腳本換掉 `berth/`、`web/`、`tests/`、`deploy/` 裡的 `plan §x.y`；`brief §` 的引用除了 §20.x 也照 01、02 的對照表換。腳本留在 `scripts/`，輸出貼 Comments。
3. 刪掉 `docs/plan.md`；改 `AGENTS.md`、`docs/agents/`、roadmap 的「拆票前讀」、M6 還沒做的票與 spec 裡指向 plan 的地方。
4. `test_reading_budget.py` 加 brief 30,000、`ARCHITECTURE.md` 15,000；`test_doc_ratchets.py` 的三個上限調到現在的數字。
5. 把 spec〈使用者試〉的清單給使用者，`docs/progress.md` 的下一步寫 `等使用者：讀 brief 與 ARCHITECTURE.md`。

## 驗收

- [ ] `docs/plan.md` 已刪；brief ≤ 30,000 字、`ARCHITECTURE.md` ≤ 15,000 字，由 `test_reading_budget.py` 守
- [ ] 除了已驗收的里程碑與 `docs/archive/`，`grep -rn "plan §\|docs/plan.md"` 沒有結果
- [ ] 使用者讀過兩份文件並回覆可以（回覆記在 Comments）
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠燈
- [ ] Comments 有對照表：這張票負責的每一段 → 新位置或刪掉的理由；整段搬移附 `scripts/docs_moved_lines.py` 的輸出（遺失 0）
- [ ] 全部檢查與 `pytest tests/unit` 綠燈

## Comments
