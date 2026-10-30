# 06 — docs/development.md 拆分

**Status:** done

**Blocked by:** 01

**讀:** `.scratch/docs-diet/spec.md`；`docs/development.md` 的章節表（`grep -n '^#'`，注意 code block 裡的 `#` 不是標題）；`tests/unit/test_readme_docs.py`；`scripts/experiments/README.md`

## 為什麼

`docs/development.md` 85 KB，〈開發指令〉一節 768 行。每張票都要讀〈全部檢查〉，卻得從整份裡找；〈UI 的 Fake 後端〉（127 行 28 KB）、〈實驗腳本〉（289 行 18 KB）、兩節 e2e（119 行 15 KB）只有特定票才用得到。

## 做什麼

1. **主檔留**：〈環境需求〉〈安裝〉〈啟動〉〈環境變數〉〈全部檢查〉〈目錄結構〉〈疑難排解〉，加一節〈索引〉列出子檔與各自什麼時候讀。標題文字不改。
2. **分到 `docs/development/`**（原文搬，不改字；分法可以調，調了在 Comments 說理由）：
   - `commands.md`：〈後端〉〈帳本重建〉〈解析基準測試〉〈前端〉〈API 型別〉
   - `release.md`：〈發版〉
   - `e2e.md`：〈e2e〉〈前端 e2e〉
   - `fake-backend.md`：〈UI 的 Fake 後端〉
   - `experiments.md`：〈實驗腳本〉
3. **引用不能斷**（開工時重新 `grep -rn 'development\.md' --exclude-dir=node_modules --exclude-dir=.git .`；`berth/`、`web/` 目前沒有）：
   - 〈全部檢查〉留在主檔，`CLAUDE.md` 那兩處不用改。
   - 改指子檔：`tests/unit/test_e2e_stack.py`、`tests/e2e/stack.py`、`tests/e2e/compose.yml`（〈e2e〉）；`tests/integration/test_rss.py`、`scripts/fake_setup_server.py`（〈UI 的 Fake 後端〉）；`scripts/experiments/README.md`（兩處，含錨點 `#實驗腳本`）、`scripts/experiments/discord_dm.py`、`scripts/experiments/jellyfin_naming.py`。
   - 不改：`docs/research/`、`.scratch/` 舊票。
4. `tests/unit/test_readme_docs.py` 的連結檢查清單加上 `docs/development/*.md`；子檔之間與子檔到 repo 的相對連結要跟著目錄深度改。
5. `CLAUDE.md`〈指令〉「開發指令的單一來源是 `docs/development.md`」改成含 `docs/development/`。

## 驗收

- [x] `scripts/docs_moved_lines.py` 對 `docs/development.md` → `docs/development/*.md` 跑出「遺失 0」，輸出貼 Comments
- [x] 主檔只剩第 1 步那幾節加索引；行數前後貼 Comments
- [x] 第 3 步列的引用都改了，`test_readme_docs.py` 連結檢查涵蓋子檔且綠
- [x] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments

- 主檔 834 → 152 行；子檔：commands 135、release 31、e2e 122、fake-backend 130、experiments 292。分法照票，沒調。
- `scripts/docs_moved_lines.py HEAD docs/development.md -- docs/development/*.md docs/development.md`：舊版工具 `missing 13`（13 行是依步驟 4 改過目錄深度的連結）。已讓 `scripts/docs_moved_lines.py` 比對前去掉連結目標的 `./` `../` 前綴（`tests/unit/test_docs_moved_lines.py` 補兩個測試：只差深度→找到；文字或目標名變了→仍遺失）。在搬移 commit `55bfe60a` 上重跑：`removed 564 lines, found 564, missing 0`。之後的 `cf50d38f` 為審查改寫主檔兩行（導言、目錄結構），那兩行是刻意改字，對最新工作樹跑會多報這 2 行。
- 子檔各加一個 `# 標題` 與一行導言（新增行）；原本的 `###` 標題不動，所以子檔裡章節是 `###`。
- 另改了票沒列的引用：`tests/e2e/conftest.py`、`.env.example`、`.github/workflows/e2e.yml`、`.github/workflows/ci.yml`（〈API 型別〉→ commands.md）、`pyproject.toml`、`docs/design-brief.md:1686`、`docs/plan.md:16`。`CHANGELOG.md` 的歷史條目不改。
- 全部檢查（`uv run pre-commit run --all-files`）全綠；`uv run pytest`：5276 passed, 1 skipped, 28 deselected。
- code-review（`991ee2d4`）：已修〈development.md〉導言與〈目錄結構〉補 `docs/development/`，`scripts/experiments/README.md` 的「單一來源」措辭。未處理：`commands.md:24`、`commands.md:99`、`e2e.md:79` 的〈章節〉引用現在指到別的子檔且沒連結（票要求原文搬，不改字）；子檔 `#` 直接接 `###` 跳級（刻意，保留原標題）；驗收「遺失 0」照字面是 13，原因見上。
