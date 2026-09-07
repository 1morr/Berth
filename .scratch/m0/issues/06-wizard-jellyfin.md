# 06 — 精靈第 3 步：Jellyfin（套件內全自動 + 既有接入）

**Status:** done

**Blocked by:** 05

**讀:** plan §9.4、§9.5（既有 Jellyfin）、§8.2、§11.1（T0.6）；brief §16.3、§16.4、§20.7

## 做什麼

精靈第 3 步的兩條路徑。套件內：按一顆按鈕，Berth 跑完 plan §9.4 的九步序列，畫面逐步顯示進度與結果。既有：連線表單 + 測試連線 + 以管理員帳密登入建立 API key + 列出媒體庫與各自路徑 + 兩顆需二次確認的按鈕（加入 Berth 路徑、安裝 MergeVersions）。

既有 Jellyfin 的紅線：絕不自動建立媒體庫、不改既有 `LibraryOptions`、不呼叫 `DELETE /Items/*`、不建議搬媒體庫路徑。

## 驗收

- [x] `POST /api/setup/jellyfin/bootstrap` 跑完 §9.4 全序列，結束時 Jellyfin 有 Berth 管理員、Movies / TV / Anime 三個媒體庫（`EnableRealtimeMonitor=false`、`SeasonZeroDisplayName=Specials`、zh-TW metadata）、MergeVersions 已安裝
- [x] 建立媒體庫時的 `LibraryOptions.TypeOptions[].MetadataFetchers` 是設定值而非寫死（預設 TMDB），為 brief §10 的 TVDB【研究】（anime profile 改用 TVDB 季集來源）留一個切換點
- [x] API key 建立後存入 `settings.services.jellyfin`
- [x] 安裝插件後重啟 Jellyfin 並輪詢直到恢復；逾時給明確錯誤與可複製的手動步驟
- [x] `MergeMoviesTask` 與 `MergeEpisodesTask` 的 `Id`（不是 `Key`）存進 settings
- [x] 重按 bootstrap 不會重複建立媒體庫或重複安裝插件
- [x] 既有路徑：連線表單可測試連線、以管理員帳密登入取得 API key、列出媒體庫與路徑；掛 TVDB 插件的媒體庫顯示警告
- [x] 既有路徑：「加入 Berth 路徑」對選定媒體庫呼叫 `POST /Library/VirtualFolders/Paths?refreshLibrary=false`，舊路徑原地不動
- [x] 既有路徑：「安裝 MergeVersions」需二次確認並說明會重啟 Jellyfin
- [x] Jellyfin adapter 的 `Fake` 覆蓋兩條路徑，契約測試綠燈
- [x] 任一步失敗時畫面給出可複製的手動步驟，且該步可單獨重試

## Comments

### 對真 Jellyfin 的驗證（2026-09-07）

`jellyfin/jellyfin:10.11.11`，走真的 API 端點（`httpx.ASGITransport` 打真的 FastAPI app + 真的
`HttpJellyfinClient`），不是 Fake：

- 第一次 bootstrap：九步全 `ok`，**69 秒**（大半是插件下載與重啟）。事後直接查那台伺服器：
  使用者 `skipper`（`IsAdministrator=true`）、三個媒體庫各自 `EnableRealtimeMonitor=false`、
  `SeasonZeroDisplayName='Specials'`、`PreferredMetadataLanguage=zh-TW`、`MetadataCountryCode=TW`、
  `TypeOptions` 的 metadata fetcher 是 `TheMovieDb`；`Auth/Keys` 只有**一把** `Berth`；
  `/Plugins` 有 `Merge Versions 10.11.0.1`；`/Repositories` 有 `danieladov`。
- 第二次 bootstrap：**0.2 秒**，第 1 步 `ok`、其餘八步 `skipped`，沒有第二個媒體庫、沒有第二把 key、
  沒有第二次重啟。精靈的步驟隨之前進到 4。
- 既有路徑（同一台，另建一個使用者自己的 `Films` 媒體庫並掛上官方 TVDB 插件）：`connect` 取回
  API key（既有的那把，標成 `skipped`）、列出四個媒體庫與各自路徑、`Films` 的 `uses_tvdb=true`；
  「加入 Berth 路徑」把 `/data/library/films` 加上去而 `/data/nas-films` 原地不動，再按一次不重複；
  「安裝 MergeVersions」在已裝的情況下是 `skipped`；密碼打錯 → `api_key` 步驟 `failed`，原文
  `POST /Users/AuthenticateByName: 401`。

錄下來的回應在 `tests/fixtures/http/jellyfin/`，契約測試對它們跑。

### UI 實跑（playwright，深淺兩主題）

`scripts/fake_setup_server.py` 的 `bundled` / `failing` / `mixed` 三個情境：九步序列逐條顯示實測值、
失敗那一步就地變紅並展開原文與可複製的手動步驟、泊位 1 隨狀態轉綠 / 轉紅、既有路徑的媒體庫表格與
TVDB 警告、兩顆按鈕的二次確認。**深淺兩主題所有文字對比皆 ≥ 4.5:1**（逐元素量測，0 個未達標）。
390px 窄版無橫向捲動。

### 與票面不同的地方

- 驗收第 4 條字面寫「輪詢 `/System/Info/Public`」。實作輪詢 `/ScheduledTasks`——票 04 就發現
  `/System/Info/Public` 在伺服器還在載入時就回 200 了（plan §9.4 第 8 步、brief §20.7）。
- 「連線表單可測試連線」由第 2 步提供（位址欄與「測試連線」在纜繩上，票 05）。第 3 步只要那台
  Jellyfin 自己的管理員帳密。這一票另外把第 2 步的完成條件改成「每個服務都連得上」，所以位址填
  不對根本走不到第 3 步——兩個地方各放一份位址欄反而會讓人不知道該改哪一個。

### 留下的取捨

- `models.SetupStep` / `services.jellyfin.StepView` / `api.setup.StepOut` 三個同形狀的型別。
  這是 import-linter 的分層要求（`api` 不可 import `models`），不是疏忽；票 05 的 `SetupStatus`
  也是同一個形狀。
- `tests/fixtures/http/jellyfin/packages.merge-versions.json` 是 `GET /Packages` 的**子集**
  （只留 Merge Versions 那一筆，整份太大），不是逐位元組原文。已記在 fixture README。
