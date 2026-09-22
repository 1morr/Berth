# 02 — 拒絕理由改由 OpenAPI 產

**Status:** done

**Blocked by:** 無 —— 可立即開工

**讀:** plan §6（門禁那三段、底下 OpenAPI 那兩條）、§7（資料那一段）、§11.2 的 T1.9；§11.3（票 01 那一列的後半）

## 做什麼

前端有**三組手抄的拒絕理由**與一組手抄的事件形狀，後端改了封閉集合它們不會紅：

- `web/src/api/jobs.ts` 的 `JobRefusal`
- `web/src/api/jellyfin.ts` 的 `AccessRefusal`
- `web/src/api/routes.ts` 的 `RouteRefusal`
- `web/src/api/events.ts` 的 `JobSignal`

M1 票 02 已經立了閘門（`pnpm gen:api` + CI 的 `git diff --exit-code -- src/api/schema.d.ts`），
但這四組沒走它——後端的拒絕理由不是 pydantic model，FastAPI 產的 OpenAPI 裡沒有它們，
`openapi-typescript` 自然產不出來。這一票把它們變成 model 並讓前端改用產出的型別。

M2 每一張票都會新增拒絕理由（`reconcile_running`、刪除旗標的拒絕、review 的拒絕…），先做這件
是因為之後每一張票都會再抄一次。

順手：`web/vite.config.ts` 設 `testTimeout` / `asyncUtilTimeout`——本機全量跑會固定有兩條
`findBy*` 逾時，那是預設值太緊而不是測試的問題。

## 驗收

- [x] 四組型別都從 `src/api/schema.d.ts` 來，`web/src/` 底下沒有手寫的拒絕理由字面量聯集
      （以 grep 佐證）
- [x] 後端改一個拒絕理由而不重跑 `pnpm gen:api` 時 CI 會紅（在票裡示範這一次變異：改一個、
      看 `git diff --exit-code` 紅、再跑產生器變綠）
- [x] 改一次無關的格式或命名不會讓那道檢查紅（雙向變異的第二項）
- [x] `vite.config.ts` 的兩個 timeout 有值，本機全量跑不再有 `findBy*` 逾時（貼輸出）
- [x] lint、type、test 綠燈（前後端都貼）

## 做了什麼

**後端**

- `berth/domain/enums.py` 加三個 `StrEnum`：`JobRefusal`（9）、`RouteRefusal`（9）、
  `AccessRefusal`（5）。`services` 的 `JobRejectedError` / `RouteRejectedError` 的 `reason`
  參數收緊成它們，所以 mypy strict 擋得住裸字串。
- 每一支 router 各有一個 `{reason, detail}` 的 model（`JobRefusalOut`、`RouteRefusalOut`、
  `AccessRefusalOut`）並以 `responses=` 宣告，enum 因此進得了 OpenAPI。新的
  `api/errors.refusal_responses()` 從「理由 → 狀態碼」那張表導出文件，文件與實際回的碼
  不會各說各話。**逐端點列**：送單、重試、重新規劃三支的集合真的不一樣（重新規劃只到得了
  兩種）；權限閘門那一組的 `responses=` 與 `except` **吃同一個例外 tuple**，所以多接一種
  例外時文件會自己跟著變。`api/inventory.py` 與 `api/media.py` 的五支也補上了。
- SSE 的推播有了 `JobSignalOut`（`state` 是 `JobState` 而不是自由字串）；序列化搬到 api 層，
  `services/events.JobSignal.payload()` 刪掉。
- 三張狀態碼表改成**總表**（沒有 `.get(reason, 422)` 的預設），由 `TestStatusTables` 守。

**前端**

- 四組型別改成 `Schemas['JobRefusal']` / `['RouteRefusal']` / `['AccessRefusalOut']` /
  `['JobSignalOut']`。
- 三份重複的解析函式收成 `api/refusal.ts` 一份；執行期的成員表改成 `ReasonSet<R>`
  （`Readonly<Record<R, true>>`，總表）。
- `vite.config.ts` 的 `testTimeout: 15_000`；`asyncUtilTimeout: 5_000` 在 `src/setupTests.ts`
  （見下方偏差 2）。

**順手修掉的 bug**：手抄的 `AccessRefusal` 漏了 `sort_not_offered`，於是後端已經說清楚的 422
被當成「沒說理由」，`retryUnlessRefused` 照預設重試三次、間隔加倍——畫面要晚七秒才說話。
封閉集合改由 OpenAPI 產出之後它自然補齊，並補了 `src/api/refusal.test.ts` 釘住。

## 驗證

**驗收 1 — grep**（把三組全部 23 個理由當 pattern，不是抽樣）：

```
$ grep -rnE "'media_missing'|'route_missing'|…|'sort_not_offered'" web/src \
    --include=*.ts --include=*.tsx | grep -v schema.d.ts | grep -vE '\.test\.tsx?:'
web/src/components/RouteDelete.tsx:102        refusal?.reason !== 'route_in_use'
web/src/components/WatchToggle.tsx:124/127/131
web/src/pages/InventoryPage.tsx:168/799
web/src/pages/MediaDetailPage.tsx:97
web/src/pages/RouteSettingsPage.tsx:254
web/src/settings/AddRoute.tsx:132
web/src/watching/WatchingRows.tsx:37
（另有 31 筆在 *.test.ts(x)，是假造回應的 fixture）
```

十筆**都是拿單一理由做比較**（`reason === 'jellyfin_unreachable'` 這種），比較的對象是產出的
聯集——打錯就是 `tsc` 錯誤。沒有一處是手寫的**聯集**。

三份 `ReasonSet` 仍逐種列出成員（型別編譯後就沒了，執行期要有一份表），但它是總表：少一格或
多一格都是編譯錯誤，而且那道閘門本身由 `refusal.test.ts` 的兩個 `@ts-expect-error` 釘著
（變異驗過：把 `ReasonSet` 放寬成 `Partial<Record<…>>` → `TS2578: Unused '@ts-expect-error'
directive`）。`--enum-values` 為什麼不能用見偏差 1。

**驗收 2 — 改一個拒絕理由、不重跑產生器**（`JobRefusal` 加一個 `mutant_reason`）：

```
A. 只改後端，不重跑產生器 → pytest 紅
$ uv run pytest tests/unit/test_openapi_contract.py -q
FAILED ...::TestRefusalReasons::test_the_generated_types_are_not_stale[JobRefusal]
1 failed, 16 passed（變異當下的測試數；補強後是 28 條）

B. 重跑產生器 → CI 那一行紅
$ pnpm gen:api && git diff --exit-code --stat -- src/api/schema.d.ts
 web/src/api/schema.d.ts | ...
exit=1

C. 產出更新之後 tsc 仍紅——新理由沒有句子
$ pnpm typecheck
src/jobs/JobRow.tsx(192,24): error TS2345: Type '"jobs.refusal.mutant_reason"' is not
  assignable to parameter of type '"jellyfin.unreachable" | ... 940 more ...'
src/media/SubmitAction.tsx(156,17): error TS2345: （同上）

D. 還原之後三者全綠
$ uv run pytest tests/unit/test_openapi_contract.py -q
28 passed in 0.71s
```

第三段是額外的收穫：`t()` 的 `strictKeyChecks` 讓「加了理由卻沒寫句子」也是編譯錯誤。
另外驗過前端那一側：`ReasonSet` 刪掉 `not_replannable` 那一行 →
`TS2741: Property 'not_replannable' is missing`。

**驗收 3 — 改一次無關的格式或命名**（`services/watch.py` 的區域參數
`played_percentage` → `pct`，加上 `api/refusal.ts` 一行註解）：

```
$ pnpm gen:api && git diff --exit-code --stat -- src/api/schema.d.ts
schema.d.ts diff exit=0 （0 = 沒紅）
$ uv run pytest tests/unit/test_openapi_contract.py -q
28 passed in 0.70s
```

讀產出檔的那兩支（`union_members` 與 `object_fields`）自己的兩個方向另外編碼在
`TestReadingTheGeneratedTypes` 裡——拿掉一個成員或改一個欄位名要讀出不同的東西，旁邊多幾行
不相干的宣告不能。手動驗過但沒編碼進去的隨 session 結束就消失了。

**驗收 4 — timeout**：`vite.config.ts` 的 `testTimeout: 15_000`、`setupTests.ts` 的
`asyncUtilTimeout: 5_000`。**票面說的兩條逾時這一輪重現不了**：改動之前連跑四次全量，
每次都是 27 files / 435 passed（12.84 / 18.56 / 17.69 / 17.23 s）。所以這兩個值是預防不是
修復，見偏差 3。

**驗收 5 — lint / type / test**：

```
後端
$ uv run ruff check .          All checks passed!
$ uv run ruff format --check . 326 files already formatted
$ uv run mypy                  Success: no issues found in 222 source files
$ uv run lint-imports          Contracts: 6 kept, 0 broken.
$ uv run pytest -q             1601 passed, 10 deselected in 230.60s (0:03:50)

前端
$ pnpm lint                    （eslint 無輸出）
$ pnpm typecheck               （tsc 無輸出）
$ pnpm exec prettier --check . All matched files use Prettier code style!
$ pnpm test                    Test Files 28 passed (28) / Tests 447 passed (447)
```

## 偏差與決定

1. **執行期仍然有一份逐種列出的成員表**（`ReasonSet<R>`）。型別編譯後就沒了，而 `refusalOf`
   要在執行期分辨「後端說不行」與「認不得的理由」。試過 `openapi-typescript --enum-values`
   （它會另外產 `export const xxxValues = [...]`）：在這份 schema 上**產出重複的識別符**
   （`Health.status` 與 `HealthStatus` 都叫 `healthStatusValues`），檔案自己編譯不過；而且值
   要放 `.ts` 不是 `.d.ts`，CI 那一行與 README 都要跟著改。改用 `Readonly<Record<R, true>>`：
   成員來自產出的聯集，兩個方向都是編譯錯誤。
2. **`asyncUtilTimeout` 不是 vitest 的選項**（查 testing-library 文件：它是
   `@testing-library/dom` 的設定，只有 `configure()` 進得去，預設 1000 ms）。所以票面說的
   「兩個都設在 `vite.config.ts`」做不到，拆成兩個檔案，各留一行說明對方在哪。
3. **票面「固定有兩條 `findBy*` 逾時」重現不了**（連跑四次全綠）。09-22 的審查確實觀察到，
   判斷是機器忙的時候才出現（這台機器同時有好幾個 worktree 在跑），不是「固定」。
4. **狀態碼表不再有預設值**。漏掉的理由以前靜靜變成 422，等於把一種沒人想過的拒絕說成
   「你送錯東西了」；現在漏掉是 `KeyError`，而 `TestStatusTables` 在那之前就先紅。
5. **`/events/stream` 多一個只為文件存在的 `_Stream` 子類別**：`sse_starlette` 不在類別上
   宣告 `media_type`，沒有它 FastAPI 會把這一支寫成 `application/json`。它不參與執行期。
6. **SSE 的 `data` 從 `json.dumps` 換成 `model_dump_json()`**，冒號後少一個空格。兩邊都是
   解析 JSON 不是比字串，等價；記一行是因為它確實是線上位元組的變化。

文件：README〈API 型別〉、plan §6 的 OpenAPI 那一條、CHANGELOG（Changed 與 Fixed 各一條）、
progress.md（session 紀錄與偏差）。

## Comments

- **`web/src/api/schemas.ts` 的 `ROUTE_CHECKS` 仍是手寫的字面聯集**，而 `RouteCheck` 在
  `berth/domain/enums.py` 裡已經是 enum——它沒進 OpenAPI 是因為 `StepOut.step` 宣告成 `str`
  （`api/schemas.py`）。同一類問題、同一種解法（把 `step` 收緊成聯集型別），但它不是拒絕理由，
  這一票沒動。要做的話順手：`SERVICE_KINDS` 那一組註解也該跟著改。
- ~~**「會拒絕的端點都要宣告 `responses=`」這一條沒有閘門。**~~ **票 02a 做出來了**
  （`TestDeclaringWhatEachEndpointRefuses`）。這一票試的是數原始碼裡 `raise access_refusal(`
  與 `responses=access_responses(` 各出現幾次——`PLAYED_RESPONSES` 這種先存成常數再用的寫法
  數不到，放寬到數得到就等於沒在守東西，所以拿掉了。票 02a 換了兩邊的讀法：`responses` 從
  **路由物件**上讀（執行期的值，怎麼寫都一樣），handler 丟得出什麼從**語法樹**讀，兩邊都不是
  字串比對。順帶補上這一票漏掉的三支——`api/setup.py` 的兩支（`DELETE /setup/routes/{id}`
  這一票沒掃到，`POST /setup/routes` 的拒絕是票 01 在另一條分支上同時加的），以及
  `api/jellyfin.py` 的 `get_image`（503 手寫成只有描述、沒有 model）。
- **`AccessRefusal` 與 `RouteRefusal` 新增一種理由時「畫面要說一句話」沒有閘門**：它們的
  消費端是查表（`AddRoute` 的 `Partial<Record<…>>`）或單一理由比較，不是動態 i18n key，所以
  `strictKeyChecks` 擋不到。只有 `jobs.refusal.*` 有（README 已寫明這個差別）。

### code-review 的發現

`/code-review 11db69f` 兩軸各跑一次，處理如下。

**修掉的**：SSE 形狀那一條閘門原本只斷言 `"JobSignalOut:" in text`（全域 CLAUDE.md
「只斷言原始碼含某個字串的規則過不了第二項」）→ 加 `object_fields`，逐欄位比對產出檔與
OpenAPI，四個 model 都納入，兩個方向各驗過（把 `hash` 改名成 `info_hash` 不重跑產生器 → 紅）；
`ReasonSet` 的總表性只手動驗過 → 以兩個 `@ts-expect-error` 編碼進 `refusal.test.ts`；
拒絕理由的 enum 清單原本寫死三個 → 改成掃 `domain/enums.py` 裡名字以 `Refusal` 結尾的每一個，
並要求每一個都在 `STATUS_TABLES` 裡有表；`_REFUSALS` 只驗「理由都有人丟得出來」→ 反向也驗
（`jellyfin_access.py` 裡定義的每個例外類別都要在表上，否則到 api 層是 `KeyError`）；
`api/jellyfin.py` 的 `get_image` 仍手組 `{"reason": "jellyfin_unreachable"}` → 改走
`access_refusal`；三張表三種名字（`_STATUS` / `_STATUS` / `ACCESS_STATUS`）→ 統一 `_STATUS`；
`api/jobs.py` 與 `api/jellyfin.py` 對「逐群組還是逐端點宣告」給了相反的理由 → 都改逐端點；
`routes.ts` 對 `error` 的裸 cast → 改成真的縮窄 + 註明剩下那一個 cast 的理由；README 宣稱
「前四件有閘門，最後一件是 `strictKeyChecks`」對 `AccessRefusal` 不成立 → 改寫（見上一條）。

**沒修**：`*RefusalOut` 三個 model 的 `reason` + `detail` 同形（Duplicated Code，輕）——
OpenAPI 要各自的名字才能讓前端分得出三組，判斷是合理的重複。
