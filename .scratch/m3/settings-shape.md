# 設定頁五頁（票 06i，2026-09-25 `/impeccable shape`）

使用者拍板三題：**後端沿用 `setup/*`**、**單欄區塊重用精靈的內層元件**、**磁碟門檻住 qBittorrent 頁**。
慣例：Jellyseerr（設定分頁與精靈共用表單元件，不共用精靈的框）、Sonarr / Radarr / Prowlarr（按領域分頁）。

## 誰、要做什麼

- **admin**，精靈跑完之後、某件事變了才來：qBittorrent 密碼改了、想多加一個索引站、TMDB key 換了、
  某個服務紅燈從健康頁點過來。Operate 模式：進來、改一件事、看到它生效、離開。
- **成功**＝在同一頁看到改完之後的結果（纜繩那一行、健康卡的狀態），不必回精靈、不必猜有沒有存。

## 結構

- 分頁照泊位板的順序：`Jellyfin | qBittorrent | 媒體庫路徑 | 索引站 | TMDB`
  → `/settings/jellyfin`、`/settings/qbittorrent`、`/settings/routes`（不變）、`/settings/indexers`、`/settings/tmdb`。
  `/settings` 落在 `/settings/jellyfin`；`/settings/services` 刪掉（站內路徑，不是對外介面）。
  泊位 → 設定頁的對應住在 `components/berths.ts`，同一份表導出分頁、健康頁與各處提示的連結。
- 每一頁：AppShell + 分頁列 + 標題 + 單欄區塊（`max-w-3xl`），與現在的服務頁同一個骨架。
  精靈的剖面、泊位板、「之後再說」、上一個 / 下一個**不**帶過來。

| 頁 | 區塊（由上而下） | 重用的精靈元件 |
| --- | --- | --- |
| Jellyfin | 健康卡 + 測試連線；既有：位址、重新登入取得 API key；對外網址 | `MooringLine` 的連線表單、`JellyfinExisting` 的登入表單 |
| qBittorrent | 健康卡 + 測試連線；既有：位址與帳密；建議設定（差異 + 還原）；磁碟空間門檻 | 連線表單 |
| 媒體庫路徑 | 不變（票 14） | — |
| 索引站 | 健康卡 + 測試連線；套件內：預設站勾選加入 + 試搜 + 移除；既有：Prowlarr / Torznab 位址與 key + 試搜 | `DefaultIndexers`、`ExistingIndexer`、`TrialSearch` |
| TMDB | 重貼 key 並測試，那一條纜繩的結果 | `TmdbKey` |

- **套件內的服務沒有位址表單**：位址是 compose 決定的，帳密是 Berth 寫進去的；那一格說出這件事，
  修的路在健康卡（紅燈時的指令）。只有既有服務給表單——與精靈第 2 步同一條規則（`needsConnectionForm`）。
- 表單送出之後同一個服務的健康卡跟著重測，結果就在上面那張卡上。

## 帶人回來的連結

`TmdbNotice`、`IndexerNotice`、`RoutePicker`、健康頁紅燈的「到設定」、原服務頁的「改位址或憑證」
一律到設定頁的那一頁；只有 admin 看得到連結，一般使用者看到「請管理員…」（原 `SetupHint` 的規則，改名 `SettingsHint`）。
精靈跑完之後打開 `/setup` 導向 `/settings`；`?berth=`、`revisited`、`setup.exit` 刪掉。

## 後端

設定頁呼叫同一批 `setup/*` 端點：命令冪等，精靈跑完之後門禁只放行 admin（`api/gate.py`），
`test_auth_api` 的表已涵蓋。不開新端點；plan §6 寫明「精靈跑完之後 `setup/*` 就是設定的寫入端點」。

## 不做

- 套件內 Jellyfin 的媒體庫清單（06f）、既有 Jellyfin 的「加入 Berth 路徑」不搬過來：改名刪除在 Jellyfin，
  Route 在媒體庫路徑頁；要在設定頁增媒體庫另開票。
- 從套件內改接既有服務（反之亦然）：那是重新部署，不在設定頁。
