# D 複核

所有路徑相對於 `web/src`，另有註明的除外。證據都是複核者自己重跑的 grep 或自己讀的程式碼。

| 編號 | 判定 | 理由（附我自己查到的證據） | 修正後的建議 / 大小 / 風險（若有改） |
|---|---|---|---|
| D1 | 通過但修正 | 沒有共用的色塊元件或常數，`label … ${SIGNAL_FILL[x]}` 到處手寫，這點成立。重數非測試檔：`px-2 py-1.5` 27 處、`px-1.5 py-0.5` 15 處、`px-1.5 py-1` 2 處，與 worker 的數字相同。**`px-2 py-1` 的數字不對**：13 行裡有 2 行不是色塊，分別是 `components/controls.tsx:216`（`COMPACT_BUTTON`，按鈕）與 `setup/IndexerStep.tsx:395`（只有外框、沒有 `SIGNAL_FILL` 的標籤）。真正的 `px-2 py-1` 色塊是 **11 處**：`SubscribePanel.tsx:110,119`、`RssPage.tsx:99`、`FirstRoundSection.tsx:47`、`ItemLine.tsx:67`、`SeriesSection.tsx:181`、`BundledLibraries.tsx:220`、`IndexerSites.tsx:275,774`、`RecommendedSites.tsx:145,196`。worker 把 `IndexerSites.tsx:774` 列進 `py-1.5` 的例子，其實它是 `py-1`。DESIGN.md:556-560 只定義了三種內距，`px-2 py-1` 只出現在 DESIGN.md:565/615/718/726，講的是規則格、select 和按鈕，**不是色塊**。所以第四種內距確實是漂移，判斷成立。 | 先拍板那 11 處 `px-2 py-1` 歸到標準還是 compact（屬設計決定）。repo 對重複方塊的慣例是 `controls.tsx` 裡的類名常數（`FILTER`、`NAV_BOX`、`COMPACT_BUTTON`，「內距由呼叫端給一次」），所以 `CHIP` / `CHIP_COMPACT` 兩個常數會比 `Chip` 元件更貼近現有寫法，元件或常數二擇一即可。大小：大（約 55 處，機械替換）。風險：11 處高度會微調，要實跑看一眼。值得度：中低。 |
| D2 | 通過 | `rss/SectionHeading.tsx` 是元件，DESIGN.md:595-597 把「區塊標題」定成規格（包括 `aria-hidden` 數字加 `sr-only` 帶單位句）。手寫版我逐一打開確認了 10 處：`media/SeasonsPanel.tsx:41`、`FilesPanel.tsx:56`、`SearchPanel.tsx:135`、`SubscribePanel.tsx:66`、`DownloadsPanel.tsx:171`、`WatchArea.tsx:135`、`discover/MediaWall.tsx:42`、`watching/WatchingRows.tsx:178`、`pages/InventoryPage.tsx:544`、`pages/JobDetailPage.tsx:178`。計數的無障礙寫法確實已經分岔：`SeasonsPanel.tsx:46` 是裸的 `<p>{n}</p>`，`FilesPanel`、`MediaWall`、`WatchingRows`、`InventoryPage:544` 有 `sr-only` 句。`IssuesPage:35`、`JobsPage:46`、`ReviewPage:47`、`RssPage:56` 是 `h1`，不併是對的。 | 照 worker 的建議。補充兩點：`SearchPanel` 的計數是一整句（`search.count`），不是數字，要走 `extra` 而不是 `count`；`WatchArea` 與 `WatchingRows` 用 `items-center` 並把連結或按鈕 `ms-auto` 推到右邊，`extra` 要容得下。大小：中。風險：低，只動 markup。 |
| D3 | 通過但修正 | `media/searchResult.ts:62-71` 手寫 `S${pad}`、`E${pad}`，自己的 `pad` 在 `:103-105`；`components/episodes.ts:13-19` 的 `seasonCode` / `episodeCode` 是單一來源（檔頭 `:9`）。全 `web/src` 的 `padStart` 只在這兩處。重複成立。**但「分隔符要先拍板」不是做這條的前提**：只要把 `S${pad(x)}` 換成 `seasonCode(x)`、`E${pad(x)}` 換成 `episodeCode(x)`、刪掉 `pad`，畫面一個字都不變（`searchResult.test.ts:55` 的 `S03E01–E13` 照樣綠）。另外，現況其實是**三種**寫法，不是兩種：`formatEpisode` 是 `S03E01-E02`（hyphen），`formatCoverage` 是 `S01 E01–E28`（空格加 en dash，DESIGN.md:875），`estimate` 是 `S03E01–E13`（不空格加 en dash）。三者都沒寫自己為何不同於另外兩種。 | 最小版：改用 `seasonCode` / `episodeCode`，刪 `pad`，不動分隔符。大小：小（一個檔）。風險：無，可見輸出不變。要不要把 `estimate` 的範圍寫法對齊 DESIGN.md:875 是另一個文案或設計決定，交給使用者，不算進簡化。 |
| D4 | 通過 | 三份我逐行讀過：`pages/JobsPage.tsx:112-125`、`pages/InventoryPage.tsx:700-725`、`media/DownloadsPanel.tsx:73-90`。結構相同，都是 `<nav flex flex-wrap gap-2>`，選中的那顆是 `<span aria-current="true" className={`${FILTER_ACTIVE} text-ink`}>`；三處都在常數外面再補 `text-ink`。全 repo 的 `aria-current="true"` 只有這三處。DESIGN.md:633-635 把「選著的那個不是連結」定成規則，`JobsPage.tsx:106` 也寫明「與媒體庫的篩選同一條」。可多選的 `ToggleChips` 是另一種（DESIGN.md:628-632 明說單選的照舊），不在這條的範圍。 | 照 worker 的建議。可以順手把重複的 `text-ink` 收進元件。大小：小。風險：低，`InventoryPage` 的 `activeOptions={{exact:true}}` 和它的註解要跟過去。 |
| D5 | 通過但修正（重寫理由，比 worker 說的更實） | 40 條 en 值帶「後端沒回應」尾巴，我用同一條 regex 重數也是 40；四個 key（`issues.failed`、`review.plan.failed`、`review.audit.failed`、`rematch.failed`）的 zh 與 en 都整句相同，我轉譯 resources.ts 實際比對過。**要緊的不是措辭兩套，而是「這次請求為什麼失敗」的判斷寫了兩處，答案已經不同**：`components/requestProblem.ts` 加 `RequestFailed` 依狀態碼分成 offline / invalid / conflict / server / signedOut…（M4 票 21，progress.md:164 寫明「422 不再說『後端沒在跑』」）；這 40 處則是拒絕解析不出來就一律說「API 沒回應」，例如 `issues/IssueRow.tsx:67`、`api/files.ts:50`、`plans/planRefusal.ts:8`，以及 `pages/IssuesPage.tsx:58`、`JobsPage.tsx:58`、`ReviewPage.tsx:73` 的 `xxx.off`。**失效條件**：`POST /issues/{id}/resolve` 回 500 或 401 時，畫面說「Berth 自己的 API 沒有回應」，可是同一個錯誤交給 `RequestFailed` 會說「後端失敗，看 log」或「登入失效」。`api/refusal.ts:23-24` 自己說的是「落回一句**誠實的**通用訊息」，現狀不誠實。 | 主建議改成 worker 的 (a)：拒絕解析不出來時，交給 `requestProblem` / `RequestFailed lead=…`（`lead` 說什麼沒做成），尾巴只剩 `PROBLEM_TEXT`。這也是票 21 在精靈與設定頁做過的同一件事，把它延伸到 issues、review、jobs、rss、media。「4 個 key 收成 1 個」價值低，解不掉分歧，不建議單做。大小：大（約 35 個呼叫端、約 80 個 zh/en 值、斷言整句的測試）。風險：動文案要使用者同意；會改變 500 與 401 時的說法（這正是要的效果）。值得度：中高。 |
| D6 | 通過 | `pages/MediaDetailPage.tsx:348-353` 與 `components/controls.tsx:274-280`（`Notice`）的類名逐字相同；`SIGNAL_FILL.neutral` 就是 `bg-deck text-ink`（`signal.ts:12`），neutral 不掛 `role`；全 repo 的 `border-2 border-rule bg-well px-3 py-2.5` 只有這兩處。`Notice` 已經在該檔 import（`:15`）。外層是 `:134` 直接放在頁面裡，不在 `<p>` 裡面，換成 `<div>` 沒問題。測試用 `findByText` 整句斷言（`MediaDetailPage.test.tsx:2014`），不受影響。 | 照建議。大小：小。風險：無。 |
| D7 | 通過 | `pages/IssuesPage.tsx:80-87`、`pages/ReviewPage.tsx:171-178` 逐字相同；`pages/InventoryPage.tsx:659-666` 多了 `max-w-[80rem]`。三處註解互相寫「同 /issues」「同 /review」。`RssPage.tsx:198-205` 的第二格是 `h-40`，形狀不同，不併是對的。 | 照建議；`max-w-[80rem]` 交給呼叫端包一層，或給元件 `className`。大小：小。風險：無。 |
| D8 | 通過 | `grep -rnw SERVICE_KINDS web/`（含 e2e）只有定義 `api/schemas.ts:59`。它的註解「泊位板逐格照它畫」已經不實：泊位板走 `components/berths.ts` 的 `BERTHS`。`.scratch/m2/issues/02-refusal-types-openapi.md:185` 當時就記過這段註解該改。`setup/signals.ts:133` 的 `ALL_PROFILES` 有自己的語意（`.env` 預設行），保留合理。 | 照建議，刪常數連同註解。大小：小。風險：無。 |
| D9 | 通過 | `TOTAL_STEPS` 只出現在 `setup/navigation.ts:32` 和 `setup/navigation.test.ts:6,29`。同一個 `it` 已經用 `toEqual` 斷言整個 `STEP`（包括 `complete: 6`），刪掉那一行 expect 不會少守任何東西。 | 照建議。大小：小。風險：無。 |
| D10 | 通過 | `media/FilesPanel.tsx:439-441`（`baseName`）與 `components/queueText.ts:4-7`（`fileName`）都是「取路徑最後一段」。差異只有兩點：`fileName` 也切 `\`；路徑以 `/` 結尾時 `baseName` 回整串、`fileName` 回空字串。`target_path` 是帳本的 POSIX 檔案路徑（`queueText.ts:3` 註解），兩點都碰不到。repo 裡沒有第三份（`split('/')` 的其他出現在 `routeChecks.ts:265`，是另一件事）。 | 照建議。大小：小。風險：無。 |
| D11 | 通過 | 10 項我都用 `grep -rnw` 對 `web/src` 加 `web/e2e` 重跑過：`Role`、`IssueType`、`ReconcileSide`、`RouteChoice`、`PlanStatus`、`Confidence`、`AuditSeries`、`SkipCode`、`Tags` 除了定義行以外，只出現在 `schema.d.ts`（產生的 schema 名）、註解或文案裡，沒有任何型別引用；`stubJsonResponse` 只有定義（`test/fetch.ts:6`），刪掉後同檔的 `vi` 仍被 `stubApi` 使用。 | 照建議。大小：小。風險：無。 |

## 待複核疑點結論

1. **D3 的分隔符**：駁回，不成為獨立發現。D3 的最小修法不需要先決定分隔符（見上表）。三種範圍寫法都沒有書面理由（DESIGN.md:875 只講 `formatCoverage` 的「一組」）；要不要統一屬文案或設計決定，記給使用者，不列入簡化。
2. **`InventoryPage` 手寫 debounce vs `useDebounced`**：改判刻意保留。`pages/InventoryPage.tsx:288-289` 的註解寫明「計時器在事件裡而不是 `useDebounced` + effect：換網址只該由打字觸發。effect 版要把 `query` 與導覽放進相依……換排序、翻頁……也會跑一次」。理由寫在程式碼註解裡，間隔也共用 `SEARCH_DEBOUNCE_MS`（`:40` import），不是兩套。
3. **空狀態 `EmptyState`**：駁回。worker 的 grep 第 7 筆 `InventoryPage.tsx:485` 是「縮小範圍」的 `role="group"`，不是空狀態。真正的空狀態外框（`InventoryPage.tsx:787,817,861,892,925`、`JobsPage.tsx:179,204`、`JobDetailPage.tsx:192`）都照 DESIGN.md:600 的同一個規格，沒有漂移；裡面的內容（一句加一到兩條不同的連結或條件列表）各自不同。共用的只有一串類名，抽出來也去不掉任何「同一判斷」，不符合票的兩類。
4. **`SetupPage` 與 `ServiceConnection` 的「等待中每 3 秒重測」**：通過，成為發現 **D12**。規則相同：該服務 `state === 'waiting'`、沒有 pending 就 3 秒後重測（`pages/SetupPage.tsx:417-419,510-517`；`settings/ServiceConnection.tsx:69-75`）。`ServiceConnection.tsx:67` 的註解說「照精靈」，這是要求兩邊同步，不是兩份並存的理由。**而且寫法已經分岔**：`SetupPage` 把整個 `retest` mutation 物件放進 effect 相依；TanStack Query 5 的 `useMutation` 每次 render 都回一個新物件（`node_modules/@tanstack/react-query/build/modern/useMutation.js` 回 `{...result, mutate, …}`），所以 SetupPage 任何一次重新 render 都會把 3 秒計時器重設。`ServiceConnection` 解構出穩定的 `mutate`，沒有這個問題。同一個檔案 `SetupPage.tsx:445` 其他地方也已經用 `const { mutate: retestNow, isPending: retesting } = retest`。這個重設在使用者眼裡會不會造成可見的延遲，我沒有 repro，不宣稱是 bug。建議：抽一個 `useWaitingRetest(waiting: boolean, busy: boolean, retest: () => void)`（放 `setup/`），兩處共用。大小：小。風險：低。值得度：低中。
5. **`formatSize` / `formatCount` 擺放**：同意 worker 的判斷，駁回。這是擺放問題，不屬於票的兩類。

## 刻意保留抽查

| 條目 | 出處是否寫了理由 | 結論 |
|---|---|---|
| `servicesQueryOptions` 與 `healthDetailQueryOptions` | **不成立**。`api/settings.ts:16` 只說「與健康頁同一份形狀」，解釋的是形狀為什麼一樣，沒有解釋為什麼要兩個端點、兩份快取。worker 補的「端點權限不同」是事實（`berth/api/gate.py:79` 把 `/settings` 列為 admin；`/health/detail` 登入即可），但不構成理由：設定頁只有 admin 進得去，admin 本來就打得到 `/health/detail`。兩份快取已經靠手動同步：`settings/useServiceCheck.ts:20-21` 兩份一起寫，`pages/HealthPage.tsx:48` 的「重新檢查」只寫 `['health','detail']`，`['settings','services']` 留著舊的（`staleTime` 是預設 0，設定頁掛上時會重抓，所以只會閃一下舊資料）。plan.md:391 有列出這個端點，但沒寫理由。 | 移回發現，見下方 R2。 |
| `deleteSetupRoute` 與 `deleteRoute` | `api/setup.ts:382-385` 寫明「精靈跑完之前還沒有人登入得了，而 `/routes/*` 永遠只有 admin」；`berth/api/gate.py:67-68` 呼應。 | 成立。 |
| `setup/BerthBoard.tsx` 與 `components/BerthBoard.tsx` | `setup/BerthBoard.tsx:13-19` 寫明一份管版面、一份管「一格寫什麼」。 | 成立。 |
| 兩個 `STATUS_SIGNAL` | `components/steps.ts`（`StepStatus`：ok / skipped / failed / running / pending）與 `inventory/InventoryTile.tsx:24`（failed / review / downloading / complete…）的值域不同，`InventoryTile.tsx:18-23` 有註解。 | 成立。 |
| `Timestamp` 與 `whenText` | `components/queueText.ts:9-12` 寫明「同 `Timestamp`」，兩者用同一個 `i18n.language` 規則。 | 成立。 |
| `formatCoverage` 的 en dash | `components/episodes.ts:48-53`、DESIGN.md:875。 | 成立。 |
| 各 `REASONS` 表 | `api/refusal.ts:8-13`：「少一種、多一種都是編譯錯誤——這就是那道閘門」。 | 成立。 |
| `CONFIRM_ACTIONS` / `ConfirmPanel` | `controls.tsx:318-326` 是 `CONFIRM_ACTIONS` 的理由（類名原本被抄三遍）。 | 成立。 |

## knip 判定核對

39 條逐條核對。做法：`grep -cw` 數該名稱在自己檔案出現幾次，再 `grep -rlw` 查 `web/src` 與 `web/e2e` 有沒有其他檔案引用（排除 `schema.d.ts` 與 `resources.ts`）。

- **「只是 export 多餘」23 條全部對**：同檔都有使用，外部零引用。三個表面上的例外查過了：`InterfaceLoginFields` 外部只 import 同檔的 `BerthLogin`、`CarriedApplying`、`NewLoginFields`；`TestLine` 只在 `SetupPage.services.test.tsx:1777` 的註解出現；`candidate` 在 `setup/IndexerSites.tsx` 出現的是同名的 prop，不是 import。
- **「真的沒人用」11 條全部對**（`SERVICE_KINDS`、`stubJsonResponse`，加 9 個 type；見 D8、D11）。
- **誤報 5 條對**：`uv` 是 `package.json:18` 的 `gen:api` 用的外部 binary；`paths`、`webhooks`、`$defs`、`operations` 在 openapi-typescript 產生的 `schema.d.ts`，檔頭寫明不手改。
- 「只在測試用」的補查（`testonly.cjs`）抽查了 8 個名稱，每個在自己的 production 檔裡都有至少一次非定義的使用（例：`internalRedirect` 在 `auth/destination.ts:40`、`lacksScheme` 在 `setup/address.ts:18`、`AUTH_REJECTED_TEXT` 在 `components/failures.ts:68`）。worker 的判斷正確。
- knip 輸出沒有 Unused files 與 Unused dependencies 兩段。入口辨識若失敗，knip 會把整棵樹報成未使用，所以兩段都空代表入口辨識正常。

## i18n 掃描可信度

- **方法本身可信**：`i18n_scan2.cjs` 用 TypeScript 轉譯 `resources.ts` 取得實際的樹，用 AST 收字串字面量與樣板字串開頭，比 regex 穩。去掉複數後綴後的 2085 個基底 key 裡，1523 個有完全相同的字面量，這部分沒有疑問。
- **弱點**（worker 只寫出一部分）：
  1. 動態前綴判定是「任一個樣板開頭是 key 的前綴」，而且有長度 > 2 或含 `.` 的過濾。寬前綴（例如 `interfaceLogin.`，7 個 key）底下的 key 一律算「可能用到」，死 key 會被吸收。
  2. `i18n_scan4.cjs` 的後綴驗證只看「最後一段 token 在含該前綴的檔案、或 `api/` / `schema.d.ts` 出現過」。`title`、`off`、`failed`、`movie` 這類常見 token 幾乎一定命中，驗證力弱。
  3. 若有 `const base = 'x.y'` 再 `` `${base}.z` `` 的寫法，前綴沒有尾點，會被判成未使用。實際結果 0 未使用，表示沒有踩到。另外全 `web/src` 沒有 `keyPrefix`。
- **我另做的抽驗**：562 個動態 key 中，取第一段後綴是 snake_case 的去 `schema.d.ts` 找 enum 值，沒找到的有 46 個，逐組查完都有封閉清單撐著：`jobs.event.*` 27 個 key 對 `jobs/eventTypes.ts` 的 `EVENT_TYPES` 27 個成員，一一對上；`jobs.plan.why.*` 51 個 code 逐一在 `berth/` 找到；`owner.title.*` 等屬前端自己的 union。i18next 有型別設定（`i18n/i18next.d.ts` 的 `CustomTypeOptions`），少 key 是 `tsc` 錯誤，但多出來的 key 不會被抓到。
- **結論**：「0 個未使用 key」可以接受。這是證據力中等的「沒找到反例」，不是證明；剩下的盲點只在寬前綴底下、後端已刪而前端還留著的值，目前抽驗沒有發現。

## 複核者另外發現（若有，需附證據）

- **R1 `MediaDetailPage` 手抄了一份 `PAGE_TITLE`**（重複，同一常數兩份）。`pages/MediaDetailPage.tsx:90` 寫 `<h1 className="value text-lg font-semibold text-ink">`，與 `components/controls.tsx:233` 的 `PAGE_TITLE` 逐字相同；全 repo 只有這兩處有這串字。`controls.tsx:229-232` 寫明 `PAGE_TITLE` 就是為了讓各頁 h1 不再各長各的（progress.md:85）。建議：import `PAGE_TITLE`（該檔已經從 `controls` import 其他東西）。大小：小。風險：無。
- **R2 設定頁與健康頁讀同一份服務狀態，卻有兩個端點、兩份快取**（從「刻意保留」移出；同一件事兩套做法）。前端：`api/settings.ts:17-20` 的 `servicesQueryOptions`（`GET /settings/services`）與 `api/health.ts:19-22` 的 `healthDetailQueryOptions`（`GET /health/detail`）。後端：`berth/api/settings.py:44-47` 與 `berth/api/health.py:53-56` 呼叫同一個 `health_detail(await read_health(session))`。兩份快取已經不同步：`HealthPage.tsx:48` 的重新檢查只更新其中一份（見上方刻意保留抽查）。建議：`settings/HealthSection.tsx` 改讀 `healthDetailQueryOptions`，`useServiceCheck` 只寫一份；後端刪 `GET /settings/services`（`POST /settings/services/{kind}/test` 照留），同步改 plan.md:391、`schema.d.ts`（`pnpm gen:api`）和後端測試。大小：小到中，跨前後端，要跟 B（後端）區塊對齊。風險：這是對外 API 的刪除，雖然只有自家前端在用，照全域規則要先告知；設定頁的權限不受影響（admin 本來就打得到 `/health/detail`）。值得度：中。
- **R3（疑點，不列為發現）媒體庫頁的 h1 用 `.label` 樣式，其他頁都用 `PAGE_TITLE`**。`pages/InventoryPage.tsx:92` 寫 `<h1 className="label text-ink">`。它早於 `PAGE_TITLE`（2026-09-15 對 2026-09-22），當時沒遷移。但 DESIGN.md:344 寫「下載列表、探索牆、搜尋、檔案這些區塊的 `h1` / `h2` 都是 `.label`」，和 `controls.tsx:229-233` 的 `PAGE_TITLE`（`value text-lg`）互相矛盾。要先由使用者或設計決定頁級 h1 採哪一種，再談合併，所以只記為疑點。
