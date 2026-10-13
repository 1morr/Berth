# D web/src

範圍：`web/src` 約 300 個 ts/tsx。前端整體已經收得很乾淨（確認對話框、`Notice`、`SettingsHint`、`TmdbNotice`、`parseRefusal`、`formatSize`、`whenText` 都已是單一來源）。下面是還剩的。

## 發現

### D1 狀態色塊（chip）在約 57 處手寫同一串類名，而且分出四種內距
- 類別：重複（同一種畫面元件）
- 是什麼：沒有 `Chip` 元件，只有 `components/AuditChip.tsx`。其餘全是各處手寫 `<span className="label px-2 py-1.5 ${SIGNAL_FILL[x]}">`。例：`components/controls.tsx:278`（`Notice` 內）、`components/StepLine.tsx:68`、`health/ServiceCard.tsx:47`、`jobs/JobSummary.tsx:24`、`pages/JobDetailPage.tsx:71`、`setup/IndexerSites.tsx:459,597,604,774`、`rss/ItemLine.tsx:67`、`inventory/InventoryTile.tsx:83`。
- 證據：`grep -rnE "label[^\"\`]*px-2 py-1.5" --include=*.tsx web/src`（排除 test）27 處；`px-2 py-1` 13 處；`px-1.5 py-0.5` 15 處；`px-1.5 py-1` 2 處（`jobs/JobTimeline.tsx:56`、`health/PollerCard.tsx:82`）。DESIGN.md:556-565〈Chips〉只定義了 `0.375rem 0.5rem`（標準）、`0.125rem 0.375rem`（compact）、`0.25rem 0.375rem`（時間線）三種；`px-2 py-1`（13 處，例 `rss/SeriesSection.tsx:181`、`setup/RecommendedSites.tsx:145,196`）不在任何一種裡，是漂出去的第四種。
- 建議：做一個 `Chip({signal, size: 'standard' | 'compact', children})`（放 `components/`，吃 `SIGNAL_FILL` / `UNPAINTED_FILL`），`AuditChip` 與 `Notice` 改包它；逐處換掉。先決定 `px-2 py-1` 那 13 處歸標準還是 compact。
- 大小：大（約 57 處、約 35 個檔，但每處是機械替換）。可拆兩個 session：先元件加 `Notice`/`AuditChip` 與標準尺寸，再換 compact。
- 風險：只動視覺類名，不動對外介面與 localStorage；`px-2 py-1` 歸併會讓那 13 處高度微調，要看一眼。
- 值得度：中。價值是「內距不再各自漂」，不是行數；沒有行為差異。

### D2 區塊標題「h2 + 計數」：`rss/SectionHeading` 已有，媒體與其他頁手寫了至少 9 份，計數的無障礙寫法也不一致
- 類別：重複
- 是什麼：`rss/SectionHeading.tsx:9-35` 是元件（`label` h2 + `aria-hidden` 數字 + `sr-only` 帶單位的一句 + `extra`），DESIGN.md:595-597 把這個寫成區塊標題的規格。手寫版：`media/SeasonsPanel.tsx:41-48`、`media/FilesPanel.tsx:56-62`、`media/SearchPanel.tsx:135`、`media/SubscribePanel.tsx:66`、`media/DownloadsPanel.tsx:168-178`（`Heading`）、`media/WatchArea.tsx:135`、`discover/MediaWall.tsx:42`、`watching/WatchingRows.tsx:178`、`pages/InventoryPage.tsx:544`、`pages/JobDetailPage.tsx:175`（`Section`，只有 h2）。
- 證據：`grep -rnE "border-b-2 border-rule-strong pb-2" --include=*.tsx web/src`（排除 test）16 處，只有 `rss/SectionHeading.tsx` 是元件。`SeasonsPanel.tsx:46` 的計數是裸的 `<p className="value ...">{n}</p>`（螢幕閱讀器念「3」），`FilesPanel.tsx:57-62` 自己補了 `sr-only` 的帶單位版——同一件事兩種實作。
- 建議：把 `SectionHeading` 搬到 `components/`（保留 `extra`、`count`，再加一個可選 `ref`/`tabIndex` 給 `SearchPanel` 的焦點需求），媒體頁的區塊換用它。頁級 `h1`（`PAGE_TITLE`）那幾處不併，另算。
- 大小：中（約 8-10 個檔）。
- 風險：只動 markup；`SearchPanel` 的 `heading` ref 與 `tabIndex={-1}` 要保留；`DownloadsPanel.Heading` 的 `justify-between` 對齊要用 `extra` 表達或加 prop。
- 值得度：中。同時順手把計數的無障礙寫法統一。

### D3 `estimate()` 自己重算季集代號，沒用 `components/episodes.ts`
- 類別：重複（同一個判斷兩處、已經分岔）
- 是什麼：`media/searchResult.ts:62-72` 手寫 `S${pad(season)}`、`E${pad(start)}`、`–E${pad(end)}`，並有自己的 `pad`（`searchResult.ts:103-105`）。`components/episodes.ts:13-34`（`seasonCode` / `episodeCode` / `formatEpisode`，`pad` 在 `episodes.ts:86-88`）是同一組代號的單一來源，檔頭 `episodes.ts:3-9` 明講「同一個代號各寫一份遲早會分岔」。已經分岔：`estimate` 的範圍是 en dash `S03E01–E02`，`formatEpisode` 是 hyphen `S03E01-E02`。
- 證據：`grep -rn "padStart" web/src` 只剩這兩處；`estimate` 被 `media/SearchResults.tsx:234`、`rss/OneshotSection.tsx:407` 用。
- 建議：`estimate` 的 season/start/end 改用 `seasonCode` / `episodeCode`，刪 `searchResult.ts` 的 `pad`。**分隔符要先決定**：`episodes.ts:48-53` 的理由是 `S01E01-E28` 是 Jellyfin 檔名寫法、範圍寫成那樣會被讀成一個檔案，`formatCoverage` 因此用 en dash；搜尋結果預估也是「範圍」不是檔名，保留 en dash 合理，但現在是靠複製貼上碰巧一致。待拍板（見「待複核」）。
- 大小：小（兩個檔 + `searchResult.test.ts`）。
- 風險：若改分隔符，`searchResult.test.ts` 與兩處畫面斷言會變；不動持久化。
- 值得度：中低。只有兩個呼叫端，但這是「同一概念兩份實作」。

### D4 單選篩選列的 markup 三份
- 類別：重複（近似元件）
- 是什麼：`<nav class="flex flex-wrap gap-2">`，選中的是 `<span aria-current="true" className={`${FILTER_ACTIVE} text-ink`}>`，其餘是 `FILTER` 的 `Link`/`button`。三份：`pages/JobsPage.tsx:112-125`、`pages/InventoryPage.tsx:700-725`、`media/DownloadsPanel.tsx:73-90`。`JobsPage.tsx:107` 的註解直說「與媒體庫的篩選同一條」。
- 證據：`grep -rn 'aria-current="true"' --include=*.tsx web/src`（排除 test）3 處，結構逐行對得上；差別只在「其餘那顆」是 `Link`（兩處）或 `button`（一處）。
- 建議：`components/FilterBar.tsx`，吃 `options`、`current`、以 render prop 畫非選中那顆。DESIGN.md:633-635 的規則（選中不是連結）改由元件一處保證。
- 大小：小。
- 風險：低；`InventoryPage` 的 `Link` 要保留 `activeOptions={{exact: true}}` 與註解。
- 值得度：低-中。三份且彼此註明要同步，但每份才十幾行。

### D5 「後端沒回應」的說法：約 40 個 i18n 值各帶一條尾巴，兩種措辭，另有共用的 `request.offline`
- 類別：重複（同一件事兩套說法）
- 是什麼：en 值裡約 40 條在「什麼沒做成」後面接同一個意思：`Berth’s own API did not answer — check that it is still running.`（約 25 條，例 `issues.failed`、`review.plan.failed`、`review.audit.failed`、`rematch.failed`、`jobs.off`、`jobs.retryOff`、`submit.off`、`settings.disk.failed`）或 `The Berth backend may be down — check the container and press again.`（約 15 條，例 `routeSettings.edit.failed`、`complete.failed`、`health.recheckFailed`、`settings.checkFailed`）。另一頭 `components/requestProblem.ts:13-14` 的 `PROBLEM_TEXT.offline → request.offline`（zh-Hant `resources.ts:394`），由 `RequestFailed`（`components/RequestFailed.tsx`，18 處用，吃 `lead`）說同一句。`issues.failed`、`review.plan.failed`、`review.audit.failed`、`rematch.failed` 四個 key 的整句完全相同。
- 證據：`i18n_dupval.cjs`（在 `scripts/`）找出整句相同的 key；對 en 值用正則 `own API (did not answer|isn.t answering)|backend may be down|Check that the Berth backend` 得 40 條。
- 建議：先做最小版：四個整句相同的 key 收成一個（4 到 1）。完整版二擇一：(a) 呼叫端改成 `RequestFailed lead=…`，尾巴只留 `request.offline`；(b) 各自保留「什麼沒做成」，尾巴收成一個 i18n 插值。
- 大小：最小版小；完整版大（約 35 個呼叫端、80 個 en/zh 值、測試斷言文字）。
- 風險：動 UI 文案，測試若斷言整句會紅；不動持久化與對外介面。PRODUCT 原則 4（失敗要說下一步）要成立——尾巴本身就是下一步，不能只刪。
- 值得度：中。現在要改「後端沒回應」的說法得動 40 處；但文案改動需使用者同意。

### D6 `MediaDetailPage.AwaitingReview` 手寫了一份 `Notice`
- 類別：重複
- 是什麼：`pages/MediaDetailPage.tsx:348-353` 的 `<p class="flex flex-wrap items-start gap-x-3 gap-y-2 border-2 border-rule bg-well px-3 py-2.5"><span class="label bg-deck px-2 py-1.5 text-ink">…</span><span class="min-w-0 flex-1 self-center text-sm text-ink">…</span></p>` 逐字等於 `components/controls.tsx:264-282` 的 `<Notice signal="neutral" label=…>`（`SIGNAL_FILL.neutral` = `bg-deck text-ink`，`signal.ts:12`；neutral 不掛 `role`）。
- 證據：兩段類名逐字對照；`grep -rn "border-2 border-rule bg-well px-3 py-2.5" web/src` 只有這兩處。
- 建議：換成 `<Notice signal="neutral" label={t('jobs.state.review')}>…</Notice>`。
- 大小：小（一個檔）。
- 風險：外層 `<p>` 變 `<div>`，不影響語意。
- 值得度：低。

### D7 排隊清單的讀取中佔位三份逐字相同
- 類別：重複
- 是什麼：`pages/IssuesPage.tsx:81-88`、`pages/ReviewPage.tsx:171-178`（皆 `Loading`）、`pages/InventoryPage.tsx:658-666`（`QueueLoading`，多一個 `max-w-[80rem]`）都是「`grid gap-3` 裡兩個 `h-24 border-2 border-rule bg-well`」；`InventoryPage` 與 `ReviewPage` 的註解分別寫「同 /review」「同 /issues」。`RssPage.tsx:198`、`JobsPage.tsx:214`、`JobDetailPage.tsx:202`、`MediaDetailPage.tsx:308` 形狀不同，不併。
- 建議：`components/QueueLoading.tsx` 一份，三處引用。
- 大小：小。
- 風險：低。
- 值得度：低。

### D8 `SERVICE_KINDS` 沒人用，三個服務的順序另有一份 `ALL_PROFILES`
- 類別：沒人用 + 重複
- 是什麼：`api/schemas.ts:59-63` 的 `SERVICE_KINDS`（註解說「泊位板逐格照它畫」）沒有任何引用；泊位板實際走 `components/berths.ts`。`setup/signals.ts:133` 另寫了 `['jellyfin','qbittorrent','prowlarr']` 當 `ALL_PROFILES`。
- 證據：`grep -rnw SERVICE_KINDS web/src` 只有定義一行（knip 同）；`grep -rn "'jellyfin', *'qbittorrent'" web/src`。
- 建議：刪 `SERVICE_KINDS` 與它那段註解；`ALL_PROFILES` 保留（有自己的理由：`.env.example` 預設那一行，`signals.ts:132`）。
- 大小：小。
- 風險：無。
- 值得度：低，但是確定的死碼。

### D9 `TOTAL_STEPS` 沒有 production 消費者，只有一條測試守著
- 類別：沒人用
- 是什麼：`setup/navigation.ts:32` `export const TOTAL_STEPS = STEP.complete`；唯一引用是 `setup/navigation.test.ts:6,29`（`expect(TOTAL_STEPS).toBe(6)`）。
- 證據：`grep -rnw TOTAL_STEPS web/src` 兩個檔。
- 建議：刪常數與那一行 expect（`STEP` 形狀的斷言在上面已有）。符合全域規則「消費點歸零的介面連同守它的測試一起刪」。
- 大小：小。
- 風險：無。
- 值得度：低。

### D10 `FilesPanel.baseName` 與 `queueText.fileName` 是同一件事
- 類別：重複
- 是什麼：`media/FilesPanel.tsx:439-441` `file.target_path.split('/').pop() || file.target_path`；`components/queueText.ts:4-7` `fileName(path)`（`split(/[\\/]/)` 取最後一段，多個列元件共用）。
- 證據：`grep -rn "queueText" web/src` 見 `fileName` 的呼叫端；`FilesPanel.tsx` 沒引。
- 建議：`FilesPanel` 用 `fileName(file.target_path)`，刪 `baseName`。差別只在路徑以 `/` 結尾時的退回，`target_path` 是檔案，不會發生。
- 大小：小。
- 風險：無。
- 值得度：低。

### D11 knip 判定「真的沒人用」的型別與函式，一次清掉
- 類別：沒人用
- 是什麼：只有定義、沒有任何引用的 type：`Role`（`api/auth.ts:7`）、`IssueType`（`api/issues.ts:11`）、`ReconcileSide`（`api/issues.ts:31`）、`RouteChoice`（`api/media.ts:17`）、`PlanStatus`（`api/plans.ts:15`）、`Confidence`（`api/plans.ts:21`）、`AuditSeries`（`api/review.ts:18`）、`SkipCode`（`api/rss.ts:29`）、`Tags`（`api/search.ts:13`）。函式：`stubJsonResponse`（`test/fetch.ts:6`，連測試都沒呼叫）。其餘 knip 條目只是 export 多餘，見下表。
- 證據：下面「工具結果判定」每條的 grep。
- 建議：刪上列 10 項；其餘拿掉 `export`。
- 大小：小（約 12 個檔、全是一兩行）。
- 風險：無（不動 `schema.d.ts`，不動對外介面）。
- 值得度：低-中。確定但很小。

## 刻意保留
- `servicesQueryOptions`（`/settings/services`）與 `healthDetailQueryOptions`（`/health/detail`）回同一個型別、兩個端點：`api/settings.ts:16` 註解（「同一份形狀」）；端點權限不同。
- `deleteSetupRoute`（`/setup/routes/{id}`）與 `deleteRoute`（`/routes/{id}`）：`api/setup.ts:382-385`（精靈跑完前沒人登入得了）。
- `setup/BerthBoard.tsx` 與 `components/BerthBoard.tsx` 兩個同名檔：前者是「一格寫什麼」，後者是版面，`setup/BerthBoard.tsx:14-20` 註解。
- 兩個 `STATUS_SIGNAL`（`components/steps.ts:15`、`inventory/InventoryTile.tsx:24`）：值域不同，`InventoryTile.tsx:18-23` 註解「常態不塗漆，例外才塗」。
- `Timestamp` 與 `whenText` 的絕對時間：`components/queueText.ts:9-12` 註解寫明同一個語言規則（共用 `i18n.language`，不是兩套）。
- 確認就地展開：`ConfirmAction`（`controls.tsx:334`）+ `ConfirmPanel` + `useInPlaceConfirm` 是單一來源；各呼叫端自訂內容的幾處（`WorkPicker`、`SeriesBinder`、`SubmitAction` 等）用 `ConfirmPanel` 是設計，`CONFIRM_ACTIONS` 註解 `controls.tsx:320-326`。
- `formatCoverage` 用 en dash、`formatEpisode` 用 hyphen：`components/episodes.ts:48-53` 註解說明。
- 各 `api/*.ts` 的 `REASONS` 表與 `parseXxxRefusal`：解析已共用 `api/refusal.ts`，各表是「少一種理由就編譯錯誤」的閘門（`api/refusal.ts:8-12`）。

## 工具結果判定

| 位置 | 項目 | 判定 | 理由 |
|---|---|---|---|
| package.json | unlisted binary `uv` | 誤報 | `gen:api` 腳本用的外部 binary，不是 npm 依賴 |
| src/api/files.ts:43 | `parseRematchRefusal` | 只是 export 多餘 | 檔內 `rematchRefusalText`（:49）用；無外部引用 |
| src/api/schemas.ts:59 | `SERVICE_KINDS` | 真的沒人用 | 全 repo 只有定義（D8） |
| src/components/routeChecks.ts:22 | `ROUTE_HEALTH_LABEL` | 只是 export 多餘 | 檔內 :41、:54 用 |
| src/components/useFadingNote.ts:4 | `NOTE_MS` | 只是 export 多餘 | 檔內 :13 預設值 |
| src/i18n/index.ts:9 | `detectLanguage` | 只是 export 多餘 | 檔內 :47 用 |
| src/media/searchFilter.ts:43 | `isListed` | 只是 export 多餘 | 檔內 :50、:137 用 |
| src/rss/seriesValues.ts:12 | `signedOffset` | 只是 export 多餘 | 檔內 :23、:26 用 |
| src/setup/InterfaceLoginFields.tsx:20 | `InterfaceLoginFields` | 只是 export 多餘 | 同檔 :167 用；外部只引 `BerthLogin`、`CarriedApplying`、`NewLoginFields` |
| src/setup/ServiceChoice.tsx:723 | `LoopbackHint` | 只是 export 多餘 | 同檔 :614 用 |
| src/setup/ServiceChoice.tsx:765 | `TestLine` | 只是 export 多餘 | 同檔 :446 用；`SetupPage.services.test.tsx:1777` 只在註解提到 |
| src/setup/useLibraryDraft.ts:14 | `SAVE_DEBOUNCE_MS` | 只是 export 多餘 | 檔內 :73 用 |
| src/test/fetch.ts:6 | `stubJsonResponse` | 真的沒人用 | 全 repo 只有定義，連測試都不呼叫（D11） |
| src/test/fixtures.ts:171 | `candidate` | 只是 export 多餘 | 檔內 :150-160 用 |
| src/test/fixtures.ts:340 | `serviceHealth` | 只是 export 多餘 | 檔內 :367-374 用 |
| src/api/auth.ts:7 | type `Role` | 真的沒人用 | 只有定義 |
| src/api/events.ts:25 | `JobSignal` | 只是 export 多餘 | 檔內 :114 用 |
| src/api/files.ts:20 | `RematchRefusal` | 只是 export 多餘 | 檔內 :27、:43 用 |
| src/api/inventory.ts:52 | `LibrarySort` | 只是 export 多餘 | 檔內 :63 用 |
| src/api/issues.ts:11 | `IssueType` | 真的沒人用 | 只有定義 |
| src/api/issues.ts:31 | `ReconcileSide` | 真的沒人用 | 只有定義 |
| src/api/issues.ts:34 | `IssueRefusal` | 只是 export 多餘 | 檔內 :40 用 |
| src/api/media.ts:17 | `RouteChoice` | 真的沒人用 | 只有定義 |
| src/api/plans.ts:15 | `PlanStatus` | 真的沒人用 | 只有定義 |
| src/api/plans.ts:21 | `Confidence` | 真的沒人用 | 只有定義（`resources.ts` 的 "Confidence" 是文案） |
| src/api/plans.ts:39 | `PlanRefusal` | 只是 export 多餘 | 檔內 :42 用 |
| src/api/review.ts:18 | `AuditSeries` | 真的沒人用 | 只有定義 |
| src/api/review.ts:50 | `ReviewRefusal` | 只是 export 多餘 | 檔內 :53 用 |
| src/api/rss.ts:29 | `SkipCode` | 真的沒人用 | 只有定義（其餘出現在 `resources.ts` 是 key 名 `skip`） |
| src/api/rss.ts:62 | `RssRefusal` | 只是 export 多餘 | 檔內 :65 用 |
| src/api/schema.d.ts:6 / 2212 / 5629 / 5630 | `paths`、`webhooks`、`$defs`、`operations` | 誤報 | 產生的檔（`pnpm gen:api`），不手改 |
| src/api/search.ts:13 | type `Tags` | 真的沒人用 | 只有定義（其他檔的 `Tags` 是別的東西或文案） |
| src/review/leadReason.ts:30 | `LeadCode` | 只是 export 多餘 | 檔內 :33 用 |
| src/routes.tsx:42 | `RouterContext` | 只是 export 多餘 | 檔內 :54 用 |
| src/setup/interfaceLogin.ts:115 | `OwnerUnfit` | 只是 export 多餘 | 檔內 :117、:172 用 |
| src/setup/interfaceLogin.ts:161 | `TakenLogin` | 只是 export 多餘 | 檔內 :180 用 |

補充：knip 預設把 `*.test.*` 當入口，所以「只有測試在用」的 export 它不報。我另寫腳本（`testonly.cjs`）找這一類並逐一確認：`internalRedirect`、`FAILURE_TEXT`、`AUTH_REJECTED_TEXT`、`createQueryClient`、`lacksScheme`、`loginProblems`、`takenLogin`、`COALESCE_MS` 都在同檔 production 有用，只是多一個給測試的 export，不算發現；只有 `TOTAL_STEPS` 沒有 production 消費者（D9）。`test/` 下的 fixture 與 helper 本來就只給測試用。

## i18n 掃描
- 方法：`i18n_scan.cjs`（第一版，用 regex 掃字串，被註解裡的撇號搞壞，作廢）→ `i18n_scan2.cjs`（用 TypeScript 編譯器 API 轉譯 `src/i18n/resources.ts` 取 zh-Hant 與 en 兩棵樹，扁平化，去掉 `_one`/`_other` 後綴得 2085 個基底 key；用 AST 取全部 production 檔的字串字面量與樣板字串開頭再配對）。後續 `i18n_scan3.cjs`、`i18n_scan4.cjs`（動態 key 後綴再驗）、`i18n_dupval.cjs`（相同值）、`testonly.cjs`。其中 `i18n_scan2.cjs`（主掃描，參數是 `web/` 路徑）與 `i18n_dupval.cjs` 留在本資料夾的 `scripts/`，其餘是一次性探查、沒留。
- 對稱：zh-Hant 2238 個葉節點、en 2238 個，雙邊差集為 0。這本來就被型別守著（`resources.ts:4-7` 的 `Translations<typeof zhHant>`），不算發現。
- 使用：2085 個基底 key 中，1523 個有字面量引用；562 個靠動態前綴（如 `` t(`jobs.event.${x}`) ``），一律視為可能被用；沒被使用的 key 為 0；只在測試被用的 key 為 0。
- 動態前綴的後綴再驗：562 個動態 key 的最後一段逐一檢查是否出現在含該前綴的檔、或 `schema.d.ts`/`api/*.ts` 的 enum 裡。5 個沒配到，全是誤報：`owner.carry.unfit.usernameShort` / `usernameColon`（值來自 `setup/interfaceLogin.ts:93,108-109` 的 `ReuseUnfit`，`OwnerStep.tsx:321` 動態組）、`media.files.jellyfin.foundCount` / `searchingCount` / `lostCount`（`media/FilesPanel.tsx:222` 的 `` `…${kind}Count` ``）。結果：0 個未使用 key。
- 局限：後綴驗證是「字串在對的檔出現過」，不證明該組合一定走得到；寬前綴（`jobs.event.` 27 個、`jobs.refusal.` 18 個…）若後端某 enum 值已刪、前端 key 仍在，檢查看不出。這幾組都有 `Record<…>`/`satisfies` 型別逼兩邊同步，風險低。
- 相同值掃描（en 值 ≥14 字、不同 key 整句相同，共 20 組）：多數合理（兩個頁面各自的標籤）；值得看的是 D5 的四個 key。`review.plan.refusal.action_not_allowed` / `episode_range_reversed` 與 `rematch.refusal.*` 同句，源頭是後端兩個 enum，不在本區塊範圍。

## 待複核疑點
- D3 的分隔符：`estimate()` 的範圍用 en dash 是故意的還是複製貼上碰巧？`searchResult.ts` 與其測試沒寫理由；要使用者拍板。
- `pages/InventoryPage.tsx:295-313` 手寫計時器的 debounce 與 `useDebounced`：它 debounce 的是「寫進 URL」這個副作用且要在卸載時清掉，看起來可能有意；`docs/progress.md` 我只用關鍵字 grep，沒讀完整段，不敢斷言。
- 「空狀態」那一塊 `grid justify-items-start gap-3 border-2 border-rule bg-well px-4 py-4`：`InventoryPage.tsx` 5 處、`JobsPage.tsx:179` 1 處（`grep -rn "justify-items-start gap-3 border-2"` 共 7 筆含另一處）；DESIGN.md:600 把「空狀態」寫成規格，但內容（一句話加一條連結）各有不同，是否抽 `EmptyState` 要看你想不想再統一內容結構。
- `pages/SetupPage.tsx:510-518` 與 `settings/ServiceConnection.tsx:70-76`：「套件內那台還在啟動就每 3 秒重測」的 effect 各寫一份（共用 `WAITING_RETEST_MS`）。`ServiceConnection.tsx` 註解說是「照精靈」，沒說為何不抽 hook。
- `formatSize`、`formatCount` 放在 `media/searchResult.ts`，卻被 `jobs/`、`issues/`、`rss/` 引用：擺放問題而不是重複，依任務定義不列為發現。
