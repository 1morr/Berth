# 12 — M6 驗收

**Status:** ready-for-agent

**Blocked by:** 01–11

**讀:** spec〈驗收〉〈共同規則〉；各票的 Comments；`docs/progress.md`〈寫法與封存〉；`docs/development.md`〈全部檢查〉〈e2e〉〈前端 e2e〉

## 為什麼

spec〈驗收〉逐條對到證據、做里程碑的 code-review、處理各票留下的 Comments，然後封存，交棒給 M6.5。

## 做什麼

1. spec〈驗收〉逐條對到一條測試或一次實跑，對照表記在 Comments，缺的補上。
2. `berth bench`：`auto_wrong` 不升、review 比例下降（AI 開著的路徑另外說明怎麼算），貼數字。
3. 關掉 AI 時與 M4 相同：沒設 provider 跑一次前端 e2e；`pytest -m e2e` 綠。
4. 里程碑 code-review（`mattpocock-skills:code-review`，對象是 M6 開工的 commit）。
5. 各票 Comments 裡沒處理的發現逐條歸到修掉、延後（寫進 `docs/roadmap.md` 的〈M6.5 Issue 與巡檢交給 AI〉或〈不排里程碑〉）或不做。
6. spec〈共同規則〉「同輪要改的文件」逐項確認；整理 CHANGELOG。要不要發版、push 先問使用者。
7. **使用者試**：把啟動方式與 spec〈驗收〉`### 使用者試` 的清單給使用者，progress.md 的「下一步」寫 `等使用者：試用 M6`，結束 session。使用者回覆後在新 session 接著做：不滿意的各開一張修復票（排在本票之前），修完再試；使用者說可以才往下。
8. **封存這個里程碑**（progress.md〈寫法與封存〉）：session 紀錄搬到 `docs/archive/m6.md`，用 `scripts/docs_moved_lines.py` 證明遺失 0；`docs/roadmap.md` 里程碑表的狀態改成「已驗收（日期）」；session 紀錄加一列 `M6.5 準備`，「下一步」寫 `/1morr:checkpoint M6`。

## 驗收

- [ ] spec〈驗收〉每一條都有對應的測試或實跑紀錄（列在 Comments）
- [ ] bench 數字貼在 Comments：`auto_wrong` 不升、review 比例下降
- [ ] 關掉 AI 的前端 e2e 綠；`pytest -m e2e` 綠
- [ ] 里程碑 code-review 做完，各票 Comments 逐條有歸處
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；CHANGELOG 已更新
- [ ] 使用者試過 spec〈驗收〉`### 使用者試` 的每一項並說可以（回覆記在 Comments）
- [ ] 已封存到 `docs/archive/m6.md`（遺失 0），progress.md 最後一列的下一步是 M6.5 的開工指令

## Comments
