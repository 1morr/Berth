# 06e — 精靈：索引站與 TMDB 拆成兩個泊位；索引站看得到語言、試搜得到東西

**Status:** done

**Blocked by:** 06d（同一輪 `/impeccable onboard` shape 定下 5 格的泊位板與導覽；這張票照 shape 的結論實作）、05（試搜命令要用它立下的副作用標記）

**讀:** plan §9.3 第 5、6 步、§8.4；brief §16.3、§20.7（Prowlarr 端點）、§20.11；`web/src/setup/SourceStep.tsx`、`web/src/components/berths.ts`、`web/src/health/HealthBoard.tsx`、`web/src/components/TmdbNotice.tsx`；`berth/services/indexer.py`、`berth/adapters/prowlarr/`

## 做什麼

使用者 2026-09-24 重跑精靈時的回饋：泊位 3 叫「來源」，不寫 Prowlarr；同一頁又夾著 TMDB；看不到索引站是什麼語言；加完不知道到底搜不搜得到東西。

**拆成兩個泊位**（使用者拍板，brief §19）。泊位板從 4 格變 5 格：Jellyfin、qBittorrent、**Prowlarr**（索引站，第 5 步）、**TMDB**（第 6 步）、媒體庫路徑。每一格對應一個服務、用產品名，「來源」這個籠統的名字不再需要。

- `components/berths.ts` 的 `BERTHS` 與 `SOURCE_SLOT`、`setup/BerthBoard.tsx` 的 `sourceDetail`（「一格兩半，TMDB 走到之後換掉索引站數」）、`SetupPage.tsx` 裡 `STEP_INDEXER` 與 `STEP_TMDB` 共用一個分支、`TmdbNotice.tsx` 的泊位號、健康頁的 `HealthBoard.tsx`（它用 `BERTHS[3]` 當媒體庫那一格）都跟著改。`components/BerthBoard.tsx` 的「欄數寫死：泊位就是那四個」改成五個，版面在 390 上怎麼排由 06d 的 shape 決定。
- 既有服務的路徑（任一 Torznab 網址）時，那一格顯示實際的那一種（Prowlarr / Torznab），不寫死 Prowlarr。
- 探測到、還沒加站時，那一格的詳情寫「Prowlarr・尚未加入索引站」，不是 `—`（現在後端 `setup._verdict_prowlarr` 在套件內時回空字串）。

**索引站看得到是什麼**：Prowlarr 的 `indexer/schema` 每個定義都帶 `language`（`zh-TW`、`zh-CN`、`en-US`…）與 `description`（2026-09-24 在 Prowlarr 2.5.2 實測）。`adapters/prowlarr` 的 `IndexerDefinition` 目前只取 `privacy`，補上這兩個；勾選清單每一列顯示語言（照 UI 語言顯示語言名，不是代碼）與一句說明（說明是英文原文、不翻，同 Tags 的處理）。

**加入之後試搜**：Prowlarr 只搜得到已經加入的站（`GET /api/v1/search?query=&indexerIds=`），所以流程是「加入 → 試搜 → 不要的移除」，不是加入前試搜。

- 加入之後，這一格停在結果上（06d）：逐站的加入結果照舊，底下多一個試搜框，預設帶一個例子（例如 TMDB 趨勢上的第一部，或空白讓使用者填——shape 決定），逐站列出搜到幾筆與前三筆標題。
- 每一站可以**移除**（Prowlarr `DELETE /api/v1/indexer/{id}`；brief §20.7 還沒記這支，先以 Prowlarr 的 OpenAPI 查證再補進 §20.7）。移除要就地確認。
- 既有 Torznab 的那條路同樣可以試搜（打它自己的 `t=search`）。
- 試搜是新的 `services` 命令，標副作用等級 `read`（票 05 的標記）；它不寫任何東西。`setup` 的其他端點同樣只有 admin 進得來。

**元件要能搬到設定頁**（使用者 2026-09-25 拍板，票 06i）：精靈跑完之後，索引站的加站、移除、試搜與 TMDB 的重貼 key 住在設定頁，重用這張票做的元件。所以兩格的元件不要依賴精靈的頁面狀態（`SetupPage` 的覆寫、泊位板），資料與動作從 props 進來。

**預設清單拿掉 AniDex**：Prowlarr 2.5.2 的 `indexer/schema` 已經沒有它（2026-09-24 實測，十個預設站只找到九個）。`services/indexer.py` 的 `DEFAULT_INDEXERS`、plan §9.3 第 5 步、README 同步；brief §20.7 記一筆。

## 驗收

- [x] 泊位板 5 格，精靈與健康頁都是；泊位號、`TmdbNotice` 與所有寫死 `BERTHS[3]` 的地方跟著改（前端測試）
- [x] 索引站那一格探測後、加站前顯示「Prowlarr・尚未加入索引站」；既有 Torznab 顯示 Torznab
- [x] 勾選清單每一站有語言與說明（adapter 單元測試用 schema fixture；前端測試）
- [x] 加入後可以試搜，逐站顯示筆數與前三筆標題；一站失敗不影響其他站（整合測試用 Fake Prowlarr；前端測試）
- [x] 每一站可以移除，就地確認；移除後試搜不再打它（整合測試）
- [x] 預設清單沒有 AniDex，README 與 plan §9.3 同步
- [x] Prowlarr 的 `DELETE indexer` 與 schema 的 `language` / `description` 補進 brief §20.7 並附來源
- [x] 試搜命令有副作用標記（票 05 的閘門綠）
- [x] playwright 實跑：加站 → 試搜 → 移除一站 → 前往 TMDB，1280 與 390，附結果
- [x] zh-Hant 與 en 並列；plan §9.3、§9.5 同步
- [x] lint、type、test 綠燈

## Comments

**開工前實測（2026-09-25，試跑環境的 Prowlarr 2.5.2.5491）**：`indexer/schema` **仍有** `Anidex`（C# 內建實作，不是會被定義更新刪掉的 YAML），拿它去 `indexer/test` 回 502，anidex.info 直接打也是 502。票面寫的「已經沒有它」不成立；問使用者，選「照樣拿掉」，理由改寫成「站掛了」（brief §20.7）。同一輪量到空白查詢 `GET /api/v1/search?query=&indexerIds=<id>` 回各站最新的發佈（dmhy 80 筆、YTS 96 筆，約 1.3 秒），試搜的預設因此是**留白**；`DELETE /api/v1/indexer/{id}` 以 Prowlarr 的 OpenAPI 查證（回 200），沒有對試跑環境的站動手。

**紅燈先行**：adapter 三條（語言與說明、`delete_indexer`、`indexerIds`）、service 九條（含 Anidex 不在清單、逐站試搜一站失敗不影響其他站、試搜不寫任何東西與 `read` 標記、移除後試搜不再打它、移除最後一站回到第 6 步、既有與非預設站不移除）、`navigation.test.ts` 八條都先紅再綠；`indexer` 模組從 `BEFORE_M3` 豁免表拿掉，整個模組標完。code review 之後補的「列消失焦點落在下一列」拿掉 `ref` 確認會紅。

**playwright 實跑（fake `bundled`，全新精靈）**：
- 1280：第 6 步板上 BTH 4 寫「Prowlarr · 尚未加入索引站」、BTH 5 未指派，一列五格；勾選清單每一站有語言名（中文（台灣）/ 英文（美國））與原文說明 → 加入九站（四站紅）→ 試搜「Frieren」：dmhy 7 筆、ACG.RIP 14 筆、Mikan 失敗（502，其餘照常）、YTS 5 筆、TPB 12 筆，各列前三筆 → 移除 YTS：第一下只展開確認、焦點進確認區，確定後那一列消失、板上變「Prowlarr · 4 個索引站」→ 前往下一個泊位是 TMDB（BTH 5 待靠泊、「憑證 待驗證」）。水平溢出 −15（捲軸寬）。
- 390：回頭到索引站再試搜（留白），板排 2+2+1（前四格 187px、第五格 375px 橫跨），沒有水平溢出，試搜列與移除鍵在窄版一欄；EN 下板寫「Prowlarr · 4 indexers」、語言「Chinese (Taiwan)」。走完精靈登入後健康頁五格，TMDB 那一格「已驗證」，console 沒有錯誤。
- 截圖在 `.local/screens/m3-06e/`（不進版控）。`pnpm -C web e2e wizard` 改成「加入 → 試搜 → 移除 → TMDB」，passed。

**code review（Standards / Spec 兩軸）處理了的**：The Focus Takes The Next Row Rule（試搜清單加 `useFocusAfterRemoval`、列是 `<article tabIndex={-1}>`、`sr-only` 說「已從 Prowlarr 移除 X」）；板上「尚未加入索引站」只在判定真的是零站時說（缺 key、沒部署、還在探時詳情是空的，原本會把有站的 Prowlarr 說錯）；`apply_default_indexers` 的反向命令改成 `None`（一次加好幾站還設登入，移除一次只撤一站）；`remove_indexer` 只移除預設站（使用者自己加的站 Berth 加不回去，標的反向命令就不成立）；plan 的 API 表、§9.3 的「十個」、service 的 docstring、CONTEXT.md 的 Health Check、完成頁「設定 → 來源」的字。

**code review 未處理的發現**（判斷題）：
- 泊位 slot 鍵仍叫 `'prowlarr'`，而那一格也可能是 Torznab；`BerthBoard` / `HealthBoard` 各自以 `if slot === 'tmdb' / 'library'` 分支（Repeated Switches）。改 slot 鍵會連 `ServiceKind` 與後端的判定一起動，06i 把兩格搬到設定頁時再看要不要收成一張表。
- `remove_indexer` 與 `apply_default_indexers` 各寫一份「非套件內就拒絕」的守門；`(indexer_id, definition_name, name)` 一起穿過 `_search_site` 與 `SiteSearch`（Data Clumps）。兩處都小，先不抽。
- 「站」與「索引站」兩個詞混用（`SiteSearch`、`TrialSite` 對 `IndexerOption`）。前端的 `IndexerSearch` 型別名與後端 adapter 協定撞名，已改成 `TrialSearchResult`。
- 06d 留下的 `SetupPage` 十個 mutation 各寫 `onMutate: hold` 沒收；「步驟 → 頁 / 泊位」四張表收成兩張（`pageOf` 刪掉、`REVISIT_PAGE` 併進以步驟號查的 `REVISIT`）。
