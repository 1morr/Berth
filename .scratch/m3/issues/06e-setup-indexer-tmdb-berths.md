# 06e — 精靈：索引站與 TMDB 拆成兩個泊位；索引站看得到語言、試搜得到東西

**Status:** ready-for-agent

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

**預設清單拿掉 AniDex**：Prowlarr 2.5.2 的 `indexer/schema` 已經沒有它（2026-09-24 實測，十個預設站只找到九個）。`services/indexer.py` 的 `DEFAULT_INDEXERS`、plan §9.3 第 5 步、README 同步；brief §20.7 記一筆。

## 驗收

- [ ] 泊位板 5 格，精靈與健康頁都是；泊位號、`TmdbNotice` 與所有寫死 `BERTHS[3]` 的地方跟著改（前端測試）
- [ ] 索引站那一格探測後、加站前顯示「Prowlarr・尚未加入索引站」；既有 Torznab 顯示 Torznab
- [ ] 勾選清單每一站有語言與說明（adapter 單元測試用 schema fixture；前端測試）
- [ ] 加入後可以試搜，逐站顯示筆數與前三筆標題；一站失敗不影響其他站（整合測試用 Fake Prowlarr；前端測試）
- [ ] 每一站可以移除，就地確認；移除後試搜不再打它（整合測試）
- [ ] 預設清單沒有 AniDex，README 與 plan §9.3 同步
- [ ] Prowlarr 的 `DELETE indexer` 與 schema 的 `language` / `description` 補進 brief §20.7 並附來源
- [ ] 試搜命令有副作用標記（票 05 的閘門綠）
- [ ] playwright 實跑：加站 → 試搜 → 移除一站 → 前往 TMDB，1280 與 390，附結果
- [ ] zh-Hant 與 en 並列；plan §9.3、§9.5 同步
- [ ] lint、type、test 綠燈
