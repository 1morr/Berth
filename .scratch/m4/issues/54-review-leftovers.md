# 54 — code-review 遺留與過期 i18n

**Status:** done

**Blocked by:** 37、39（設定頁索引站與頁 4 的改動先落地）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（§A3「code-review 留下沒處理的」與「過期的 i18n」）；票 15、19、26、27、31 的 `## Comments`；`PRODUCT.md`、`DESIGN.md`

## 為什麼

審計的 §A3 列了一批各票 code-review 或 audit 留下、沒有票的項目，不在改進清單裡。使用者 2026-10-06 決定另開這一張收掉。

## 做什麼

逐條處理，先確認前面的票是不是已經順手修掉；能寫出失效條件的才修（全域規則：沒有 repro 就不修）。

1. 票 19：探針 torrent 在 `finally` 刪除失敗時會留在使用者的 qBittorrent。
2. 票 26：帳號被拒，或兩次 `setPreferences` 之間斷線時，qBittorrent 會留下「原帳號＋新密碼」。
3. 票 27：設定頁索引站的 `IndexerActions` 沒跟著改（每次重讀 key、已有站算數）。
4. 票 15：audit P2——`radiogroup` 沒有名字、五處 `truncate`。
5. 票 31：媒體庫深連結對 `host.docker.internal` 的問題。
6. `jellyfin.step.*` 等沒有引用處的 i18n 鍵：刪掉，並讓 `resources.test.ts`（或同類的閘門）擋未引用的鍵；做不到就在 Comments 說明。

## 驗收

- [x] 每一條在 Comments 有結論（已修＋測試／已由 NN 處理／不修＋理由）
- [x] 修掉的每一條都有先紅後綠的測試
- [x] 若加了未引用 i18n 鍵的閘門，在測試檔內做雙向變異驗證
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

### 逐條結論（2026-10-07，開工 `5cf03c1`）

| # | 結論 | 測試 |
| --- | --- | --- |
| 1 票 19 探針刪不掉 | **不修**（見下） | — |
| 2 票 26 「原帳號＋新密碼」 | **不修**（見下） | — |
| 3 票 27 設定頁 `IndexerActions` | **已修**：讀不到清單（`indexers.error`）時與精靈頁 4 同一段 `ReadFailed`，「重新讀取」打同一支 `POST /setup/services/prowlarr/test`（`restart: true`）；舊的 `Unreachable`（「連不上套件內的 Prowlarr…跳過這一步」＋`docker compose ps/logs`）刪掉。「已有站算數」那一半是精靈的前進條件，設定頁沒有前進鍵，不必改 | `IndexerSettingsPage.test.tsx`〈站的清單讀不到〉 |
| 4 票 15 `radiogroup`、`truncate` | **已修**：拿掉沒有名字的 `role="radiogroup"`（外層 `fieldset` 由 legend 命名），radio 的名字只剩標題（`aria-labelledby`）、說明走 `aria-describedby`；四處 `truncate`（泊位板兩處、連線測試那一行、健康卡位址）改 `wrap-anywhere`。另兩處（`RouteStep`、`StepLine`）已由票 15 的 critique 處理 | `ServiceChoice.test.tsx`〈兩格的名字〉；`wrapping.test.ts` 加擋 `truncate`（檔內雙向） |
| 5 票 31 深連結 `host.docker.internal` | **已修**：`jellyfinBase` 對 Berth 連過去的位址走 `browserReachable`（`host.docker.internal` 換瀏覽器主機名、compose 主機名不給），管理員填的對外網址照用；完成頁原本的那一份 `jellyfinWeb` 併進來刪掉。code-review 另抓到頁 3 建媒體庫失敗的手動步驟用的是 `jellyfin.base_url`（套件內是 `http://jellyfin:8096`），改走同一份推導 | `jellyfinLink.test.ts` 三條；`SetupPage.jellyfin.test.tsx`〈建媒體庫那一步失敗就停〉改成期待瀏覽器開得了的位址 |
| 6 沒有引用處的 i18n 鍵 | **已修**：刪 41 個鍵（zh-Hant 與 en 各一份）；`jellyfinSteps.ts` 的 `STEP_LABEL`／`STEP_FIX`／`STEP_ENDPOINT`／`manualSteps` 只有 `.libraries` 被讀，連同 `isJellyfinStep`、`JELLYFIN_STEPS` 一起刪，`auditCopy.test.ts` 守 `jellyfin.fix.configuration` 的那一條跟著刪 | `resources.test.ts`〈unreferenced keys〉：TypeScript 語法樹取字面值與樣板字串，檔內雙向（註解提到不算、四種寫法都認、沒有命名空間的樣板不算）。**擋不住**查表裡從沒被讀的那一格（表本身就是引用處），寫在測試的說明裡 |

**第 1 條不修的理由**：失效條件寫得出——探針答完、`finally` 移除那一下 qBittorrent 斷線（重啟、網路斷）：例外蓋掉已得到的答案，探針留在那一台（停住、沒有分類與 tag、檔案已被呼叫端刪掉，poller 看不到）。但兩條修法的代價都大過效益：

- 下一次探針前掃掉 `.berth-probe-*`：會刪不是這一輪加的 torrent，票 33 的寫入白名單（`test_setup_owned_writes.py`，`delete_torrent` 只准 `made.probes`）要放寬。
- 刪不掉時把 hash 記進設定、下一次補刪（照票 47 `added_sites` 的做法）：只動 Berth 加的，但 adapter 層的純函式要開始寫設定，白名單測試也要跨輪記憶。

斷線當下例外照實浮出（連不上），不是錯的答案。brief §16.4 物件表那一列補上「答完之後移除那一下斷線時可能殘留」，處理方式照舊手動刪。要不要做補刪由使用者決定。

**第 2 條不修的理由**：前端照 qBittorrent 的規則先擋（`carriedUnfit`／`LOGIN_RULES`），剩下的只有繞過前端直打 API，或兩次 `setPreferences` 之間斷線。Berth 不知道原本的密碼（全新的套件內那一台是隨機的臨時密碼），補償寫入做不到；只寫套件內那一台，Berth 連它靠白名單。之後的結論：全新那一台再測時回到 `pending`（要再設一次，蓋過去）；保留 config 重裝的那一台會被當成「它自己設過」記成 `skipped`，帳號是舊的、密碼是使用者剛填的——兩樣使用者都知道，登得進去。

### 驗證

- 全部檢查（`uv run pre-commit run --all-files`）：全部 Passed。
- vitest：88 檔 1388 條全綠；pytest 3620 passed（後端沒改）；前端 e2e（`pnpm build && pnpm e2e`）35 passed——改完 `RouteStep` 後第一次跑有 1 條失敗、輸出沒留下，再跑兩次都全綠。
- playwright 實跑（演練情境 `healthy`、`bundled`，跑完關掉）：390 寬的 `/health`、`/settings/indexers`、`/settings/qbittorrent` 沒有橫向捲動、沒有被截的 `.value`，服務卡位址完整；頁 1 沒有 `radiogroup`，兩格 radio 的名字是「套件內」「既有」、說明另外念。設定頁讀不到清單的那一種演練情境演不出來，由 vitest 守。

### code-review（`5cf03c1` 起，兩軸 opus）

- 已處理：頁 3 手動步驟的位址（見第 5 條）；`resources.test.ts` 說明裡已刪的例子與一句沒有閘門的「要靠消費點歸零時一起刪」；`useId` 的名字（`cardId`）；plan §9.4「畫面照它列」；brief §16.4 那一列；第 1、2 條理由的措辭（Spec 軸指出的另一條修法與 `skipped` 的情形）。
- 沒處理（判斷題）：設定頁的「重新讀取」與連線區的「重新測試」是同一支的兩個 mutation（錯誤各畫各的）；`inventory/jellyfinLink` 從 `setup/serviceWeb` 拿 `browserReachable`，兩個目錄互相 import（前端沒有成文的分層規則）；radio 說明那一段 `<span>` 裡有 `<div>`（`<label>` 裡放 `<div>` 是原本就有的）；套件內 Prowlarr 真的掛掉時設定頁不再給 `docker compose ps/logs`（與精靈頁 4 一致）。
