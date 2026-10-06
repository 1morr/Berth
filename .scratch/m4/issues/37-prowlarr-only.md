# 37 — BTH 4 只支援 Prowlarr：拿掉通用 Torznab 端點

**Status:** done

**Blocked by:** 33（兩張都改寫 brief §16.4，33 先定好定義）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（§D 全部，那張「會影響的地方」表就是清單；改進清單 P1-9）；brief §19「精靈審計後的八項」D3、§3、§16.3、§16.4、§20.7 與 §20 的 Jackett 結論；plan §4、§8.4、§9.3

## 為什麼

- **D3 拍板**：拿掉通用 Torznab 端點與 Jackett。這推翻 brief §3「只依賴 Torznab 協定、支援 Jackett」。
- Torznab 路徑本來就缺頁 4 最核心的能力：沒有站清單、不能加站、不能測站、沒有版本下限。整條 `kind` 分岔散在設定、API、services、health 與前端。
- 泊位名改成「Prowlarr」，與 Jellyfin、qBittorrent 兩格一致。

## 做什麼

1. 刪 Torznab 的 adapter（`TorznabSearch`、client、fake、caps）、`IndexerKind` 與 `kind` 欄位、services 與 health 裡的分岔、相關 fixture 與測試。
   Prowlarr 搜尋若共用 Torznab 的 session 或解析器，留它需要的那部分。
2. **資料格式是破壞性變更**（D3 已拍板）：寫一支資料 migration，把已存 `kind="torznab"` 的索引站設定清掉，讓頁 4 回到待處理。先例是 M4 的 `setup_choices` migration。
3. 前端：頁 4 與設定頁拿掉「接法」單選與 Torznab 說明；泊位名、`board.*`、`indexer.title`、完成頁等改成「Prowlarr」；約 8 對 zh-Hant / en 文案。
4. API：`IndexerConnectIn.kind` 拿掉，更新 OpenAPI 型別。CHANGELOG 記破壞性變更。
5. 文件同一個 commit 改：brief §3 表格與頂端那句、§16.4、§20 的 Jackett 結論（標「已不採用」並保留來源）；plan §4、§8.4、§9.3；README、`CONTEXT.md:122`、`PRODUCT.md`。

## 驗收

- [x] 整合測試：存著 `torznab` 設定的資料庫跑 migration 之後，頁 4 是待處理，搜尋回「沒有設定」而不是 500
- [x] `grep -ri torznab` 在 `berth/`、`web/src/`、`tests/` 只剩 Prowlarr 搜尋自己需要的部分，每一處在 Comments 說明為什麼留著
- [x] 前端：精靈與設定頁沒有 Torznab 與 Jackett；泊位名是「Prowlarr」（zh-Hant 與 en）
- [x] 文件已改；progress.md「偏差與決定」記一行
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e、真服務 e2e 綠燈

## Comments

**2026-10-07 實作紀錄**

- 後端：刪 `berth/adapters/torznab/`、`adapters/indexer/torznab.py`、`IndexerKind`、`IndexerSettings.kind`、
  `IndexerConnectIn.kind` / `IndexerSetupOut.kind`、`ServiceClientFactory.torznab()`；`indexer_search(base_url, api_key)`。
  頁 4 既有那一條纜繩的 key 改成常數 `PROWLARR_STEP`。`health._origin` 只剩 `setup.origin_of`，併進 `_view`。
- **連帶刪掉 tmdbid 搜尋**：`IndexerSearch.capabilities()`、`SearchCapability`、`SearchQuery.tmdb_id / kind`、
  `services.search._queries` 與 `IndexerProblem.NO_SEARCH` / `StepFailure.NO_SEARCH`。它們只為 Torznab 的
  `t=caps` 存在，`ProwlarrSearch.capabilities()` 恆回「可搜、沒有 tmdbid」；連不上改由 `sites()`（`GET /api/v1/indexer`）
  先擋，行為同。`SiteSearchOut.indexer_id` 一律是整數（單一端點算一站、沒有 id 的情況沒了）。
- migration `b4ca280eaeca`：`kind="torznab"` 的安裝清空位址與 key、拿掉 `setup.choices.prowlarr`、頁 4 的纜繩、
  跳過與介面登入；其餘安裝只少 `kind`。降版不還原（CHANGELOG 記破壞性）。
- 驗收測試 `tests/integration/test_prowlarr_only.py`：停在前一版、精靈跑完再改成接 Jackett，升到 head 之後
  `current_step == 4`、`read_indexer_status` 是還沒選、`search_torrents` 是 `not_configured`，經 HTTP 的
  `/api/search` 是 200 加 `not_configured`。變異：migration 不清 Torznab 時紅（`assert 6 == 4`），還原綠。
- 前端（sonnet 子代理照計畫做）：頁 4 與設定頁拿掉「接法」單選；泊位、`indexer.title`、剖面標題、完成頁的
  跳過清單與「設定 → Prowlarr」、設定頁標題（「Prowlarr 設定」，票面沒列，與另兩頁「X 設定」一致）改成 Prowlarr；
  泊位詳情列拿掉產品名前綴（「既有 · 2 個索引站」）；剖面「接法」那一列的既有值是新 key `indexer.cutaway.existing`。
- 實跑（playwright，`mixed` 情境走到頁 4）：泊位名 Prowlarr、詳情列「既有 · 2 個索引站」、既有表單沒有單選，
  頁面文字沒有 Torznab / Jackett；截圖在 scratchpad（`t37-page4-*.png`）。

- 真服務 e2e（`uv run --env-file .env python -m tests.e2e.stack`）：第一輪 20 passed、3 failed，三條都在
  `test_3_m2_repair`，原因是 Jellyfin 回 `ReadError` 與 `503 still loading`。`test_2` 最後一支 `docker stop/start`
  Jellyfin，它 17:30:49 起來後 17:31:02 又重啟一次；`back()` 等到第一次就放行，`test_3` 撞上第二次。這兩個模組
  這次沒動，是既有的時序競爭（沒開票）。第二輪 23 passed（18:22）。

**`grep -ri torznab` 留下的（`berth/`、`web/src/`、`tests/`）**

- `berth/adapters/indexer/__init__.py:6`、`prowlarr.py:3`：說明搜尋為什麼走 REST（Prowlarr 不提供跨站聚合 Torznab）。
- `berth/migrations/versions/b4ca280eaeca_m4_prowlarr_only.py`：舊資料的值就叫 `torznab`。
- `tests/integration/test_prowlarr_only.py`：造舊資料、斷言被清掉。
- `web/src/pages/SetupPage.services.test.tsx:1646,1648`：反向斷言既有表單沒有 Torznab。
- `web/src/api/schema.d.ts` 無。

**code-review 未處理的發現**

- Standards：`IndexerMode` 剩 `'bundled' | 'prowlarr'`，`'prowlarr'` 其實是「既有」、`modeOf` 近於 `origin` 改名；
  前端照舊寫死 `'prowlarr'` 步驟鍵（與 `'prowlarr_login'` 同一寫法）；`test_setup_choice.py`、`test_prowlarr_version_floor.py`
  仍用字串 `"prowlarr"`。都是改名題，不影響行為，留著。
- Standards：`test_prowlarr_only.py` 的 `_upgrade_to` / `_sqlite` 與 `test_database.py` 的同名 helper 重複；它驗的是
  migration 之後的服務與 API 行為，與 `test_database.py` 只驗 JSON 形狀不同，所以另開檔。
