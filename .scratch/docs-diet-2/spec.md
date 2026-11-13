# docs-diet-2 — brief 與 plan 瘦身

不是里程碑：規格就是本檔（使用者 2026-11-13 同意）。不改產品行為；只動 `docs/`、`ARCHITECTURE.md`、`AGENTS.md`、`tests/unit/` 裡守文件的測試、`.scratch/docs-diet-2/`，以及 `berth/`、`web/` 裡指向文件的註解與字串。

## 量測（2026-11-13）

| 檔 | 大小 | 最大的節 |
| --- | --- | --- |
| `docs/design-brief.md` | 約 76,000 字（§20 的事實已搬到 `docs/research/facts-*.md`） | §16 部署與跨切面需求 16,700、§15 RSS 10,100、§6 解析與比對 9,200 |
| `docs/plan.md` | 約 214,000 字 | §6 API 面 49,000、§9 開箱即用 45,000、§2 資料模型 24,000、§3 狀態機 24,000、§8 外部整合 23,000 |
| 程式碼引用 `plan §` / `brief §` 的行 | 2,813（`tests/unit/test_doc_ratchets.py` 只減不增） | |

## 目標

brief 不超過 30,000 字、只寫需求與產品決定的現況；`docs/plan.md` 換成根目錄的 `ARCHITECTURE.md`（不超過 15,000 字），只留打開程式碼看不出來的東西。使用者兩份都讀得完。

## 範圍

### 做

- brief 每一段歸位：留下（需求、產品決定與一兩句理由）、搬到 `docs/research/`（查證與量測的細節）、寫成 ADR（需要寫理由的決定）、搬到 `docs/guide/`（部署與操作說明）、刪掉（已由程式與測試說明的行為細節）。
- plan 每一段歸位：留在 `ARCHITECTURE.md`（模組分工、依賴規則、跨模組的資料與契約、測試策略）、搬到 `docs/development.md` 與 `docs/development/`（操作步驟）、寫成 ADR、刪掉（程式與測試已說明的）。
- 程式碼裡的 `plan §x.y`：照各票的對照表，用腳本換成新位置（`architecture〈節名〉`、ADR 編號，或直接刪掉指向、留下理由）。`brief §20.x` 是事實的編號，不動。
- 做完刪掉 `docs/plan.md`；`tests/unit/test_reading_budget.py` 加 brief 30,000、`ARCHITECTURE.md` 15,000 兩條上限；`test_doc_ratchets.py` 的上限調到做完時的數字。

### 不做

- 不改 brief 的決定，不改產品程式與測試的行為。
- `docs/archive/`、已驗收里程碑的票、`docs/research/` 既有的檔是歷史，不改。

## 共同規則

1. **一段都不能憑空消失**：每張票的 Comments 放對照表「舊的每一段（節號加開頭幾個字）→ 新位置，或刪掉的理由」。刪掉的理由只能是「這個行為由 `<測試或程式檔>` 說明」，寫出是哪個檔；code-review 的 Spec 軸照表對 `git show <開工 commit>:<檔>`。
2. **整段搬移用 `scripts/docs_moved_lines.py` 證明遺失 0**，輸出貼進 Comments。
3. **只寫現況**：票號、日期、「某日改」不進 brief 與 `ARCHITECTURE.md`；來龍去脈在 `docs/decisions.md`、ADR 與 `docs/archive/`。
4. **拿不準就留、並列出來**：分不清是契約還是實作細節時留著，在 Comments 列給使用者決定。
5. **矛盾不自己挑**：文件和程式或彼此對不上時，列在 Comments 問使用者。
6. plan 的節搬完後留標題與一行「已搬到 …」，節號不變（程式碼還在引用）；最後一張票才換掉引用、整份刪掉。
7. 一個 session 一張票；每張票收尾跑 `docs/development.md`〈全部檢查〉與 `pytest tests/unit`。

## 驗收

- brief ≤ 30,000 字、`ARCHITECTURE.md` ≤ 15,000 字，兩條上限進了 `test_reading_budget.py`；`docs/plan.md` 已刪。
- 每張票的對照表涵蓋它負責的每一段。
- 除了已驗收的里程碑與 `docs/archive/`，repo 裡沒有指向 `docs/plan.md` 或 `plan §` 的引用；全部檢查、pytest、vitest 綠燈。

### 使用者試

- 使用者把瘦身後的 brief 與 `ARCHITECTURE.md` 各讀一遍，回覆看不懂的段落與覺得不該刪的內容；改完才算驗收。

## 票序

01、02（brief，互不相擋）；03 → 04、05、06、07、08（plan，03 之後互不相擋）；全部做完 → 09。和 M6 的票互不相擋。
