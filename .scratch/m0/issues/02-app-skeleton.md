# 02 — 應用骨架：啟動、migration、M0 資料模型、健康端點、前端 shell

**Status:** ready-for-agent

**Blocked by:** 01

**讀:** plan §1.1、§1.2、§2.1、§2.2、§2.3（只取 `events`）、§7、§11.1（T0.2）；brief §16.1、§16.2

## 做什麼

`berth serve` 起一個 FastAPI 程序：lifespan 內自動套用 Alembic migration，在 `/config/berth.db` 建立 M0 需要的表，SQLite 開 WAL；`GET /api/health` 匿名可呼叫回 ok；前端 build 產物由同一個程序提供，瀏覽器開 `http://localhost:8383` 看到深色 shell（`zh-Hant` 唯一語言檔、TanStack Query 與 Router 已接好、一個顯示 health 結果的佔位頁）。開發時 Vite dev server 代理 `/api`。

**與 plan 的偏差**：plan §11.1 T0.2 的驗收是「§2 全部表」。本票只建 M0 用得到的五張表（`users`、`sessions`、`settings`、`routes`、`events`），`jobs` / `plans` / `ledger` / `rss_*` / `issues` 等在需要它們的里程碑用 Alembic 增量加。開工時把這條記進 `docs/progress.md` 的「偏差與決定」。

## 驗收

- [ ] 空的 `CONFIG_ROOT` 下啟動後 `berth.db` 建立，`alembic current` 指到最新版本，五張表與索引齊全
- [ ] 第二次啟動不重跑已套用的 migration 也不出錯
- [ ] `PRAGMA journal_mode` 回 `wal`
- [ ] `GET /api/health` 匿名回 200
- [ ] `settings` 的 pydantic 分組（`services.jellyfin`、`services.qbittorrent`、`services.indexer`、`services.tmdb`、`paths`、`setup`）可讀可寫，未設定時回預設值
- [ ] `CONFIG_ROOT`、`DATA_ROOT`、`PORT` 可用環境變數覆寫，預設 `/config`、`/data`、`8383`
- [ ] `pnpm -C web build` 後單跑後端就能在瀏覽器開到前端頁面，UI 文案全部走 i18n key
- [ ] README 更新啟動與開發指令，`.env.example` 建立
- [ ] lint / type / test / import-linter 綠燈

## Comments
