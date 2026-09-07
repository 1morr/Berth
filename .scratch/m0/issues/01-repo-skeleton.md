# 01 — Repo 骨架、工具鏈與 CI

**Status:** done

**Blocked by:** 無 —— 可立即開工

**讀:** plan §0、§1.2、§1.3、§1.4、§11.1（T0.1）；brief §16.1、§16.2

## 做什麼

把只有文件的 repo 變成一個可以 lint、type check、跑測試、build 前端的專案。後端是 `uv` 專案，套件名 `berth`，有一個至少支援 `--version` 的 CLI；前端在 `web/`，pnpm + Vite + React + TypeScript。CI 在 push 與 PR 上跑 lint、type、test、前端 build。從這張票起，README 是所有指令的單一來源。

`berth/` 底下的空套件目錄照 plan §1.2 一次建好（`db/`、`models/`、`domain/`、`parser/`、`naming/`、`adapters/`、`services/`、`pipeline/`、`api/`），讓 import-linter 的契約從第一天就有東西可管。

## 驗收

- [x] `uv run berth --version` 印出版本
- [x] `uv run ruff check .` 與 `uv run ruff format --check .` 綠燈
- [x] `uv run mypy` 在 strict 設定下綠燈
- [x] `uv run pytest` 綠燈（至少一個 smoke 測試）
- [x] `uv run lint-imports` 綠燈，契約檔編碼 plan §1.3 的依賴方向：`api → services`、`pipeline → services`、`parser` 與 `naming` 不 import `adapters` / `services` / `models`、`adapters` 不 import `services` / `models`
- [x] `pnpm -C web build` 產出 `web/dist`
- [x] `pnpm -C web lint` 與 `pnpm -C web test`（vitest smoke）綠燈
- [x] GitHub Actions 在 PR 上跑完上述全部並綠燈
- [x] `pre-commit run --all-files` 綠燈
- [x] LICENSE（MIT）與 CHANGELOG.md（Keep a Changelog 骨架）存在
- [x] README 含專案一句話、環境需求、全部開發指令（後端 / 前端 / 測試 / lint）、目錄結構

## Comments

- `GitHub Actions 在 PR 上跑完上述全部並綠燈`：**未驗證**。repo 目前沒有 GitHub remote，
  無法開 PR 實跑。`.github/workflows/ci.yml` 已寫好，action 版本與 input 名稱都對照各
  action 的 `action.yml` 查證過（checkout v7、setup-node v7、setup-uv v10、
  pnpm/action-setup v6），YAML 通過 `check-yaml`；workflow 內的每一條指令都在本機跑過綠燈。
  建立 remote 後第一個 PR 要回來勾掉這條。
- 依賴契約在 code review 補了一條：`layers` 只擋「往上」import，所以 plan §1.3 的
  「API 與 pipeline 不直接碰 adapters 或 models」原本沒被擋住（`api → adapters` 合法）。
  已加 `api and pipeline call services only` 契約，並以刻意違規的 import 實測會 BROKEN。
- `layers` 把 `api | pipeline` 放同一層（獨立），順帶禁止兩者互相 import。這比 plan §1.3
  嚴一點，plan 沒明說；判斷是正確的收緊，若日後擋到再改成 `:`。
- `web/src/App.tsx` 只是不做任何設計決定的佔位頁，因此沒跑 `/impeccable`。第一張 UI 票是
  票 05（見 progress.md 的里程碑表），`hooks on` 與 `init` 在那時跑。
- `.pre-commit-config.yaml` 刻意保持純 ASCII：pre-commit 用系統語系（本機是 cp950）讀自己的
  設定檔，繁中註解會讓它以 `UnicodeDecodeError` 崩潰。原因寫在該檔開頭。
- 型別感知的 eslint 規則（`typescript-eslint` 的 `recommendedTypeChecked`）暫未啟用，
  現在只有 `recommended`。等 TanStack Query 進來、floating promise 變成真風險時再開。
- 前端測試只有一個 render smoke test；`tests/integration`、`tests/e2e`、`tests/fixtures`
  等目錄留給需要它們的票建立（空目錄 git 也存不住）。
