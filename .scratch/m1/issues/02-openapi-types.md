# 02 — OpenAPI 型別產生器與 CI 過期檢查

**Status:** done

**Blocked by:** 無 —— 可立即開工

**讀:** plan §6（OpenAPI 段）、§11.2（T1.9 第一條）；`.scratch/m0/issues/10-health.md` 的 Comments
（「同一份形狀寫了四層」）

## 做什麼

前端不再手寫 API 的回應型別。加一個從 FastAPI 的 OpenAPI schema 產 TypeScript 型別的步驟，
把 `web/src/api/` 現有手寫的回應型別全部換成產出的型別；後端改了 response model 而沒有重新產生
型別時 CI 紅燈。

這是 **prefactor**：M1 會長出 discover / media / search / jobs / plans / events 六組端點，先接上
生成器，那批頁面才不會把「同一份形狀寫四層」再乘一次。「make the change easy, then make the
easy change.」

改動範圍橫跨現有的每一個前端 API 模組，但是機械性的，一次做完仍然綠燈。

## 驗收

- [x] 一個指令能產出型別檔（從離線產生的 `openapi.json`，不需要跑起服務），指令寫進 README
- [x] `web/src/api/schemas.ts` 與各 `api/*.ts` 裡手寫的回應型別全數移除，改用產出型別
- [x] `pnpm typecheck`、`pnpm lint`、前端測試全綠，測試沒有為了配合型別來源而放寬
- [x] 產出的型別檔是否進版控有明確決定，理由寫在票上
- [x] CI 有一個 job 在型別檔過期時紅燈；用一次真的後端 response model 改動證明它會紅
- [x] 後端 response model 的欄位名或可選性改變時，前端在編譯期就抓得到（附一個實例）
- [x] `docs/progress.md` 記一行

## Comments

### 決定：型別檔進版控，`openapi.json` 不進

`web/src/api/schema.d.ts` 進版控（並標 `linguist-generated`，PR 上預設收起來）；中間產物
`web/openapi.json` 進 `.gitignore`。理由：

- 型別檔進版控，`pnpm install` 之後沒有 Python 環境也能 `pnpm typecheck` 與跑測試——CI 的
  `web` job 就是這樣，不必為了型別多裝一套 uv。
- `openapi.json` 帶 `info.version`，每次發版都變，進版控只會製造沒有意義的 diff；它每一次都
  由 `berth openapi` 現產，留著沒有價值。

### 指令與 CI

- `uv run berth openapi [--output PATH]`：`create_app().openapi()`，**沒有 lifespan、不碰資料庫**
  （`tests/unit/test_cli.py::TestOpenapi` 有一條就是斷言它不留下 `CONFIG_ROOT`），一律寫 UTF-8
  位元組——描述來自繁體中文 docstring，交給 Windows 主控台的 cp950 會炸。另有一條測試斷言
  同一份程式碼產出的位元組完全相同，因為 CI 的檢查是 `git diff --exit-code`。
- `pnpm -C web gen:api`：上面那支 → `openapi.json` → `openapi-typescript` → `src/api/schema.d.ts`。
- CI 的 `api-types` job 跑同一個指令再 `git diff --exit-code -- src/api/schema.d.ts`。

`--default-non-nullable false`：openapi-typescript 預設把「有預設值」的欄位當成必填，那會讓
`POST /setup/indexers/apply` 這種 body 全欄位變必填，與 OpenAPI 的 `required` 不符。實測這個旗標
只影響七個 `*In`（請求）schema，所有 `*Out`（回應）欄位仍然全部必填。

### 實證：CI 會紅、編譯期抓得到

在 `berth/api/schemas.py` 的 `ServiceHealthOut` 上做一次真的改動（`failures` → `failure_count`、
`detail: str = ""`、`drift: list[str] = []`），已還原：

1. **不重跑產生器**時 `pnpm typecheck` 仍然是綠的——這正是過期檢查存在的理由。
2. 重跑 `pnpm gen:api` 之後 `git diff --exit-code -- src/api/schema.d.ts` 回 **exit=1**
   （`7 insertions(+), 4 deletions(-)`，`failures: number` → `failure_count: number`、
   `detail: string` → `detail?: string`）。CI 的 job 就是這一步。
3. 重產之後 `pnpm typecheck` 紅：
   - 欄位改名 → `ServiceCard.tsx(56,16)` 與 `(58,50)` `TS2339: Property 'failures' does not exist`，
     以及 `fixtures.ts(263,5)` `TS2353`。
   - 可選性改變 → `ServiceCard.tsx(76,44)`、`(78,59)`、`signals.ts(27,10)`
     `TS18048: 'row.drift' is possibly 'undefined'`。

**換過來的第一天就抓到一個真的漂移**：`ServiceDetection` 少了後端早就在回的 `configured`
（`berth/services/setup.py:80`）。手寫型別看不出來，換成產出型別之後 `tsc` 直接指著
`src/test/fixtures.ts` 說少一個必填欄位。

### 順手做掉的

- 三個元件的 prop 型別本來是手寫的 API 形狀（`AdminStep`、`JellyfinExisting` / `JellyfinStep`、
  `SourceStep`），改用 `AdminInput` / `JellyfinConnectInput` / `IndexerConnectInput`。
- `api/setup.ts` 裡七個手寫的 request body literal 加上 `satisfies Schemas['...']`——
  `apiPost` 的 `body` 是 `unknown`，不加的話後端改請求欄位名前端不會紅（已實測會紅：
  `TS2561 Object literal may only specify known properties`）。
- 刪掉沒有人用的 `PROFILES` 與 `OverallStatus`。
- `./schema`（產出）只由 `api/schemas.ts` 這一個門 import，其餘模組取它 export 的 `Schemas`。

### 未處理

- `Credentials`（`LoginIn`）的 `username` / `password` 是**選填**，因為後端刻意給它們 `""` 預設值
  （`api/auth.py` 的 docstring：不設必填，422 與 401 才不會變成可以試探的差別）。產出型別忠實
  反映了它，登入表單本來就兩個都填，先不動。
- CI 的 `api-types` job 與 `backend` / `web` job 重複做 checkout 與安裝。合併進 `web` job（補
  setup-uv）可以省一輪安裝；維持獨立是為了「忘了重跑產生器」有自己的紅燈訊號，而不是混在
  前端測試的失敗裡。M1 的 CI 時間如果變成問題再合併。
