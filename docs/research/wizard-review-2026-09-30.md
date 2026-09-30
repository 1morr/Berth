# 設定精靈審查（2026-09-30，main `a419467`）

M4 全部票做完之後，協調者用瀏覽器走了三條路（全新全選套件內、接配置正確的既有服務、接配置錯誤的既有服務），
再對照程式碼與成熟產品的做法。結論：**方向對，細節不能上線**——四類問題開成 M4 票 18–22。

## 測試環境（repo 外）

- `C:\Users\Roxy\berth-existing`：模擬「使用者原本就有」的服務。帳密、API key 與每台錯在哪見該目錄的
  `CREDENTIALS.md`；`setup.sh` 重建、`verify.py` 從 Berth 容器裡逐台核對。
  - `good/`（`ok-*`）：Jellyfin 12.1 `:48096`、qBittorrent 5.2.3 `:48080`、Prowlarr 2.6 `:48696`，媒體掛在
    `berth-trial/data` 的 `/data`——與 berth-trial 同一個宿主目錄，應一路綠。
  - `broken/`（`bad-*`）：Jellyfin 10.10.7 `:58096`；Jellyfin 12.1 媒體庫在 `/tv`、`/movies`（沒有 `/data`）
    `:58097`，另有非管理員帳號 `guest`；qBittorrent 4.3.9 `:58080`；qBittorrent 5.2.3 只掛 `/downloads`、留著一個
    指到 `/downloads/tv` 的 `berth-tv-shows` 分類 `:58081`；Prowlarr 1.0.1 `:59696`。
- 受測的 Berth 用 repo `deploy/` 的 compose 另起一份（改容器名、port、子網），`COMPOSE_PROFILES=` 空，
  `DATA_ROOT` 指 `berth-trial/data` 才能與 `good/` 共用 `/data`。**Windows 上 49696 被系統服務佔用**，別用。
- 踩過的坑：qBittorrent 5.x 登入成功回 `204` 空內容（4.x 是 `200 Ok.`），失敗 `401`（4.x 是 `200 Fails.`）；
  Git Bash 會把 `savePath=/downloads/tv` 這類參數改寫成 Windows 路徑（`MSYS_NO_PATHCONV=1`）；兩個 Berth 都開在
  `localhost` 不同 port 時瀏覽器共用 session cookie，一個用 `127.0.0.1` 開。

## 錯誤設定在哪裡被抓到

| 錯誤設定 | 在哪一頁 | 使用者看得懂怎麼修嗎 | 票 |
| --- | --- | --- | --- |
| 位址填 `localhost` | 頁 1、2、4，填的當下 | 能 | — |
| Jellyfin 10.10.7 | 頁 1，**登入時**（測連線仍綠） | 勉強：英文原文 | 18 |
| Jellyfin 非管理員 | 頁 1 | 能 | — |
| 擁有者成立後把位址改成另一台 Jellyfin | **沒擋**，存下來 | — | 18 |
| Jellyfin 媒體庫不在 `/data` | 頁 3 | 不能：compose 片段給的是 berth | 19 |
| 「新的 Berth 路徑」而 Jellyfin 沒掛 `/data` | 頁 3，`POST /Library/VirtualFolders/Paths: 404` | 不能：丟掉了 Jellyfin 的 `The path does not exist`，還建議手動加（同樣會失敗） | 19 |
| qBittorrent 沒掛 `/data` | **抓不到**：`download_path` 驗的是 Berth 自己剛建的目錄 | — | 19 |
| qBittorrent 舊分類衝突 | 頁 3 | 能（中文補法清楚，上面掛英文原文） | 21 |
| qBittorrent 4.3.9 | 頁 2 | 能，但連線卡綠、泊位卡紅 | 21 |
| qBittorrent 連錯 5 次被封 | 頁 2 | 大致能；「到它自己的介面解除」做不到 | 21 |
| Prowlarr 1.0.1 | 頁 4 | 不能：`/ping: response is not JSON`＋「連不上」 | 20 |
| 既有 Prowlarr 0 站 | **抓不到**：標「已完成」，精靈裡不能加站 | — | 20 |
| TMDB key 錯（401） | 頁 5 | 不能：手動步驟叫人查網路 | 21 |

## 對照成熟產品

| 面向 | 成熟做法 | Berth | 結論 |
| --- | --- | --- | --- |
| 媒體伺服器選定後能不能換 | Seerr 只支援一台，換＝重裝（[issue #2522](https://github.com/seerr-team/seerr/issues/2522)）；HA 擁有者憑證遺失要刪 `.storage` 重來（[onboarding](https://www.home-assistant.io/getting-started/onboarding)） | 鎖來源，但位址可換到別台 | 鎖對，要鎖到「同一台伺服器」（票 18） |
| 既有下載端的全域設定 | *arr 只建自己的分類、per-torrent 動作；全域只讀，不對就 Test 報錯（[第三方原始碼整理](https://notes.debridmediamanager.com/internals/qbittorrent-client-contract)） | 同 | 一致；未完成目錄可以只開在分類上（票 22） |
| 路徑不一致的偵測 | *arr 的 Test 不驗路徑，靠 Health 與匯入失敗（[Servarr System](https://wiki.servarr.com/radarr/system)） | 頁 3 當場探測＋硬鏈接 | Berth 較早，但漏了 qBittorrent 那一側（票 19） |
| Remote path mapping | TRaSH：Docker 下從源頭統一成單一 `/data`，mapping 是最後手段（[TRaSH](https://trash-guides.info/Sonarr/Tips/Sonarr-remote-path-mapping)、[Basic Setup](https://trash-guides.info/Downloaders/qBittorrent/Basic-Setup)） | 不做 | 一致；補法沿用 TRaSH 的說法 |
| 版本下限 | Sonarr 的 qBittorrent Test 低於下限直接失敗，「至少 X，你的是 Y」 | 三個服務各擋在不同時機 | 測連線當下擋、同一句型（票 18、20、21） |
| 錯誤訊息 | *arr 已知情況用人話掛在欄位上，未知例外才包原文；HA config flow 用錯誤代碼由前端翻譯（[config flow](https://developers.home-assistant.io/docs/core/integration/config_flow)） | 後端英文、HTTP 狀態碼、errno 當標題 | 代碼＋翻譯，原文收進「技術細節」（票 21） |
| 精靈導覽 | NN/g：描述性按鈕、可回上一步、可續做（[Wizards](https://www.nngroup.com/articles/wizards)） | 大致符合 | — |

TRaSH 對 qBittorrent「Keep incomplete torrents in」的立場是個人偏好，只提醒跨碟會退化成複製再刪除
（[Basic Setup](https://trash-guides.info/Downloaders/qBittorrent/Basic-Setup)）。
