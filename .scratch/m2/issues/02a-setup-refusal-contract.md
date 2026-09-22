# 02a — `setup/*` 的拒絕進文件、進畫面，並補上閘門

**Status:** done

**Blocked by:** 無 —— 可立即開工（票 02 已 done，這一票補它漏掉的兩支端點）

**讀:** plan §6（OpenAPI 那一條、routes 與 setup 兩個群組）、§9.5（精靈第 7 步）、§7（前端那一節）；
`.scratch/m2/issues/02-refusal-types-openapi.md` 的 `## Comments`（閘門為什麼沒做成）、
`.scratch/m2/issues/01-backend-loose-ends.md`（`route_missing` 為什麼會出現在 `POST /setup/routes`）

## 這一票為什麼存在

票 01、02、03 是並行做的。票 02 把拒絕理由收成 enum、替每個 router 補上 `responses=`，
讓前端的封閉集合改由 OpenAPI 產出；但它掃 api 模組的時候 `berth/api/setup.py` 裡還沒有任何
`route_refusal(`——`POST /setup/routes` 的那一行是票 01 在另一條分支上同時加的。合併之後留下三個缺口，
彼此是同一條拒絕的不同段落。

## 做什麼

1. **`api/setup.py` 的兩支 Route 命令宣告 `responses=`**。
   - `POST /setup/routes`：這一步順帶重跑既有 Route 的檢查，途中被刪掉的那一條是 404 `route_missing`（票 01）。
   - `DELETE /setup/routes/{route_id}`：404 `route_missing` + 409 `route_in_use`（票 14a 定的）。
   - **各自給一張小表**（`refusal_responses(RouteRefusalOut, {...})`），不要直接沿用 `api/routes.py` 的
     `REFUSAL_RESPONSES`——那支表是 `routes/*` 五支端點的聯集，套過來就是過度宣告，
     而 `refusal_responses` 的 docstring 寫明「收的是端點真的會回的那幾種」。
2. **補「會拒絕就要宣告」的閘門**。票 02 試過數原始碼裡 `raise x_refusal(` 與 `responses=` 各出現幾次，
   `PLAYED_RESPONSES` 這種先存成常數再用的寫法數不到，放寬到數得到就等於沒在守東西，所以拿掉了
   （票 02 Comments）。**這一票要做成由構造或由文件保證的版本**，例如：走訪 `create_app()` 的每一條路由，
   對照它的 handler 實際接得住哪幾個 refusal 例外（`__wrapped__` / `inspect` 取得 except 的例外 tuple，
   權限閘門那一組已經是這個形狀），handler 接得住而 OpenAPI 的 `responses` 沒列就紅。
   做不到就**在票的 Comments 寫清楚試了什麼、為什麼不成**，並把 plan §6 那一句改成沒有閘門的說法——
   不要留一條靠運氣被遵守的規則（全域 CLAUDE.md「規則要有閘門」）。
3. **精靈第 7 步畫得出拒絕**。`web/src/pages/SetupPage.tsx` 的 build mutation 現在只傳
   `requestFailed={build.isError}`，所以票 01 新加的 404 `route_missing` 到畫面上是一句通用失敗，
   沒有原因也沒有下一步（違反 PRODUCT 原則 4）。改成走 `routeRefusalOf`，與
   `RouteSettingsPage.tsx:217`、`AddRoute.tsx:103`、`RouteDelete.tsx:57` 同一個形狀。
   `route_missing` 的下一步是「那條 Route 已經被刪掉了，重新整理這一步」。

順手（同一個檔案、同一個主題，做不做都可以，不做就記進 Comments）：
`web/src/api/schemas.ts` 的 `ROUTE_CHECKS` 仍是手寫的字面聯集，而 `RouteCheck` 在
`berth/domain/enums.py` 已經是 enum——它進不了 OpenAPI 是因為 `StepOut.step` 宣告成 `str`
（`api/schemas.py`）。同一類問題、同一種解法（把 `step` 收緊成聯集型別）；票 02 沒動是因為它不是拒絕理由。

## 驗收

- [x] `api/setup.py` 兩支端點的 OpenAPI `responses` 各自只列它真的會回的那幾種（404 / 404+409），
      不是 `routes/*` 的聯集；`pnpm gen:api` 重跑後 `git diff --exit-code -- web/src/api/schema.d.ts` 乾淨
- [x] 有一條閘門：把任何一支的 `responses=` 拿掉會紅。**雙向變異驗證寫在測試檔內**——
      造一個違規證明它會紅，改一次無關的格式或命名證明它不會紅（全域 CLAUDE.md）
- [x] **不適用**（上一條做到了）：原本是「做不到時 Comments 寫明為什麼不成」。plan §6 那一句
      照樣同輪改掉，改成閘門的說法而不是沒有閘門的說法
- [x] 精靈第 7 步遇到 404 `route_missing` 時畫面說得出原因與下一步（vitest 斷言訊息內容，不是斷言有沒有 class）
- [x] 既有的三個 `SetupPage.*.test.tsx` 沒有因此改壞（它們沒有把 `requestFailed` 釘成斷言，所以不該需要改）
- [x] playwright 實跑一次精靈第 7 步的拒絕畫面，附截圖或文字結果
- [x] plan §6 那一句的「`setup/*` 還沒宣告」註記隨這一票拿掉；票 02 Comments 的補記同輪更新
- [x] lint、type、test 綠燈（貼指令輸出）

## Comments

- **閘門做成了，不必退而求其次**（驗收第 3 條因此不適用）：`TestDeclaringWhatEachEndpointRefuses`
  走訪 `create_app()` 的每一條路由，比對路由**物件**上的 `responses`（執行期的值）與 handler
  的**語法樹**丟得出來的拒絕形狀，兩個方向都要求相等——漏宣告與過度宣告都紅。票 02 收手的
  原因（`PLAYED_RESPONSES` 先存成常數再用）在這裡根本不經過。`mark_played` / `mark_unplayed`
  把 `try` 交給共用的 `_mark`，所以語法樹要跟著同模組的呼叫往下走，否則那兩支會被讀成
  「它不會拒絕」而判成過度宣告。
- **第一版的閘門是靜靜綠燈的**：`[route for route in app.routes if isinstance(route, APIRoute)]`
  在 FastAPI 0.141 回空 list（`include_router` 的結果包在 `_IncludedRouter` 裡），而**空的
  `parametrize` 會產生一個什麼都不驗的項目然後通過**。改走 `iter_route_contexts`（FastAPI 自己
  產 OpenAPI 時攤平路由用的那一支），並加 `test_it_walks_every_operation_in_the_document`：
  走訪到的要剛好是文件上的每一個 operation——閘門自己也要有閘門。
- **`api/jellyfin.py` 的 `get_image` 順手修掉**（不在票上）：它 `raise access_refusal(...)` 回
  503，但 `responses` 是手寫的，那一格只有描述、沒有 `model`，閘門一上就紅。補上
  `"model": AccessRefusalOut` 是照實宣告；404 `image_missing` 維持只有描述——那個理由不在
  `AccessRefusal` 裡，body 是手組的。
- **`route_missing` 的畫面是對真後端實跑驗的，不是攔截回應**：`scripts/fake_setup_server.py
  --scenario bundled` 走到第 7 步，一個背景迴圈持續刪 `tv` 那條 Route，瀏覽器按下
  「建立 1 條 Route 並檢查」時其中一次刪除落在 `_run_checks` 途中，後端真的回了
  `404 {"reason":"route_missing"}`（瀏覽器 console 上那一條 404 就是它）。截圖存在
  `.playwright-mcp/`（在 `.gitignore` 裡）。
- **`ROUTE_CHECKS` 仍是手寫的字面聯集（票上的「順手」項，沒做）**，理由不只是省時間：把
  `StepOut.step` 收緊成聯集型別會撞上 `models/setting.py` 的 `SetupStep.key` **刻意**是 `str`
  ——「這個型別給每個泊位共用，而各泊位的步驟集合各不相同；存下來的舊值也不該因為某一步被
  改名就讓整份設定讀不回來」。Route 的檢查結果存在 `routes.health_detail_json`，收緊之後舊
  blob 裡一個被改名的 key 就是讀取時 500。要做的話得先替 Route 的檢查另開一個 `RouteCheckOut`，
  而換來的只是半道閘門（`SERVICE_KINDS` 那個 `satisfies` 擋得到寫錯的成員，擋不到後端新增
  一個成員）。值不值得另開一票決定。
- **`api/routes.py` 自己五支端點仍共用 `REFUSAL_RESPONSES`**（九種理由的聯集），所以
  `GET /jellyfin/libraries` 的文件上列得出 `route_in_use` 這種它丟不出來的理由。新的閘門是
  **形狀**（model）那一層，抓不到理由那一層的過度宣告。這一票沒動是因為票上只要求
  `api/setup.py` 那兩支各自成表；要收的話就是替那五支各寫一組 `route_responses(...)`。

### code-review 的發現

`/code-review 2e8b7e8` 兩軸各跑一次（工作區尚未 commit，所以 diff 是 `git diff 2e8b7e8`）。

**修掉的**：

- **README 與 plan §6 的宣稱大於閘門**（兩軸都點名，全域 CLAUDE.md「一句不準的宣稱會讓下一個人
  不去檢查」）。原本寫「只宣告它真的會回的那幾種……過度宣告都紅」，但閘門比的是 **model 形狀**，
  理由那一層沒有守。兩處都改成「閘門只到形狀那一層，理由那一層是慣例」，並明講 `routes/*`
  那五支仍共用聯集表、`GET /jellyfin/libraries` 因此列得出它丟不出來的 `route_in_use`。
- **CHANGELOG 沒更新**（上一輪合併審查已經點過同一件事）：補了 Added 一條（兩支端點的宣告、
  `get_image` 的 503、新閘門）與 Fixed 一條（精靈第 7 步那句通用失敗）。
- **帶模組前綴的 `raise` 繞得過閘門**：`_raised_helper` 只認 `ast.Name`，寫成
  `routes_api.route_refusal(...)` 就讀成空集合、又沒宣告，全綠。改走 `_called_name`
  （`Name` 取 `id`、`Attribute` 取 `attr`），並加 `_refuses_through_the_module` 驗它（拿掉
  `Attribute` 那一支會紅，驗過）。
- **拒絕的形狀掛在 200 上也算宣告**：`declared_models` 不看狀態碼。改成只算 4xx / 5xx
  （`"4XX"` 這種範圍 key 也吃得下），並加一條測試（拿掉過濾會紅，驗過）。

**查了但不成立**：審查說「`walk` 的 `seen` 沒有先放入入口函式，自我遞迴的 handler 會無限遞迴」。
實測不會——終止靠的是**呼叫點**那一份 `seen`（跟進去之前先記下來），入口函式在第一次被當成
巢狀呼叫時就進了集合。我先照建議加了「入口先進 `seen`」，但雙向變異驗證顯示它與拿掉它**一樣綠**，
所以撤掉那個改動，只留下一條說得準的回歸測試（`_refuses_and_recurses`）。

**沒修**：

- `route_responses()` 定義在 `api/routes.py` 卻只有 `api/setup.py` 用（Standards 軸的「放錯家」）。
  它得貼著 `_STATUS` 住——那是「理由 → 狀態碼」的唯一來源，搬走就要把表也搬走或公開它。
- `route_responses()` 與 `api/jobs.py` 的 `_refusals()` 同形（Duplicated Code）。第三支
  `access_responses()` 收的是例外型別不是理由，收不進同一個 helper，所以合併只省得掉兩支裡的一支。
- `refusal?.reason === '…'` 的 cascade 在前端第六處（Repeated Switches）。那一層沒有閘門是
  README 已經寫明的既有狀態（`ReasonSet` 守成員，畫面那一句沒人守），不是這一票造成的。
- 跨模組委派讀成「不會拒絕」：`walk` 只跟同模組的呼叫。那是**假紅**（逼人拿掉正確的宣告）
  而不是靜靜放過，有人會看到並回來補，`raised_models` 的 docstring 寫明了。

**指令輸出**（收尾時最後一輪）：

```
$ uv run ruff check .            All checks passed!
$ uv run ruff format --check .   328 files already formatted
$ uv run mypy                    Success: no issues found in 223 source files
$ uv run lint-imports            Contracts: 6 kept, 0 broken.
$ uv run pytest -q               1689 passed, 10 deselected in 260.69s (0:04:20)
$ pnpm -C web lint               （無輸出）
$ pnpm -C web format:check       All matched files use Prettier code style!
$ pnpm -C web typecheck          （無輸出）
$ pnpm -C web test               Test Files 29 passed (29) · Tests 468 passed (468)
$ pnpm -C web gen:api            重跑後 schema.d.ts 一字不差
```

`pytest` 由開工時的 1615 到 1689，多 74 條，全部在 `test_openapi_contract.py`（28 → 102）：
`TestDeclaringWhatEachEndpointRefuses` 65 條（63 條是逐路由的 `parametrize`，另兩條是登記簿
與走訪範圍）、`TestReadingWhatAHandlerRaises` 9 條變異。其中最後三條是 code-review 之後補的
（模組前綴的 `raise`、自我遞迴、200 上的形狀）。
前端 468 條含這一票的 2 條。**本機曾出現一次 vitest worker 崩潰**（28/29 檔、434/468 條，
沒有任何測試失敗），之後連跑四次都是 29/29、468/468；與這一票的改動無關，記在這裡以免下次
有人以為是新問題。
