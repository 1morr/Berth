# Berth

自託管媒體取得與入庫協調器：索引站 / RSS → qBittorrent → 解析 → 硬鏈接入 Jellyfin。文件是唯一的記憶，對話不是。

## 文件

- `docs/design-brief.md`：需求、決定、查證過的事實（§20，附來源）。決定衝突時以它為準。
- `docs/plan.md`：架構、資料模型、狀態機、解析器、API。§11 是路線圖：沒開工的里程碑各一小節，開工後縮成一行連到 spec。
- `docs/progress.md`：進行中里程碑的閱讀指引、session 紀錄、偏差與決定。每個 session 的起點與終點。已驗收的里程碑封存在 `docs/archive/<里程碑>.md`。
- `.scratch/<里程碑>/spec.md`：進行中里程碑的規格，開工 session 寫（M6 起；`tests/unit/test_scratch_specs.py` 守）。
- `.scratch/<里程碑>/issues/`：票，執行單位；狀態在票的 `Status:` 行。
- `CONTEXT.md`：名詞表，唯一來源；命名一律用它的詞。
- `PRODUCT.md`、`DESIGN.md`：impeccable 維護的產品與設計脈絡（第一個 UI 票起）。

## 每個 session 的流程

工作單位是**票**：`.scratch/<里程碑>/issues/NN-slug.md`，由使用者在新 session 下 `/to-tickets docs/plan.md 拆 <里程碑> 的票` 產生（里程碑開工，見〈Skills〉）。一個 session 只做一張票。

1. 讀 `docs/progress.md`（只含進行中的里程碑，讀得完；M0–M5 在 `docs/archive/`，按需查），再讀該里程碑的 `spec.md` 與票；只讀票列出的 plan / brief 章節，其他按需讀。
2. `/implement <票路徑>`：tdd、定期 typecheck、結尾 `/code-review <開工時的 commit>`、commit。
3. 驗證：`docs/development.md`〈全部檢查〉（`pre-commit run --all-files`：lint、type 與檔案衛生）加 test；貼指令輸出。
4. 實作若推翻 plan 或 brief，同一 commit 改文件，並在 progress.md「偏差與決定」記一條（≤ 200 字，帶里程碑標記）；票內的取捨記在票的 `## Comments`。
5. 票的 `Status:` 改為 `done`、勾掉驗收條件、code-review 未處理的發現記到票的 `## Comments`；progress.md 加一列 session 紀錄（≤ 200 字，帶里程碑標記；每列每條的字數與標記由 `tests/unit/test_progress_rules.py` 守）；驗收票多一步「封存這個里程碑」（做法在 progress.md〈寫法與封存〉，用 `scripts/docs_moved_lines.py` 證明沒丟；封存後 session 紀錄加一列 `<下一個里程碑> 準備`，「下一步」寫它的開工指令，沒有下一個里程碑就留空、只在對話告訴使用者）；commit。

完成標準：票上每個驗收條件打勾、全部檢查與 test 綠燈、progress.md 已更新、已 commit。缺一就還沒完成。

**所有 session 的結尾**（做票、訪談、寫 plan、里程碑開工都算）：告訴使用者下一步要在新 session 下的完整指令，並把同一句寫進 progress.md 那一列的「下一步」（`tests/unit/test_progress_rules.py` 守最後一列）。下一張票是 `/implement <票路徑>`，里程碑做完是 `/to-tickets docs/plan.md 拆 <下一個里程碑> 的票`；要使用者先決定才能繼續時，寫 `等使用者：<要決定什麼>`。

## 事實與查證

- 外部服務的端點、參數、版本行為只信兩處：brief §20，以及 context7 / OpenAPI 現查。brief 沒寫的先查再用，查到的補進 brief §20 並附來源。
- 程式庫 API 用 context7 查，或寫最小測試驗證。
- 現況以指令為準：`git log`、`git status`、測試輸出。progress.md 與 repo 不符時以 repo 為準並修 progress.md。

## 上下文紀律

- 讀大檔案、查文件、跑實驗交給子代理回摘要（模型規則見全域 CLAUDE.md）。
- brief 與 plan 各 500+ 行，只讀任務指到的章節。
- 對話已長或一個任務碰了十幾個檔案：把進度與下一步寫進 progress.md，結束 session。

## 架構規則（細節在 plan §1）

- 依賴方向 `api → services → domain / parser / naming / adapters / models`；`pipeline → services`；`parser` 與 `naming` 是純函式；`adapters` 不 import `services`。import-linter 強制。
- 改狀態的操作都是 `services` 內的命令函式；API 與 pipeline 只呼叫 services。`services` 裡每一支公開的 `async def`（含 `@asynccontextmanager` 包過的）都要標 `@command(Effect..., inverse=..., flags={Flag...})`（brief §14，M5 的命令登錄表讀它；旗標、inverse 的三種寫法與「要不要人」的唯一規則 `needs_person` 在 `services/commands.py`；`tests/unit/test_command_marks.py` 守有沒有標、inverse 指不指得到，以及判斷過的那幾支命令的標記；沒有豁免）。非 `internal` 的命令進命令登錄表（`services/registry.py`），簽名要推得出 pydantic 輸入：收 ORM 列或函式的改成注入或標 `internal`（`tests/unit/test_command_registry.py` 守）。
- 解析器改動必跑 `berth bench`，`auto_wrong` 不得上升。
- 檔名 token、log、識別符英文；UI 文案一律走 i18n key，zh-Hant 與 en 並列（plan §7、`PRODUCT.md`）。

## UI

- 所有前端頁面走 `/impeccable`：第一次做 UI 前 `init`；新頁面先 `shape` 再實作；設定精靈用 `onboard`；每個里程碑 UI 收尾前 `critique`、`audit`、`polish`；設計系統定稿後 `document`。
- 第一個 UI 任務開頭執行 `/impeccable hooks on`。
- UI 改動用 playwright 實跑驗證，附截圖或文字結果。

## Skills

- 里程碑開工：入口是使用者在新 session 下 `/to-tickets docs/plan.md 拆 <里程碑> 的票`。這個 session 依序做完三步，第 3 步 commit 後才算完成：
  1. 把 plan §11 裡它的那一節，依最新的 brief、plan 與上一個里程碑的結果細化成 `.scratch/<里程碑>/spec.md`，段落為〈目標〉〈範圍〉〈共同規則〉〈驗收〉〈票序〉。plan 那一節的內容搬進 spec，標題與章節編號留著，內文縮成一行連結（程式碼引用 §11.x，編號不能變）。文件不足以寫出 spec 時，問使用者並補進文件。
  2. 照 skill 提出切法，使用者同意後寫票，每張票寫明「讀：plan §x、brief §y」與驗收條件。
  3. 票序寫回 spec〈票序〉，progress.md 加一列 session 紀錄，commit。
- 之後的里程碑留在 plan，開工時才有 spec。
- `parser`、`naming`、`domain`、`services` 的新功能與修 bug：`mattpocock-skills:tdd`（紅 → 綠 → 重構，benchmark fixture 就是紅燈）。
- 設計 adapter 介面、解析器階段、services 命令的邊界：`mattpocock-skills:codebase-design`。
- 用實驗回答設計問題（T0.3 的 Jellyfin 命名實測這類）：`mattpocock-skills:prototype`，結論寫回 brief。**實驗腳本留在 `scripts/experiments/`**（plan §10：一次性但保留腳本，下一次換版本要重量），UI 原型不留。
- 查證外部事實：`mattpocock-skills:research`，輸出放 `docs/research/`，結論摘進 brief §20 並連結。
- 每張票收尾與里程碑收尾：`mattpocock-skills:code-review`（Spec 軸讀票，Standards 軸讀本檔）；難 bug 或效能退化：`mattpocock-skills:diagnosing-bugs`。
- 改本檔或 progress.md 的流程段：`mattpocock-skills:writing-for-agents`。

## 指令

開發指令的單一來源是 `docs/development.md` 與 `docs/development/`（子檔，索引在主檔）。README 只給使用者：英文為主，`README.zh-Hant.md` 是同內容的繁中版，改一份就同輪改另一份（兩份的標題層級與連結要一致，`tests/unit/test_readme_docs.py` 守）；部署與操作的細節在 `docs/guide/`（英文）。

## Agent skills

### Issue tracker

Local markdown：票與 spec 以檔案存在 `.scratch/<feature-slug>/`。See `docs/agents/issue-tracker.md`.

### Triage labels

五個預設角色標籤，字串與角色名相同。See `docs/agents/triage-labels.md`.

### Domain docs

Single-context：根目錄 `CONTEXT.md` + `docs/adr/`。See `docs/agents/domain.md`.
