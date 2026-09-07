# 02 — 應用骨架：啟動、migration、M0 資料模型、健康端點、前端 shell

**Status:** done

**Blocked by:** 01

**讀:** plan §1.1、§1.2、§2.1、§2.2、§2.3（只取 `events`）、§7、§11.1（T0.2）；brief §16.1、§16.2

## 做什麼

`berth serve` 起一個 FastAPI 程序：lifespan 內自動套用 Alembic migration，在 `/config/berth.db` 建立 M0 需要的表，SQLite 開 WAL；`GET /api/health` 匿名可呼叫回 ok；前端 build 產物由同一個程序提供，瀏覽器開 `http://localhost:8383` 看到深色 shell（`zh-Hant` 唯一語言檔、TanStack Query 與 Router 已接好、一個顯示 health 結果的佔位頁）。開發時 Vite dev server 代理 `/api`。

**與 plan 的偏差**：plan §11.1 T0.2 的驗收是「§2 全部表」。本票只建 M0 用得到的五張表（`users`、`sessions`、`settings`、`routes`、`events`），`jobs` / `plans` / `ledger` / `rss_*` / `issues` 等在需要它們的里程碑用 Alembic 增量加。開工時把這條記進 `docs/progress.md` 的「偏差與決定」。

## 驗收

- [x] 空的 `CONFIG_ROOT` 下啟動後 `berth.db` 建立，`alembic current` 指到最新版本，五張表與索引齊全
- [x] 第二次啟動不重跑已套用的 migration 也不出錯
- [x] `PRAGMA journal_mode` 回 `wal`
- [x] `GET /api/health` 匿名回 200
- [x] `settings` 的 pydantic 分組（`services.jellyfin`、`services.qbittorrent`、`services.indexer`、`services.tmdb`、`paths`、`setup`）可讀可寫，未設定時回預設值
- [x] `CONFIG_ROOT`、`DATA_ROOT`、`PORT` 可用環境變數覆寫，預設 `/config`、`/data`、`8383`
- [x] `pnpm -C web build` 後單跑後端就能在瀏覽器開到前端頁面，UI 文案全部走 i18n key
- [x] README 更新啟動與開發指令，`.env.example` 建立
- [x] lint / type / test / import-linter 綠燈

## Comments

code-review（Standards / Spec 兩軸）跑完，驗收九條全過。以下是當時未處理、留給後續票的發現：

- plan §6 的「前端用 `openapi-typescript` 產型別，CI 檢查型別檔是否過期」還沒做。目前 `web/src/api/` 是手寫型別，`apiGet` 用 `as T` 斷言。API 面在票 05 長出第二、三個端點時一起接，CI 加一個檢查步驟。
- brief §16.2 的「結構化日誌，每行帶 job id」還沒做。目前只有 `logging.getLogger(__name__)`，沒有設定 handler 與格式，警告靠 uvicorn 的預設輸出。有背景迴圈（票 10 起）之後才有意義。
- `settings.services.*` 只有連線資訊，plan §2.1 要求的「最後健康狀態」留給票 10 一起定形狀（見 progress.md 偏差與決定）。
- Spec 軸提的「`degraded` 分支永遠不會產生，前端卻做了文案與紅色樣式」不改：`Health.status` 的型別依 plan §6 就是 `ok | degraded`，前端把宣告出來的值都處理掉是完整性，不是前瞻。票 10 讓後端真的回 `degraded`。
- Spec 軸回報 `test_unknown_api_paths_stay_json_404` 疑似 flaky，實際上是它在讀工作目錄時我正在改 `_is_api`。真正的 bug 是 Windows 上 StaticFiles 交來的路徑用反斜線，已改成用 `PurePath` 比對第一個路徑段，並補了 `/apiary` 的回歸測試。
