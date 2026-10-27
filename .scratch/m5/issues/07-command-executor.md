# 07 — 命令執行器

**Status:** done

**Blocked by:** 06

**讀:** plan §11.6〈分段〉第 2 段、§6（API 面與門禁）；brief §11（帳號與權限）、§19「M5 的方向」⑦；`docs/research/m5-ai-direction-2026-10-27.md` A3 的 R9、R12、R14；`berth/api/gate.py`；用到 `nudge()`、`hub.publish`、`current_actor()` 的 API 模組

## 為什麼

命令的語意散在 API 層：喚醒背景迴圈、推播事件、誰在做、角色判斷、把例外轉成 HTTP。AI 直接呼叫 service 會漏掉這些，M7 的 Discord 與 MCP 也一樣。執行器是三個介面共用的那一條路。

## 做什麼

1. `execute(name, args, actor)`：查登錄表、驗輸入、檢查角色、執行、做事後動作（喚醒、推播），把拒絕轉成結構化理由。
2. **actor** 有人、`system`、`rss:<id>`、`ai`。`ai` 動作要記下是替誰做的（R14：統一寫法；沒有 `job_hash` 的帳本列確認與撤銷也要記事件）。
3. **角色**：
   - 每個命令帶一個 `audience`（`admin` / `user`），預設 `admin`。
   - 一般使用者能用的是讀取類，以及處理自己送單的那幾支（brief §19「M5 的方向」⑦）；「自己的」由命令檢查 `user_id`，與 API 現在的行為一致。
   - API 的門禁與登錄表的 `audience` 要對得上，用測試守。
4. 會登錄成 AI 工具、或能被 Proposal 執行的命令，**它們的 API 路由改走執行器**，舊的呼叫路徑刪掉。其餘的路由等用到再搬。
5. 拒絕理由沿用各模組現有的 enum，經執行器變成同一個形狀。API 的 OpenAPI 形狀不變（`pnpm gen:api` 沒有差異）。

## 驗收

- [x] 經執行器的命令會喚醒、推播、記 actor（測試）
- [x] 一般使用者經執行器碰不到 admin 命令、碰不到別人的送單（測試）
- [x] API 門禁與 `audience` 一致（測試）
- [x] 搬過去的路由行為不變（既有測試綠）；`pnpm gen:api` 沒有差異
- [x] plan §6 補執行器；全部檢查與 pytest 綠；progress.md 已更新

## Comments

- 2026-10-27（票 07 做完）：`services/executor.py`（`Executor.execute(session, name, args, actor)`、`CommandRefusedError`、執行器自己的 `CommandRefusal`）、`domain/actor.py`（`Actor`、`SYSTEM`、`label_of`、`rss_label`、`owner_of`）、`@command(audience=)`、`api/commands.Command` 相依。
  - **使用者選定**：搬的路由是票 10/13/14 的 9 支加重試、重算（共 11 支，`test_executor_routes.ROUTED`）；AI 的 actor 寫 `ai:<user id>`。
  - **重試、重算只動得了自己送的**（`jobs.own_job`）：別人的與不存在的同一個 `job_missing`（不新增理由，`gen:api` 才沒有差異），`retryable`／`replannable` 也照按的人算；RSS 送的（沒有人）只有管理員按得到。
  - 執行器的喚醒照「動到的 Job 停在誰的狀態」，不逐命令宣告：`completed`／`planning` 叫規劃器、`importing` 叫 importer；只讀的命令不推播、不喚醒。`POST /jobs` 因此多推一則 SSE（含 `created=False` 的那一種，無害）。
  - `CommandRefusal` 不放 `domain/enums.py`：那裡的 `*Refusal` 由 `test_openapi_contract` 要求出現在 API，而這兩種到不了 HTTP。路由的 `_refuse`／`rss_refusal`／`why_not_refusal` 收到別的 enum 會 `ValueError` → 500，前提是門禁與 `audience` 一致（測試守）。
  - R14：`actor_of` 與各模組的 `SYSTEM`、claims 的 `_user_id`、重試寫死的 `"user"` 收斂到 `domain/actor.py`；`add_download` 的 `actor` 必填；沒有 Job 的帳本列確認／撤銷寫 `record_work_event`（掛在作品上）。
  - code-review 修掉的：`subscribe_mikan` 的 `bound_by` 記成人而不是 `ai:<id>`（Spec 軸，`_bind` 改收 `bound_by`）；只讀命令也推播（Standards 軸）；`add_download` 的選填 actor、`weekly` 的多餘別名、沒人用的 `Actor.rss`、`Any` 的註解。
  - 沒處理的：
    - **沒走執行器的路由，`audience` 沒有東西守**（Spec 軸）：門禁是 SIGNED_IN 的讀取命令（discover、inventory、watching、watch_area、`notify.read_mine` 等）仍是預設 `admin`，方向是擋多。票 11 開讀取工具、搬路由時一起標。
    - `plan.replan_job` 不記按的人：它本來就沒有「按了重算」的事件，`_plan` 寫的都是 `system`。要的話加一筆事件，留給 AI 活動頁（票 21）決定。
    - `subscribe_search` 建的搜尋 feed 之後長出的 Series，由 `_prebind` 以 `label_of(feed.user_id)` 綁，AI 建的也記成人：要記成 `ai:` 得在 Feed 上存 actor。
    - 執行器每次呼叫重算簽名與型別（`_injected`），登錄表已算過一次，可以存進 `CommandSpec`；registry 認得的注入名字（`now`、`sleep`、`timeout`、`published_port`）與型別（`JellyfinAccess`、`BundledServices`、`HostResolver`）執行器給不出，沒預設值的命令執行時丟 `RuntimeError`（`watching.read_watching` 那一條測試），沒有閘門掃全部命令。
    - 三支路由的拒絕轉換（`Enum(refusal.reason)` → body → `_STATUS`）形狀相同，沒抽出共用的一支。
