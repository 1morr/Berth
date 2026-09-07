# Changelog

本專案所有重要的變更都記在這個檔案。

格式依循 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，版本號依循 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

## [Unreleased]

### Added

- Repo 骨架：uv 後端專案與 `berth` CLI（`--version`）、pnpm + Vite + React + TypeScript 前端。
- 工具鏈：ruff、mypy（strict）、pytest、import-linter、eslint、prettier、vitest。
- `import-linter` 契約，編碼 plan §1.3 的依賴方向。
- pre-commit 設定與 GitHub Actions CI（後端 lint / type / test、前端 lint / test / build、檔案衛生）。
- LICENSE（MIT）與 README（指令的單一來源）。
- `berth serve`：FastAPI 程序，啟動時自動套用 Alembic migration 並以 WAL 開啟 `<CONFIG_ROOT>/berth.db`。
- M0 資料表：`users`、`sessions`、`settings`、`routes`、`events`（plan §2）。
- `settings` 的分組模型：`services.jellyfin`、`services.qbittorrent`、`services.indexer`、
  `services.tmdb`、`paths`、`setup`，未設定時回預設值。
- `GET /api/health`：匿名可呼叫，回總體狀態與版本。
- 前端 shell：深色為預設、亮色跟隨系統的 Tailwind 主題，`zh-Hant` 語言檔，
  TanStack Router 與 Query，以及顯示健康狀態的佔位頁；build 產物由後端同一個程序提供。
- 環境變數 `CONFIG_ROOT`、`DATA_ROOT`、`WEB_ROOT`、`PORT` 與 `.env.example`。
