# 01 — Repo 骨架、工具鏈與 CI

**Status:** ready-for-agent

**Blocked by:** 無 —— 可立即開工

**讀:** plan §0、§1.2、§1.3、§1.4、§11.1（T0.1）；brief §16.1、§16.2

## 做什麼

把只有文件的 repo 變成一個可以 lint、type check、跑測試、build 前端的專案。後端是 `uv` 專案，套件名 `berth`，有一個至少支援 `--version` 的 CLI；前端在 `web/`，pnpm + Vite + React + TypeScript。CI 在 push 與 PR 上跑 lint、type、test、前端 build。從這張票起，README 是所有指令的單一來源。

`berth/` 底下的空套件目錄照 plan §1.2 一次建好（`db/`、`models/`、`domain/`、`parser/`、`naming/`、`adapters/`、`services/`、`pipeline/`、`api/`），讓 import-linter 的契約從第一天就有東西可管。

## 驗收

- [ ] `uv run berth --version` 印出版本
- [ ] `uv run ruff check .` 與 `uv run ruff format --check .` 綠燈
- [ ] `uv run mypy` 在 strict 設定下綠燈
- [ ] `uv run pytest` 綠燈（至少一個 smoke 測試）
- [ ] `uv run lint-imports` 綠燈，契約檔編碼 plan §1.3 的依賴方向：`api → services`、`pipeline → services`、`parser` 與 `naming` 不 import `adapters` / `services` / `models`、`adapters` 不 import `services` / `models`
- [ ] `pnpm -C web build` 產出 `web/dist`
- [ ] `pnpm -C web lint` 與 `pnpm -C web test`（vitest smoke）綠燈
- [ ] GitHub Actions 在 PR 上跑完上述全部並綠燈
- [ ] `pre-commit run --all-files` 綠燈
- [ ] LICENSE（MIT）與 CHANGELOG.md（Keep a Changelog 骨架）存在
- [ ] README 含專案一句話、環境需求、全部開發指令（後端 / 前端 / 測試 / lint）、目錄結構

## Comments
