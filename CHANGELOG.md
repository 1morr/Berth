# Changelog

本專案所有重要的變更都記在這個檔案。

格式依循 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，版本號依循 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

## [Unreleased]

### Security

- **log 與錯誤訊息裡的網址不再帶 query 的值**（M4 票 76）：之前 httpx 的 INFO log 把每個對外請求的整條網址印進
  `docker logs`，包括 Mikan 聚合 feed 的個人 `token`、TMDB v3 的 `api_key`、Prowlarr 下載連結的 `apikey`；RSS 抓不到時
  的錯誤原文（Feed 列表上的那一句）也帶整條網址。現在 query 的每一個值都換成 `***`（`token=***`），不分參數名；沒有
  query 的網址照常完整出現。uvicorn 的 access log 同樣處理。**之前版本留下的 log 可能含 RSS token，建議到 Mikan 重新產生
  token**：舊網址隨之失效，Berth 裡那個 Feed 要刪掉、用新網址重加（目前不能直接改網址）。

### Changed

- **搜尋跳過請求預算放不下的站，其他站照問**（M4 票 77）：之前索引站背後有一站（例如被 RSS 用完的 Mikan）放不下
  這一批，整次搜尋一站都不問；現在只問放得下的站，結果下面「這次沒問」列出跳過的站與多久之後放得下。每一站都
  放不下才是原本的「等請求預算」，時間改說最早有一站放得下的時刻，不再貼後端的英文原文。API：`GET /search` 多
  `skipped`（`site`、`indexers`、`until`），`retry_at` 的意思改成最早有一站放得下；`detail` 在 `budget_exhausted`
  時是空的。
- **README 開頭說明為什麼有 Berth、能做什麼**（M4 票 75）：兩份 README 多〈Why Berth〉與〈What it does〉兩節，
  原本開頭那段的內容併進條列。`docs/guide/upgrading.md` 拿掉〈From 0.2.0 (the zip)〉：目前沒有從 0.2.0 升級的使用者
  （使用者 2026-10-09 決定）；下面 0.2.1 那段提到它的地方照歷史紀錄留著。
- **README〈Status & known limitations〉縮成〈Status〉**：拿掉連到內部票的「已知問題」與「上一輪審計之後已修好」，
  只留支援的服務、通知、實測平台與「不要開到公網」；修好了什麼看 CHANGELOG。
- **關機時背景工作先把手上那一輪做完**（M4 票 71b）：原本停止容器會打斷正在跑的輪詢、規劃、入庫，偶爾留下一條沒
  關的資料庫連線；現在等那一輪做完才停（迴圈幾乎都在等待，多半不必等）。
- **RSS 綁定一律補舊集，拿掉「同時補下載舊集」勾選**（M4 票 78，brief §15）：手動綁定與作品頁的 Mikan 訂閱
  照自動綁定的做法整季補齊，鍵改成「綁定並送出」與「訂閱並送出」。**API 破壞性變更**：
  `PUT /rss/series/{id}/binding` 與 `POST /rss/subscriptions/mikan` 拿掉 `backfill`（多送的欄位被忽略）。
  **資料庫 migration `d71e4b9a3c58`**：刪 `rss_series.passed_before`；當初因取消勾選而略過的舊集放回去——
  綁著的下一輪輪詢照常去重後送出，解綁了的回到待綁定。降版只把欄位加回來，不改回略過。
- **設定頁的 Jellyfin 連線改成唯讀摘要**（M4 票 78）：來源、位址、版本、狀態，與為什麼換不成另一台；不再畫
  選不了的「套件內／既有」卡片。既有的那一台照舊可以改位址。
- **設定頁的介面登入是一般的改帳密表單**（M4 票 78）：qBittorrent 與 Prowlarr 那一區說出目前的帳號，帳號、
  新密碼、再輸入一次、「儲存」。「沿用 Jellyfin 帳密」只留在精靈裡。

## [0.2.1] - 2026-10-09

**部署只要 compose 檔加 `.env`**（M4 票 70、71，使用者 2026-10-09 拍板，推翻 0.2.0 的 release 附件）：貼進 Unraid
的 Compose Manager，或放進任何一個資料夾，`docker compose up -d`。不下載 zip、不 clone、旁邊不放別的檔案。image
是 `ghcr.io/1morr/berth:0.2.1`，同時是 `:0.2` 與 `:latest`。

**從 0.2.0 升級**（[docs/guide/upgrading.md](docs/guide/upgrading.md)〈From 0.2.0 (the zip)〉）：

- **換掉整個 `docker-compose.yml`**，用 README 連到的 `v0.2.1` 那一份，再 `docker compose pull && docker compose up -d`。
  qBittorrent 的白名單腳本改成寫在 compose 檔裡，`preseed/` 目錄不再使用，新檔起來之後可以刪掉。只換 image、留著
  舊 compose 也照常能跑（舊檔仍掛 `./preseed/`），但之後的版本只照新寫法說明。
- **需要 Docker Compose 2.23.1 以上**（`docker compose version`）：compose 檔用了頂層 `configs` 的 `content`。
- `.env` 不用改，`.env.example` 沒有新變數。**Unraid 上 `DATA_ROOT`、`CONFIG_ROOT` 一定要是絕對路徑**：Compose
  Manager 把 stack 放在隨身碟上，`./data`、`./config` 會寫到隨身碟。
- 沒有資料庫 migration、沒有 API 變更。

### Changed

- **部署檔**：`deploy/docker-compose.yml` 以頂層 `configs.qbittorrent-preseed` 內嵌白名單腳本，寫進
  `/custom-cont-init.d/10-berth.sh`、`mode: 0555`（brief §20.18：linuxserver 的 init 只跑有執行位元的檔）；拿掉
  `./preseed/qbittorrent` 那條掛載與 `deploy/preseed/`。compose 裡不再有任何相對路徑。`.env.example` 的註解寫明
  Unraid / Compose Manager 上兩個根要用絕對路徑。
- **README 與 `docs/guide/`**：安裝改成取得兩個檔 → 改幾個值 → `up -d`，連結指向這一版 tag 底下的原始檔；
  `requirements.md`〈Unraid〉改成 Compose Manager 的貼上做法（Add New Stack → Edit Stack 貼 compose → ENV File 貼
  `.env` → Compose Up），不再提 Indirect Path 與 `berth-deploy` 目錄。
- **套件內 qBittorrent 要帳密時的說明**多一種原因：清單裡沒有 `/32` 那一行時，多半是 compose 沒完整複製，請
  重新完整複製再 `docker compose up -d --force-recreate qbittorrent`。zh-Hant 與 en 都改。
- **rootless Docker 的說明**（M4 票 42，Ubuntu 26.04 實跑）：README〈Install〉、`docs/guide/requirements.md` 新增
  〈Rootless Docker〉、`docs/guide/existing-services.md`〈Addresses〉、部署檔 `.env.example` 與 compose 的註解。rootless 上
  `PUID` / `PGID` 要填 `0` / `0`（填 `id -u` 時宿主上的自己寫不進 `DATA_ROOT`），既有服務的位址要填宿主的區網 IP
  （`host.docker.internal` 連不到宿主）。image 不變，部署檔只改了註解；不是 rootless 的部署不用改 `.env`。

### Removed

- **release 附件 `berth-deploy.zip` / `berth-deploy-<版本>.zip`**：打包腳本、它的測試與 release workflow 的附件
  步驟都拿掉。Release 頁照常建，內容是這一段 CHANGELOG。0.2.0 的 Release 上那兩個 zip 留著，但
  `releases/latest/download/berth-deploy.zip` 從 0.2.1 起找不到檔案（最新的正式版沒有附件）。

### Fixed

- **精靈頁 5 回頭看的說明不再說測不過的 TMDB key 照樣存下**（M4 票 58 發佈後實跑看到）：票 45 之後只有測過的 key
  才存，測不過時原本那一把照樣在用；zh-Hant 與 en 兩句都改。

## [0.2.0] - 2026-10-09

**公開 beta**：`ghcr.io/1morr/berth:0.2.0`，同時是 `:0.2` 與 `:latest`。部署檔第一次以 release 附件發佈：
`https://github.com/1morr/Berth/releases/latest/download/berth-deploy.zip`（README〈Install〉）。M4 的通知與巡檢
還沒做；這一版收的是 0.1.0 之後兩輪試跑與審計的修補（M4 票 43–60）。

**測過的平台**：Windows Docker Desktop（每一輪試跑與審計都在這裡跑）、Unraid 7.1（M4 票 55：套件內三個
服務、與既有的 Emby 並存、硬鏈接過 mover）。其他 Linux 發行版與 NAS 還沒有人實跑。已知限制在
README〈[Status](README.md#status)〉。

**從 0.1.0 升級**：照 [docs/guide/upgrading.md](docs/guide/upgrading.md)，**下載 0.2.0 的 zip 解壓蓋過原本的部署
目錄**，再 `docker compose pull && docker compose up -d`。0.1.0 沒有 zip、多半只抓了 compose 一個檔，蓋過時會補上
`preseed/`；`.env` 不在 zip 裡、不會被蓋掉。`.env.example` 沒有新變數；三個檔的註解改成英文，compose 檔另外只改了
`DATA_ROOT` / `CONFIG_ROOT` 沒設時的錯誤訊息。沒有資料庫 migration。破壞性變更：

- **既有服務的憑證測不過就不存**（票 45）：`POST /api/setup/services/{kind}` 選既有而測不過時改回 400
  `connection_failed`（`ChoiceRefusalOut` 多一個 `attempt`），不再 200 存下紅燈；擁有者之後的既有 Jellyfin 新位址
  不回答也改成這一種，原本是 409 `unverified`。`POST /api/setup/tmdb/test` 測不過不再存下那一把：0.1.0 存下的
  沒驗過的 TMDB key 升級後讀成沒有，在設定 → TMDB 重新貼一次、測過就好。

票 43、44、46–57、59、60 沒有破壞性變更：新端點與回應欄位都是加的，逐條在下面。要注意的只有票 46 讓
`ConnectionReason` 多了三個值（`data_unseen`、`data_unreadable`、`data_unsettled`），對它做窮舉比對的 client 要補上。

### Added

- **重裝之後在畫面上把帳本找回來**（M4 票 60，brief §19 E6）：媒體庫裡有 Berth 帳本不認得的檔案時（重裝、資料庫遺失），
  精靈完成頁與「待處理」最上面說有幾個、為什麼，一顆「從媒體庫重建帳本」——與 `berth rebuild-ledger` 同一個命令，
  只加不刪、可以重按，按完說找回幾個、幾個變成非受管檔案。作品頁的「檔案與版本」在帳本空而 Jellyfin 有這部時，
  改說「Jellyfin 有這部，Berth 的紀錄裡沒有」並連到待處理，不再寫「還沒有任何檔案入庫」。「無主 torrent」那一列
  說清楚「認領並建立下載」會做什麼。精靈跑完之後打開 `/setup` 被帶到設定頁時多一句「精靈已經完成」；重跑精靈的做法
  寫在 `docs/guide/backup-and-reinstall.md`。新端點 `GET /api/issues/rebuild-ledger` 與 `POST /api/issues/rebuild-ledger`（只有管理員）。

- **換一台 qBittorrent 之後 Route 自動重新檢查，以及「全部重新檢查」**（M4 票 59）：在設定 → qBittorrent 換了一台、新那台
  測過之後，Berth 自動對每一條 Route 重跑檢查（分類建在新那台、探針重問），畫面說「正在重新檢查 N 條 Route」並逐條
  顯示進度，跑完說幾條過了、沒過的指去「媒體庫路徑」。「媒體庫路徑」設定頁多一顆「全部重新檢查」，健康頁的 Route
  總結是「要重新檢查」時管理員也有同一顆。新端點 `POST /api/routes/check`（只有管理員）。

- **部署套件改成 release 附件**（M4 票 56，brief §19 E4）：每一版 release 附一個 zip，解壓出 `berth/`（compose 檔、
  `.env.example`、`preseed/`），不必 clone repo。檔名帶版本的 `berth-deploy-<版本>.zip` 之外另有同內容的
  `berth-deploy.zip`，`https://github.com/1morr/Berth/releases/latest/download/berth-deploy.zip` 永遠是最新的正式版；
  預發佈版本也有附件，但不動這個連結。以前只抓 compose 一個檔的話少了 `preseed/`，套件內 qBittorrent 不放 Berth
  進去。升級改成解壓新的 zip 蓋過原本的 `berth/`（`.env` 不在 zip 裡）。`.env.example` 開頭說明一台主機只跑一套。

- **作品頁打開時先問一次 Jellyfin**（M4 票 51）：入庫後 Jellyfin 已經有這部、媒體庫頁也看得到，作品頁的「檔案與版本」
  卻還寫「Jellyfin 還在掃描」，因為 Berth 的反查在退避（最晚 10 分鐘）。現在作品頁有檔案還在等時先問一次，Jellyfin
  已經列出的就改成已收錄；真的還沒有的照舊，而且不算反查的一次。那一句改說「Berth 下一次確認在 …」，排程是 Berth 的。
  新端點 `POST /api/media/{id}/resolve`。
- **作品頁搜尋用年份與類型篩**（M4 票 49）：電影搜尋不再把讀得出季集的發佈（`S04E02`、`第2季`）與年份差超過一年的重拍
  列在主清單；劇集搜尋照常收季集，只收起首播之前或播完之後的年份。收起來的說出筆數、可展開，展開後照樣能送單。
  搜尋 API 的回應多 `set_aside` 與 `set_aside_total` 兩格。自己打關鍵字時不篩。
- **換一台 qBittorrent / Prowlarr 時列出 Berth 在原本那一台留下的東西**（M4 票 47，brief §19 D6）：確認框列出
  `berth-` 分類（各有幾個 torrent）、Berth 加進去的站、Berth 設的介面登入；使用者自己的分類與站不列。原本那一台
  連不到時列 Berth 記得建過的，並說明確認不了現況。可以一鍵移除空的 `berth-` 分類；有 torrent 的、不是 `berth-`
  的不碰，站與登入只列出。新端點 `GET /api/setup/services/{kind}/leftovers` 與
  `DELETE /api/setup/services/qbittorrent/leftovers/categories`。站的紀錄從這一版開始累積，之前加的站不會列出。
  精靈頁 2 選過一台之後換另一台一律先確認（原本既有的那一台換走時沒有確認）。

### Changed

- **部署檔的註解改成英文**（M4 票 58）：`docker-compose.yml`、`.env.example` 與 `preseed/` 腳本給使用者看的說明，
  以及 `${DATA_ROOT}` / `${CONFIG_ROOT}` 沒設時 Compose 印的錯誤，都改成英文，與英文 README 一致。設定值與預設值
  不變。preseed 腳本裡「save path 等由精靈設定、看得到差異」那句在票 32 之後已經不對，一併改正。

- **README 改成英文為主，另有繁中版；安裝頁只留必讀**（M4 票 57，brief §19 E7）：`README.md` 是英文，
  `README.zh-Hant.md` 是同內容的繁中版，兩份開頭互相連結。README 只留取得 zip、改 `.env` 的幾個值
  （`DATA_ROOT`、PUID / PGID、`TZ`、已有服務時的 `COMPOSE_PROFILES`）、`up -d`、先申請 TMDB key、精靈每頁一句、
  現況與已知限制，附四張英文介面截圖。其餘搬到 `docs/guide/` 的六份英文 guide：精靈（逐頁、帳號與密碼、精靈之後的
  各頁）、接既有服務（含 Unraid 模板的「Add another Path」）、前置需求與版本下限、升級、疑難排解、備份與重裝。
  開發指令、e2e、演練伺服器、實驗腳本與目錄結構搬到 `docs/development.md`，它是開發指令的單一來源。順手改正：
  掛媒體根的是三個容器不是四個；Berth 不存 Jellyfin 密碼的明文，介面登入存的是加鹽雜湊；套件內媒體庫不即時監看，
  手動丟進去的檔案要等 Jellyfin 下一次掃描；「唯一要離開 Berth 的是 TMDB」只對套件內＋公開站成立。
  `.env.example` 的註解說清楚 `DATA_ROOT` 試跑可不改、正式用改到哪，`TZ` 要改成自己的時區。

- **每日對帳不再洗掉「沒配上的理由」**（M4 票 60）：重建帳本或「認領進帳本」配不上時，那一件非受管檔案寫著理由；
  04:00 的對帳再記同一件時原本把它清空，待處理頁那一行就不見了。現在留著。

- **健康頁的媒體庫路徑不再假綠**（M4 票 59）：換了一台 qBittorrent 之後，那一格原本還寫「已繫上」，三條 Route 卻都是
  「尚未檢查」；探針那一條從沒問過的 Route（5 / 6）也算綠。現在那一格與那幾條 Route 說「要重新檢查」，問到結論才是
  「已繫上」。它不算降級：匿名的 `GET /api/health` 照樣是 `ok`。送單規則不變，還沒檢查完的 Route 照樣收單。
- **完成精靈之後健康頁一打開就有紀錄**（M4 票 59）：原本四格都是「尚未檢查」、「上次檢查 沒有紀錄」，要按「立即重測」。
  現在完成時把各頁測過的結論寫進健康紀錄；自動檢查在完成之後一個間隔（5 分鐘）才跑第一輪。

- **套件內 Jellyfin 的伺服器名稱是「Berth」**（M4 票 52）：精靈沒設名稱時，Jellyfin 的用戶端顯示的是容器 ID。現在 Berth
  替全新的套件內 Jellyfin 跑初始設定時寫 `ServerName = Berth`；已經初始化過的（重裝保留設定）與既有的那一台不改，
  要改名到 Jellyfin 的「控制台 → 一般」。
- **健康頁的 Route 說出 qBittorrent 探針是沿用的**（M4 票 50）：5 分鐘的自動檢查不跑探針（會觸發 qBittorrent 的「torrent
  完成時執行外部程式」），那一條原本看起來像剛問過；現在說「沿用上一次的結論」與那一次的時間，從沒問過的才是
  「尚未執行」。斷在探針之前的一次「重新檢查」不再洗掉上一次的結論，修好之後不會從此停在 5 / 6。Route 的 API 回應多
  `probed_at` 與 `probe_carried`。

- **精靈頁 2 測連線時就問 qBittorrent 看不看得到 `/data`**（M4 票 46）：只掛了 `/downloads` 的 qBittorrent 原本頁 2
  是綠的、要到頁 3 才紅；現在頁 2 就紅，補法與頁 3 同一組（在原本那一份多加一條 `${DATA_ROOT}:/data`）。測試時 Berth
  在 `/data` 放一個探測檔、請 qBittorrent 停住校驗一次後移除；這個探針校驗不會跑完，不觸發「torrent 完成時執行外部
  程式」，設了「torrent 加入時執行外部程式」的話會觸發一次。`ConnectionReason` 多三個值：`data_unseen`、
  `data_unreadable`、`data_unsettled`。

- **只存測過的憑證，錯誤標在欄位上**（M4 票 45）：既有 Jellyfin、qBittorrent、Prowlarr 的位址與憑證，以及 TMDB 的
  key，都要測過才存；測不過什麼都不換，已經有一組能用的照舊在用。精靈與設定頁的既有表單把錯誤標在欄位旁：位址錯
  標位址、帳密或 API key 錯標憑證，其餘留在表單裡。**破壞性**：`POST /api/setup/services/{kind}` 選既有而測不過時
  改回 400 `connection_failed`（`ChoiceRefusalOut` 多一個 `attempt`，是那一次的測試結果），不再 200 存下紅燈；擁有者
  之後的既有 Jellyfin 新位址不回答也改成這一種（原本 409 `unverified`）。`POST /api/setup/tmdb/test` 測不過不再存下
  那一把；`GET /api/setup/tmdb` 的 `api_key_present` 只在有一把驗過的 key 時為真，「已存下，沒通過驗證」這個狀態
  不再出現（0.1.0 存下的沒驗過的 key 讀成沒有，下一次測過就蓋掉）。qBittorrent 連錯的次數改以位址記，升級後從 0
  重數。
- **精靈頁 3 套件內第一次來就自動建立並檢查，看得到進度**（M4 票 43，brief §19 D7）：清單是預設、什麼都還沒建時，
  進頁就建媒體庫、建 Route、跑檢查，不必按「建立並檢查」；改過清單、跑過一次之後，或既有 Jellyfin，照舊由人按。
  跑的時候每條 Route 先畫成一列，說出跑到第幾條檢查；跑到一半重新整理也接得上，不會再送一次。
  `GET /api/setup/jellyfin` 多一個 `bundled_default`。
- **精靈頁 4 套件內一顆鍵加入可用的推薦站**（M4 票 44）：「測試推薦站，加入通過的」一次做完測試與加入，結果逐站
  列出；測試通過、加入時卻失敗的站單獨說明，不算進已加入。Prowlarr 已經有站時不給這顆鍵。逐站測試與勾選、其他公開站
  收進「進階」，照樣能用。新增 `POST /api/setup/indexers/recommended`（只給套件內，既有回 422）；`SiteCheckOut` 多一個
  `stage`（`test` / `add`：結論來自測試還是新增）。

### Fixed

- **「S01 + S02」「S1-S2」讀成多季合集，不是 S01E02**（M4 票 48）：這類發佈名原本被當成第 1 季第 2 集的單集。現在
  讀成第 1 到第 2 季的合集，名字裡明寫的集號照讀。RSS 的「不自動下載合集」原本擋不到這種包，綁上之後會整包自動
  送單；現在照設定排除，還沒綁定的舊項目在綁上時重新篩一次。
- **各票 code-review 留下的幾處**（M4 票 54）：既有 Jellyfin 填 `host.docker.internal` 時，媒體庫、作品頁與 Route
  設定頁的「在 Jellyfin 開啟」連結改開在瀏覽器的主機名上（原本是瀏覽器開不了的位址；填 compose 主機名的不給連結）。
  設定 → Prowlarr 讀不到站的清單時（例如在 Prowlarr 重新產生了 API key）與精靈頁 4 說同一段、給「重新讀取」，不再說
  「連不上套件內的 Prowlarr」並叫人跳過。選套件內／既有的兩格，讀屏器念的名字只剩標題、說明另外念；位址與名字在窄版
  換行而不是被截掉後半。
- **精靈上四句與實際行為不符的說明**（M4 票 53，2026-10-06 審計的「文件與實作不符」表）：套件內 qBittorrent 不收
  Berth 時原本叫你重啟、說會補上白名單，但預置腳本不蓋掉你改過的設定，在 WebUI 關掉白名單之後重啟補不回來——現在說
  到 qBittorrent 的「選項 → WebUI → 驗證」勾回那一格，不再給 `docker compose restart` 那一行。既有 Jellyfin 卡片補上頁 1
  會建 API key「Berth」；Jellyfin 初始設定的手動步驟不再寫死繁體中文與台灣；頁 4 選擇前的說明補上你自己的 Prowlarr
  也能加站，選了之後與回頭看的說明從「按一次加進去」改成「勾選通過的加進去」（實際是測過、勾選、確認才加）。

## [0.1.0] - 2026-10-07

第一個正式版本：`ghcr.io/1morr/berth:0.1.0`，同時是 `:0.1` 與 compose 範本 pin 的 `:latest`。M0–M3 驗收完成；
M4 在 2026-10-06 精靈與可用性審計之後，先把擋送單與擋第一次設定的問題（審計改進清單的 P0-1 與 P1，M4 票 32–40）修完才發
（brief §19 D8）。同為 P0 的原生 Linux 實跑（P0-3，M4 票 42）排在發佈之後、用這個 image 跑（使用者 2026-10-06 同意），
所以原生 Linux 與 NAS 宿主還沒有人實跑過。

**從 `0.1.0-rc1` 或自己 build 的 image 升級**：照 README〈版本與升級〉，**compose 範本要一起換**——rc1 之後它改了
容器名（`berth-*`）、把 Jellyfin 從 `:latest` 釘到 12.1 這條線、五個 port 改從 `.env` 讀，只拉新 image 拿不到這些。
接既有 Jellyfin 的要先升到 12.0 以上（README〈外部服務的前提〉）。資料庫 migration 由 Berth 啟動時自動套用。審計之後（M4 票 32–40）的破壞性變更：

- **qBittorrent 的「建議設定」整組拿掉**（票 32）：`POST /api/settings/qbittorrent/apply`、
  `GET /api/settings/qbittorrent/diff` 刪除；`QbittorrentOut` 少 `diffs`、`writes_preferences`，`ServiceHealthOut` 少
  `drift`，`StepFailure` 少 `save_path_missing`。套件內 qBittorrent 不再寫 `save_path`、`auto_tmm_enabled`、
  `category_changed_tmm_enabled`，**已經寫過的不改回去**。
- **BTH 4 只接 Prowlarr**（票 37）：通用 Torznab 端點與 Jackett 不再支援，設定與 API 少 `kind`。**資料 migration
  `b4ca280eaeca` 清掉存著 Torznab 端點的索引站位址與 key**，精靈頁 4 回到待處理、搜尋說沒設定，要先裝 Prowlarr
  再接；降版不會還原。
- **`POST /api/setup/indexers/connect` 拿掉**（票 39）：既有 Prowlarr 改送 `POST /api/setup/services/prowlarr`，
  `GET /api/setup/indexers` 少 `reason`。
- **真服務 e2e 的指令換了**（票 34，只影響開發）：`uv run --env-file .env python -m tests.e2e.stack`，不再要先
  `export CONFIG_ROOT`。

票 33、35、36、38、40 沒有破壞性變更（40 只多 `web_ui_login_by_berth` 欄位）。rc1 是 M0 開工那天的骨架，之後的
對外變動沒有逐條標「破壞性」：拿掉的端點、欄位與頁面在下面的 Removed，改了行為或形狀的在 Changed。

**M0（骨架）在 2026-09-08 通過驗收**（brief §17、`.scratch/m0/issues/11-m0-acceptance.md`）：在乾淨的
Windows Docker Desktop（NTFS bind mount）與 Linux（ext4）上各跑一次 `docker compose up` → 只操作 Berth
→ 四項健康檢查綠燈，全程沒有打開 qBittorrent / Jellyfin / Prowlarr 的介面；另以「既有 Jellyfin +
套件內 qBittorrent 與 Prowlarr」的組合走一次，既有媒體庫是**加**一條路徑而不是搬路徑，項目 ID 與
觀看紀錄都沒有變。M0 建的東西全部列在下面，M1 之後的變更接在同一份清單後面。

**M1（手動全流程）在 2026-09-17 通過驗收**（brief §17、`.scratch/m1/issues/15-m1-acceptance.md`）：一部美劇一季
（The Bear S03）、一部動漫一季（葬送的芙莉蓮 S01 加 11 個特典）、一部電影（奧本海默）從送單到入庫不經人工，
硬鏈接兩端同一個 inode，Jellyfin 以正確的名稱、季集與海報列出它們，Berth 反查到的 item 就是 Jellyfin 的那一個。
這條路徑現在是 nightly 的 e2e（`tests/e2e/`），對真的 qBittorrent 與 Jellyfin 跑。

**M1.5（媒體庫瀏覽）在 2026-09-19 通過驗收**（brief §17、`.scratch/m1.5/issues/11-m15-acceptance.md`）：以一個
只開放一個媒體庫的**一般使用者**登入 Berth，不打開 Jellyfin Web 就從媒體庫找到要看的那一集、看到自己的進度並
標記已看，按播放落在 Jellyfin 的那一集；他在 Jellyfin 沒有權限的媒體庫在 Berth 也看不到；既有媒體庫裡不是
Berth 入庫的作品照樣瀏覽得到。這六件事現在是 nightly e2e 的第二個模組（`tests/e2e/test_2_m15_library.py`），
對真的 Jellyfin 12.1 跑。

**M2（修正與對帳）在 2026-09-24 通過驗收**（brief §17、`.scratch/m2/issues/16-m2-acceptance.md`）：對真的
qBittorrent 與 Jellyfin，三種人為破壞——在 Jellyfin 裡刪掉一集、用複製品取代硬鏈接、手動刪掉 complete 裡的
來源——都由對帳偵測到、按 Issue 上的動作修好，下一輪不再問；整個媒體庫的內容刪光之後按一次「重新入庫」回到
同樣的路徑、同一個 inode、同樣的帳本列。medium 自動入庫的檔案在審核佇列一鍵撤銷。以 `user` 登入時，審核、
Issue、修正、對帳、刪除與重新入庫的每一條端點都是 403，畫面上也沒有入口。前兩件是 nightly e2e 的第三個模組
（`tests/e2e/test_3_m2_repair.py`）。

**M3（RSS）在 2026-09-26 通過驗收**（brief §17、`.scratch/m3/issues/21-m3-acceptance.md`）：一個 Mikan 聚合 feed
與一個從作品頁訂閱的 acg.rip 搜尋 feed 全自動追完——認得出的作品自動綁定（同類型的 Route 不只一條時送進 Feed 說的
那一條），中途訂閱的一部補齊舊集、之後的新集自動入庫；同一集兩個字幕組、同組 v1 與 v2 都並存；合集被排除；一部
split-cour 的第一批被播出日比對整批擋在審核，改正一次並套用到 RSS Series 之後其餘集數跟著對、自動入庫；Jellyfin
認到的季集與帳本不同時開出 Issue；已確認的 RSS Series 的新集數不再進 audit 清單。這八條是 nightly e2e 的第四個
模組（`tests/e2e/test_4_m3_rss.py`），公開 RSS 站由 compose 裡的替身冒充，下載與入庫走真的 qBittorrent 與 Jellyfin。

### Added

- Repo 骨架：uv 後端專案與 `berth` CLI（`--version`）、pnpm + Vite + React + TypeScript 前端。
- 工具鏈：ruff、mypy（strict）、pytest、import-linter、eslint、prettier、vitest。
- `import-linter` 契約，編碼 plan §1.3 的依賴方向。
- pre-commit 設定與 GitHub Actions CI（後端 lint / type / test、前端 lint / test / build、檔案衛生）。
- LICENSE（MIT）與 README（指令的單一來源）。
- `berth serve`：FastAPI 程序，啟動時自動套用 Alembic migration 並以 WAL 開啟 `<CONFIG_ROOT>/berth.db`。
- M0 資料表：`users`、`sessions`、`settings`、`routes`、`events`（plan §2）。
- `settings` 的分組模型：`services.jellyfin`、`services.qbittorrent`、`services.indexer`、
  `services.tmdb`、`paths`、`setup`，未設定時回預設值。
- `GET /api/health`：匿名可呼叫，回總體狀態、版本與精靈是否已完成。
- 前端 shell：深色為預設、亮色跟隨系統的 Tailwind 主題，`zh-Hant` 語言檔，
  TanStack Router 與 Query，以及顯示健康狀態的佔位頁；build 產物由後端同一個程序提供。
- 環境變數 `CONFIG_ROOT`、`DATA_ROOT`、`WEB_ROOT`、`PORT` 與 `.env.example`。
- `deploy/`：多階段 Dockerfile（node build → python slim、非 root、`PUID` / `PGID` 入口腳本）、
  四個服務的 `docker-compose.yml`（profiles、固定子網、健康檢查）、qBittorrent 的
  preseed 腳本與部署用的 `.env.example`。
- GHCR 發佈 workflow（`v*` tag）與 CI 的 image build job。
- `scripts/experiments/`：對真實外部服務的可重跑驗證腳本（Jellyfin 10.10 / 10.11 命名、
  qBittorrent 4.4 / 5.x 參數矩陣、Prowlarr `config/host`、硬鏈接），只用標準庫，
  可搬到 NAS 上跑；結果寫在 `docs/research/m0-experiments.md`。
- 設定精靈的前兩步（plan §9.3）：`GET /api/setup/status`、`POST /api/setup/admin`、
  `POST /api/setup/detect`、`POST /api/setup/services/{kind}`。setup 未完成時匿名開放，
  完成後只有 `admin` 進得來。
- Jellyfin、qBittorrent、Prowlarr 三個 adapter 的第一版：各有 `Protocol` 介面、HTTP 實作與
  `Fake`，錯誤分成「服務不在 compose 裡」「還在啟動」「要憑證」「不是這個服務」四種；
  契約測試對 `tests/fixtures/http/` 的錄製回應執行。
- Prowlarr 的 API key 從唯讀掛載的 `config.xml` 或 `PROWLARR__AUTH__APIKEY` 讀取，
  兩處都沒有時精靈退回手動貼上。新增環境變數 `EXT_ROOT`。
- 設定精靈第 7–8 步（plan §9.3）：`GET/POST /api/setup/routes` 從 Jellyfin 媒體庫建立 Library Route，
  每條 Route 在 qBittorrent 建 `berth-*` category（已存在但 save path 不同時回報衝突且不覆寫）並跑
  五項跨服務檢查——qBittorrent 與 Jellyfin 回報的路徑在 Berth 內 `stat` 得到、Jellyfin 看得到 Berth
  寫的探測檔（`Environment/ValidatePath`）、complete 目錄與寫入目標之間真的 `link()` 得起來且同
  inode。`POST /api/setup/complete` 在每條 Route 都綠燈時寫下 `settings.setup.completed`，之後
  `setup/*` 需登入、`/` 不再導向精靈。
- fs adapter（plan §8.6）：`link`、`stat`、`same_inode`、`link_test`、`free_space`、`is_within`
  與探測檔；所有寫入都要帶允許的根目錄，不在其中就拒絕（防路徑逃逸）。
- 設定精靈 UI（`/setup`）：常駐的四格泊位板、第 1 步建立管理員、第 2 步逐服務探測與
  就地展開的既有服務連線表單與可複製的手動步驟。setup 未完成時其他頁面導向 `/setup`。
- 認證（plan §6、brief §11）：`POST /api/auth/login`（以 Jellyfin 帳密驗證，角色取自
  `Policy.IsAdministrator`）、`POST /api/auth/logout`、`GET /api/auth/me`。session 以
  httpOnly、`SameSite=Strict` 的 cookie 承載，壽命 30 天不續期，資料庫只存 token 的雜湊。
- `/api` 的門禁 middleware：預設拒絕，白名單只有 `auth/login`、`auth/logout`、`health`；
  非 GET 請求要求 `X-Requested-With` 標頭。精靈跑完之後 `setup/*` 只有 `admin` 進得來。
- 登入頁 `/login`，以及登入後頁首的身分區（角色、設定入口、登出）。未登入時任何頁面
  導向 `/login`，非 admin 看不到也進不了設定。
- UI 語言 `zh-Hant` 與 `en` 並列，跟隨瀏覽器並可切換，選擇存在 localStorage。
- `scripts/fake_setup_server.py`：以 Fake adapter 起一台真的 Berth，用來實跑驗證精靈。
- 設定精靈第 3 步 Jellyfin（plan §9.4、§9.5）：`GET /api/setup/jellyfin`、
  `POST /api/setup/jellyfin/bootstrap`、`/connect`、`/libraries/paths`、`/plugin`。
  套件內一鍵跑完九步（建管理員、Movies / TV / Anime 三個媒體庫、API key、安裝 MergeVersions、
  重啟並記下兩個合併任務的 `Id`），每一步冪等、失敗可單獨重試；既有服務只做檢查，
  提供「加入 Berth 路徑」與「安裝 MergeVersions」兩顆需二次確認的按鈕。
- `settings.services.jellyfin` 新增 `api_key`、`metadata_fetchers`（建立媒體庫時的 metadata
  provider，預設 TMDB，是 brief §10 的 TVDB【研究】的切換點）、`merge_movies_task_id`、
  `merge_episodes_task_id`；`settings.paths` 新增 `library_root`。
- Jellyfin adapter 補上初始精靈、媒體庫、API key、插件、排程任務；`Fake` 是有狀態的假伺服器，
  複製了實測到的行為（同名媒體庫不被拒、`Auth/Keys` 不去重、重啟後回 503）。
- `adapters/fs.py`：媒體庫目錄由 Berth 建立（plan §9.1）。
- 設定精靈第 4 步 qBittorrent（plan §9.3、§8.1）：`GET /api/setup/qbittorrent/diff` 現查逐鍵差異
  （`temp_path_enabled`、`temp_path`、`save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`），
  `POST /api/setup/qbittorrent/apply` 只寫有差異的鍵；勾了「同一組帳密」時另設套件內的 WebUI 密碼。
  Web API 低於 2.8.4 拒絕接入並給升級指令；既有服務的 temp path 未啟用只警告。
- 設定精靈第 5–6 步來源（plan §9.3、§8.3、§8.4）：`GET /api/setup/indexers`、
  `POST /api/setup/indexers/apply`（十個預設公開站，逐站顯示成敗，重按不會重複新增）、
  `/connect`（既有 Prowlarr 或任意 Torznab 端點）、`/skip`，以及 `GET /api/setup/tmdb`、
  `POST /api/setup/tmdb/test`、`/skip`。勾了「同一組帳密」時一併設定套件內 Prowlarr 的介面登入。
- qBittorrent adapter 補上偏好讀寫與分類，版本判斷（`paused` / `stopped`、2.8.4 下限）綁在
  4.4.5 與 5.2.3 兩組錄製回應上；Prowlarr adapter 補上索引站定義、新增、驗證與 `config/host`。
- 新增 TMDB 與 Torznab 兩個 adapter（各有 `Protocol`、HTTP 實作、`Fake` 與契約測試）。
  TMDB 內建專案級憑證，`settings.services.tmdb.api_key` 可覆寫，v3 key 與 v4 token 都收。
- 套件內 Prowlarr 的 API key 在探測時就存進 `settings.services.indexer`，之後的步驟與里程碑
  從同一個地方拿憑證。
- `health_checker` 背景迴圈（plan §3.2）：由 lifespan 啟動與關閉，每 30 秒醒來、上一輪滿 5 分鐘
  才真的跑，精靈跑完之前不跑。四項檢查——Jellyfin（連線與 API key）、qBittorrent（連線、Web API
  版本、建議設定漂移）、索引站（Prowlarr 或 Torznab）、每條 Route 的五項跨服務檢查（與精靈第 7 步
  同一組、寫回同一個欄位）。每一項各自 try/except，一個服務掛掉不影響其他檢查。
- `GET /api/health/detail`（要登入）與 `POST /api/health/check`（立刻重跑）：逐服務與逐 Route 的
  明細、最後成功時間、連續失敗次數與失敗原文。`GET /api/health` 的 `status` 改成由上一輪的結果
  導出（`ok` / `degraded`），只讀一列設定，不連任何服務。
- `settings` 新增 `health` 分組：迴圈上一輪的逐服務結果與 Route 總結。與 `services.*`
  分開存——那幾組是整組覆寫的使用者設定。
- 服務設定 API（plan §6，只有 `admin`）：`GET /api/settings/services`、
  `POST /api/settings/services/{kind}/test`（只重測一個服務）、`GET /api/settings/qbittorrent/diff`、
  `POST /api/settings/qbittorrent/apply`（「還原建議設定」，brief §16.3）。
- 健康頁 `/health`（唯讀，一般使用者也看得到）與服務設定頁 `/settings/services`（只有 admin）：
  與精靈同一塊四格泊位板，紅燈就地展開服務回的原文與修正步驟（套件內給 docker 指令，既有指回
  精靈），Route 綠燈收起、紅燈展開五條纜繩；qBittorrent 設定漂移顯示逐鍵差異與還原按鈕。
  頁首長出導覽，`/` 在 M1 的探索頁之前先導向 `/health`。

- `berth openapi`：印出 OpenAPI 文件（`--output` 寫檔）。只組裝路由，不跑 lifespan、不碰資料庫。
- `pnpm -C web gen:api`：從上一條產出前端的 API 型別 `web/src/api/schema.d.ts`（openapi-typescript）。
  CI 多一個 `api-types` job，型別檔過期時紅燈。

- M1 資料表：`media`（Berth 手上的作品，資料夾名一凍結就進了檔案系統）與 `tmdb_cache`（探索與搜尋的
  一小時快取，整列丟掉不會失去任何東西）。
- TMDB adapter 補上 `trending/{tv,movie}/week`、`{tv,movie}/popular` 與 `search/multi`，以及
  **全域 40 req/s 的令牌桶**——上限是每個 IP 的，所以桶是程序層級的一個，不是每個 client 一個。
- `GET /api/discover/trending`、`/api/discover/popular`、`/api/discover/search?q=`：回作品卡片
  （tmdb id、類型、顯示用標題、英文標題、年份、完整海報網址）。**拿不到 TMDB 時仍是
  200**，理由放在 `problem`——一頁上有三個 feed，一個垮掉時另外兩個要照樣畫得出來。
- 探索頁 `/`：趨勢與熱門兩面海報牆（劇集與電影交錯）、鍵入即搜的搜尋（500 ms 防抖、2 字起跳、
  結果接管整面牆），以及 TMDB 條款要求的歸屬聲明與標誌。**卡片上還沒有狀態**——「已追蹤 /
  部分 / 完整 / 下載中」要等 Job 與帳本才推導得出來。
- `scripts/fake_setup_server.py` 新增 `discover` 與 `tmdb-down` 兩個情境；前者打**真的** TMDB
  （憑證由環境變數 `TMDB_API_KEY` 帶入，與實驗腳本同一個名字；根目錄的 `.env.example` 有欄位）。
  **Berth 本身不讀那個變數**——產品的唯一來源仍是精靈寫進資料庫的 `settings.services.tmdb.api_key`。
- TMDB adapter 再補上詳情那四支：`tv/{id}`、`movie/{id}`（各自帶它需要的 append）、
  `tv/{id}/season/{n}` 與 `tv/episode_group/{id}`。**絕對編號從 0-based 的 `order` 推**，
  不是 group 裡的 `episode_number`——後者保留播出序原值，照它讀會把第二季算成第 1 集起。
- `GET /api/media/{id}`、`POST /api/media/{id}/refresh`：TMDB 詳情與各季各集的快照
  （24 小時，過期自動重抓），以及收得下這部作品的 Route 清單。**拿不到 TMDB 時仍是 200**，
  存過的快照照樣回，只是掛一條「這是舊的」。
- Media 詳情頁 `/media/:id`：海報與三個標題（顯示用、英文、原文）、識別欄位、簡介、各季可展開的
  集表（集號、標題、絕對編號、片長、播出日），以及「入庫到哪裡」的 Route 下拉。**電影沒有季集
  區塊**，改列片長。搜尋 torrent 與送單在 M1 後段接上去之前，這一頁是唯讀的瀏覽頁。
- 探索牆的每一格現在是連到詳情頁的連結（票 03 刻意留下的那條線）。
- `domain/media.py` 的 `MediaSnapshot` / `SeasonSnapshot` / `EpisodeSnapshot`：`media.tmdb_snapshot_json`
  的型別化版本，也是 `naming` 與（M1 後段的）`parser` 的輸入。
- `naming.folder_name()`：plan §5 凍結模板的第一格——`{title} ({year}) [tmdbid-{id}]`。
- 解析器的前三層（plan §4.1、brief §6.2、§6.3、§6.8）：
  - `parser.classify`：依副檔名、關鍵字與資料夾判 `kind`。`sample` 要**同時**滿足「檔名含
    sample」與「遠小於正片」；`disc` 是整包的判定（有 `BDMV/` 或 `VIDEO_TS/` 就整包需人工）。
  - `parser.normalize_cjk`：中文字幕組命名的詞典。抽出字幕語言、內嵌 / 內封 / 外掛、季號、
    集號、合集、特典、劇場版與組名，並剝掉 `★` 前綴、招募廣告、地區限制與 CJK 標題，
    剩下的拉丁字母那一半才交給 guessit。**季號認全形羅馬數字（`无职转生Ⅲ`）與不以空白收邊的
    半形羅馬數字（`Mushoku Tensei III:`）**——M1 票 01 量到漏掉這兩種會把整輪播出錯置成第一季。
  - `parser.parse_release` / `merge_release`：guessit 打底，補上它在字幕組格式下會漏或會錯的
    幾條（多方括號裡的集號、`Season 3 [04]` 被讀成兩個季號、年份被當成季號、`HD1080P`、
    結尾 `-[Group]`、把字幕 token 當組名）。檔名說了算，torrent 名補空缺。
  - `domain.Tags.render()`：brief §6.8 的順序與 token，`subs` 依 `CHS < CHT < JP < EN` 以 `+` 連接。
- `berth bench`：解析基準測試（plan §4.6、brief §6.9）。**離線跑**——真實 torrent 的
  檔案清單（`tests/fixtures/parser/`）與凍結的 TMDB 快照（`tests/fixtures/tmdb/`）都在
  repo 裡。報表逐分類列出 `auto_correct` / `auto_wrong` / `review` / `missed` /
  `unmatched_correct` / `extra_correct` / `skipped`（七個桶加起來等於檔案數）、分類與 tag
  的正確率，以及 high / medium 誤判率；門檻在
  `tests/fixtures/parser/baseline.json`，同一支邏輯就是 `tests/unit/test_bench.py`，所以 CI
  不另開 job。
- 解析器的第四層：季集對應與信心（plan §4.1、§4.4、brief §6.4、§6.5、§6.6）。
  - `parser.structure_hints`：只讀資料夾——`Season 2` / `S2` / `第二季` / `2nd Season` /
    `Part 2` / `Specials` / `SPs`，以及 `Subs/` `字幕/` 與其下的語言子資料夾。
  - `parser.map_episode`：brief §6.4 的優先序（上下文季號 → 檔名的顯式季號 → 資料夾 → 篇章名
    → 只有集號），每一個答案都是一個帶理由的 `Candidate`。**三條規則來自 M1 票 01 的量測**：
    **篇章名 → 季號**（佔失敗的九成；比對各季在三輪語言下的名字，`最終季` 對到最後一季）、
    **`第二部分` / `Part.2` 當 cour 偏移**（唯一「有季號還是錯」的一類），以及 **180 天的虛擬季
    門檻**（TMDB 把好幾輪播出併成一季時的換算）。絕對編號三法（episode group、各季累加、
    虛擬季）各產一個 Candidate。
  - `parser.match_media`：正規化後比 `name` / `original_name` / 別名 / 翻譯，年份加權。上下文
    有 Media 時它是覆核（對不上就壓低信心）；`ParseContext.candidates` 有東西時（RSS 與
    重新入庫）它就是認作品的那條路，而「標題 + 年份精確命中」才配得上 high 信心。
  - `parser.score`：批次一致性（同模式、連續集號、數量與 TMDB 吻合）。兩個檔案宣稱同一集、
    或一季十二集卻對出二十個檔案時，**那一季都不自動入庫**——是哪一個讀錯了看不出來；
    整包用同一種模式讀而只有一個例外時，那一個降到 medium。
  - 特典的處置（brief §7.6）：發佈明說 `S00Exx` 就照它走但信心至多 medium，只寫 `[SP][01]`
    這種自己的序號則是 `unmatched`，等人工指派。
- `MediaSnapshot` 的各季多一個 `names`：同一季在 `en-US` / `zh-TW` / `zh-CN` 三輪的名字。
  篇章名比對的對手是真實發佈寫的那一種字（`柱训练篇`），只留英文季名的話那條規則不會命中。
  代價是 `tv/{id}` 多打一輪 `zh-CN`（只取季名，電影不打）。
- 語料補三筆真實發佈（動漫 11 / 劇集 8 / 電影 4，共 23 筆 333 個檔案）：篇章名（鬼滅之刃
  柱訓練篇）、cour 偏移（進擊的巨人 Season 3 Part 2）與單檔多集（`- 01-02` 的 `.ts`）。
- `berth bench` 的報表多一欄**信心達標率**：語料寫的 `min_confidence` 有沒有達到。不達標不是
  做錯事，但它說得出「本來該自動入庫的少了幾個」。
- `scripts/record_tmdb_snapshots.py`：用產品自己的路徑（暫時的資料庫 + `refresh_media`）錄
  `tests/fixtures/tmdb/`，語料加了新作品時跑。
- `import-linter` 契約「parser and naming do no IO」：`berth.parser` 與 `berth.naming` 不得
  import `os` / `pathlib` / `httpx` / `sqlalchemy` 這一類會做 IO 的模組——benchmark 能離線跑
  靠的就是這條。
- **命名引擎**（`berth/naming/`，plan §5）：作品資料夾、季資料夾、劇集檔、電影檔、外掛字幕、
  extras 六種凍結模板，輸出相對於 Route 目標的路徑。集名來自快照（缺、空、或 `Episode 5`
  這種佔位就省略，上限 80 字元）；`sanitize` 逐段套用，檔名的 200 位元組上限先扣掉副檔名。
- **外掛字幕附掛**（`berth/parser/subtitles.py`，brief §6.7）：主幹相同（去掉語言後綴）或
  字幕資料夾裡的集號 → 那個影片；語言由字幕自己的後綴、資料夾、檔名決定。檔名走
  `{影片主幹}.{CHT|CHS}.zh.{ext}`，日文與英文只用 `ja` / `en`——`zh-Hant` 只有 Jellyfin 10.11
  認得（brief §20.6 實測）。
- **Plan 產出目標路徑**：`PlanItem.target_path`，只有真的會被寫出去的檔案有值。
  兩個檔案指到同一條路徑就是衝突，兩個都進 review（brief §6.4 第 5 點）。
- `berth bench` 的比對**含目標路徑**，報表多一個 `subtitle_correct` 桶（八個桶），
  baseline 多守 `extra_correct` 與 `subtitle_correct` 兩格。
- **索引站搜尋**（`berth/adapters/indexer/`、`berth/services/search.py`，plan §6、§8.4）：
  `IndexerSearch` 介面加兩個實作——`ProwlarrSearch`（REST `/api/v1/search`，Prowlarr 刻意不提供
  跨站聚合 Torznab）與 `TorznabSearch`（任意 Torznab 端點，`t=caps` 決定能不能用 tmdbid 搜，
  不支援時退回 `q=`）。介面**一次一個查詢**；多標題展開、併發、合併去重與逐查詢逾時在 services。
- `GET /api/search?media=&q=&route=`：結果附解析出的 Tags 與預估季集。`route` 是**這一輪搜尋的
  偏好，不是承諾**（票 04b）——它只決定 anime profile 要不要加 `第N季` / `Season N` 變體。
- `GET /api/search/queries?media=&route=`：按下搜尋之前先給看會拿哪幾個名字去問（PRODUCT 原則 2）。
  不打索引站，只讀快照，所以改 Route 時可以隨手重問；規則只有一份實作，前端不重算。
- **Media 詳情頁的搜尋區塊與結果表**（`.scratch/m1/search-results-shape.md`）：待命 → 按了才搜
  （一次搜尋實測 35–85 秒），逐條纜繩顯示每個關鍵字問到幾筆，五欄結果表（發佈名 + Tags / 大小 /
  做種 / 來源 / 預估），可依做種與大小排序，390px 上塌成堆疊列。Route 下拉從身分帶搬進這一區塊
  ——它現在真的驅動一件事。
- `--scenario search`：TMDB 與索引站都打真的那一台的演練情境。
- **送單**（`berth/services/jobs.py`、`berth/api/jobs.py`，plan §3.1、§3.3、§6 jobs 群組）：
  `POST /api/jobs`（`{source, media, route}`）建一筆 Job（`requested`）→ qBittorrent 收下
  → `submitted`，兩個轉換各寫一筆 event。同 hash 重複送單回傳既有 Job，不重複送單。
  qBittorrent 拒絕或不可達 → `submit_failed` 加服務回的原文，`POST /api/jobs/{hash}/retry`
  可以退回 `requested` 再送一次。
- `jobs` 與 `job_files` 兩張表與 migration（plan §2.3）。**主鍵是 info hash**，所以
  「同一個 torrent 送兩次」在資料庫層就是同一列。`job_files` 這一票只建表。
- `GET /api/jobs`、`GET /api/jobs/{hash}`、`GET /api/jobs/{hash}/events`。
- **送單前 Berth 自己把 torrent 抓下來**（`berth/adapters/torrent.py`）：索引站的下載連結 →
  info hash（磁力連結就地解析，`.torrent` 逐位元組取 `info` 再 SHA-1）+ 要交給 qBittorrent 的
  那一份。兩個理由——`jobs.hash` 是主鍵而索引站不一定報 hash（實測 ACG.RIP 不報），以及交一條
  網址給 `torrents/add` 是**背景抓取**，抓失敗永遠沒有下文（`202` + `pending_count`），
  那樣 `submit_failed` 這個狀態永遠觸發不到。
- `torrents/add`（`berth/adapters/qbittorrent/`）：`category` + `tags=berth` +
  `contentLayout=Original` + `autoTMM=true` + 版本對的那個開始參數（API ≥ 2.11 是 `stopped`，
  否則 `paused`，值都是 `false`）。`savepath` 不送——`autoTMM` 開著時路徑由 category 決定。
- **`media.folder_frozen`**：資料夾名在**第一次送單成功那一刻**定死（plan §2.2、brief §4.5、
  票 04b）。送單確認裡印著那一串字，按下去之前就看得到；已經凍結過的第二次送單不重凍。
  `media.default_route_id` 同時寫成「上次用的」，下一次進詳情頁時下拉停在它。
- **Tracked Media 以 `EXISTS(jobs)` 推導**（`berth/services/tracking.py`、`CONTEXT.md`、票 04b）：
  詳情頁與探索牆的卡片讀同一份推導，不是欄位。票 12 的帳本與 M3 的 Rule 之後加進同一支函式。
- **下載列表頁 `/jobs`**（`.scratch/m1/jobs-shape.md`）：一份船期表，逐列狀態色塊 + 作品 +
  Route + trigger + 大小 + 進度 + 時間；點一列**就地展開**時間線、info hash 與重試，
  其他列不動、不跳頁（The Failure Expands In Place Rule）。最新的在前面。
- **結構化日誌**（`berth/logs.py`，brief §16.2、plan T1.9）：一行一筆 JSON，job 上下文裡的
  每一行都帶 job id。id 由 `ContextVar` 帶著、在 record 建立那一刻蓋上，不靠呼叫端記得傳。
- `--scenario submit` / `--scenario submit-failing`：送單與下載列表的演練情境。
- **`qbit_poller`**（`berth/pipeline/downloads.py`、`berth/services/downloads.py`、plan §3.1、§3.2、
  票 10）：`sync/maindata` 帶 `rid` 做增量，驅動 plan §3.1 中由客戶端狀態觸發的每一個轉換
  （`metadata_ready`、`downloading`、`stalled`、`missing_files`、`client_error`、`client_removed`、
  `completed`）。轉換一律 compare-and-set，每個 job 另有程序內的 `asyncio.Lock`。間隔有活躍 job 時
  5 秒、否則 30 秒、連續失敗退避到 5 分鐘，而且**每次醒來重算**——送單那一刻多半落在一個閒置間隔
  中間，沿用上一輪的答案會讓使用者等最多半分鐘才看到第一個變化。
- **`GET /api/events/stream`（SSE）**（`berth/api/events.py`、`berth/services/events.py`、plan §6）：
  推 `{hash, state, progress}`，前端據此讓 `['jobs']` 失效再問一次。下載列表因此**不用重整就自己動**
  ——沒有「即時」指示器、沒有輪詢（`.scratch/m1/live-jobs-shape.md`，使用者拍板）。
- **`job_files`**：`metadata_ready` 那一刻由 `torrents/files` 建起來，`rel_path` 是它回的 `name` 原樣
  （相對 `save_path`、含 torrent 自己的根目錄那一層，brief §20.7 再驗一次）。
- **時間線多五種事件**（brief §5.2）：`metadata_received`（檔案數與總大小）、`progress`（**每跨 25%
  一筆**，不是每一輪一筆）、`stalled`、`completed`、`issue_detected`（`IssueType` 四種）。
- **健康頁的「下載迴圈」區塊**：上次輪詢、輪詢間隔、連續失敗與服務回的原文，以及**無主 torrent**
  的清單（qBittorrent 上掛著 Berth 記號、Berth 卻沒有 Job 的那些）。`issues` 表在 M2，所以 M1 的
  載體是一筆 `issue_detected` 事件加這一份「現在還在不在」的清單。
- **`IpBannedError`**（plan §8.1、brief §20.2、解掉 plan T1.9 的第四條）：qBittorrent 連續 5 次登入
  失敗會封住來源 IP 並回 `403`，而帳密不對在 4.4.5 是 `200` + `Fails.`、5.2.3 是 `401`——所以登入
  端點上的 403 只有「被封了」一個意思。兩種都有可行動的訊息：一個要去改設定，一個要等封鎖過期。
- `--scenario poll`：qBittorrent 打**真的**那一台，送單到完成的狀態自己走完（見 README）。
- `sse-starlette` 相依。
- **`planner_runner`**（`berth/pipeline/planning.py`、`berth/services/plan.py`、plan §3.1、§3.2、
  票 11）：下載完成之後**沒有人在場**的那一段——讀 mediainfo → 解析（plan §4）→ 建 Import Plan →
  照信心決定自動入庫還是停下來問人。事件驅動（poller 動了什麼就叫醒它）加每 60 秒掃一次
  `completed` 與 `planning`；例外只記 log，迴圈不死。
- **`plans` 與 `plan_items` 兩張表**（plan §2.3）：一個 Job **一份「現在的計劃」**（`job_hash`
  unique），重跑改寫同一列而不是再長一份——不然 `GET /api/plans/{id}` 要先回答「哪一個 id 才是
  現在那一份」。上一份留在時間線上。
- **pre-plan**（brief §5.1）：檔案清單一到手就先算一份預估（`plans.status = preplan`），不碰網路、
  不碰磁碟、不動 Job 的狀態。它回答的是「這一包對不對、還來得及取消嗎」。
- **mediainfo adapter**（`berth/adapters/mediainfo.py`、plan §8.7）：`probe(path)` 回時長、寬高、
  codec、bit depth、音軌語言與逐條內封字幕軌。**失敗不阻擋**（讀不到、讀不懂、函式庫自己爆掉都回
  `None`），Plan 只少一個訊號。`pymediainfo` 相依（wheel 內含 libmediainfo，不需系統套件）。
- **時長 < 5 分鐘的「正片」降為 extra**（`berth/parser/classify.py`、brief §6.2）：檔名像第一集而
  mediainfo 說它 88 秒時，檔名輸。**沒量到不是量到 0**：pre-plan 那一輪一個訊號都沒有，
  而那時候每個檔案都還在下載。
- **`GET /api/plans/{id}`** 與 **`POST /api/jobs/{hash}/replan`**（plan §6）：一份 Plan 的逐檔決定、
  信心與理由；重跑限 `completed` / `planning` / `review`——`importing` 的那一份已經被採信，
  而 importer 正照著它動檔案（票 12）。
- **下載列表的展開區多一塊「匯入計劃」**（`web/src/jobs/JobPlan.tsx`）：一個檔案一列（包含略過的
  那些），逐列說得出處置、信心、季集、**它會被寫到哪一條路徑**與理由。停下來時說得出三種理由
  中的哪一種與下一步。M1 唯讀——逐列編輯與核准是 M2 的 Review Queue。
- **時間線多三種事件**（brief §5.2）：`preplan`、`plan_generated`、`review_required`。
- `--scenario plan`：下載完成 → Import Plan 的演練情境（見 README）。
- `pymediainfo` 相依。
- `AiPlanner` 介面與 `NullAiPlanner`（`berth/adapters/ai.py`，plan §4.5、brief §6.10）：
  `propose(context, files, rules_plan) -> Plan | None`。M4 才有實作，介面先定是因為它約束的是
  規則層——AI 只能提出規則層表達得出來的處置，碰不到檔案。
- **`importer`**（`berth/pipeline/importing.py`、`berth/services/importer.py`、plan §3.1、§3.2、§3.3、
  票 12）：Import Plan 真的落到媒體庫——逐檔建目錄 → 硬鏈接 → 寫帳本 → 事件，**一個檔案 commit
  一次**。目標已經存在時比 inode：同一個就是「上次做到了」，補上帳本；不同就是別人的檔案，整筆
  停在 review 而且不覆寫它。正片鏈接不成是 `import_failed`（重試從沒做完的接著做），字幕與特典
  鏈接不成只記在那一列上。全部落地之後才通知 Jellyfin（`POST /Library/Media/Updated`），失敗
  只記事件、不擋 `imported`。planner 算完就叫醒它，另外每 60 秒掃一次 `importing`。
- **`ledger` 表**（plan §2.3）：一條「來源檔案 → 目標硬鏈接」一列，`target_path` unique。它自己
  站得住——`job_hash` 是弱引用、處置與季集抄一份進來（重新規劃會換掉 plan items）；inode 與
  device 存 TEXT（Windows 的 `st_dev` 超過 SQLite 的有號 64 位元）。
- **`jellyfin_resolver`**（`berth/pipeline/resolving.py`、`berth/services/resolver.py`）：入庫的
  正片在 Jellyfin 裡是哪一個 item。每筆帳本自己的排程 30 秒 → 2 分 → 10 分 → 1 小時 ×3，共 6 次，
  存在帳本上所以重啟不會忘；兩段查詢都以媒體庫為 parent（brief §20.1），也比 `MediaSources` 的
  路徑（第二個版本不是 item 自己的 `Path`）。找到之後觸發 MergeVersions；耗盡寫一筆
  `issue_detected(jellyfin_item_unresolved)`。沒找到兩次以上改跑 Jellyfin 的「重新掃描媒體庫」排程
  任務——**路徑通知對從沒掃到過內容的媒體庫無效**（Jellyfin 12.0.0 實測，brief §20.1），而套件內的
  媒體庫一開始一定是空的。
- Jellyfin adapter 多三支：`notify_paths`、`items`、`run_task`（plan §8.2）。
- **時間線多六種事件**（brief §5.2）：`linked`、`link_failed`（帶 `errno` 與原文）、
  `jellyfin_scan_requested`、`jellyfin_item_resolved`、`merge_versions_requested`、
  `jellyfin_request_failed`；停下來的理由多一種 `target_exists`，需要處理的事多一種
  `jellyfin_item_unresolved`。
- 下載列表上入庫失敗的那一筆有一顆「再試一次入庫」（與「重新送單」同一個端點，回到的是另一站；
  不叫「重新入庫」——那是 M2 的 Reimport）。鏈接失敗只有擋住入庫時才是紅字。
- **媒體庫頁 `/library/:routeSlug`**（票 13、`.scratch/m1/library-shape.md`）：依 Route 分頁的卡片牆，
  牆上是這條 Route 上有 Job 的作品加上檔案落在它底下的。一格說得出狀態（失敗 → 待審 → 下載中 →
  已入庫 / 部分 / 沒有檔案，依序取第一個成立的；只有需要人的那幾格塗漆）、`N / M 集入庫`（分母是
  已播出的正片，S00 不算），以及 Jellyfin 找到了沒——找到了是一條深連結，還沒找到說原因、不給死
  連結。「待審」「Unmatched」兩個篩選在網址上。卡片本體連到 Media 詳情，Jellyfin 那一行是並排的
  另一條連結。`GET /api/inventory`、`GET /api/inventory/{slug}`；頁首多一項「媒體庫」。
- Media 詳情的第 4 塊「檔案與版本」：帳本裡每一個檔案的季集、Tags、目標路徑、帳本狀態與 Jellyfin
  反查狀態（還在掃描時說下一次什麼時候查），對不到的檔案，以及多版本並存（電影是 Tags，劇集是
  整個檔名主幹，brief §7.7）。集表多一欄「入庫」：已入庫 · 卡住 · 下載中 · 缺 · 未播出。
- **Jellyfin 對外網址**（`settings.services.jellyfin.public_url`，在服務設定頁改；
  `GET|POST /api/settings/jellyfin`）：選填，沒填時推導——既有服務用它自己的位址，套件內用瀏覽器
  的主機名加 `base_url` 的 port（Seerr 的 `externalHostname` 慣例）。深連結的形狀是
  `{對外網址}/web/#/details?id=…`，不帶 `serverId`（Jellyfin 12.0.0 實測不需要）。
- 帳本多一欄 `jellyfin_series_id`：resolver 反查到一集時連同它所屬的 Series 寫下，深連結開到作品
  而不是某一集。
- 演練情境 `inventory`（`scripts/fake_setup_server.py`）：替身 Jellyfin 會「掃到」入庫的檔案，媒體庫
  的卡片看得到從「還在掃描」換成「在 Jellyfin 開啟」。
- **Route 設定頁 `/settings/routes`**（票 14、`.scratch/m1/route-settings-shape.md`，只有 admin）：與服務設定頁
  共用一條子分頁列。每條 Route 一列，綠燈收起、紅燈或停用就地展開；展開區改名稱、profile、啟用，
  重新檢查五條纜繩，以及刪除（二次確認）。**同一個 Jellyfin 媒體庫可以建第二條 Route**（brief §4.3）：
  清單下方的「新增 Route」按下去才向 Jellyfin 現查媒體庫與路徑，已經有 Route 的路徑選不了。新建或
  重新啟用時檢查紅燈就維持停用；被下載或入庫檔案指著的 Route 不給刪除鍵，說出原因與出路（停用）。
  `GET|POST /api/routes`、`PUT|DELETE /api/routes/{id}`、`POST /api/routes/{id}/check`、
  `GET /api/jellyfin/libraries`。健康頁的 Route 區塊對 admin 多一條「到 Route 設定」。
- 演練情境 `routes`（`scripts/fake_setup_server.py`）：TV 媒體庫在 Jellyfin 上多掛一顆碟、Movies 多一條
  沒掛進來的路徑、TV 那條 Route 有一筆下載——第二條 Route、紅燈建立與「刪不得」三種樣子都看得到。
- 語料補五筆「只有集號、TMDB 上多季」的真實發佈（票 14c；動漫 14 / 劇集 10 / 電影 4，共 28 筆 368 個
  檔案）：SPY×FAMILY 第二季合集、我的英雄學院 139、航海王 1089–1104、Home and Away 第 8214 集、
  超人回來了 E079。絕對編號換算那一支第一次有語料走到；baseline 的 `auto_correct` 140 → 169，
  `auto_wrong` 仍是 0。
- `scripts/experiments/profile_effect.py`（票 14c）：Route profile 對語料有沒有作用——四種組合重算、
  逐檔比桶、側錄 `_from_number` 的分支。結論在 `docs/research/profile-effect.md`：使用者拍板移除
  profile（票 14d、14e）。
- 語料補兩筆（票 14d；動漫 16 / 劇集 10 / 電影 4，共 30 筆 383 個檔案）：Erai-raws《死神 千年血戰篇 相剋譚》
  01–14（每 cour 重數，正解 S02E27–40；改解析器之前是 `auto_wrong` 14）與 SubsPlease `Spy x Family - 05`
  （第一季的無季號發佈，正解 S01E05）。baseline 的 `auto_correct` 169 → 170，`auto_wrong` 仍是 0。
- `scripts/experiments/absolute_rule_cost.py`（票 14d）：用 M1 票 01 以發佈時間判定正解的 Mikan 發佈，量「集號
  ≤ 第一季集數就送審核」擋下的對與錯，以及「標題有認不出的多餘字」能不能分開兩者（結論：分不開，研究 §6.1.1）。
  `anime_episode_source.py` 的 `Trial` 為此多帶 Mikan 的原始標題。
- **e2e**（票 15、plan §10、README〈e2e〉）：`tests/e2e/` 疊在 `deploy/docker-compose.yml` 上，對真的
  qBittorrent、Jellyfin 12.1 與 TMDB 走一遍 M1（Prowlarr 起來讓精靈偵測，索引站那一步跳過）——精靈八步只打
  Berth 的 API，送美劇一季（The Bear S03）、動漫一季（葬送的芙莉蓮 S01 + 特典）、電影（奧本海默），驗三筆不經
  人工、依序走過完成 → 規劃 → 入庫、帳本季集對語料、硬鏈接兩端同一個 inode、帳本逐檔的 item id 就是 Jellyfin
  在那條路徑上的 item。下載的替身是 `torrents` 容器：由語料的
  檔案清單與 `tests/fixtures/e2e/` 的兩支 330 秒種子影片造出發佈與 `.torrent`，送單之後放進 qBittorrent 的
  下載路徑再 recheck。平常的 `uv run pytest` 不收它（`-m e2e` 才跑）；`.github/workflows/e2e.yml` 在
  nightly、`v*` tag 與手動觸發時跑，TMDB 憑證是 repo secret `TMDB_API_KEY`。
- `scripts/experiments/jellyfin_permissions.py`（M1.5 票 01）：在一次性的 Jellyfin 12.1 上以只開放部分媒體庫的使用者，
  實測伺服器 API key 代讀時哪些端點套用媒體庫權限、`/Items` 的過濾排序分頁是否真的有作用、由 TMDB id 找作品、
  Series / Season 標記遞迴與停用帳號；自己起停容器，`--record` 重錄契約測試用的 fixture（`UserViews`、
  `/Users/{id}`、帶 `UserData` 的 `/Items`、`/Items/Filters`、Resume、NextUp、Seasons、Episodes、
  `UserPlayedItems`、圖片標頭，以及沒權限時的 404 與 `parentId` 洩漏）。結論在 `docs/research/library-browsing.md`
  §2、§3.1、§5、§10、§11 與 brief §20.8。`lib.Response` 多帶回應標頭。
- `jellyfin_permissions.py --only`（M1.5 票 03）：只寫指定的 fixture 檔名；加錄了牆的第二頁與整份清單兩份。
- `jellyfin_permissions.py`（M1.5 票 06）：加錄牆的排序（評分遞增 / 遞減、電影庫的 `DatePlayed`）與類型、年份篩選
  五份 fixture，排序實測補上電影庫的 `DatePlayed`。
- 演練情境 `library`（M1.5 票 03）：整庫瀏覽、分頁、受限使用者，以及 `POST /demo/jellyfin/{disable,enable}` 停用帳號。
- **媒體庫牆上的海報是 Jellyfin 的圖，由 Berth 轉給瀏覽器**（M1.5 票 04，brief §19）：`GET /api/jellyfin/items/{item_id}/images/{image_type}?size=&tag=`。
  瀏覽器不必連得到 Jellyfin，HTTPS 的 Berth 配 HTTP 的 Jellyfin 也沒有 mixed content。縮放由 Jellyfin 做，只收白名單裡的
  類型與具名尺寸（現在是 `Primary` 與 `poster`，其餘 422）；要登入，向 Jellyfin 取圖不帶 API key。圖片回應是 `/api`
  底下唯一不是 `no-store` 的：`private, max-age=31536000, immutable`（網址帶著 Jellyfin 的 `ImageTags`，換圖就換網址）。
  `InventoryCardOut.poster_url` 在 Jellyfin 裡的作品上是這一支的網址；Jellyfin 沒有圖、或圖載不下來時卡片印「無海報」。
  Berth 端不另存圖（量測見 `docs/research/library-browsing.md` §6.1）。
- `scripts/experiments/jellyfin_images.py`（M1.5 票 04）：量縮圖參數與格式協商、Jellyfin 自己的縮圖快取，以及 6 條並行下
  直連 Jellyfin 與經過 Berth 的延遲。演練情境 `library` 的替身 Jellyfin 帶海報。
- **媒體庫牆上的卡片說得出你看到哪了，並可標為已看 / 未看**（M1.5 票 05，brief §12）：Jellyfin 那一頁的每一格多一行
  「已看」「看到 42%」（電影）或「剩 4 集沒看」（劇集，沒開始看的也說），照 jellyfin-web 卡片的判定；最下面那一行多一顆
  「標為已看 / 未看」，寫進你在 Jellyfin 的紀錄，寫完那一格當場換掉、不重抓整面牆。**標為未看先確認**：它清掉觀看次數與
  最後觀看時間、找不回來，劇集清的是每一集。`POST` / `DELETE /api/jellyfin/items/{item_id}/played` 回寫入之後的
  `WatchStateOut`；Jellyfin 的使用者 id 只從 session 來，你在 Jellyfin 看不到的 item 回 404 `item_not_visible` 而且沒有寫入。
  `InventoryCardOut` 多 `watch`（`tracked` 與還沒進 Jellyfin 的是 `null`）。演練情境 `library` 的替身 Jellyfin 每部劇擺
  六集，`deckhand` 與 `skipper` 各看過一些。
- **媒體庫牆可以排序，並依類型、年份篩選**（M1.5 票 06，brief §13）：排序選單照 jellyfin-web，劇集庫與電影庫各自一份
  （劇集有「新集加入」「最近看過」，電影有「影評評分」「播放次數」「片長」），可切遞增 / 遞減；類型與年份各一份勾選清單，
  選項是這個媒體庫的作品真的有的（Jellyfin `/Items/Filters`），可多選、勾了就套用。狀態都在網址上
  （`?sort=&order=&genres=&years=`），重新整理與分享的連結還原得回來，換任何一項回到第 1 頁；「待審」「Unmatched」
  切過去再切回「全部」，排序與篩選還在。篩類型或年份時「還沒進 Jellyfin」那一條收起（它們在 Jellyfin 裡沒有類型），
  篩完一部都沒有時說出篩了什麼，並給一條清掉類型與年份的路。`GET /api/inventory/{library_id}` 多收 `sort`、`order`、
  重複的 `genres` 與 `years`，選單外的排序鍵回 422 `sort_not_offered`；新增 `GET /api/inventory/{library_id}/filters`；
  `InventoryLibraryOut` 多 `sorts`。演練情境 `library` 的作品有類型與評分。
- **首頁與媒體庫頁上方有繼續觀看與下一集**（M1.5 票 07，brief §13、§19）：首頁 `/` 在搜尋列之上是你在 Jellyfin 看到一半的
  集與電影（「看到 42%」），以及每部看過的劇的下一集；媒體庫頁在切換列之下只列這個媒體庫的（只在第 1 頁、沒有篩選時）。
  沒有內容的那一列不畫；一行放不下時收起，「全部 N 項」就地展開。卡片是 16:9 的圖（照 jellyfin-web 橫卡的順序取，經
  Berth 代理），說得出作品、季集與集名，點下去在新分頁開 Jellyfin 的那一集——Jellyfin 沒有直接播放的網址。Jellyfin
  連不上時首頁說一行原因並可重試，探索照畫。新增 `GET /api/jellyfin/watching`
  （整個帳號）與 `GET /api/inventory/{library_id}/watching`（`WatchingOut`：`jellyfin`、`resume`、`next_up`）；圖片代理多開
  `Thumb`、`Backdrop` 兩種類型與 `wide`（16:9、342×192）尺寸。演練情境 `library` 的劇有集號與橫圖、`deckhand` 有看到
  一半的集，另加什麼都沒看過的 `bosun` / `knot`。
- `jellyfin_permissions.py`（M1.5 票 07）：dummy 媒體樹幾部作品多 `landscape.jpg` / `fanart.jpg`，加錄 Resume 與 NextUp
  六份 fixture（Berth 的參數，加上拿掉 `mediaTypes`、帶 `parentId`、換 `nextUpDateCutoff` 的對照）。
- **Media 詳情最上面有觀看區**（M1.5 票 08，brief §12、§13）：作品在 Jellyfin 裡、而且你在 Jellyfin 看得到它時，
  標題底下是一顆主按鈕——看到一半的集是「繼續看 S01E04」、看過前面的是「看下一集」、沒看過是「從 S01E01 開始看」、
  電影是「在 Jellyfin 看 / 繼續看」——在新分頁開 Jellyfin 的那一集（哪一集由 Jellyfin 的 NextUp 算）；下面一塊「觀看」
  是 Jellyfin 的季切換與那一季的集（16:9 劇照、季集代號、集名、已看 / 看到幾 %），每一集可以就地標為已看 / 未看，點下去
  開那一集。電影的標為已看在主按鈕旁邊。**看不到的作品頁面上沒有任何 Jellyfin 的東西**：不在 Jellyfin 與看不到是同一個樣子。
  新增 `GET /api/media/{id}/watch`（`WatchAreaOut`，不在或看不到時是 `null`）與
  `GET /api/jellyfin/shows/{series_id}/episodes?season_id=`（`WatchEpisodeOut[]`）。演練情境 `library` 的 The Office 有兩季
  與 Specials、The Bear 的集有劇照。
- `jellyfin_permissions.py`（M1.5 票 08）：加錄由 TMDB id 找作品、`/Items/{id}` 的劇與電影、這部劇的下一集三種情況
  （看過前面的、看到一半的、沒看過的）六份 fixture。
- **季集與入庫可以只看缺集**（M1.5 票 09）：標題列下方一顆「只看缺集」，開著時每一季說「缺 N 集 / 沒有缺集」、工具列說
  整部作品共缺幾集，展開的集表只留缺的那幾列。缺是已播出、沒有任何下載在處理的集——卡住、下載中、未播出都不算。
- 演練情境 `long-lists`（M1.5 票 09）：同 `inventory`，索引站只給 benchmark 語料裡葬送的芙莉蓮 `[7³ACG]` BD 合集那一包
  （39 個檔案），送到 Anime 之後計劃、入庫與 Jellyfin 反查全是產品自己的程式碼；名偵探柯南（一季 1216 集）打開詳情頁就是。
- **缺集一鍵搜**（M1.5 票 10）：季表上有缺集時，工具列一顆「搜這部作品缺的集」、每一季展開區第一行一顆
  「搜 S01 缺的集」，按下去把查詢交給上面那一個搜尋區塊（結果與送單照舊）。**查詢由後端產生**：
  `GET /api/search` 與 `GET /api/search/queries` 都收 `missing=true` 與 `season=`，兩支走同一個 `missing_queries`，
  所以預覽寫的就是待會兒送出去的。整季缺問季包（`S03`），缺幾集、缺一集逐集問，有絕對編號的用絕對編號
  （`26`，照 Sonarr 的動漫查詢）；記號放不下五個查詢的配額時先收成季記號，六季以上有缺才退回作品名。

- **e2e 多一個模組：權限與瀏覽**（M1.5 票 11，plan §10）。`tests/e2e/` 疊在同一輪 compose 上（精靈、送單、入庫的
  fixture 搬到 `conftest.py`，session scope），`test_2_m15_library.py` 以 Jellyfin API 建一個**只開放一個媒體庫**的
  一般使用者，用它登入 Berth，對真的 Jellyfin 12.1 驗六件事：看不到沒權限的媒體庫、直接請求那個媒體庫也被拒；
  不經 Berth 放進 TV 媒體庫的一部作品照樣在牆上（`tracking` 是 `null`）；觀看區每一集的 `item_id` 就是 Jellyfin
  在帳本那條路徑上的 item；標為已看 / 未看之後**那個帳號自己的**觀看紀錄真的變了（一集自己一次、整部劇遞迴一次）；
  帳號在 Jellyfin 被停用之後 Berth 的 session 結束。最後一條停掉 Jellyfin 容器，驗「問不到 Jellyfin」那一句
  （票 07 留下的：那條路徑之前只有 vitest 與後端單元測試）。
- **刪除範圍：四個可組合的旗標與空間估算**（M2 票 04，brief §9.2、plan §3.1、§6）。
  `DELETE /jobs/{hash}?unlink=&remove_torrent=&delete_files=&purge=`——移除 library 硬鏈接 /
  從 qBittorrent 移除 torrent（不刪檔）/ 刪除 complete 檔案 / 清除帳本與 Job 紀錄，**四個預設
  全不勾**（後端也是，不只對話框）。`delete_files` 沒帶 `remove_torrent` 是 422：qBittorrent
  還握著那個 torrent 時把檔案抽走，它會在下一次重新檢查時把整包再抓一遍。Job 進 `removed`、
  時間線多一筆 `deleted`，payload 說的是**真的**做掉了什麼而不是勾了哪幾個。檔案由 Berth 自己
  逐檔刪（不用 `torrents/delete?deleteFiles=true`）：torrent 可能早就不在客戶端了，而時間線要
  數得出刪了幾個、空出多少。刪除與鏈接同一道路徑守衛（`fs.remove` 要 `roots`），空掉的目錄跟著收。
- **空間估算逐一 `stat`**（M2 票 04，`GET /jobs/{hash}/deletion`）。不用 qBittorrent 報的
  `total_size` 去猜——那是 torrent 的大小，而磁碟上可能只下載了一部分。把要刪的路徑按
  `(device, inode)` 分組，**一組的路徑數等於它的 `st_nlink` 時才算進「真的會釋放」**：硬鏈接
  底下只有最後一個名字消失時那些位元組才回到檔案系統，有 Berth 不知道的第三個鏈接握著的另
  外報 `held`。對話框在算的時候說「正在逐一量測這幾個檔案…」，算不出來仍然刪得下去。
- **`issues` 表與最小 Reconciler**（M2 票 05，plan §2.4、§3.2、brief §9.1）。十一種型別是一個
  封閉集合（對帳的七種加上管線已經在用的四種），冪等鍵 `(type, subject)` 由資料庫守著——
  partial unique index **只蓋 `status = 'open'`**，所以決定過的那一筆留著當歷史，而同一條路徑
  第二次出問題仍然問得到人。`subject` 依型別取哪一欄寫死在 `domain.SUBJECT_OF`，兩張表都要
  涵蓋整個 enum（加一種型別而沒替它決定 subject 或動作就紅）。
- **一輪對帳先把四方各自問完才寫 Issue**（M2 票 05，brief §9.1、§16.2）。四方是帳本、
  qBittorrent、complete 目錄、每一條 Route 的媒體庫目錄；**任一方問不到就跳過那一方並在這一輪
  的結果上說出來**，不把「問不到」誤判成「不見了」。媒體庫那一方**逐 Route** 判斷問得到沒有：
  一條沒掛上不讓其餘幾條停擺，落在它底下的帳本連 `status` 都不動——照著「查不到就是沒有」寫
  的話，一輪對帳會產出一份把整個媒體庫報成失蹤的清單，而使用者會照著它按下「承認刪除並清帳本」。
  這一輪只做 `library_link_missing` 一種檢查（其餘六種在票 09）。
- **`GET /issues`、`POST /issues/{id}/resolve | ignore`、`POST|GET /reconcile`**（M2 票 05，plan §6）。
  `POST /reconcile` 回 **202** 與這一輪的 id（那一輪在背景跑），`GET /reconcile` 回上一輪與進行中
  的進度，正在跑時再按是 **409 `reconcile_running`**——**不排隊**，因為排隊的那一輪看到的會是
  同一份磁碟。整組只有 `admin` 進得來（規則在門禁）。
- **Issue 的三顆按鈕**（M2 票 05，brief §9.1 的「預設建議動作」那一欄）：重新鏈接（照帳本那一列
  再 `os.link` 一次，走 Route 的路徑守衛，帳本那一欄回 `ok`）、承認刪除並清帳本（刪掉帳本那一列，
  來源與其他鏈接不動）、連 complete 一起刪（走票 04 的 `delete_job`，**四個旗標全勾**）。
  **做得到才記成 `resolved`**：修不好時那一件仍然是 `open`，清單上還看得到它並說出原因——畫面說
  修好了而媒體庫沒變是最糟的結果。按得了哪幾顆由後端算（型別**與**這一筆的資料一起決定），
  前端照 `actions` 畫按鈕。
- **`/issues` 頁**（M2 票 05，plan §7、§11.3 決定 3、`.scratch/m2/issues-shape.md`）。獨立的一頁
  而不是健康頁的一段：健康頁是唯讀診斷，這一頁要按動作。一列一件事（型別色塊 + 一句話 + 動作），
  頁首橫幅一顆「立刻對帳」並就地展開四方的進度；「連 complete 一起刪」就地二次確認，文案說清楚
  它的單位是**整筆下載**而不是那一個檔案。導覽入口只有 `admin` 看得到（後端同時回 403）。
- **`services/qbittorrent.managed()`**（M2 票 05，plan §3.2）：「掛著 Berth 記號的那幾筆」
  （category 是某一條 Route 的**或** tag 是 `berth`）只留一份實作，`qbit_poller` 的無主 torrent
  與對帳的客戶端那一方共用——加第三道篩子時不會漏改一邊。
- **演練情境 `issues`**（M2 票 05，README〈設定精靈的 Fake 後端〉）：真的入庫一包三集，真的刪掉
  其中一個媒體庫檔案，所以整條迴圈在瀏覽器裡跑得起來。
- **Review Queue：`GET /review` 一支端點、一份清單、一列一件事**（M2 票 06，plan §6、§11.3 決定 6）。
  每一列以 `kind` 區分形狀，共同的是指向它的物件（`ref`）、一句封閉集合的理由（`reason` 是 code +
  參數，句子由前端翻）、按得了的動作與開始等人的時間。排序是**需要人動手的排前面**
  （`REVIEW_PRIORITY`：`plan` / `unmatched` → `audit` / `duplicate` → `issue`），同一類之內舊的在前；
  **不分頁**，超過 200 列回前 200 並帶 `total`。這一票填進 `audit` 與 `issue` 兩類，其餘三類在票 07、08。
  整組只有 `admin`（規則在門禁）。
- **audit 的確認與撤銷**（M2 票 06，brief §6.5、CONTEXT.md 的 Audit）：`POST /review/audit/{ledger_id}/confirm`
  清掉帳本與 Plan Item 兩處旗標並寫 `audit_confirmed`；`.../undo` 先拆掉那一條硬鏈接（與刪除範圍的
  `unlink` 同一步、同一道 Route 守衛），**拆成了**才刪帳本那一列、Job 回 `review`、Plan 回
  `pending_review` 並帶 `review_reason = audit_undone`，寫 `audit_undone`（`unlinked` 照實說拆到了沒）。
  拆不掉是 409 `unlink_failed`，什麼紀錄都不改。complete 裡的來源不動。
- **`/review` 頁**（M2 票 06，`.scratch/m2/review-shape.md`）：三段抬頭（要你決定 / 已入庫，等你看一眼 /
  外面發生的事），空的段不畫；撤銷就地二次確認並說出「complete 裡的檔案不動、這一筆回到待審核」。
  `/issues` 與 `/review` 的列共用新的 `QueueRow`，Issue 那一列在兩頁是同一個元件、就地按。
- **`user` 看得到「等管理員審核」**（M2 票 06，brief §11）：`/jobs` 上停在待審核的那一列、Media 詳情
  （`MediaOut.awaiting_review`）各一句；admin 不畫。
- **演練情境 `review`**（M2 票 06）：`issues` 加上兩集真的硬鏈接、掛 audit 的 medium 自動入庫。
- **低信心 Plan 逐列改、核准、拒絕**（M2 票 07，plan §3.1 `review` 的出邊、§6 plans 群組）：
  `PUT /plans/{id}/items`（改處置與季集，回改完的整份——新的目標路徑與跟著搬的字幕都在裡面）、
  `POST /plans/{id}/approve`（`review → importing`，叫醒 importer）、`POST /plans/{id}/reject`
  （`review → completed`，叫醒規劃器整份重算）。三支只有 admin（門禁的 `ADMIN_ROUTES`），`GET` 照舊誰都讀得到。
  **核准＝照提案入庫**：待審核的列季集完整就入庫，寫下的路徑就是 `pending_review` 的 Plan 在畫面上
  顯示的那一條（`services/plan_view.landing`）；沒有提案的列與撞同一條路徑的兩列擋住核准。不合法的
  改動是 11 種封閉集合的拒絕（`PlanRefusal`：集數範圍反了、動作與檔案分類矛盾、已經入庫的列…），
  整批不寫。每一列改得成哪幾種處置由後端依分類給（`EDITABLE_ACTIONS`）。時間線多一種 `review_decided`。
- **Review Queue 的 `plan` 那一類**（M2 票 07，`.scratch/m2/plan-edit-shape.md`）：停在 review 的 Plan
  排在「要你決定」那一段，逐列表格就地展開——要人看的列攤在最前，其餘照 `/jobs` 的分組收著；
  逐列「改 → 套用」當場換成後端給的新路徑，核准一顆主要動作，拒絕就地確認。`/jobs` 上停在待審核的
  那一筆，admin 展開看到一條到 `/review` 的路。演練情境 `review` 多一筆由規劃器算成低信心的 `- 05`。
- **修正一個檔案：`POST /files/rematch`**（M2 票 08，brief §7.4、§9.4、plan §6 files 群組）：已入庫的檔案
  （帶 `ledger_id`）與對不到、留在 complete 原位的檔案（帶 `job_file_id`）改成「指派到某一集」「標記為特典」
  「忽略」。一律經過 Plan：內部建一份 `job_hash = NULL`、`engine = user` 的單列 Plan 並立刻套用，走 importer
  的同一步（建新鏈接 → 拆舊鏈接 → 改帳本 → 通知 Jellyfin，拆掉的路徑也通知）；帳本那一列改寫而不是刪了再建，
  字幕跟著它的影片走（改指派時改名跟過去，標記特典或忽略時一起拿掉）。拆不掉或鏈不起來時什麼都不改，
  拒絕是 14 種封閉集合（`RematchRefusal`）。時間線多一種 `rematched`，說得出誰把什麼改成什麼。`files/*`
  只有 admin。
- **重複版本**（M2 票 08，brief §7.8）：規劃時與帳本比，同一集同一組 Tags、或同一個起始集而結束集不同
  （`S01E03-E04` 對 `S01E03`）的那一列**自動模式略過並記事件**（`duplicate_skipped`），其餘照常入庫；
  `plan_items.duplicate_of` 記著撞上的是帳本哪一列（新 migration）。Review Queue 上它是一列 `duplicate`，
  三顆：取代舊版（同一條路徑一步換過去，舊版本的字幕一起拿掉、新版本的字幕跟著進來）、保留兩者
  （完全相同的那一種新檔名多一個 `[2]` 序號標籤）、跳過。`POST /review/duplicate/{item_id}/{decision}`，
  時間線多一種 `duplicate_decided`。
- **Review Queue 的 `unmatched` 與 `duplicate` 兩類**（M2 票 08）：對不到的檔案在「要你決定」那一段，
  修正表單直接攤在列上；重複版本在「已入庫，等你看一眼」，句子說得出後果（範圍不同的那一種：Jellyfin 12
  會把它們併成同一集的兩個版本，後面那一集從集列表消失），取代與「範圍不同時仍然保留兩者」就地確認。
- **Media 詳情的修正入口**（M2 票 08）：Unmatched 區每一列一顆「修正」，檔案清單每一列展開後一顆
  （字幕沒有——它跟著影片走），與 `/review` 同一個表單、打同一支；已入庫的先就地確認。只有 admin 看得到。
  演練情境 `review` 多一筆 S01E03 + OVA：一個重複版本、一個對不到的特典。
- **對帳的其餘六種檢查**（M2 票 09，brief §9.1、plan §3.2）：`source_missing`（媒體庫那一份還在、來源不見了）、
  `inode_mismatch`（附大小是否一致）、`orphan_complete`（只看每一條 Route 的 complete 子目錄）、
  `unknown_torrent`（與 `qbit_poller` 共用冪等鍵與內容）、`unmanaged_library_file`（**只列出，永不刪**）、
  `job_without_files`（那一份 Plan 本來就沒有要鏈的、或使用者自己清掉帳本的不算）。每一種只用它需要的那幾方，
  缺一方就整種不做。
- **Issue 的六顆新按鈕**（M2 票 09）：標記為已無來源、以硬鏈接取代（只在大小一致時給）、刪除孤兒目錄、
  重新規劃、重新反查、重新掃描媒體庫。會刪東西的三顆就地二次確認，而且按下去那一刻重問一次它依據的事
  （目錄仍然沒有主、複製品仍然與來源一樣大）。新的拒絕理由 `in_use`、`size_differs`、`jellyfin_unreachable`、
  `delete_failed`。「認領」類三顆在票 10，管線三種的動作在票 09c。
- **對帳的第五方 Jellyfin**（M2 票 09，brief §20.9）：`GET /reconcile` 的 `sides` 多一方 `jellyfin`。它不開 Issue，
  只把反查過的正片照 Jellyfin 現在的樣子重對一次——票 13 之前反查完的劇集補上 Series id（媒體庫卡片不再一直說
  「還在掃描」），Jellyfin 12 合併之後不再是主條目的 item id 換成主條目。
- **管線三種 Issue 的五顆按鈕**（M2 票 09c，brief §9.1、plan §3.1）：`missing_files` 的重新校驗 / 承認遺失、
  `client_error` 的重試、`client_removed` 的重新送單 / 承認移除。重新校驗與重試向 qBittorrent 送
  `torrents/recheck` + `torrents/start`（4.x 是 `torrents/resume`，照 Web API 版本挑），Job 回到檔案清單到手之後那一站，
  poller 照常往前推；重新送單先問過 Route、下載連結（要拿回同一個 hash）與 qBittorrent 才動 Job；兩顆承認讓 Job 進
  `removed`，磁碟與 qBittorrent 都不動。按鈕只在 Job 還停在那個壞掉的狀態時給。新的拒絕理由 `source_unavailable`、
  `resubmit_failed`、`route_unusable`。
- **兩種新的 Issue：`library_uses_tvdb` 與 `low_disk_space`**（M2 票 09c）。`health_checker` 每一輪在四項之後量：
  每條 Route 的 Jellyfin 媒體庫掛不掛 TVDB 的 metadata fetcher、incomplete / complete 剩的空間夠不夠。條件解除時
  系統自己收掉（`resolved_by = system`），問不到不算解除；它們的「忽略」在條件持續期間有效。十一種變十三種。
- **磁碟空間門檻 `GET|POST /settings/disk`**（M2 票 09c）與服務設定頁上的一個欄位：`min_free_gb`，預設 10，`0` 是不量。
  形狀照 Sonarr 的 Minimum Free Space（一個全域數字），單位是 GB。存完立刻重量一次。新的設定分組 `settings.disk`。
- **重新入庫 `POST /jobs/{hash}/reimport`**（M2 票 10，brief §9.3）：以那一筆的 complete 目錄重新走
  planning → importing，torrent 不在客戶端也行；`job_files` 照磁碟上現在的樣子重寫。只有 admin（門禁），
  `/jobs` 展開區多一顆「重新入庫」（`JobOut.reimportable`）。新的拒絕理由 `not_reimportable`、`content_missing`。
- **`berth rebuild-ledger`**（M2 票 10，plan §11.3 決定 9）：從媒體庫的 inode 反查 complete，季集與 Tags
  由命名模板反解（`naming.read_target`）；配不上的一律變成 `unmanaged_library_file`，理由在 `detail.reason`。
- **三顆認領**（M2 票 10）：`orphan_complete` 的「重新入庫」、`unknown_torrent` 的「認領並建立下載」
  （兩顆都在列上就地選作品，`POST /issues/{id}/resolve` 多帶 `media`）、`unmanaged_library_file` 的
  「認領進帳本」。三顆都不刪東西。新的拒絕理由 `media_required`、`unclaimable`。
- **刪除對話框是一個元件**（M2 票 04，plan §7）：Media 詳情的版本清單與 `/jobs/:hash`（M2 票 12 起；
  在那之前掛在 `/jobs` 的展開區）共用。就地展開而不是 dialog（The Failure Expands In Place Rule）——
  「哪一筆正在被刪」正是這個動作最怕搞錯的事。取消「移除 torrent」會把「刪除檔案」一起收掉，
  不留一個送出去一定被擋下來的勾。版本清單上的刪除掛在**每一個版本**上（`VersionOut` 多帶
  `job_hash`）：多版本並存時要拿掉的是其中一個。

- **大媒體庫量測腳本**（M2 票 11）：`scripts/experiments/large_library.py` 自己 build Berth 的 image、起一次性的
  Jellyfin 12.1 與 qBittorrent 5.2、造 1,000 部 × 12 集，量 `GET /inventory/{id}` 的 p95、對帳一輪與票上五件，
  量完全部拆掉；`--keep` / `--reuse` / `--stages` 讓改了 Berth 之後只重量那一段。
- **Job 詳情頁 `/jobs/:hash`**（M2 票 12，brief §13、`.scratch/m2/job-detail-shape.md`）：身分帶（狀態、發佈名、
  實測值、送單的人、服務原文、hash）→ 動作（重新規劃、重試、重新入庫、刪除範圍）→ 檔案與決策（唯讀的 `JobPlan`）、
  **計劃歷史**、完整時間線。一筆 Job 只有一份現行 Plan，所以計劃歷史是時間線上九種與 Plan 有關的事件
  （`jobs/eventTypes.ts` 的 `planHistory`），畫法仍是 `JobTimeline`。深連結：`/jobs` 的一列、`/review` 四類列與
  `/issues` 的「所屬下載」、直接貼網址；不存在的 hash 是「找不到這筆下載」加回下載列表的路。

- **媒體庫頁的「待審 / 對不到」是審核佇列的清單**（M2 票 14，`.scratch/m2/review-shape.md`「媒體庫的子集」）：篩出來的是
  要處理的事，所以一列一件事、列就是 `/review` 那一列（`review/ReviewItem.tsx`，兩頁同一個 import），就地核准、
  指派；清單下方一句連到 `/review`，說審核佇列裡還有幾件。後端 `GET /review?library=<Jellyfin 媒體庫 id>` 只回
  Route 指向它的 `plan` 與 `unmatched`，另帶 `queue_total`。
- **媒體庫頁的繼續觀看與下一集收成一行「接著看 N 項」、就地展開**（M2 票 14，M1.5 critique P1）：兩列把 390px 上
  的第一張卡推到 y=889，而這一頁的工作是瀏覽媒體庫。首頁的兩列照舊攤開。
- **Media 詳情的季表說得出它是哪一套編號**（M2 票 14，M1.5 critique P3）：標題列下方一句「季與集照 TMDB 的編號」，
  觀看區在時再說上面那一份是 Jellyfin 的；集號欄從裸的 `E09` 改寫成 `S01E09`。
- **媒體庫牆上按名字找**（M2 票 14）：`GET /inventory/{id}?q=` 轉成 Jellyfin 的 `searchTerm`（名字裡的任一段、
  不分大小寫，12.1.0 實測），寫進網址 `?q=`；邊打邊搜、停手 500ms 才換網址（與探索頁同一個間隔），換網址用
  replace、回第 1 頁。搜不到時說搜了什麼，名字與類型年份各一條清除的路。
- **前端 e2e 閘門**（M2 票 15，plan §10）：`pnpm -C web e2e` 以 playwright 對演練情境跑四條流程——精靈八步走完、
  從作品頁送單到已入庫、`/review` 確認一筆 audit、`/issues` 修一條 `library_link_missing`。一條流程一台
  `scripts/fake_setup_server.py`（替身都在程序裡，不打真的索引站與 TMDB），CI 的 `web-e2e` job 每個 push 都跑，
  失敗時截圖、trace 與 HTML 報告上傳成 artifact `playwright-evidence`。演練情境多一個 `import`：送單到入庫整條
  走完、一個請求都不出網。
- **e2e 的 M2 模組**（M2 票 16，plan §10）：`tests/e2e/test_3_m2_repair.py` 疊在 M1 / M1.5 那一輪之上，對真的
  qBittorrent 與 Jellyfin 造三種破壞（Jellyfin 的 `DELETE /Items/{id}`、複製品取代硬鏈接、手動刪來源）與一個
  complete 裡沒人認領的目錄，各自對帳 → 按動作 → 再對帳確認不再開；再把整個 Anime 媒體庫的內容刪光、一次重新入庫。
- **「每一條端點是誰的」有閘門了**（M2 票 16）：門禁的分類收成一支 `api/gate.access_of`（匿名 / 精靈 / 管理員 /
  登入即可），`tests/integration/test_auth_api.py` 以一張涵蓋 app 上每一條路由的表逐條比對——新增端點而沒決定
  它是誰的、修正類的端點忘了進門禁、一般使用者的端點被誤關，三種都會紅；admin 那幾條另以 `user` 真的打一次，
  拿到 403。前端的導覽列逐角色列齊。
- **審核頁的「全部確認」**（M3 票 05）：同一個 Job 的 audit 收成一組、一顆「全部確認」；「已入庫，等你看一眼」
  那一段的標題列另有一顆整段的，先就地確認並說出件數，只確認畫面上列出的那些。後端一支
  `POST /review/audit/confirm`（`{ledger_ids}` → `{confirmed, skipped}`），已經被別處確認或撤銷的列跳過、
  不算失敗。
- **收起的 audit 列說得出為什麼是 medium**（M3 票 05）：「信心 medium：季號是推論的（TMDB 只有一季）」，
  整組原因相同時說一次；完整理由仍在展開裡。
- **命令的副作用標記**（M3 票 05，brief §14）：`services/commands.command(Effect, inverse=...)`，只帶 metadata，
  M5 的命令登錄表讀它；`tests/unit/test_command_marks.py` 守著反向命令必須是已標記的命令，M3 起新增的 service
  模組裡公開的 `async def` 都要有標記。
- **索引站看得到語言，加入之後可以試搜與移除**（M3 票 06e）：勾選清單每一站顯示語言（照 UI 語言的語言名）與
  Prowlarr 定義自帶的英文說明（`GET /api/setup/indexers` 的選項多 `language`、`description`、`indexer_id`）。
  加完站之後的「試搜」逐站列出搜到幾筆與前三筆標題，一站失敗不影響其他站，留白就是問各站最新的發佈
  （`GET /api/setup/indexers/search?query=`，只讀）；每一站可以就地確認後移除（`DELETE /api/setup/indexers/{id}`，
  只對套件內的 Prowlarr）。既有 Prowlarr 或 Torznab 接上之後同樣可以試搜。
- **套件內 Jellyfin 的媒體庫由你命名、增刪**（M3 票 06f）：泊位 1 的剖面在按「開始靠泊」之前是一張可編輯的
  清單——內容類型（電影 / 劇集）、名稱、資料夾（`<library_root>` 底下一層，名稱是英文時自動帶出），預設仍是
  Movies / TV / Anime。停手就存（`PUT /api/setup/jellyfin/bundled`，`GET /api/setup/jellyfin` 多 `bundled`、
  `library_root`），重名、重複資料夾、跳出根目錄的資料夾與空清單各有說法。靠泊之後建好的列鎖住（改名與刪除去
  Jellyfin），新加的列重跑時才建；第 5 步替每一個建出來的媒體庫建一條 Route。

- **精靈的冷啟動閘門與瀏覽器 e2e 四條**（M3 票 06h）：`tests/e2e` 不加 `--wait`，四個容器同時起來、Berth 一回應
  就開始精靈，照常輪詢到三個服務都判定完成、不按重新探測（第一輪就全部判定完成算失敗）；`torrents` 容器改成自己等
  Berth。`GET /api/setup/status` 多 `probe_targets`：第 2 步探的三個 compose 位址，畫面照它寫，`.env` 換了
  `QBITTORRENT_WEBUI_PORT` 就跟著變。`pnpm -C web e2e` 多既有服務（`mixed`）、冷啟動（`starting`）、精靈跑完之後的
  設定頁（`healthy`）三條，精靈與設定頁的四條在 1280 與 390 各走一次、每一格留一張截圖。替身的 `starting` 照
  探測次數演四個容器同時起來的時間線（Jellyfin 回不像它的東西、兩次 503），原本「讀不到 Prowlarr 的 API key」
  拆成 `key-missing`；`mixed` 的舊媒體庫路徑是真的存在的暫存目錄，精靈走得完。
- **RSS：Mikan 聚合 feed → 待綁定 → 綁定 → 入庫**（M3 票 08，brief §15、plan §2.4、§3.2、§8.5）：新頁 `/rss`
  （只有管理員）。貼上 Mikan「我的番組」的 RSS 網址加一個 Feed，背景迴圈 `rss_poller` 照每個 Feed 自己的間隔
  （預設 15 分鐘）輪詢；每一筆第一次出現時讀它的單集頁，認出是哪一部 × 哪一個字幕組（RSS Series），新的一律待綁定、
  它的集數留著不送。在待綁定那一列搜 TMDB、選作品與 Route，確認時說出會定下來的資料夾名與要送出的集數，按下去
  就綁好並送單（`trigger = rss`）；之後同一個 RSS Series 的新集數每一輪自動送。同一個 Feed 輪兩次不會多出 Item 或
  下載（GUID 去重）；Mikan 的發佈時間讀 `<torrent><pubDate>` 當 UTC+8。刪 Feed 連它的 Item 一起刪、RSS Series 與
  綁定留著。新表 `rss_feeds`、`rss_series`、`rss_items`（migration `b7e2c4d9a813`），新依賴 `feedparser`。
  規劃時讀 RSS Series 上的季號與集號偏移（改正與重算在票 13）。演練情境 `--scenario rss`，`pnpm -C web e2e` 多
  `rss` 一條（1280 與 390）。
- **RSS Series 自動綁定**（M3 票 09，brief §15「綁定」）：新長出的 RSS Series 在那一輪就去認作品——讀 Mikan 番組頁的
  中文名與「放送开始」，加上發佈名的標題骨幹去搜 TMDB。名字相同、開播日期落在 TMDB 某一季首播前後 14 天內、而且只有
  一部這樣的作品，**同時**收得下它的啟用中 Route 只有一條，就以 `system` 身分綁上並送單；時間線的「已建立」與 `/rss`
  綁好的那一列說出依據。其餘留在待綁定，那一列寫出為什麼（沒有候選、同名不同年、兩部都對得上、Route 不只一條……），
  認得出的作品列成候選、一鍵選定就接到 Route 與確認。`rss_series` 多 `reasons_json`、`candidates_json`（migration
  `a9c4e2f7b315`）；`POST /rss/feeds/{id}/poll` 多回 `bound`，`GET /rss/series` 每一列多 `reasons` 與 `candidates`。
  量測腳本 `scripts/experiments/rss_auto_bind.py`。
- **RSS 的排除條件三層與去重**（M3 票 10，brief §15「全部接受，只排除」「處理」）：Feed 裡的項目預設全部下載，
  只擋排除條件寫的——全域（`/rss` 的「排除條件」段，存在 `settings.rss`）、每一個 Feed、每一個 RSS Series 三層取
  聯集。規則格式照 Sonarr 的 release profile：一般字詞不分大小寫、比對整個標題，`/…/` 是正則（`/…/i` 不分大小寫）；
  寫壞的存不進去（422 `rule_invalid`，說出 Python `re` 的原因）。**預設不自動下載合集**（不是單集的：合集、區間、季包），
  可以關掉；720p、简体這類是一鍵加入的建議項。規則收緊時還沒送出去的 Item 照新規則再看一次，放寬不把已經擋下的放回來。
  去重：同一個 info hash（另一個 Feed、手動送過、刪掉過）與帳本已有同一部作品、同一季集、同一組 Tags 的不再送；
  v2 的 Tags 不同，同一集的 v1 與 v2、兩個字幕組的版本都入庫並存。擋下的 Item 是 `excluded` / `duplicate`，`/rss`
  的清單說出是哪一層的哪一條、或重複了哪一筆。新端點 `GET/PUT /rss/exclusions`、`PUT /rss/feeds/{id}/exclusions`、
  `PUT /rss/series/{id}/exclusions`；`rss_feeds` 與 `rss_series` 多 `exclude_json`、`rss_items` 多 `skip_json`
  （migration `d5b8e1a3c702`）。`pnpm -C web e2e` 多 `rss-exclusions` 一條（1280 與 390）。
- **Nyaa 與 acg.rip 的 Feed**（M3 票 11，brief §15）：`/rss` 收 `nyaa.si`（搜尋與使用者 feed，magnet 模式也收）
  與 `acg.rip`（搜尋 feed）的 RSS 網址。這兩站的 RSS Series 以標題骨幹 + 字幕組認出來（同一組的简日、繁日發佈
  是同一個）；沒有番組頁，自動綁定只列候選、留給你選。
- **新 Feed 的第一輪預覽**（M3 票 11）：搜尋 feed 第一輪就帶著幾個月的歷史，所以選過之前一筆都不送——`/rss`
  頁首的「等你決定」列出每一筆會送出、綁定之後送、被排除（合集在這裡）或重複，選「只追之後的」或「全部下載」。
  Mikan 的 Feed 不走預覽。新端點 `GET /rss/feeds/{id}/preview`、`POST /rss/feeds/{id}/prime`；Feed 多 `primed_at`、
  Item 多 `size` 與 `passed` 狀態（migration `c3e9a7f1b204`，既有的 Feed 算選過）。`pnpm -C web e2e` 多
  `rss-preview` 一條（1280 與 390）。
- **Mikan 的補舊集與每日補漏**（M3 票 12，brief §15「補舊集」）：聚合 feed 只有最近的集數，所以綁定 Mikan 的
  RSS Series 時會讀它的單一 feed（`/RSS/Bangumi?bangumiId=&subgroupid=`），聚合 feed 沒帶到的舊集一起送；
  媒體庫已經有、或已經下載過的跳過，合集照樣被排除條件擋下。綁定畫面多一格「同時補下載舊集」，預設勾選；
  取消勾選時綁定之前發佈的舊集記成略過（之後的每日補漏、換到另一個 Feed 也一樣）。自動綁定照預設全補。之後每個
  綁好的 Mikan RSS Series 每天再讀一次單一 feed，接住 Berth 停機期間被聚合 feed 捲掉的集數；讀不到寫在那個
  Feed 的錯誤上、下一輪再試。`PUT /rss/series/{id}/binding` 多 `backfill`（預設 `true`）；`rss_series` 多
  `backfilled_at` 與 `passed_before`（migration `e8a3d6c1f59b`；既有的已綁定 Mikan RSS Series 不在升級那一刻補整季，
  只補它出現之後被捲掉的）。
  `pnpm -C web e2e` 多 `rss-backfill` 一條（1280 與 390）。
- **RSS Series 的第一批審核、改正並套用到整個 Series**（M3 票 13，brief §15「季號與 offset」）：新 RSS Series 送進來的
  集數入庫之後不論信心都等人看一眼，`/review` 以 RSS Series 分組、一組一顆「全部確認」；確認之後這個 Series 的
  medium 入庫不再進 audit 清單。第一批裡改一集的季集時可以勾「套用到這個 RSS Series」：由那一集算出季號與
  offset 寫回 Series，還沒確認的集數跟著重算——已入庫的搬到正確路徑（仍留在第一批裡等確認），停在審核的重新
  規劃；split-cour（TMDB 併成一季、字幕組每個 cour 從 01 重數）改一次就整季修好。每份計劃記下它用的季號與
  offset，`/jobs/:hash` 看得到。新端點 `POST /review/series/{id}/confirm`；`POST /files/rematch` 多
  `apply_to_series`（回應多 `series`，拒絕多 `not_from_series`、`no_episode_number`）；`GET /review` 的 audit 列多
  `action` 與 `series`、理由多 `first_batch`；`GET /plans/{id}` 多 `series`。`rss_series` 多 `confirmed`、`plans`
  多 `rss_series_id` / `season_hint` / `episode_offset`（migration `a4f7c2e9d168`；既有的 Series 算還沒確認，
  既有的 Plan 不回填）。演練情境多 `rss-split-cour`。
- **播出日比對**（M3 票 14，plan §4.4、§11.4「三道程式檢查」①）：規劃時拿來源的發佈時間比換算出的那一集的
  TMDB 播出日，可疑的不自動入庫、停在 `/review`，理由說出兩個日期。兩條規則：發佈早於那一集的播出日超過兩天
  （換算過頭，手動送單與 RSS 都套）；連載中的 RSS Series 對到的那一集比作品在發佈當時最近播出的一集早 6 週以上
  （split-cour 從 01 重數而 offset 沒設）。被擋的那一列季集與路徑留著，BD 版晚發這種其實沒錯的核准就照畫面上的
  位置入庫。來源沒給發佈時間、或 TMDB 沒有那一集的播出日時不擋，理由裡記一筆。新的審核理由 `air_date_conflict`
  與四種逐列理由（`released_before_airing`、`behind_latest_episode`、`air_date_missing`、`published_missing`）。
  發佈時間跟著 Job 存下來：`jobs.published_at`（migration `c8d2f5a1e734`；既有的 RSS Job 從 Feed Item 回填），
  `POST /jobs` 的 `source` 多選填的 `published_at`；搜尋結果 `GET /search` 每一列多 `published_at`，結果表多一欄
  「發佈」（相對時間，滑過去是完整日期；索引站沒給時 `—`）。
- **片長驗證**（M3 票 15，plan §4.1、§11.4「三道程式檢查」②）：規劃時拿 mediainfo 量到的片長比換算出的那一集的
  TMDB 片長，差超過 3 分鐘**而且**超過 15% 的不自動入庫、停在 `/review`，理由說出兩個片長——抓 SP、OVA、兩集合併
  的檔案被當成一集正片。被擋的那一列季集與路徑留著，片長其實沒錯的核准就照畫面上的位置入庫。手動送單、RSS、
  認領與重新入庫都走同一條；TMDB 沒有那一集片長時不擋、記一筆，mediainfo 沒量到時不擋。短於 5 分鐘的「正片」
  照舊由分類器自動降成特典。新的審核理由 `runtime_conflict` 與兩種逐列理由（`runtime_mismatch`、
  `runtime_missing`）。
- **以發佈時間推測虛擬季**（M3 票 16，brief §6.4、plan §4.4）：字幕組每一輪播出從 01 重數時，看哪一種讀法換算出
  的那一集是發佈前六週內播的——只有「某一輪的重數」那一個剛播，就照那一輪數。TMDB 把好幾輪放在同一季的作品
  （《死神》千年血戰篇、Re:Zero）不再被照字面讀成第一輪的集數，第二季以後從 01 重數的也不再只能送審核。至多
  medium，推測出的集數照樣過播出日比對；沒有一種讀法剛播（BD、補檔、重播）或不只一種時照舊。規劃、RSS 送單前的
  去重與搜尋結果的季集預估都用它。新的策略 `published_run` 與逐列理由 `published_in_run`；benchmark 語料多了選填的
  `published_at`（帶時區）與四筆《死神》，`auto_correct` 172 → 177，其中一筆原本自動入錯。
- **Jellyfin 回驗**（M3 票 17，plan §11.4「三道程式檢查」③）：反查找到 item 之後，Jellyfin 認到的季號、集號
  （多集檔是範圍）與所屬作品的 TMDB id 要與帳本一致，不一致就開一件新型別的 Issue `jellyfin_item_mismatch`
  （一列帳本一件），`/issues` 上並排說出帳本與 Jellyfin 各自認成什麼、差在哪，動作是「重新反查」；下一次比到
  一致時系統收掉。每日對帳的 Jellyfin 那一方比同一份，入庫之後才出的意外（重掃時兩份不同範圍的正片被併成一集、
  有人在 Jellyfin 裡改認作品）也抓得到。它是便宜的保險：Berth 自己算錯的集數抓不到——Jellyfin 認集數靠的就是
  Berth 取的檔名。
- **一次性 RSS 連結**（M3 票 18，brief §15）：`/rss` 多一段，貼一條 Mikan、Nyaa 或 acg.rip 的 RSS 網址讀一次，
  列出每一筆的季集、tags 與是不是合集；選一部作品與一條 Route 之後季集照那部作品換算，並標出已經有下載、媒體庫
  已經有同一個版本的那幾筆；勾幾筆（「勾選全部單集」不勾合集與已經有的）就逐筆走一般的手動送單，舊的先。
  **不建 Feed、不長 RSS Series**，之後的集數不追；排除條件只管自動下載，合集這裡照樣送得出去。新端點
  `POST /rss/oneshot`（只讀）；網址認不出、讀不到、讀到的不是 RSS 各有自己的理由（新的 `feed_not_rss`）。
- **詳情頁的「RSS 訂閱」**（M3 票 19，只有 admin）：列出綁在這部作品上的 RSS Series；新增訂閱時 Mikan 由 Berth 代搜番組、選字幕組、建單一 feed 並綁上（預設補齊整季），Nyaa / acg.rip 以作品的標題建搜尋 feed、長出的字幕組都預先綁到這部作品，第一輪就地預覽。新端點 `GET /api/rss/mikan/search`、`GET /api/rss/mikan/bangumi/{id}`、`POST /api/rss/subscriptions/mikan`、`POST /api/rss/subscriptions/search`；`GET /api/rss/series` 多 `?media=` 與五個欄位；`rss_feeds` 多三欄（migration `f4b9d2e6a157`）。
- **一個站一份請求預算**（M3 票 20，plan §3.2）：RSS 輪詢、補舊集與每日補漏、索引站搜尋與 `/rss` 上人按的讀取共用一份，以主機名為鍵、每站每小時 60 個（滾動窗，形狀照 Prowlarr 的 Query Limit）；用完的那一個不送，被擋下的工作照原本的退路下一輪再試。健康頁多一塊「請求預算」，新端點 `GET /api/health/budget`；搜尋放不下時回 `problem = budget_exhausted` 與 `retry_at`，`/rss` 的讀取回 429 `budget_exhausted`；自動綁定被擋下的理由是新的 `lookup_deferred`、之後的輪詢再認。
- **Feed 帶一條自動綁定的 Route**（M3 票 21，brief §15「綁定」）：收得下認出來那部作品的 Route 不只一條時（預設安裝的 TV 與 Anime 都收劇集），自動綁定送進加 Feed 時選的那一條（照 Sonarr Import List 的 Root Folder），理由是新的 `feed_route`。`POST /api/rss/feeds` 多選填的 `route`（不存在是 422 `route_missing`），Feed 的每一列多 `route_id`；`/rss` 的新增表單在兩條以上啟用中的 Route 時多「自動綁定送進」，Feed 列說出它。
- 真服務 e2e 多第四個模組 `tests/e2e/test_4_m3_rss.py`（M3 的八條驗收），公開 RSS 站由 compose 裡的 `sites` 容器冒充（`tests/e2e/sites.py`，HTTPS，測試 CA 在 `tests/fixtures/e2e/tls/`）。前端 e2e 多 `rss-auto-bind`。

### Changed
- **精靈的密碼只問一次**（M4 票 40，brief §19 D4，2026-10-06 審計 S1、E-3）：全套件內的流程原本要打 4 次密碼
  （建擁有者 2 次、qBittorrent 與 Prowlarr 的介面登入各 1 次）。頁 1 建套件內 Jellyfin 的管理員時多一個預設勾著的
  「套件內 qBittorrent 與 Prowlarr 的介面也用這組」：密碼只留在精靈那一個分頁的記憶體裡，到頁 2、頁 4 自動以
  「沿用 Jellyfin 帳密」送出（後端照舊先向 Jellyfin 驗過才寫），重新整理之後才再問；Jellyfin 密碼不合
  qBittorrent 的規則時頁 2 說明不能沿用、給自設的欄位。完成頁的介面登入照實際情況說：這一輪精靈設的、那一台
  原本就有的（重裝保留 config，原本也說成「精靈裡設的那一組」）、還沒設的。API：`GET /api/setup/qbittorrent/diff`
  與 `GET /api/setup/indexers`（及回同一份的命令）多 `web_ui_login_by_berth`——那一組是這個 Berth 寫進去的；
  登入那一條纜繩分不出來（Prowlarr 的「加入」每次把它重算成 `skipped`）。
- **精靈、設定頁與健康頁的錯誤分成人話與技術細節**（M4 票 21）：失敗的那一條說一句人話（由後端的封閉代碼選
  i18n 文案）、給照來源挑的補法，後端的英文原文、HTTP 狀態、端點、`dev=` / `inode=` 收進預設收起的「技術細節」。
  API：`StepOut` 多 `failure`（`StepFailure`）與 `params`；`QbittorrentOut` 與 `IndexerSetupOut` 多 `failure`；
  `ServiceOut` 多 `error`（連線測試的原文）與 `auth_failures`（這個位址上連續幾次帳密不被接受）。舊資料裡沒有代碼的
  失敗讀出來是 `unexpected`。
- **qBittorrent 的版本在測連線時就擋**（M4 票 21）：低於 4.4（Web API 2.8.4）的那一台，服務頁的連線測試是
  `version_unsupported`，不再是綠燈之下的泊位卡紅燈；既有那一台的補法不給 `docker compose pull`。
- **既有 qBittorrent 的帳密不對時，Route 檢查的第一條說的是登入那一次**（M4 票 21）：原本登入的失敗被吞掉、
  建分類時以 403 紅燈，補法給成「分類衝突」。
- 精靈頁首數的是泊位（「第 2 個，共 5 個泊位」，完成頁說「收尾」）；qBittorrent 的主鈕「套用這 N 項」把要設的
  介面登入算進去；偏好表與媒體庫類型用人話的名字。
- **缺集一鍵搜分批問完**（M3 票 20，plan §8.4）：季記號放不下一次搜尋的五個查詢時不再退回作品名，而是分批——每一批一組季，搜尋區塊說出這一批問了哪幾季、下一批是哪幾季、請求預算何時放得下，「問下一批」由人按。`GET /api/search` 與 `/search/queries` 多 `from_season=` 參數（下一批從哪一季起）與 `batch` 回應欄位（`from_season` 單獨帶著是 422 `from_season_without_missing`）。
- **從審核裡套用到 RSS Series**（M3 票 14b，brief §15）：連載中的 split-cour 第一批會被播出日比對整批擋在
  `/review`、一集都沒入庫，現在停在審核的計劃列也有「套用到這個 RSS Series」（`PUT /plans/{id}/items` 的
  `apply_to_series`，只配一列）。那一列照人說的、那一份仍等你核准；同一份裡沒人碰過的列、同一個 Series 其餘
  停在審核的計劃照新的季號與偏移重算，播出日比對照跑，對了就自動入庫（仍在第一批裡）；管理員逐列改過的
  其他計劃不動。回應多 `corrected`，拒絕多 `not_from_series`、`no_episode_number`。演練情境
  `rss-split-cour-airing` 與 e2e `series-offset-held`。
- **標題自己寫了 `(Batch)`、`[Vol.1]` 的發佈算季包**（M3 票 11）：Nyaa 與 acg.rip 搜尋 feed 裡的 BD 單卷與季包
  原本被當成單集、會被 RSS 自動下載；現在「不自動下載合集」擋得下它們。只認自己一格括號的寫法，標題裡的
  `The Bad Batch`、`Vol. 2` 不算。
- **RSS 送出的下載，時間線上的建立者是 `rss:<RSS Series id>`**（M3 票 08，plan §2.3）：原本一律寫 `system`。
- **同一個 torrent 已經由別的 Feed、手動送單送過（或刪掉過）時，RSS 的那一筆記成「重複」而不是「已送單」**
  （M3 票 10）：連到原本那一筆下載；刪除過的那一筆不再讓 RSS 每一輪撞一次 `job_removed`。同一個 RSS Series 自己
  送過的（刪掉 Feed 再加回來、送單中途程序中斷）照舊認回成已送單。
- **精靈每一步的工作面排在剖面前面**（M3 票 06h）：窄版第一屏就是這一步的標題與動作（390 寬時原本要捲到
  800–1500px），桌機看起來不變；套件內 Jellyfin 要建的媒體庫清單從剖面搬進工作面、排在「開始靠泊」之前。換步時
  焦點給新一步的標題，按下的鍵做完被換掉時接到「前往下一個泊位」；窄版捲動時底部留出固定動作列的高度。
- **既有 Jellyfin 的媒體庫加過 Berth 路徑時，第 5 步預選它當寫入目標**（M3 票 06h）；第 5 步的「加入 Berth 路徑」
  改成與第 3 步同一顆就地確認。
- **精靈只管第一次，設定頁接手之後的修改**（M3 票 06i）：設定分五頁，照泊位板的順序——
  `/settings/jellyfin`、`/settings/qbittorrent`、`/settings/routes`、`/settings/indexers`、`/settings/tmdb`
  （`/settings` 落在 Jellyfin）。每一頁重用精靈那一格的元件、送精靈的同一批 `setup/*` 命令：既有服務換位址或
  帳密、既有 Jellyfin 重新登入換 API key、加站 / 試搜 / 移除、換 TMDB key；每一頁頂端是那個服務的健康卡與
  「重新檢查」。套件內的服務沒有位址表單。Jellyfin 對外網址住 Jellyfin 頁，建議設定的還原與磁碟空間門檻住
  qBittorrent 頁。精靈跑完之後打開 `/setup` 會被帶到設定頁；探索頁、詳情頁、搜尋結果與健康頁的「去補上」
  連結一律指設定頁的那一頁（「前往設定：TMDB」），一般使用者看到的是「請管理員…」。索引站的勾選清單改從
  Prowlarr 現在有的那幾站勾起，移除的站不會在下一次加站時被加回來。
- **已經有一把驗過的 TMDB key 時，新的測不過就不換**（M3 票 06i）：`POST /api/setup/tmdb/test` 照樣回這一次的
  紅燈，但不存、`verified` 仍是 `true`；還沒有驗過的 key 時照舊先存再測。設定頁說出「沒有換掉」。
- **索引站與 TMDB 拆成兩個泊位，泊位板變五格**（M3 票 06e）：BTH 4 索引站（第 6 步）、BTH 5 TMDB（第 7 步），
  精靈與健康頁都是；`?berth=5` 是 TMDB（探索頁與詳情頁「憑證缺失」的連結跟著改），`?berth=4` 仍是索引站。
  索引站那一格的詳情列說出接上的是哪一種（Prowlarr / Torznab）與站數，還沒加站時寫「Prowlarr · 尚未加入索引站」；
  健康頁的 TMDB 那一格讀精靈第 7 步那一次憑證測試的結果（`GET /api/health/detail` 多一個 `tmdb_verified`），
  不是第五項檢查。
- **預設索引站拿掉 AniDex，剩九個**（M3 票 06e）：Prowlarr 的定義還在，但 anidex.info 從 2026-09-08 起一直回 502。
- **精靈的步驟順序：媒體庫路徑移到 qBittorrent 之後**（M3 票 06d）：第 5 步是 Route、第 6 步索引站、第 7 步 TMDB；
  泊位板與健康頁的順序跟著變（BTH 3 媒體庫路徑、BTH 4 來源），`?berth=` 的號碼也是。`GET /setup/status` 的
  `current_step` 照新順序。套件內的媒體庫走到那一步就自動建 Route、跑五條檢查，沒有要按的鍵。
- **精靈有導覽了**（M3 票 06d）：每個泊位做完停在結果上、按「前往下一個泊位」才走；泊位板上走過的格子可以點；
  每一頁有「上一個泊位」，回頭看時有「回到目前這一步」與「這裡能做 / 不在這裡做」的說明。第 1、2 步在板上方的
  前置列，原本每一頁頂部的「改帳密」「重新探測」拿掉；「重新偵測這個服務」放在出問題的那一格旁邊
  （`POST /setup/detect` 多一個選填的 `kind`）。
- **精靈第 1 步的「將會寫入」照第 2 步的判定說話**（M3 票 06c）：三個服務的標籤都是「帳密」、值寫
  「帳號 · 密碼同上」（不顯示密碼）；偵測之前寫「第 2 步偵測到是套件內的才建立 / 寫入」，既有服務寫
  「你自己的服務，不建立 / 不寫入」，Berth 那一列在既有 Jellyfin 時寫「用你 Jellyfin 的管理員登入」。
  lede 與勾選框的提示不再在偵測前斷定 Jellyfin 會被建立管理員。
- **帳號交給 Jellyfin 之後，第 1 步只改得動 qBittorrent 與 Prowlarr 介面那一組**（M3 票 06c，Seerr 的慣例）：
  `GET /api/setup/status` 多了 `interface_username` 與 `jellyfin_owns_account`；套件內 Jellyfin 的管理員建好、
  或 Jellyfin 判為既有之後，`POST /api/setup/admin` 只覆寫介面那一組，畫面說出密碼在 Jellyfin 裡改、改完要
  回到第 4、5 步重新套用。`settings.setup.admin` 多了 `interface_username` / `interface_password`，
  migration `c3d8a6f1b240` 從舊的那一組抄過去；`settings.setup.indexer.login_password` 記 Berth 上一次寫進
  Prowlarr 的密碼。
- **部署套件的五個對外 port 進 `.env`**（M3 票 06b，brief §19 2026-09-24）：`BERTH_PORT`、`JELLYFIN_PORT`、
  `QBITTORRENT_WEBUI_PORT`、`QBITTORRENT_BT_PORT`、`PROWLARR_PORT`，預設是原本的號碼，舊的 `.env` 照樣能用。
  qBittorrent 的兩個 port 內外兩側一起換（並設 `WEBUI_PORT` / `TORRENTING_PORT`），換 WebUI port 不再吃 401，
  也不靠 `WebUI\HostHeaderValidation=false`。`JELLYFIN_PORT` 與 `QBITTORRENT_WEBUI_PORT` 同時傳給 Berth
  （新的同名環境變數，`berth/config.py`）：精靈探 `http://qbittorrent:<QBITTORRENT_WEBUI_PORT>`，第 4 步與
  Route 檢查連判定記下的那一條。
- **`/review` 不再列 Issue**（M3 票 05，brief §19 2026-09-24）：Issue 只在 `/issues`，`/review` 原位一行
  「另有 N 件待處理」連過去（`GET /review` 多一格 `issues_open`，`kind` 少了 `issue`，`total` 與 `queue_total`
  不再算 Issue）。處理完一件 Issue 的那一句朗讀搬到 `/issues`。
- **探索頁只放 TMDB 牆，登入後落在媒體庫**（M3 票 06，brief §19 2026-09-24）：繼續觀看與下一集只在媒體庫頁
  （「接著看 N 項」）；沒有指定去處時登入後到 `/library`，第一次開 `/` 不再被記成「原本要去的那一頁」。
- **Berth 送出的回應以 gzip 壓縮**（M3 票 06，M2 票 16 audit）：前端那一包 JS 傳輸從 760 KB 降到約 216 KB；
  SSE 與已壓縮的圖不壓。

- **媒體庫牆一頁 50 部**（M2 票 13，原本照 jellyfin-web 的 100）：100 部的牆量到 1,732 個 DOM 節點、222 個 Tab 停留點；
  減半之後 931 個、121 個，`GET /api/inventory/{id}` 的回應 53.7 KB → 27.6 KB（`--scenario library` 的 Movies）。
- **首頁與媒體庫頁的繼續觀看、下一集讀取中照上一次的形狀佔位**（M2 票 13，使用者拍板）：原本讀完才插進來，
  下面整頁往下推，首頁 CLS 0.3453、媒體庫 0.1538；現在兩者都是 0（第一次來沒有紀錄時照舊）。上一次的列數存在
  瀏覽器的 `localStorage`（`berth.watching.<使用者>.<頁面>`），存不下或讀不到就不佔位。媒體庫翻頁、篩選時那兩列
  不畫，那個位置改成一行字說它們在第 1 頁，並給一條回去的路（上一次有東西可接著看時才說）。
- **圖片代理多兩個尺寸 `poster_large`、`wide_large`**（684 寬，M2 票 13），前端每一張圖帶 `srcset`（TMDB 海報給
  `w185`–`w780`）：手機兩欄與高密度螢幕上 342 寬的圖是糊的。詳情頁的海報與牆共用同一個 `ArtSlot`。
- **`GET /api/search/queries` 多一個 `problem`**（M2 票 13）：沒接索引站時是 `not_configured`，Media 詳情的搜尋區塊
  按下去之前就說下一步。
- **牆上卡片的連結與按鈕名字帶上作品名**（M2 票 13，plan §11.3 的二選一）：「在 Jellyfin 開啟：The Bear（開新分頁）」
  「標為已看：The Bear」、整格連結的名字就是作品名（繼續觀看與下一集、集卡是「作品名 S01E04 集名」），類型年份與狀態改成描述。
  四面牆（探索、媒體庫、繼續觀看與下一集、集卡）都是 `<ul>` 清單、作品名都是 `<h3>`。

- **`/jobs` 的展開區只剩狀態與時間線摘要**（M2 票 12，plan §11.3 決定 1）：最近三段時間線（說出較早的還有幾筆）、
  hash 與「下載詳情」。計劃與每一顆動作（重試、重新規劃、重新入庫、刪除）搬到詳情頁，那一塊不再有第二份實作。

- **帳本以來源冪等**（M2 票 10）：importer 先以目標路徑、再以「同一筆 Job 的同一個來源」找那一列帳本。
  TMDB 改了集名之後重新入庫，那一列換到新的路徑、舊的那條鏈接（同 inode 才算自己的）被收掉，
  而不是多長一列、讓 Jellyfin 多一個同一集的版本。
- **重新入庫把 Issue 收乾淨**（M2 票 10 後續）：importer 接回帳本某一列時，掛在那一列上的
  `library_link_missing` / `source_missing` / `inode_mismatch` 由系統收掉（以 `ledger_id` 認，集名改了
  也收得到）；入庫長回至少一列帳本時，那一筆的 `job_without_files` 一起收。規劃時帳本上來源就是這一包
  自己檔案的那幾列不算另一個版本（`rebuild-ledger` 長回的無 Job 列曾讓自己被判成自己的重複）。
- **選作品**（M2 票 10 後續）：搜尋框預填解析器從名字讀出的標題（`IssueOut.query`）、展開時焦點進搜尋框，
  搜尋與探索頁共用 500ms 防抖（`useDebounced`）。`/jobs` 時間線上重新入庫那一格標「重新入庫」而不是「重試」。
- **重新入庫要下載完過**（M2 票 10 後續）：`JobOut.reimportable` 與命令本身都要求 `completed_at`，
  下載到一半就被移出 qBittorrent 的那一包不再按得下去。
- **`rebuild-ledger` 在 complete 讀不到時不開 `no_source`**（M2 票 10 後續，brief §16.2）：印出
  `unreadable complete` 與 `not decided` 兩行，離開碼 1。

- **管線 Issue 的那一列以下載的名字認**（M2 票 09c）：`missing_files` / `client_error` / `client_removed` 的
  `detail` 多帶 `name`，清單上不再是一串 hash。時間線上 `retried` 那一筆分得出是哪一顆（重新校驗、重試、重新規劃），
  不再一律說「退回已建立」。
- **管線發現的那四種 Issue 從此兩邊都寫**（M2 票 05，plan §2.4）。`missing_files` /
  `client_error` / `client_removed` / `unknown_torrent` / `jellyfin_item_unresolved` 原本只有
  一筆 `issue_detected` 事件（`issues` 表要到 M2 才有），現在同時寫一列 `issues`：**事件是歷史**
  （時間線上那一行），**Issue 是「還沒有人決定」的那一件**（清單上那一列）。兩者共用同一個
  `IssueType`，所以不可能只加到其中一邊。`jellyfin_item_unresolved` 的事件仍是一筆 Job 一行
  （一季 24 集的時間線不該被 24 行淹沒），而 Issue 是一列帳本一件——它的下一步是逐集去 Jellyfin
  看那個檔案被認成了什麼。
- **`issues/*` 與 `reconcile` 只有 `admin`**（M2 票 05，plan §6、brief §11）：修正與對帳都是
  管理員的事。規則加在 `api/gate.py` 的 `ADMIN_PREFIXES`，底下之後新掛的端點什麼都不做就在同一
  道門後面。
- **門禁多一個維度：方法**（M2 票 04，plan §6）。`ADMIN_PREFIXES` 只比路徑前綴，而 `/jobs`
  整組不能是 admin——`user` 要送得了單、看得到自己的 job。新的 `ADMIN_ROUTES` 是
  `(方法, 路徑樣式)`，樣式裡的 `*` 配一段，所以 `DELETE /jobs/*` 與 `GET /jobs/*/deletion`
  是 admin 而 `POST /jobs` 不是。規則仍然只在 `api/gate.py` 一處，不散到 router 的相依裡。

- **顯示用海報也跟著 UI 語言走**（M1.5 票 11，brief §7.5、plan §8.3）。TMDB 的海報分語言，票 02 只換了標題與簡介，
  所以 EN 介面上 Moana 仍掛著「海洋奇緣」的中文海報。API 兩輪都送（`poster_url` / `poster_url_en`），前端照
  `i18n.language` 與標題挑同一輪：探索牆、Media 詳情、媒體庫牆上還沒進 Jellyfin 的卡片；在 Jellyfin 裡的卡片
  兩輪同一張（Jellyfin 的圖不分語言，名稱也是兩格相同）。快照與 `tmdb_cache` 各多一欄，票 11 之前寫下的讀出來
  是空字串，下一次刷新補上。

- **zh-Hant 介面的 `Unmatched` 翻成「對不到」**（M1.5 票 11，使用者拍板）。它是 `CONTEXT.md` 的名詞，UI 原本直接印英文，在「待審 1」旁邊站著「Unmatched 1」；程式碼識別符、文檔與英文 UI 不動。

- **只支援 Jellyfin 12 以上**（票 14b、brief §19、§20.9）。12.0 起同一集的多個版本由 Jellyfin
  自己合併成一個條目，10.x 需要的 MergeVersions 插件在它上面是空跑，還會跨媒體庫誤併——所以
  **插件整段移除**：精靈第 3 步從九步變七步（沒有「裝插件」與「重啟」）、既有服務少了「安裝
  MergeVersions」按鈕與那支 `POST /api/setup/jellyfin/plugin`、resolver 不再觸發合併任務、
  adapter 的介面上不再有 `/Repositories`、`/Packages`、`/Plugins` 與 `/System/Restart`。
  設定裡的 `merge_movies_task_id` / `merge_episodes_task_id` 與 `setup.jellyfin.merge_versions_installed`
  一併拿掉；舊資料庫存的那幾個鍵照樣讀得回來（`extra="ignore"`），不需要 migration。
- **低於 Jellyfin 12.0 就紅燈**：精靈第 3 步（套件內與既有都是）與健康檢查讀 `/System/Info/Public`
  的 `Version`，不足就停下，說出目前版本、為什麼要 12，以及升級前後要做的事（先完整備份、
  移除第三方插件、升級後完整掃描、降不回去）。`GET /api/setup/jellyfin` 多 `version` 與
  `version_supported` 兩個欄位。
- **精靈第 3 步的重試在 12.x 走得完**：`POST /Startup/User` 在第一個使用者已有密碼時回 403，
  現在當成「已經設過了」繼續往下（密碼對不對由之後的登入驗證）。原本會翻成 `AuthFailedError`，
  讓「第 4 步失敗後重試」永遠卡在第 3 步。
- **劇集的版本名改讀 Jellyfin 回的 `MediaSources[].Name`**，不再自己重算（12.0 起它是「去掉各版本
  檔名的共同前綴」剩下的部分，算法連 12.0 與 12.1 都不一樣）。反查到的那一刻抄進帳本
  （`ledger.jellyfin_version_name`，migration `3f6c0a7d94e2`）；Jellyfin 還沒收錄的版本顯示檔名的
  tags 並說明那不是版本名。
- **多集檔與同起始集的單集送審核**（brief §7.8）：同一份 Plan 裡、或與同一部作品同一季的帳本
  Entry 之間，起始集相同而結束集不同的正片一律停下等人，理由說出「Jellyfin 12 只用季號與集號
  分組，會把它們併成一集、後面那一集從集列表上消失」。
- `deploy/docker-compose.yml` 的 Jellyfin 從 `:latest` 釘到 `lscr.io/linuxserver/jellyfin:version-12.1ubu2604`。
- 演練情境：`installed` 與 `failing` 換成 `old-jellyfin`（既有 Jellyfin 停在 10.11 的樣子）。
- **精靈第 7 步略過寫入目標已經被佔用的選擇**（票 14a）：佔用者可以是既有的 Route，也可以是同一批
  前面的選擇；不回 422。沒有 `ItemId` 的舊 Route 在媒體庫改名之後，重跑不再長出同一個目標的第二條。
- **精靈跑完之後重跑第 7 步新建的 Route 先停用，檢查綠了才啟用**（票 14a）。原本是先啟用、檢查紅了
  再停掉，檢查跑完之前的那幾秒裡送單選得到還沒驗過的 Route。
- `GET /api/jellyfin/libraries` 的 `locations` 與 `taken` 合成 `paths[{path, route_name}]`：已經有 Route 的
  路徑帶著 Route 名，新增 Route 的表單不再拿清單反查。`DELETE /api/routes/{id}` 的 409 `route_in_use`
  另帶 `jobs` 與 `ledger_entries`，畫面照著說數字。建立時同一時間撞上唯一索引回 409 `route_conflict`。
- Route 設定頁：被引用而且還啟用著的 Route 旁邊有一顆「停用這條 Route」（送的是存下來的名稱與
  profile），刪除、停用、重新檢查之後都有 `aria-live` 播報；新增時媒體庫沒有空路徑，給一條到 Jellyfin
  媒體庫設定的連結。頁首的「設定」連到新的 `/settings`（導向服務設定），兩個設定頁上都標成當前頁。
- **精靈第 7 步只新增、不改不刪**（票 14）：重跑不再隱式刪掉沒勾的 Route，也不再改寫已經有 Route
  的媒體庫；那些媒體庫在勾選表上鎖住，重跑的意思是「補上新勾的、全部重驗」。每條 Route 底下有
  明確的刪除（被引用時拒絕）。
- **停用的 Route 不算進健康總結與精靈第 7 步的完成條件**（票 14）：停用是「刪不得」時的出路，
  它紅著不再讓整台 Berth 顯示 degraded。
- `/api/routes` 與 `/api/jellyfin/libraries` 跟著 `/api/setup` 的門禁規則：精靈跑完之前匿名開放，之後只有 admin。
- **Route 檢查與精靈認 Jellyfin 媒體庫改用 `ItemId`**（票 14）：在 Jellyfin 改了名字或有兩個同名的媒體庫時，
  Route 不再驗到別的媒體庫。精靈跑完之後重跑第 7 步新建的 Route 紅燈就維持停用；電影媒體庫的 Route 不收
  anime profile。精靈的 `GET /api/setup/routes` 裡 `libraries[].selected` 改名 `has_route`。
- **事件一分鐘內不重複**（`record_event`、plan §3.3、票 12）：`(job_hash, type, payload)` 相同就跳過，使用者按下的重試是界線。
  迴圈的一輪可能在寫完事件之後、下一步落地之前被關掉，重啟後的第一輪會把同一件事再做一次。
- **`POST /api/jobs/{hash}/retry` 也收 `import_failed`**（回 `importing`），`retried` 事件的
  `state` 分得出是哪一種重試。
- **fs adapter 的 `link()` 會建好目標那幾層資料夾**（守衛之後才建），`EXDEV` 另外說出來源與目標
  各自落在哪一個掛載上（仍是同一個 `errno` 的 `OSError`，plan §8.6）。
- **`/api` 底下的每一個回應都帶 `Cache-Control: no-store`**（`berth/api/gate.py`、plan §6、票 10）。
  這不是最佳化：Berth 原本一個快取 header 都不送，於是瀏覽器對 `200` 套用它自己的啟發式快取——
  實跑抓到 SSE 推來「這一筆完成了」之後前端重問一次，拿回來的卻是幾秒前那份說「已送出」的快取，
  畫面因此永遠停在錯的狀態。這裡的每一支回的都是「現在的狀態」，沒有一支的答案在下一秒還算數。
- **`torrents/add` 的成功形狀依版本判定**（brief §20.2、§20.7、plan §8.1）：2026-09-10 對真的
  qBittorrent 5.2.3 與 4.4.5 各錄一輪，發現 5.2.3 成功回的是一份 JSON 摘要而不是 `Ok.`——
  brief 原本記的「一律回 200 `Ok.`」只對 4.4.x 成立，只認 `Ok.` 的話 5.x 上每一次成功的送單
  都會被判成失敗。`409` / `415` / `202` 的意義一併記進 brief §20.7 與 fixture。
- **`/` 不再導向 `/health`**，它就是探索頁（plan §7）。登入之後落到的第一個畫面因此從「看它有沒有
  壞」變成「找東西」；健康頁留在導覽列上。
- 依實測更正 TMDB 的三件事（brief §20.3、plan §8.3）：`language` 會換掉 `trending` 回的**成員與
  順序**而不只是文字（兩輪 20 筆差 3 筆），所以清單以 `en-US` 那一輪為準、`zh-TW` 只當查表；
  回應裡的 `popularity` **不是**清單的排序依據，所以兩種作品合成一面牆時用交錯而不是重排；
  `{tv,movie}/popular` 的每一筆沒有 `media_type`。
- `settings.services.tmdb` 新增 `image_base_url`，精靈第 6 步驗憑證時順手寫下——`configuration`
  對同一把憑證是常數，每次探索都問一次是白花一個請求。
- **`naming` 移到 `parser` 之下**（plan §1.3 的依賴圖與 import-linter 契約）：`plan` 階段要
  產出目標路徑，而衝突偵測比的就是那條路徑。反向不成立，另有一條契約守著。
- **「兩個檔案同一集」不再一律進 review**：同一集不同 tags 的檔案本來就該並存（brief §7.7），
  简繁分軌與 1080p / 720p 同包都是常態。衝突改比**目標路徑**——那正是「會不會蓋掉對方」的定義。
- **標題自己帶著同一個年份時不再接一次**：TMDB 上真的有 `GTO (2026)` 這種標題，照字面套模板
  會寫成 `GTO (2026) (2026)`。年份不同的兩個數字說的是兩件事，照樣兩個都留。
- **作品資料夾名在第一次送單成功那一刻凍結**（plan §5、brief §4.5）：那是它第一次真的通向磁碟，
  而且有人在場確認。在那之前它跟著 TMDB 的標題走，畫面上是「將會是」的預覽；凍結之後 TMDB
  改標題也不動它——已入庫的檔案不該因為別人改了條目就對不上。**「追蹤」不是一個按鈕**，它是
  「Berth 曾為這部作品下載、訂閱或入庫過」的推導結果（`CONTEXT.md`）。
- `DiscoverProblem` 更名為 `TmdbProblem` 並新增 `not_found`：探索頁與 Media 詳情頁問的是同一台
  服務、四種理由的下一步也一樣，各寫一份遲早會走樣。訊息塊因此收成共用的 `TmdbNotice`。
- TMDB 詳情的 `append_to_response` 拿掉 `external_ids` 與 `release_dates`：快照裡沒有欄位讀它們，
  而後者每部電影是一百多筆各國上映日（實測 138 筆）。plan §8.3 已同步。
- 依實測更正文件：brief §7.2（電影檔名必須含 `[tmdbid-<id>]` 才算多版本）、§7.7（劇集的版本
  標籤是整個檔名而非 tags）、§20.1；plan §5 的命名模板**凍結**，§8.1、§8.2、§9.2、§9.4 依
  實測修正。細節見 `docs/research/m0-experiments.md` 與 `docs/progress.md` 的「偏差與決定」。
- 視覺系統重寫成「泊位調度板」（`.impeccable/surfaces/` 的 direction contract）：四個信號色
  各只有一個意思、狀態三重編碼、無圓角無漸層。票 02 的七個佔位色彩 token 被取代。
- `settings.setup` 不再存「走到第幾步」的游標，步驟由狀態導出。
- 精靈第 2 步要**每個服務都連得上**才算做完（判定多一個 `resolved` 旗標）。原本只看「有沒有
  結論」，會讓從 `COMPOSE_PROFILES` 拿掉的服務一有結論就跳過那張唯一能填位址的表單。
- HTTP adapter 新增 `ServiceBusyError`（503）：Jellyfin 重啟後「還在載入」與「壞了」要分得開。
- `/api/settings/*` 只有 `admin` 進得來，規則與 `setup/*` 一樣放在門禁 middleware。
- 前端共用件從 `setup/` 移到 `components/`（纜繩、狀態對照、Route 檢查的文案與 compose 片段），
  跨頁共用的 API 型別移到 `api/schemas.ts`（後端對應 `api/schemas.py`）——精靈、健康頁與設定頁
  講的是同一批東西。
- 前端 eslint 開啟 `@typescript-eslint/no-floating-promises` 與 `no-misused-promises`（需要型別資訊）。
  這是票 01 把型別感知規則延後時寫下的理由——TanStack Query 進來之後忘了 `await` 才變成真風險。
  只開這兩條而不是整包 `recommendedTypeChecked`：整包在這個 repo 上抓到的 36 條全是框架慣用法
  （TanStack Router 的 `throw redirect(...)`）與測試裡的型別噪音，沒有一條是真的缺陷。
- 英文的精靈階段字串從 `Berth {{code}}` 改成 `{{code}}`——`code` 本身就是 `BTH 1`，原本讀起來是 `BERTH BTH 1`。中文維持「泊位 BTH 1」：`泊位` 與 `BTH` 不同字集，而且它替第一次看到這個代號的人解釋了它是什麼。
- `routes.tsx` 的「精靈沒跑完就去跑、跑完了就要有 session」收斂成 `requireSignedInPage`
  （票 07 留的「頁面變多時再收」）。精靈那一頁仍然自己寫——它在同一個條件下是留下來而不是導走。

- 前端不再手寫任何 API 的形狀：`web/src/api/*.ts` 只把後端的類別名（`RouteOut`）換成前端在講的
  名字（`RouteView`），欄位與可選性全部來自產出的型別。M0 票 10 記的「同一份形狀寫了四層」的第四層
  就此消失。換過來的第一天就抓到一個漂移：`ServiceDetection` 少了後端已經在回的 `configured`。

- **Berth 不再內建 TMDB 的專案級憑證，改由使用者自備**（推翻上面 M0 那一條，也削掉 brief §16
  「開箱即用」的一角）。不替所有使用者背一把共用憑證；而兩個 metadata provider 在「使用者自己
  申請一把」上本來就對稱（brief §10、§20.7）。憑證的唯一來源是 `settings.services.tmdb.api_key`，
  精靈第 6 步從「可跳過的覆寫」變成**必填的閘門**：`POST /api/setup/tmdb/skip` 移除，測不過就
  停在第 6 步，`POST /api/setup/complete` 在沒有一把綠燈憑證時回 422。v3 key 與 v4 read access
  token 兩種形狀仍然都收。取得步驟寫在 README 的〈先申請一把 TMDB API key〉。
- `scripts/experiments/anime_episode_source.py` 的 TMDB 憑證改從環境變數 `TMDB_API_KEY` 讀
  （原本是從 adapter 原始碼刮那把內建的）。
- **只有集號、TMDB 上不只一季時，絕對編號換算的信心改看證據，不再看 Route 的 profile**（票 14d，brief §6.4）：
  預設 medium（自動入庫），集號沒超過第一季的集數、或檔名的播出日與換算出的那一集在 TMDB 上的播出日不同，
  就降到 low 送審核並說出是哪一條。所以 `anime` Route 上第一季的無季號發佈（`Spy x Family - 05`）改送審核，
  `standard` Route 上的跨季連號與播出日對得上的（`The.Return.of.Superman.E079.150524`）改自動入庫。
  Route 上的 profile 欄位隨票 14e 拿掉（見下）。
- 發佈名解析多讀檔名裡的播出日（`ReleaseInfo.air_date`）；六位數的短日期年份在前，韓國電視台的 `150524`
  讀成 2015-05-24，而不是 guessit 預設的 2024-05-15。
- **破壞性：Route 不再有 profile**（票 14e，brief §19）。`routes.profile` 欄位由 migration `9d4f1b6e2a70`
  刪除（降版補回 `standard`；升降兩個方向都不動 `jobs.route_id` 與 `media.default_route_id`——batch 重建
  `routes` 會被外鍵的 `SET NULL` 清空它們，所以升版用 SQLite 原生的 `DROP COLUMN`）。API 形狀跟著改：
  `RouteOut`、`LibraryChoiceOut` 少了 `profile`，`POST /api/routes`、`PUT /api/routes/{id}` 與
  `POST /api/setup/routes` 的 body 不再收它；`GET /api/search` 與 `GET /api/search/queries` 不再收 `route`，
  查詢只由作品的快照決定。語料的 `context.profile` 整批拿掉。內部 API，不留相容層。
- **搜尋的季號變體對所有劇集都做**（票 14e）：最新一季 ≥ 2 就多問 `<英文標題> Season N` / `<標題> 第N季`，
  不再只給 anime Route；單季與電影不加。效果沒有量，要打真的索引站才量得到。
- **畫面上的作品標題與簡介跟著介面語言**（M1.5 票 02，brief §7.5）：EN 介面的探索牆、搜尋結果、Media 詳情
  （h1 與簡介）、下載列與媒體庫牆顯示 TMDB `en-US` 那一輪，ZH 介面維持 `zh-TW` 那一輪；在頁首切換語言當場換掉，
  不重新整理也不重抓。檔名、資料夾名與季名比對不受影響；海報仍是 `zh-TW` 那一輪的。API 兩輪都送：`MediaOut`
  多 `overview_en`，`JobOut` 的 `media_title` 改為 `zh-TW` 那一輪（缺就是英文）並多 `media_title_en`。
  快照多一欄 `overview_en`，舊快照照樣讀得開（英文簡介先是空的，下一次刷新補上），不需要 migration。
- **媒體庫頁改成一個 Jellyfin 媒體庫一頁、瀏覽整個媒體庫**（M1.5 票 03，brief §13、§19）：切換列只列你在 Jellyfin
  看得到的電影與劇集媒體庫；牆上是那個媒體庫的每一部作品（不是 Berth 入庫的也在），100 部一頁、上一頁 / 下一頁；
  Berth 經手的作品疊上入庫狀態，在 Jellyfin 裡的顯示 Jellyfin 的名稱，還沒進 Jellyfin 的另列一條「還沒進 Jellyfin」；
  沒有 TMDB id 的作品只給 Jellyfin 深連結。「待審」「Unmatched」篩選換成這個媒體庫裡被標記的每一部。Berth 的作品
  與 Jellyfin 的作品不再只靠帳本的 Series id 對應：Jellyfin 的 TMDB id 對得上也算，所以「反查找到了集卻一直說還在
  掃描」不會再發生在已經在 Jellyfin 裡的作品上。頁面網址 `/library/:routeSlug` → `/library/:libraryId`（舊網址不轉址）；
  `GET /api/inventory` 回媒體庫而不是 Route，`GET /api/inventory/{slug}` → `GET /api/inventory/{library_id}?page=`，
  回應的 `route` / `items` 換成 `library` / `titles` / `tracked`，每一格的入庫狀態收進 `tracking`，兩個篩選的數字
  從切換列搬到牆上（`review` / `unmatched`）。內部 API，不留相容層。
- 對外服務的 HTTP client 整個程序共用一個 SSL context（M1.5 票 04）：httpx 預設每個 client 各建一個，要讀一次
  certifi 的憑證包、約 14 ms 的 CPU，而且卡在事件迴圈上。每個請求都開新 client 的 services 因此每次多付這一筆；
  量到經過 Berth 的圖 6 條並行時每張從 140 ms 降到 54 ms（`docs/research/library-browsing.md` §6.1）。
- **Media 詳情重排**（M1.5 票 08）：身分帶的五列識別剖面收成標題下一行（類型、首播 / 上映、季集數或片長、TMDB id），
  資料夾名搬進搜尋區塊（送單會寫死的就是它），在 Jellyfin 裡的作品多一顆主按鈕與觀看區；Berth 的那一半順序固定為
  搜尋 → 季集與入庫（原本的「季集」）→ 檔案與版本。量到的差別：1280×900 下「搜尋」從 y=1027 升到 579（葬送的芙莉蓮）、
  953 → 501（奧本海默），390px 從第三屏到第二屏。**搜尋結束之後有回應的纜繩收成一行**、展開才逐條列，垮掉的照舊一條一條
  畫在上面：五個關鍵字的纜繩從 287 px 變成 44 px。
- **標為已看也可能先確認**（M1.5 票 08，使用者拍板）：看到一半的集或電影標為已看會把那個位置歸零、找不回來，所以先說；
  整部劇標為已看一律先說（每一集看到一半的位置都會歸零，而劇集的紀錄看不出底下有沒有這種集）。媒體庫牆與 Media 詳情是
  同一顆鍵。
- **長清單不再整份攤開**（M1.5 票 09，使用者拍板）：季表收起的季不渲染集列——名偵探柯南開頁的 DOM 節點從 10,147 個
  降到 119 個；展開的一季（以及下面兩種組）摘要列黏在畫面頂端、最後一行另有「收起」，捲到哪裡都收得起來。「檔案與版本」
  與下載列展開的計劃**依決定分組**：一組是同一季 × 同一處置（計劃再分信心與待確認），一行說蓋到哪幾集
  （`S01 E01–E28`）、幾個檔案、帳本與 Jellyfin；需要人的組排最前、左線加重；逐檔要展開那一組才畫。葬送的芙莉蓮那一筆
  下載列展開從 5,394 / 8,513 px 降到 707 / 928 px（1280 / 390 寬）。
- **逐檔那一列自己也收起來**（M1.5 票 09b）：展開一組之後，一個檔案從三到四行收成一行——外面留季集與檔名，
  「Tags」「目標」與解析器的理由收在列自己的展開區裡。組的摘要說過而且是常態值的不再重複（處置、帳本「對得上」、
  Jellyfin「已收錄」）；例外留著，因為組數得出幾個卻說不出是哪一個。葬送的芙莉蓮 S01 那 28 個檔案展開後，
  「檔案與版本」從 2,824 px 降到 1,032 px、`/jobs` 的計劃從 3,655 px 降到 863 px（1280 寬）。電影不分組，
  上面沒有摘要說過，所以那幾格全部留在列上。
- 媒體庫的整份清單（`library_index`，比對 Berth 經手的作品用）多帶每部的 Primary 圖 tag（M1.5 票 04）：
  篩選「待審」「Unmatched」時，已在 Jellyfin 裡的作品也畫得出海報。Jellyfin 連它的 BlurHash 一起回，每部多一百多個位元組。
- **拒絕的理由變成封閉集合並進 OpenAPI**（M2 票 02）：`JobRefusal`、`RouteRefusal`、`AccessRefusal`
  三個 enum 進 `berth/domain/enums.py`，各 router 以 `responses=` 宣告 `{reason, detail}` 的形狀，
  前端改用產出的型別——原本那三份是手抄的字面聯集，後端加一種理由時沒有任何東西會紅。
  SSE 推的 `{hash, state, progress}` 同樣有了 model（`JobSignalOut`），`state` 是 `JobState` 而不是自由字串。
  理由 → 狀態碼的三張表現在要涵蓋整個集合（以前漏掉的會靜靜變成 422）。
- **會拒絕的端點都要宣告，而且各自宣告它真的會回的那幾種**（M2 票 02a）：精靈的兩支 Route 命令補上
  `responses=`——`POST /setup/routes` 是 404 `route_missing`（這一步順帶重跑既有 Route 的檢查），
  `DELETE /setup/routes/{id}` 是 404 加 409 `route_in_use`；兩支各一張小表，不是 `routes/*` 九種理由的聯集。
  `GET /jellyfin/items/{id}/images/{type}` 的 503 也補上 model（原本只有一行描述）。
  票 02 留下的「沒有閘門」補成 `TestDeclaringWhatEachEndpointRefuses`：走訪每一條路由，比對它
  `responses` 上宣告的拒絕**形狀**與 handler 語法樹丟得出來的，漏宣告與多宣告都紅。

- **媒體庫已有的集，起始集相同而結束集不同時不再把整份 Plan 擋在待審核**（M2 票 08）：那一列略過、
  成為佇列上的一列重複版本，同一包其餘的集照常自動入庫（M1 票 14b 的規則不變，處置改了）。同一包之內
  互撞的那一種照舊送 review。
- **Plan Item 的理由改成封閉集合的 code + 參數**（M2 票 07）：`reasons` 從解析器拼好的英文句子
  變成 `[{code, params}]`（`domain.ReasonCode`，42 種），句子在前端、zh-Hant 與 en 兩份都有。參數是
  檔名、季集、日期這種不翻譯的事實；每一種 code 帶哪幾個參數寫死在 `REASON_PARAMS`，`why()` 組的那一刻
  核對，兩份語言的佔位符由 `tests/unit/test_reason_codes.py` 逐句比對。`/review` audit 列的 `notes`
  （英文原文）改成同一套 `reasons`。**既有 `plan_items.reasons_json` 的英文句子由 migration 清空**
  （使用者拍板不轉換）；重新規劃就用新格式重算。`/jobs` 計劃區那幾句「M1 還沒有審核佇列」改成指向審核佇列。

- **「待審」「對不到」兩個篩選鍵的數字改數件不數部**（M2 票 14，使用者拍板）：與那兩個篩選的清單同一支查詢
  （`services/review.library_counts`）。原本數的是 `tracked` 裡旗標成立的部數，而旗標的定義與佇列不同（光碟檔、
  已移除的下載、等審核的那一份裡的 Unmatched 都算），會出現「對不到 1」清單卻是空的。
- **一般使用者的媒體庫頁沒有「待審 / 對不到」**（M2 票 14，使用者拍板）：那是管理員的工作佇列，`review/*`
  本來就只給 admin；網址上帶著 `?filter=` 也照畫整面牆。

- **媒體庫牆的卡片與觀看區的集卡共用一個外框**（M2 票 14，M1.5 critique）：`components/Tile.tsx`——圖、標識帶的
  節奏、一條連結與並排的底行只有一份，`InventoryTile` 與集卡只決定填什麼。探索牆的 `MediaTile` 不併（整格一條連結、
  沒有底行）。
- **EN 的 Route 設定頁與精靈泊位 4 的標題改叫 `Routes`**（M2 票 16，票 03 留下的）：子分頁早就是 `Routes`，
  頁標題還叫 `Library paths`，同一個東西兩個名字。zh-Hant 不變（「媒體庫路徑」）。

- **`settings.services.jellyfin.metadata_fetchers` 的鍵是媒體庫的資料夾、預設是空的**（M3 票 06f）：沒寫的媒體庫
  依內容類型落回 TMDB（目前電影與劇集都是 `TheMovieDb`）；已經存了三列 `movies` / `tv` / `anime` 的設定照舊有效。
- `POST /api/rss/feeds/{id}/poll` 的回應多 `failed`（這一輪抓不到 Feed 的原文）；`/rss` 上那一輪讀不到時說「這一輪沒讀到」，不再說「新 0 筆」。
- 健康頁的 Jellyfin 卡片把媒體庫數量交給 i18n（`library_count`），不再是後端寫死的英文「N libraries」。
- e2e 的種子影片照語料的 TMDB 快照改寫標頭的片長：片長驗證（票 15）會擋下 330 秒對半小時的集數。
- **RSS Series 的第一批證據夠強時不再等人**（M4 票 11，brief §15）：整批每一集都照檔名的集號對應、發佈時剛播、
  播出日對得上時，入庫不掛 audit，Series 由系統確認，每一筆的時間線記新事件 `series_confirmed`（`series`、
  `name`、`episodes`）；有一集不符合、或同一個 Series 還有集數沒落地，就照舊整批等人。仍要人看的那一組，審核頁
  與作品頁的「第一批待確認」說一句在問什麼（哪幾集、季集怎麼讀出來），組的鍵改叫「確認整個 Series」。
  `GET /api/review` 的 audit 列 `series` 多 `group` 與 `ask`，`GET /api/rss/series` 多 `ask`
  （`spans` 加 `basis`：`literal` / `series` / `absolute` / `runs` / `arc` / `mixed`）。

- **下載列表一頁 50 筆、分四組**（M4 票 04，`.scratch/m4/jobs-paging-shape.md`）：在路上（還沒入庫也沒被移走，
  需要人的也在裡面）· 需要人 · 已入庫 · 全部，各帶件數；打開 `/jobs` 預設看在路上的，入庫的那一筆移到「已入庫」。
  篩選與頁碼在網址上（`?filter=&page=`），分頁的樣子與媒體庫的牆相同。**`GET /api/jobs` 的回應從陣列改成一頁**：
  `{page, page_size, total, jobs, counts}`，參數 `filter`（`active` 預設 / `attention` / `imported` / `all`）與 `page`。
- **一批 SSE 推播只重抓一次下載列表**（M4 票 04）：原本每一則推播都讓整份 `['jobs']` 失效，poller 一輪推 N 則就是
  N 次整份 `GET /jobs`、每一列展開中的時間線與計劃跟著重問。現在一秒內到的併成一次，只失效清單與推播到的那幾筆，
  進行中的請求不取消（前端的讀取接上 `AbortSignal`，換頁時沒人要的請求真的被取消）；刪除估算不再被別的 Job 的進度
  重算（它每重算一次就逐檔 `stat`）。
- **作品頁多一段「下載」**（M4 票 12，`.scratch/m4/media-downloads-shape.md`）：排在 RSS 訂閱之後、季集之前，
  列出這部作品的每一筆下載——狀態、進度（即時）、大小、來源與字幕組、Route、時間，展開看裡面的檔案、大小與計劃
  對到的季集，連到下載詳情。預設只列還沒了結的（在路上的，加上已入庫而還有檔案待確認的），其餘在「全部」；從沒
  送過下載的作品不畫這一段。季表上「下載中」「卡住」那一格連到蓋到那一集的那一筆（原本「卡住」連到整份下載列表）。
  API：`GET /api/jobs` 多參數 `media` 與篩選 `open`（`counts` 多 `open`），新 `GET /api/jobs/{hash}/files`，
  `JobOut` 多 `series`、集表的每一集多 `job`；下載列表的每一列也印出 RSS 送的那一筆的字幕組。
- **RSS 頁以作品呈現 RSS Series**（M4 票 13，`.scratch/m4/rss-series-shape.md`）：綁好的 Series 作品一塊、字幕組
  一列，列上說 Mikan 的番組名與字幕組名（連到番組頁）、已入庫 / 在路上 / 排除各幾筆、最近**發佈**的那一集與時間；
  展開看它的每一筆 Item 與送出的下載，Series 層的排除條件、季號與 offset、解除綁定收在展開區的「進階」。畫面上
  不再出現 Mikan 的數字 id（`Mikan 3985 × 583`、`mikan:…` 的鍵）。TMDB 說完結而且它入庫過的那幾季都在庫（最後一筆
  發佈滿一週）、或 30 天沒有新的一筆的 Series 收進段尾預設收起的「已完結」——紀錄不刪，新的一筆出現就回到上面。「最近的 Feed
  Item」每一列說出來自哪個 Feed、屬於哪部作品的哪個字幕組（沒綁的說待綁定）。作品頁的 RSS 訂閱也改說 Mikan 的
  字幕組名。API：新 `GET /api/rss/series/{id}/items`；`SeriesOut` 多 `mikan_bangumi_name`、`mikan_subgroup_name`、
  `latest_episode`、`imported`、`active`、`excluded`、`finished`，`ItemOut` 多 `episode`；
  `POST /api/rss/subscriptions/mikan` 多選填的 `subgroup_name`。番組名取自自動綁定讀的番組頁與單一 feed 的 channel
  標題（補舊集與每日補漏本來就讀它），字幕組名取自番組頁；資料庫多兩欄（migration `d5c8e2a7f391`，既有的留空，
  下一次補漏補上番組名，畫面上沒有就不顯示）；TMDB 快照多 `ended`（至多 24 小時後刷新補上）。
- **媒體庫裡還沒有 Berth 入庫的東西時，登入後落在探索**（M4 票 10，brief §19 2026-09-26）：精靈剛跑完、或接上
  既有 Jellyfin 而 Berth 還沒入庫過東西時，原本落在一面空牆（或只有別人的片）。現在這個人看得到的媒體庫裡帳本
  一筆都沒有就落在探索，其餘照舊落在媒體庫；`?redirect=` 照舊優先。API：`GET /api/inventory` 每一列多
  `has_imports`。
- **精靈第 1 步改為「擁有者」：Jellyfin 的管理員就是 Berth 的擁有者**（M4 票 06，brief §11、§19 2026-09-26；
  Seerr 的做法）。Berth 沒有自己的帳號，原本的「建立 Berth 管理員」那組帳密在接既有 Jellyfin 時精靈結束後登不進
  Berth。現在第 1 步先找到 Jellyfin：套件內的那一台以你填的帳密建立它的管理員、跑完它的初始設定、換 API key；
  既有的那一台用它自己的管理員登入（不是管理員就拒絕）。成功那一刻就登入 Berth，之後登入 Berth 就用這一組；
  **密碼只交給 Jellyfin，Berth 不存**。qBittorrent 與 Prowlarr 的偵測移到第 2 步；泊位 1 剩下建媒體庫（套件內）
  或列媒體庫（既有，不再要帳密）；精靈跑完直接進 Berth，不必再登入一次。API：`POST /api/setup/admin` 由
  `POST /api/setup/owner` 取代（成功時發 session cookie；拒絕是 `OwnerRefusal`：409 / 401 / 403 / 502）；
  `SetupStatusOut` 的 `admin_created`、`admin_username`、`interface_username`、`jellyfin_owns_account`、
  `apply_to_services` 換成 `owner`、`owner_signs_in`；`GET /api/health` 多 `owner_established`。資料：
  `settings.setup.admin` 由 `owner`（Jellyfin 的 user id 與名字）取代，migration `e8a1c4d7b293` 拿掉舊的兩組帳密與
  Berth 寫進 Prowlarr 的那一份；精靈已經跑完的安裝不受影響，跑到一半的回到第 1 步。
  **套件內 qBittorrent 與 Prowlarr 的介面密碼暫時不設**：第 1 步的「同一組帳密也套用」勾選框拿掉了，各自泊位上的
  欄位在下一張票補上；這之前 Berth 照常運作，自己開 qBittorrent WebUI 要用容器 log 的臨時密碼。
- **套件內 qBittorrent 與 Prowlarr 的介面登入在各自的泊位上填，而且必填**（M4 票 07，
  `.scratch/m4/service-logins-shape.md`）：泊位 2 與泊位 4 多一組「帳號（預填擁有者的名字）、密碼、再一次密碼」，
  跟著「套用」「加入」送出；沒設過就停在那一步。設過之後回頭看只說帳號是誰，按「更換登入」才打開。設定頁
  → qBittorrent 與 → 索引站多「介面登入」一區，只換登入，舊的那一組隨即失效。既有服務沒有這一格。API：
  `POST /api/setup/qbittorrent/apply` 收 `{login}`、`POST /api/setup/indexers/apply` 多 `login`（都可省略，省略是登入
  照舊；對既有服務帶了回 422），新增 `PUT /api/setup/qbittorrent/login`、`PUT /api/setup/indexers/login`；
  `QbittorrentOut`、`IndexerSetupOut` 的 `sets_password` 換成 `web_ui_login`、`web_ui_username`。沒設過登入的套件內
  那一台，密碼那一條纜繩是 `pending`。
- **精靈重做：每個服務由你自己選「套件內」或「既有」，不再偵測**（M4 票 15，brief §19 2026-09-29，
  `.scratch/m4/service-pages-shape.md`）。原本的偵測只能靠「免密可進」「沒有索引站」這類跡象猜服務是誰的，猜錯就
  寫到你的服務上。現在 Jellyfin、qBittorrent、Prowlarr 各一頁，頁首二選一、不預選；選了 Berth 才去連，選完當場測。
  頁序是 Jellyfin（擁有者）→ qBittorrent → 媒體庫與路徑 → Prowlarr 與索引站（併成一頁）→ TMDB → 完成，泊位板五格、
  沒有前置列；泊位板每一格的狀態字跟著連線結果（連不上就寫「失敗」），選的來源寫在詳情列。套件內那一台還在啟動就每 3 秒再測（上限 2 分鐘）；它不在 compose 裡時說出怎麼把它加回
  `COMPOSE_PROFILES`。選「既有」時說出同主機、同容器路徑的條件與要從 `COMPOSE_PROFILES` 拿掉哪一個。擁有者表單
  跟著那一台的狀態走：還沒初始化就建立管理員（選既有也一樣），已經有管理員就登入（套件內重裝保留 config 也一樣）。
  擁有者成立之後 Jellyfin 的來源鎖住；qBittorrent 與 Prowlarr 隨時可改選，那一頁重做（Berth 已經寫進原本那一台的
  東西不撤回），換了 qBittorrent 媒體庫路徑要重新檢查。套件內 Jellyfin 的媒體庫清單從 Jellyfin 頁搬到媒體庫與路徑
  頁。套件內 qBittorrent / Prowlarr 已經設過介面登入（重裝保留 config）就不強迫再設。介面登入預設**沿用 Jellyfin
  帳密**：帳號是擁有者、密碼打一次，Berth 先向 Jellyfin 驗過才寫。API：`POST /api/setup/services/{kind}` 改收
  `{origin, base_url, api_key, username, password}`（擁有者之後改 Jellyfin 的來源是 409），新增
  `POST /api/setup/services/{kind}/test`；`SetupStatusOut.services` 換成每個服務的選擇與測試結果（`ServiceOut`：
  `origin`、`base_url`、`state`、`reason`、`detail`、`waited_seconds`），`probe_targets` 改名 `bundled_targets`、
  `waited_seconds` 移到每個服務上；`DetectionReason` 換成 `ConnectionReason`，`ServiceOrigin` 只剩 `bundled` /
  `existing`；`InterfaceLoginIn` 多 `reuse_owner`（帳號可以留空），沿用而 Jellyfin 驗不過是 422 / 502
  `InterfaceLoginRefusal`。**還沒選的服務，寫入它的命令一律拒絕**；`POST /api/setup/jellyfin/bootstrap` 對既有
  Jellyfin 回 422。資料：`settings.setup.services`（偵測判定）換成 `settings.setup.choices`，migration `f3c9a1d6b2e8`
  把有結論的判定轉成同一個來源的選擇（連得上的測試是綠的），還在探測、逾時、以及偵測猜成既有卻沒被你填過的
  丟掉——那一頁回到二選一。
- **套件內三個服務的容器名改成 `berth-jellyfin` / `berth-qbittorrent` / `berth-prowlarr`**（M4 票 16，brief §20.14）：
  同一台主機上原本就有叫 `jellyfin` 的容器，而 `COMPOSE_PROFILES` 忘了拿掉套件內那一台時，`docker compose up -d`
  會連 Berth 在內**整套都起不來**（實測，不是只有撞名的那一台）。`berth` 的容器名不變；compose 的服務名與 profile
  也不變，`.env` 不必改。**已經部署的人**：`docker compose up -d` 之後三個容器以新名字重建，設定都在 `CONFIG_ROOT`
  的 bind mount 上，不受影響；自己寫過 `docker exec qbittorrent …`、`docker logs jellyfin` 這類指令的要改成新名字
  （`docker compose exec qbittorrent …` 用的是服務名，照舊）。
- **`berth` 連得到宿主上的服務**（M4 票 16，brief §16.4）：compose 的 `berth` 服務加
  `extra_hosts: host.docker.internal:host-gateway`，Linux 上既有服務的位址也能填 `host.docker.internal`
  （Docker Desktop 本來就有這個名字，明寫這一條不改變它）。`.env.example` 在 `COMPOSE_PROFILES` 旁寫明接既有的
  哪一個就拿掉哪一個；README〈部署疑難排解〉多了 `port is already allocated` 與連不到宿主兩條。
- **既有 Prowlarr 有版本下限了：1.3.2**（M4 票 17，brief §20.14，`docs/research/prowlarr-version-floor.md`）：
  Berth 用到的端點裡最晚出現的是匿名的 `/ping`。精靈（頁 4 的既有表單、服務頁的選擇與重新測試）與健康檢查都讀
  `GET /api/v1/system/status` 的版本，太舊時停在 Prowlarr 頁、說出目前版本與下限（`ConnectionReason` 多一個
  `version_unsupported`）。Torznab 端點不受影響。
- **既有服務填 `localhost` 時就地提示**（M4 票 17，brief §16.4）：位址是 `localhost`、`127.x.x.x`、`::1` 時，
  位址欄下說明那是 Berth 自己的容器、改填 `host.docker.internal` 或區網 IP；只提示、不擋。測試連不上時的補法也說同一句。
- **三個服務頁的「既有」旁寫出版本下限**（M4 票 17）：Jellyfin 12.0（附 12.0 發佈文的升級注意連結）、
  qBittorrent 4.4、Prowlarr 1.3.2。
- **Jellyfin 的版本在測連線時就擋**（M4 票 18）：10.x 原本測試是綠燈、到登入才 502 一句英文；現在頁 1 當場紅在
  `version_unsupported`，補法說「至少要 Jellyfin 12.0，這一台是 X」（Prowlarr 同一句型），擁有者表單不出現。
  套件內那一台太舊也當場紅，不等輪詢上限。
- **擁有者成立之後 Jellyfin 只能換到同一台**（M4 票 18，brief §20.15）：換位址時先問新位址的 ServerId
  （`/System/Info/Public` 的 `Id`），與擁有者成立時記下的不同就 409 `other_server`、新位址不回答就 409
  `unverified`，兩者都不存；同一台就存下並以 Berth 的 key 重驗，被撤了測試紅在 `auth_required`，頁 1 與設定頁
  就地用管理員重新登入換一把。存下的位址後面換成另一台時，重新測試紅在新的 `other_server`。
  `settings.setup.owner` 多 `jellyfin_server_id`；之前成立的擁有者在下一次測試時記下測到的那一台。
- **替還沒初始化的既有 Jellyfin 建立擁有者時問語言與地區、遠端存取**（M4 票 18，使用者拍板）：`POST /api/setup/owner`
  多 `ui_culture`、`metadata_language`、`metadata_country`、`remote_access`，寫進它的 `/Startup/Configuration` 與
  `/Startup/RemoteAccess`。預設跟著 UI 語言、不開遠端存取。**套件內那一台不再開遠端存取**（原本開），語言也跟著
  UI 語言（原本固定 `zh-TW`）。
- **頁 1 的文案**（M4 票 18）：Jellyfin 那一格的鈕叫「改位址」，表單不再說「管理員帳密在下一格」；回頭看只列畫面上
  真的有的動作；測試結果不再說兩次「連上了」。
- **精靈的「媒體庫與路徑」頁進頁不動手，一顆「建立並檢查」做完**（M4 票 08，plan §9.3 頁 3）：原本一走到就自動建
  分類、寫探測檔；現在按下之前列出這一輪會做的事（建哪幾個媒體庫、在哪個媒體庫加哪一條路徑、幾個分類、幾個測試檔）。
  套件內的媒體庫清單與 Route 併成一個畫面，「開始靠泊」「前往 Route 與檢查」拿掉；既有 Jellyfin 的「加入 Berth
  路徑」變成寫入目標的一個選項，按下時才加，沒有「確認加入」。一段失敗就停，後面的不送。
- **每條 Route 收成一列「5 / 5 通過」**（M4 票 08）：精靈、健康頁與 Route 設定頁同一個列元件，紅的自動展開、全過收起。
  既有 Jellyfin / qBittorrent 的檢查失敗時，另說同一台主機、同一個父目錄掛在同一個容器路徑的條件；Jellyfin 在別台
  主機（看不到探測檔）與分開掛載（`EXDEV`）各一句。
- **精靈的「上一個 / 前往下一個泊位」在桌機也固定在底部**（M4 票 08）：頁 3 做完是好幾條 Route，原本要往下捲才找得到。
- **媒體庫名稱帶空白時，新建的 Route、分類與 Berth 路徑用 `-`**（M4 票 08）：「TV Shows」是 `berth-tv-shows`、
  `/complete/tv-shows`，不再是 `berth-tv shows`。**已經建好的不改名**（改分類路徑會搬走它底下的 torrent）；
  已經加到 Jellyfin 上的 `…/tv shows` 仍認作那個媒體庫的 Berth 路徑，不會再加一條。
- **索引站先測再加，一站都不預勾**（M4 票 09，plan §9.3 頁 4）：原本九個推薦站預設全勾、按一次全加。現在每一站
  一顆「測試」（`POST /api/setup/indexers/test`，Prowlarr 現場連一次那個站、什麼都不建立），推薦清單一顆「測試全部」，
  通過的才勾得起來；主鈕只數還沒加的站。推薦清單之外多了「其他公開站」：這台 Prowlarr 的 schema 裡所有公開的
  torrent 站，依名稱或語言叫出來。私站連到 Prowlarr 自己的介面加，連結開的是瀏覽器所在主機的 `PROWLARR_PORT`，
  不再是瀏覽器解不到的 `http://prowlarr:9696`。
- **一站沒通過的呈現**（M4 票 09）：Prowlarr 的英文原文收進「Prowlarr 原文」，列上說一句理由（Cloudflare 擋住、
  查無結果、連不上、其他）；上方一條摘要說幾站沒通過、各是什麼理由，整段只有這一個 live 區，不再一次跳出好幾塊
  紅色警示——一站沒通過不擋這一頁。
- **「已加入」列出 Prowlarr 裡的每一站**（M4 票 09）：含你在 Prowlarr 自己加的（要帳號的站 Berth 不移除），每一列
  可以單獨搜（`GET /api/setup/indexers/search` 多 `indexer_id=`），也可以「搜尋全部」。既有 Prowlarr 同樣列出它的站
  與站數、可以試搜，沒有勾選與加入。精靈這一頁與設定頁的索引站分頁進來只讀，不測任何一站。`GET /api/setup/indexers`
  的 `options` 拆成 `sites`、`candidates`、`checks`，多 `web_port`。
- **服務頁換另一格的確認**（M4 票 09，頁 1、2、4 與設定頁）：方向鍵在「套件內 / 既有」間移動只是瀏覽，不再當場
  存下並測試套件內那一台（鍵盤選到的另有「使用套件內的 X」）；這一頁有結果時換另一格走就地確認，焦點移進去、
  Esc 收起；確認之前標題就跟著選著的那一格；從既有換走時不再說 Berth 寫過那一台的偏好。
- **compose 多傳 `PROWLARR_PORT` 給 `berth`**（M4 票 09）：「在 Prowlarr 加私站」的連結用它。
- **Route 多一條檢查：qBittorrent 讀得到 Berth 寫的檔**（M4 票 19，brief §20.2）：`download_path` 之後的
  `download_visible`。Berth 在分類路徑寫一個小檔、做成 private 的單檔 torrent，停住加進 qBittorrent（明送
  `savepath`、不掛分類、不帶 tag）並校驗，100% 才是綠的，之後移除 torrent（不刪檔）、小檔由 Berth 刪。原本只在
  Berth 容器裡 `stat` 那個它自己剛建的目錄，既有 qBittorrent 只掛 `/downloads` 時照樣綠。一條 Route 從五條纜繩
  變六條（`RouteCheck.download_visible`）。精靈、新增 Route 與「重新檢查」時真的問；**5 分鐘的健康迴圈沿用上一次
  的結論**：校驗到 100% 會觸發 qBittorrent 的「torrent 完成時執行外部程式」（4.4.5、5.2.3 實測）。
- **`library_path` 只驗 Route 的寫入目標**（M4 票 19）：它仍要是那個媒體庫現在報的路徑之一、Berth 看得到；
  媒體庫的其他路徑（例如舊的 `/movies`）Berth 看不到也不紅——Berth 只在寫入目標底下讀寫。
- **頁 3 的補法指向要改的那一台**（M4 票 19）：`library_path`、`probe_visible` 給 Jellyfin 的 volumes 片段，探針給
  qBittorrent 的，`download_path` 與硬鏈接的 `EXDEV` 才是 berth 自己；既有服務的說法是「你那一份 compose」、
  照 TRaSH 用單一共用掛載。不是 `EXDEV` 的硬鏈接失敗不再附片段。
- **「加入 Berth 路徑」逐個媒體庫試、逐個回報**（M4 票 19）：`POST /api/setup/jellyfin/libraries/paths` 的
  body 從 `{library}` 改成 `{libraries: [...]}`，回應多 `berth_paths`（每個媒體庫的 `status`、`reason`、`error`）。
  送出前先寫探測檔問 Jellyfin 看不看得到（它對加不上的路徑只回 404 `Error processing request.`），看不到就說
  「Jellyfin 看不到 <路徑>：它沒掛 /data」並收回剛建的目錄；不再建議到 Jellyfin 手動加、不再給 Berth 連它用的
  那個瀏覽器開不了的位址。
- **頁 3 進頁時重讀既有 Jellyfin 的媒體庫**（M4 票 19）：`POST /api/setup/routes/libraries`，另有一顆「重新讀取」；
  頁 1 之後在 Jellyfin 改的掛載與路徑看得到了。**既有模式的寫入目標預設「新的 Berth 路徑」**，只有一條路徑的
  媒體庫也是（推翻 brief §4.3 的「自動選定」）。
- **未完成目錄只開在 Berth 的分類上**（M4 票 22，brief §4.1、§20.2）：建分類時帶 `downloadPathEnabled` +
  `downloadPath=/data/torrent/incomplete/<slug>`（Berth 先建好那個目錄），下載中的檔不再落在 complete 那一側，
  也不必動 qBittorrent 的全域設定——4.4.5 與 5.2.3 實測全域關著也生效、開著時分類的贏。**套件內的那一台不再寫
  全域 `temp_path` / `temp_path_enabled`**，建議鍵從五個變三個（`QbittorrentStep` 少兩個值）。已存在的 Berth
  分類有自己的未完成目錄而不同時照衝突規則回報、不覆寫；票 22 之前建的沒有，照舊跟著全域設定下載、不算衝突。
- **送單前的磁碟門檻量那條 Route 的未完成目錄**（M4 票 22）：以前量全域的 incomplete 根目錄，既有 qBittorrent
  根本不寫那裡；在途量照舊（M4 票 03）。
- **接既有 qBittorrent 不再列偏好表、不再警告「沒有啟用未完成目錄」**（M4 票 22）：`GET /api/setup/qbittorrent/diff`
  對既有的那一台回空的 `diffs`，按「確認」只記密碼那一條 `skipped`。那句警告的理由不成立（完成看的是
  qBittorrent 回報的狀態），而它的全域偏好沒有一個影響 Berth。
- **既有 Prowlarr 一站都沒有時，精靈停在索引站那一頁**（M4 票 20，brief §19 2026-09-30）：原本連上就標「已完成」，
  零站的 Berth 什麼都搜不到。現在那一頁待處理，說出三條路：到 Prowlarr 加站後按「重新讀取」、在精靈加推薦的公開站、
  或「之後再說」。**既有 Prowlarr 也能加站**：同一套先測再勾、按一次加入，按鈕旁寫明會加進哪一台、加哪幾站；
  Berth 不移除它的站、不碰它的介面登入。`POST /api/setup/indexers/test` 與 `/apply` 對既有 Prowlarr 不再 422
  （Torznab 端點照舊 422）。
- **比 1.3.2 舊的 Prowlarr 說得出版本，key 錯不再說「連不上」**（M4 票 20）：連線測試從
  `GET /api/v1/system/status` 問起、不先問 `/ping`（1.0.1 的 `/ping` 回介面的 HTML），太舊時說「至少 1.3.2，你的
  是 X」；401 是 `auth_required`，補法說 API key 在 Prowlarr 的「設定 → 一般」。測試那一行標的端點跟著改。
- **套件內 Prowlarr 的介面登入是自己的一顆按鈕**（M4 票 20）：「加入 N 個站」貼著站清單、不必先填登入；
  介面登入一區寫明必填與理由（Prowlarr 第一次打開介面會跳出關不掉的設定視窗），按「設定介面登入」走
  `PUT /api/setup/indexers/login`。**`POST /api/setup/indexers/apply` 不再收 `login`**。加站與移除之後，連線卡與
  泊位卡的站數跟著清單；回頭看頁 4 的說明依套件內 / 既有分兩套。
- **真服務 e2e 改成一條指令、與試跑環境並存**（M4 票 34）：`uv run --env-file .env python -m tests.e2e.stack`
  起、測、一定 `down --volumes`，本機與 nightly 同一條。e2e 有自己的專案名、容器名（`berth-e2e-*`）、網路與子網、
  host port（28xxx）與 named volume，正式 compose 不動；compose 的變數只放進子程序、蓋過呼叫端 shell 的同名
  變數，不再要 `export CONFIG_ROOT`。精靈那一段多守三件事：qBittorrent 不收的介面密碼停在頁 2、全域預設儲存路徑
  改掉之後送單照常、完成時照頁序再驗。
### Removed
- **頁 4 的既有 Prowlarr 表單改用頁 1、2 那一份，`POST /api/setup/indexers/connect` 拿掉**（M4 票 39，brief §19 D5、
  審計 E-2）：**破壞性**——既有 Prowlarr 改送 `POST /api/setup/services/prowlarr`（`{origin: "existing", base_url,
  api_key}`），精靈的 `choices` 只剩這一條寫入路徑，換台時一律經過同一份清理；`GET /api/setup/indexers` 不再回
  `reason`（只給那份表單選補法，連線測試的理由在 `GET /api/setup/status` 的 `services`）。畫面上 key 錯時與頁 1、2
  同一個錯誤版面（有「測試結果」那一列、補法說去哪裡複製 key），右欄的 API key 那一格跟著最近一次連線測試，失敗時
  不再寫「已取得」；設定 → Prowlarr 的位址與 key 改在與另兩頁同一個連線區。
- **BTH 4 只接 Prowlarr：通用 Torznab 端點與 Jackett 拿掉**（M4 票 37，brief §19 D3，2026-10-06 使用者拍板）：
  **破壞性**——`POST /api/setup/indexers/connect` 不再收 `kind`（只收 `{base_url, api_key}`）、`GET /api/setup/indexers`
  不再回 `kind`、`IndexerProblem` 與 `StepFailure` 少 `no_search`、`SiteSearchOut.indexer_id` 一律是整數、
  設定 `services.indexer` 少 `kind`。`TorznabSearch`、`adapters/torznab/`、`IndexerKind`、`IndexerSearch.capabilities()`
  與 tmdbid 搜尋一起刪（Prowlarr REST 只有關鍵字搜尋）；泊位名改「Prowlarr」，頁 4 與設定頁沒有「接法」單選。
  資料 migration `b4ca280eaeca`：存著 Torznab 端點的安裝，索引站位址與 key、精靈的 Prowlarr 選擇與頁 4 的步驟都清掉，
  頁 4 回到待處理、搜尋說沒設定；Prowlarr 的安裝只少 `kind` 這一個鍵。**降版不會還原清掉的資料。**
  代價：Jackett 與單站 Torznab 網址沒有路徑（先裝 Prowlarr），單站 Torznab 比 Prowlarr REST 冷查詢快的那條捷徑（1.2 秒對
  60–85 秒）跟著消失。
- **qBittorrent 的「建議設定」整組**（M4 票 32，brief §19 D2）：**破壞性**——`POST /api/settings/qbittorrent/apply`
  （「還原建議設定」）與 `GET /api/settings/qbittorrent/diff` 拿掉，設定頁的 qBittorrent 改讀頁 2 的
  `GET /api/setup/qbittorrent/diff`（路徑名照舊）。`QbittorrentOut` 少 `diffs` 與 `writes_preferences`、健康那一列
  （`ServiceHealthOut`）少 `drift`、`StepFailure` 少 `save_path_missing`；頁 2 的「將會寫入的鍵」、設定頁的差異表與
  還原鍵、健康頁的「設定被改過」一起消失。存下的舊紀錄照樣讀得回來：三個鍵的步驟讀的時候丟掉、`save_path_missing`
  讀成 `unexpected`（下一次檢查就換掉）。
- **`QbittorrentOut.temp_path_warning`**（M4 票 22）：既有 qBittorrent 沒開全域未完成目錄不再是一件事。

- **精靈的偵測**（M4 票 15）：`POST /api/setup/detect`、「偵測服務」那一步與泊位板上方的前置列、「重新偵測這個服務」
  （換成出問題那一頁的「重新測試」）。選之前 Berth 不對任何服務發請求。

- **服務設定頁 `/settings/services` 與精靈的 `?berth=` 深連結**（M3 票 06i）：前者拆進設定的各分頁，後者連同
  「改位址或憑證」與精靈跑完之後的「回到 Berth」一起拿掉——精靈跑完之後不再是設定入口。後端的
  `GET /api/settings/services` 照舊（設定頁的健康卡讀它）。

- 精靈完成頁的「回媒體庫路徑」（M3 票 06d）：它是唯一一顆「上一步」、按了之後出不去；由「上一個泊位」取代。

- Route 的 profile 選擇（票 14e）：精靈泊位 4、設定 →「媒體庫路徑」的新增與修改都不再問「命名 profile」，
  `ProfilePicker` 刪除；拒絕理由 `profile_unsupported`（電影 Route 不收 anime）跟著規則一起消失。
- `scripts/experiments/profile_effect.py`（票 14e）：它量的東西不存在了。研究文件
  `docs/research/profile-effect.md` 留著當紀錄。

- `job_files.release_info_json`（M3 票 01，migration `f2a7c91d4e38`）：M1 起就沒有人寫它。RSS 要的時候直接解析
  Item 的標題（純函式，M3 票 10），不另存一欄。
- `InventoryOut` 卡片上的 `tracking.needs_review` 與 `tracking.has_unmatched`（M2 票 14）：唯一的消費點是舊的
  卡片牆篩選，換成審核佇列的清單之後沒有人讀它們。
- `GET /api/jellyfin/watching`（M3 票 06）：整個帳號的繼續觀看與下一集，唯一的消費點是探索頁上方那兩列。
  媒體庫頁那一份 `GET /api/inventory/{library_id}/watching` 不變。

### Fixed
- **精靈頁 2 測試通過就做完：拿掉不寫入的確認鍵**（M4 票 38，brief §19 D5，2026-10-06 審計 S2、S5）：
  既有 qBittorrent 測試通過之後還要按「確認，不改任何設定」才能前進，按下去什麼都不做；重裝保留套件內
  qBittorrent 的 config 時三鍵都「已經是這樣」，仍要按「套用這 0 項」。現在既有的那一台連線測試通過即完成；
  套件內的那一台連線測試順便讀它自己的 WebUI 帳號（設過的就記下），只有介面登入還沒設、或按了「更換登入」時
  才有一顆「設定介面登入」。`POST /api/setup/qbittorrent/apply` 的形狀不變，前端只在設登入時呼叫它。
- **既有服務的接入說明：只多掛一條 `/data`，並真的停掉套件內那一台**（M4 票 36，2026-10-06 審計 §C1、§C2、S2）：
  「既有」卡片原本寫「同一個容器路徑（例如都是 /data）」，Berth 的三層路徑其實固定在 `/data` 底下；改寫成只能是
  `/data`、`DATA_ROOT` 要建得了硬鏈接，既有 Jellyfin 要先有對應類型的媒體庫。掛載的補法原本叫人把下載目錄移到
  `/data` 底下、別分開掛 `/downloads`，照做舊 torrent 會找不到檔案；現在是在原本那一份多加一條
  `${DATA_ROOT}:/data`、原本的掛載不動，compose 與 `docker run -v` 各給一行（精靈頁 3，Route 設定頁也照選擇給這一份）。
  選了既有之後原本只說「從 `COMPOSE_PROFILES` 拿掉再 `docker compose up -d`」，那停不掉已經在跑的套件內容器，
  現在多給 `docker compose stop <服務>`（`scripts/experiments/compose_profile_removal.py` 實測，brief §20.14）。
- **「套件內」卡片把停掉的容器說成「沒有起」，起回來測試轉綠之後還留著**（M4 票 35，2026-10-06 審計 S3）：停掉的容器
  與不在 `COMPOSE_PROFILES` 裡的服務主機名一樣解不到、分不出來，卡片改說「這套 compose 的 X 沒在跑」，補法兩種都給：
  停了就 `docker compose start X`，不在就加回 `COMPOSE_PROFILES` 再 `docker compose up -d`（測試那一條的補法同一組）。
  那一頁每次選擇或按「重新測試」之後重問主機名，加註不再停在進頁那一刻。
- **套件內 qBittorrent 的全域預設儲存路徑一改，Route 就轉紅、送單被擋**（M4 票 32，2026-10-06 審計 S5）：Route 檢查
  對套件內那一台另外現查全域 `save_path`，Berth 卻不落在那裡——送單逐個 torrent 帶自己的分類與 `autoTMM=true`。
  錯誤還掛在分類路徑底下、講的是另一個目錄。現在兩種來源都只看分類回報的兩個路徑（完成與未完成），**套件內那一台
  也不再寫 `save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`**，頁 2 只剩 WebUI 登入。
  **已經被 Berth 寫過的不改回去**（Berth 沒存原值）：想讓自己手動加的 torrent 放回別處，在 qBittorrent 的
  「選項 → 下載」改預設儲存路徑即可，不影響 Berth。
- **精靈的文案與顯示細節**（M4 票 31，2026-10-01 實測的 P3 與第 21 條）：`POST /api/setup/complete` 照頁序把每一頁
  再問一次（原本只驗頁 3 與頁 5，另一個分頁回頭弄壞頁 2 或頁 4 也完成得了），422 說最前面那一頁，畫面回到那一頁並說
  為什麼回來。`POST /api/setup/routes` 的「選擇不成立」改成帶理由的 422（`{reason, detail}`：`library_missing`、
  `library_unsupported`、`target_not_in_library`，新的 `library_without_path`），畫面照理由說去哪裡改，不再一律說
  「畫面過時了」。套件內 Route 的分類與 complete 子目錄照清單上填的資料夾名（媒體庫「電影」、資料夾 films 是
  `berth-films`），Route 照清單順序建。文案：Route 的檢查不寫條數（原本「五條」實際六條）；帳密被拒照服務說
  （qBittorrent 說帳密、TMDB 自己一句）；另一台 Jellyfin 不再用容器 ID 稱呼；「主機名解得到但連不上」改日常說法、
  啟動中不說「回的不是這個服務」；被封 IP 時說宿主瀏覽器也登不進 WebUI；既有卡片照實說 Berth 會加什麼；回頭看帶子
  用泊位名；套件內 qBittorrent 不提「完成時執行外部程式」。顯示：完成頁列出各服務自己介面的網址與登入方式；泊位板
  媒體庫路徑那一格寫建了幾條 Route、TMDB 沒填 key 時說「還沒填」；TMDB key 形狀不對在送出前擋下；「改位址」可取消；
  Jellyfin 語言下拉跟著介面語言；登入既有 Jellyfin 時密碼空著說 Berth 不收沒有密碼的擁有者、改了帳密收起舊的拒絕；
  「重新讀取」讀到了也說；頁 4 的測試與試搜結論在離開再回來之後還在、Prowlarr 刪到 0 站時三處一致；設定頁 qBittorrent
  的建議設定表先寫人話；路徑預覽不印 `../etc`；Prowlarr 介面登入在 Berth 停著時說請求沒走完。
- **精靈的導覽：上一頁回到上一步、重新整理留在原頁、手機首屏、只有 Berth 時的套件內卡片**（M4 票 30，2026-10-01
  實測第 23、24 條與 brief §19 的決定）：畫面上那一頁在網址上（`/setup?step=N`），瀏覽器的上一頁回到上一個看過的頁、
  不再直接離開精靈；回頭看或剛做完的頁重新整理留在那一頁（原本被帶回目前這一步、或被推到下一頁）；網址指到還沒到的頁
  就拉回目前那一頁。手機寬度的泊位板收成一列摘要（五個小色塊＋目前那一格＋展開），首屏先看到這一頁要做的事。新增
  `GET /api/setup/compose`：只查三個套件內主機名解不解得到、不對服務發請求，服務頁的「套件內」卡片照它說「這套 compose
  沒有起 X」並給加回 `COMPOSE_PROFILES` 的那一行；卡片照樣可選、不預選。
- **頁 1 的剩餘問題：重試保留語言、媒體庫語言跟介面、帳號規則先擋**（M4 票 29，2026-10-01 實測第 16、17、18 條）：
  未初始化的 Jellyfin 在建好管理員之後某一步失敗，重新整理後頁 1 仍是建立表單、照上一次選的語言與遠端存取重填
  （`GET /api/setup/status` 多一欄 `jellyfin_startup`，存在 `setup.jellyfin.startup`），只有那一台真的跑完初始精靈才改成
  登入——原本重試會以 zh-TW、不開遠端存取蓋掉使用者的選擇。套件內媒體庫的 metadata 語言與國家照 Jellyfin 自己的設定
  （`GET /System/Configuration`）建，英文介面不再建出繁中媒體庫。建立管理員時照 Jellyfin 12 的帳號規則先擋並說出規則
  （原本被 Jellyfin 400、畫面只說「那一段沒做完」），只有空白的密碼當成沒填；登入頁與頁 1 一樣修剪帳號前後的空白。
- **擁有者成立之前不能提早登入、Jellyfin 目標不能被悄悄換掉**（M4 票 28，2026-10-01 實測第 14、15 條）：
  擁有者成立之前 `POST /api/auth/login` 一律 403、帳密不交給任何一台（原本頁 1 一選 Jellyfin，那一台上任何帳號都能
  直接拿到 session）。`POST /api/setup/owner` **必帶**畫面上測過的 `base_url` 與 `server_id`（`GET /api/setup/status`
  每個服務多一欄 `server_id`），與存下的不同是 409 `target_changed`，帳密不送；比對過之後序列釘在那一台上，第一步答的
  ServerId 不同就停在帳密之前。兩個人同時成立擁有者時只有一個成立，另一個 409 `owner_exists`。畫面說位址在填表時被換過、
  給「重新測試」，重讀到另一台時打好的帳密清掉。
- **套件內 Prowlarr 換了 API key、或本來就有站，頁 4 不再是死路**（M4 票 27，2026-10-01 實測第 2、9、22 條）：
  「重新測試」每次都重讀唯讀掛載的 key（讀不到時沿用貼上的那一把），key 被拒的補法說掛載、不再說 qBittorrent 的
  免密白名單；連線卡綠而站清單讀不到時說讀不到、給「重新讀取」。Prowlarr 上已經有站（重裝保留它的設定）就算站那一半
  做完，介面登入設好就往下走；跳過索引站時完成頁照實際站數說。頁 4 還沒做完時，前進鍵的位置列出還差什麼
  （加站、介面登入），按了跳到那一區。
- **qBittorrent WebUI 登入照它的規則先擋、被拒說對原因、失敗不留半套**（M4 票 26，2026-10-01 實測第 3、20 條）：
  精靈頁 2 與設定頁的「更新登入」照 qBittorrent 5.2 起的規則在送出前擋下（帳號至少 3 字元、不能有冒號，密碼至少
  6 字元；沿用 Jellyfin 帳密時也檢查，太短就說不能沿用、請另設），不再卡在「回應的不是 qBittorrent」。
  qBittorrent 仍回 400 時那一條是新代碼 `login_rejected`、原文進技術細節；Berth 先送密碼再送帳號（5.2 帳號先寫、
  密碼後驗，brief §20.2），兩個都進去了才記帳號，失敗後表單不收成「帳號：xxx」，取消沿用時上一次的失敗不再掛著。
  頁 2 補法的連結改成瀏覽器開得了的位址（`GET /setup/qbittorrent/diff` 等多回 `web_port`），給不出就不給。
- **精靈的補法照原因給，不照檢查項目給**（M4 票 25，2026-10-01 實測 B5、B9、E2、E8～E12）：Berth 自己寫不進
  （`berth_cannot_write`）不再被說成 Jellyfin 或 qBittorrent 沒掛 `/data`、分類衝突，改說 PUID / PGID 與目錄權限、
  不給別的容器的片段；目錄被刪（新代碼 `directory_missing`）與不在共用掛載底下分開；qBittorrent 沒報預設儲存路徑
  說回頁 2 重新套用。`https://` 打到講 http 的 port、位址沒寫 `http://` 不再說成連不上（新理由 `scheme_mismatch` /
  `scheme_missing`），位址欄送出前先驗。`library_path` 的補法說先刪掉這條 Route 再選新路徑。精靈裡 Berth 自己的
  401 / 403 各說各的：不是管理員（給登出）、擁有者在別處搶先成立、登入失效（給登入），不再說後端沒在跑或出錯。
  只有 Berth 時選套件內 Prowlarr 先連線再讀 key，說主機名解不到而不是讀不到 key。qBittorrent 套用之後停了，
  頁 2 的連線卡跟著變紅、出現「重新測試」，頁 2 不再算做完（前進鍵收起）；主機名解不到的句子說出容器可能停了。
- **關機時被打斷的資料庫連線沒有關**（M4 票 24 之後，`test_setup_api.py` 單獨跑三次兩次紅）：lifespan cancel 背景迴圈
  時若正好打在開新連線（含設 pragma），SQLAlchemy 與 aiosqlite 都把那條連線丟著不關，worker thread 之後把結果交回已經
  關掉的事件迴圈。連線改由 `berth/db/engine.py` 的 `async_creator` 開，pragma 不再走 `connect` 事件；開連線與設 pragma
  被 cancel 時先做完、關掉再往上丟。
- **精靈頁 3 的前進條件跟畫面一致**（M4 票 24，2026-10-01 實測 R-04～08、E6-14～16、E8-04～05）：保留 Jellyfin、
  只清 Berth 重跑時清單全部已建立，Route 全綠卻永遠停在頁 3——頁 3 的前半改看媒體庫快照（清單每一列都在
  Jellyfin 上），不再看「建媒體庫那一步有沒有跑過」。套件內只替清單上的媒體庫建 Route（`LibraryChoiceOut.listed`）：
  使用者自己在 Jellyfin 加、路徑不在 `/data` 的媒體庫不再自動建成紅的 Route、刪掉又長回來；套件內進頁與按下
  「建立並檢查」之前也重讀 Jellyfin，在那邊刪掉的媒體庫不再列出。刪掉 Route 之後重讀精靈進度，最後一條紅的
  刪掉就出現「前往下一個泊位」，既有模式那個媒體庫取消勾選。換一台 qBittorrent 時 Route 的逐條明細一起清掉，
  不再寫「尚未檢查」卻掛著上一台的 0 / 6 與錯誤。
- **精靈剛做完的一頁被舊狀態蓋回去**（M4 票 23，2026-10-01 實測 L-P2-1）：套件內服務啟動中時前端每 3 秒重測，
  後端每次都讀整份 `settings.setup`、等網路、再整列寫回，同時在頁 2 做完的結果幾秒後就變回上一次的失敗；兩個
  分頁同時操作同理。精靈寫 `settings.setup` 與 `services.*` 的命令都改成在寫鎖內重讀、只改自己那一段；測到一半
  換了位址，舊那一台的結果不記；兩人同時送頁 1，後到的是 `owner_exists`。前端的啟動中輪詢只測畫面上那一頁的服務。
- **精靈頁 1 擁有者的密碼打錯時，整頁被捲回頂端、看不到錯誤訊息**（M4 票 15 的 critique）：那個 401 被當成登入
  失效、重跑了路由守衛；現在與登入頁一樣當成帳密不對。
- **自動綁定握著寫交易問 TMDB**（M4 票 13 的 code-review 抓到，plan §3.3）：搜尋與讀詳情寫了快取卻不 commit，下一個
  搜尋詞與每一部候選的詳情都在寫交易裡打 TMDB——一個番組最多十幾個請求，期間其他寫者只能等，是 M4 票 01
  `database is locked` 那一型。現在每問完一次就 commit；`test_write_discipline` 多一條監看 TMDB 的閘門。
- **搜尋 feed 的第一輪預覽要兩秒多**（M4 票 13b）：30 筆的預覽把同一個發佈名丟給 guessit 約四次，一次 120 次、握著
  事件迴圈，背景同時規劃補舊集時前端 e2e 5 秒內等不到它。`parse_release` 記住最近 2048 個名字的結果，預覽降到
  0.15 秒左右、建搜尋 feed 降到 1 秒內；量測腳本 `scripts/experiments/rss_subscribe_timing.py`。
- **剛加的 Feed 按「立即輪詢」偶爾說「新 0 筆」**（M4 票 13c）：背景 poller 正好在輪它時，按下去的那一輪排在後面，
  讀到的全是前一輪剛收下的 Item。後到的現在直接拿正在跑的那一輪的結果（Go `singleflight` 的做法），不再多抓一次。
- **精靈第 2 步探測完，「前往泊位 1」上方印出一行程式碼註解**（M4 票 10）：`//` 註解寫在 JSX 子節點裡就是文字。
  `pnpm -C web lint` 多開 `@eslint-react/jsx-no-comment-textnodes` 擋這一型（`web/src/lint.test.ts` 守著它還開著）。

- **精靈的文案與實際不符的幾處**（M3 票 06h）：完成頁寫「四個泊位」、既有 Jellyfin 也說「用剛才建立的管理員
  登入」；前置列把探測中的服務也算成已判定；第 2 步寫死 `qbittorrent:8080`；連線表單三個服務的範例位址都是
  `:8096`；設定頁的 TMDB 說明提到精靈的進度。淺色主題泊位板上沒塗漆的格子對比只有 3.73:1（現在 5.71:1）；
  TMDB 測試結果與探測結果放進常駐的 live region，螢幕閱讀器念得出來。

- **精靈回頭之後走得回來**（M3 票 06d）：完成頁按「回媒體庫路徑」之後沒有任何按鈕解除，只能重新整理；
  走完過的人按「重新探測」再按「前往泊位 1」，落到的是最後一步。

- **精靈第 1 步改了帳密之後，第 3 步不再用 Jellyfin 不認得的密碼登入**（M3 票 06c）：Berth 改不了 Jellyfin
  的密碼，原本「改帳密」會把 Berth 記的那一組換掉，停在拿到 API key 之前的第 3 步重跑就被 401。
- **只改密碼時，重新套用第 5 步會把新密碼寫進 Prowlarr**（M3 票 06c）：原本只比帳號與驗證方式，帳號沒變就
  當成已經設好了。
- **套件內 Jellyfin 發佈在別的 port 時，「在 Jellyfin 開啟」開到對的那一台**（M3 票 06b）：深連結推導的第 3 條
  原本取 `base_url` 的 port，也就是容器內的 8096；發佈成 `18096:8096` 時開到的是同一台機器上另一台 Jellyfin。
  現在用 `JELLYFIN_PORT`。
- **精靈第 5 步加站還在跑時按「測試 TMDB」，TMDB 的結果不再被蓋掉**（M2 票 15 的 e2e 抓到）：兩支命令都是「讀
  `settings.setup`、打網路、整份寫回」，後寫完的那一支把對方剛寫的那一半蓋回去——畫面說 TMDB 已完成，精靈卻卡在
  第 6 步。反過來（TMDB 先送出、加站先寫完）則是逐站結果消失。三支命令（加預設站、測既有索引站、測 TMDB）改在
  寫鎖裡重讀、只改自己那一半（`services/settings.update_settings`）。

- **網址上認不得的 `?filter=` / `?page=` / `?sort=` 不再原樣漏到媒體庫頁**（M2 票 13）：根路由不驗網址，子路由拿到的
  是兩者合起來，驗不過的那一格沒寫回去就照原樣留著。守衛收成一份 `isInventoryFilter`，頁面那一道拿掉。
- **導覽方塊的當前頁不再同時帶兩種邊框色**（M2 票 13）：`activeProps` 的 class 是接在後面的，改用 TanStack 的
  `data-status="active"`。篩選列選著的那一個不再掛 `aria-current="page"`（它是一個選項，不是另一頁）。
- **媒體庫牆上下兩組分頁是兩個名字不同的地標**、集表有 `<caption>`、排序方向有看得見的標籤、窄版集表看得到片長與
  播出日、TMDB 標誌的替代文字走 i18n（M2 票 13，M1.5 audit 的 P2 / P3）。
- **缺集搜之後關鍵字欄不再說「留空就用這部作品的各個名字」**（M2 票 13）：留空問的是缺的那幾集。

- **拒絕之後重算出來的那一筆「待審核」不再被時間線吞掉**（M2 票 07）：事件一分鐘內同內容只寫一次，
  界線原本只有使用者按的重試；拒絕之後重算的 `review_required` 與第一份一字不差，於是時間線停在「已拒絕」
  而那一筆已經又停回待審核。審核決定（`review_decided`）現在也是界線。
- **撤銷一個 audit 之後不能原樣再核准**（M2 票 07 code-review）：撤銷的那一列 Plan Item 回到沒有提案
  （`review`、季集與路徑清空），核准被 `undecided` 擋到管理員改那一列為止——否則按一次核准就把剛拆掉
  的鏈接鏈回同一條路徑。同一次 `PUT /plans/{id}/items` 裡同一列出現兩次是 422，不再後者蓋前者。

- **同一個新使用者兩次登入同時進來不再是 500**（M2 票 01）：`services/auth.py` 的鏡像使用者撞上
  `users.jellyfin_user_id` 的唯一索引時重讀那一列，兩條都拿到同一個鏡像使用者。
- **檢查途中被另一個分頁刪掉的 Route 不再是 500**（M2 票 01）：`POST /setup/routes` 順帶重跑既有 Route 的檢查時，
  那一條的寫回改判成 404 `route_missing`——與 `routes/*` 同一種拒絕。逐條 commit 因此也各自獨立：
  第二條被刪掉不會把第一條已經算好的結果一起退掉。
- **`Season 3 / … Season 3 - 46` 不再被讀成 `S03E03–E46`**（M2 票 01）：`Season <季> - <集>` 這種寫法裡的
  破折號數字是集號不是範圍尾。兩筆真實發佈進語料，`berth bench` 的 `auto_wrong` 維持 0。
- **下載列表不再逐列查關聯**（M2 票 01）：`list_jobs` 的 Route / Media / User 與計劃改成四次批次查詢，
  查詢次數不隨下載筆數成長。
- **精靈第 7 步遇到「Route 被另一個分頁刪掉」時只說「請求沒有走完」**（M2 票 02a）：那是一句
  既沒有原因也沒有下一步的通用失敗。現在說的是「這一步順便重新檢查了既有的 Route，其中一條在途中
  被刪掉了」與「重新整理這一步」，與 Route 設定頁上的三處同一個形狀。
- **精靈與設定頁的十餘處狀態說不出後果**（M2 票 03）：表單沒改過時「儲存」不再亮、所有路徑都被佔用時
  「建立並檢查」不再畫成主動作、確認區的「取消」不再比主動作寬、通過 TMDB 閘門後泊位 3 的詳情列跟著更新、
  缺憑證時 `complete.failed` 不再錯怪後端、第 7 步的勾選表直接標出已被佔用的路徑。
- **三句 EN 文案與兩處 i18n**（M2 票 03）：`Already so` → `Already there`、`Moored` → `Ready`、
  `10 of 46 episodes in` → `10 of 46 episodes imported`；EN 子分頁 `Library paths` → `Routes`（CONTEXT.md 的詞是 Route）、
  `routes.cutaway.category` 的 zh-Hant 值原本是英文；信心在同一塊展開區的兩套詞統一成一套。
- **排序鍵不在選單上時不再空等七秒**（M2 票 02）：前端手抄的那一份權限拒絕漏了 `sort_not_offered`，
  於是後端已經說清楚的 422 被當成「沒說理由」，TanStack Query 照預設重試三次、間隔加倍。封閉集合改由
  OpenAPI 產出之後它自然補齊了。
- **「只看缺集」不再跟著換過去的那一部作品走**（M1.5 票 09b）：`/media/$mediaId` 是同一條路由，所以在作品之間
  換頁時季表不重掛，上一部篩過的狀態會留在下一部身上（目標已在快取裡、沒有讀取中的空檔時特別明顯）。季表
  連同工具列抽成 `SeasonsPanel`，由詳情頁以 `key={media.id}` 掛上。
- `scripts/fake_setup_server.py` 的 `--port` 真的生效（M1.5 票 09b）：演練用的 torrent 下載連結寫死了 `8484`，
  所以換 port 之後送單只會回 `source_unavailable`。
- **M1 的 critique（票 15，26 / 40）**：`/jobs` 在手機上被沒有空格的發佈名撐出 67px 橫向捲動（機器字串改用
  `overflow-wrap: anywhere`）；季表的「入庫」欄在窄版畫面外、季名與集數疊在一起；medium 自動入庫的檔案在
  下載列與媒體庫卡片上看不出「還要看一眼」（新增「N 個待確認」色塊與 API 的 `audits` 欄位）；送單與其他就地
  確認在按下之後把鍵盤焦點丟回頁首、Esc 不關、確認不說送到哪條 Route；頁面沒有 skip link、頁首導覽不是
  landmark、探索與 Route 設定頁沒有 h1、詳情頁 h1 直接接 h3、`<summary>` 裡包著連結、語言鍵只有 23px 高。
  另外：連續的「已鏈接」事件合成一行、可展開的列會說「展開 / 收起」、S00 的正片標「特別篇」、torrent 從
  客戶端消失不再是紅字、媒體庫切換列不再把 Route 名大寫。
- **請求的 commit 發生在回應送出之後**（票 15，`berth/api/deps.py`）：FastAPI 對 `yield` 相依的收尾預設在
  回應送出之後才跑，客戶端拿到 200 時寫入還沒落地——緊接著的下一個請求讀到舊狀態，commit 失敗時手上也已經是
  一個成功。e2e 第一輪就抓到：精靈第 2 步判定完、第 3 步馬上讀不到 Jellyfin 的位址。瀏覽器按鈕之間的間隔
  通常蓋掉了它。
- **TMDB 改名之後，下一包入庫到另一個資料夾**（票 15）：資料夾名在第一次送單成功那一刻凍結（brief §4.5），
  但命名一律照快照的標題重算，凍結的那一串沒有任何人讀。同一部作品因此會在 Jellyfin 裡出現第二部，電影的多版本
  也斷掉。計劃與 pre-plan 現在都照凍結的資料夾名寫。
- **目標路徑寫法不正規（`…//tv/`）的 Route，媒體庫牆是空的**（票 15）：帳本的目標是正規化過的，前綴卻照字面比。
  與票 14a 修掉的刪除引用數同一個問題、同一個修法。
- **英文在只有一筆時說「1 routes」「1 services decided」**（票 15）：七個帶 `{{count}}` 的鍵沒有 `_one` /
  `_other`，i18next 找不到就退回原鍵。補齊之後加了一條測試：任何帶 `{{count}}` 的值都必須成對。
- **Windows 的 PowerShell 裡 `deploy/` 腳本測試全紅**（票 15）：`bash` 解析到 WSL 的啟動器，它讀不到 `C:/…`
  路徑（exit 127）。改成先問 bash 讀不讀得到宿主路徑，讀不到就略過；Linux 與 Git Bash 照跑。

- **季號剛好等於方括號集號時被丟掉**（票 14f，`berth/parser/release.py`）：為 `The_Final_Season[28]`
  寫的規則是「季號等於方括號集號就丟掉季號」，於是 `Mushoku Tensei S2 [02]` 讀成沒有季號的第 2 集。
  TMDB 併成一季的 Re:Zero 因此把 `S2][02]` 以 medium **自動入錯**成 S01E02（正解 S01E27），多季作品
  則被絕對編號的規則送審核。判準改成「`Season` 緊接著方括號」：票 01 的 16,688 個 Mikan 標題裡，
  原本丟對的 94 個照樣丟、丟錯的 21 個讀回季號，其餘標題的季集逐筆不變。語料補兩筆，`berth bench`
  的 `auto_correct` 170 → 172、`auto_wrong` 仍是 0。
- **刪除 Route 與送單的競態**（票 14a）：刪除先算引用數再刪，兩步之間另一個請求送的單會先落地，
  接著被刪除設成 `route_id = NULL`。現在算引用數與刪除在同一把 SQLite 寫鎖裡，那一筆等到刪除 commit
  之後撞上外鍵，送單回 422 `route_missing` 而不是 500（`add_download` 的 `try` 往前擴到 flush）。
- **兩個分頁同時新增 Route 回 500**（票 14a）：兩邊都看到目標沒人佔、算出同一個 slug，後到的撞上唯一
  索引。建立改在寫鎖內重讀再寫，後到的那一個回 `target_taken`；修改與重新檢查途中 Route 被刪掉回 404
  `route_missing`。
- `/api/routes/{id}` 的刪除只算那一條的引用數（帳本以前綴粗篩、`owning_route` 精判），不再整張帳本讀進來。
- 前端測試的 fetch 替身遇到 204 會自己丟 TypeError，票 14 的刪除成功測試因此從來沒走到成功分支。
- **`[01-13Fin]` 被讀成「第 1 集」**（`berth/parser/release.py`）：`Fin` / `END` 黏在集號後面是中文
  字幕組的季末寫法，而方括號的集號規則不認得它們，於是一整類季包的預估季集是錯的。`完` / `完結`
  沒事——`normalize_cjk` 已經把它們吃掉了。票 08 在真的索引站回應裡抓到，`berth bench` 的
  `auto_wrong` 仍是 0。

- **英文的「{{count}} titles」在只有一筆時說「1 titles」**（探索頁的搜尋計數）。i18next 傳 `count`
  時查的是 `_one` / `_other`，兩個都沒有就退回原鍵。其他頁面既有的同類鍵尚未處理，留給 M1 的 UI 收尾。
- **一把真的 TMDB v3 API key 被當成「同形狀的假值」寫進測試**（票 08）。它從未被推送——帶著它的
  兩個 commit 都還在本地 `main` 上——但憑證仍已換掉，字串換成 `0000…0003`。假值的號碼表寫進
  `tests/fixtures/http/README.md`，那條規則現在管的不只是 fixture 檔，也管任何寫得出憑證形狀的測試。
- **泊位板的實測值標籤對比只有 3.56:1**（WCAG 2.2 AA 的驗收條件，PRODUCT.md）。`opacity-70` 疊在
  信號色塊上，正好把 `index.css` 註釋裡「白字配中明度色只有 3.6:1，過不了 AA」那個數字加了回來。
  拿掉 opacity 之後同一批標籤實測 **9.63:1**，精靈與健康頁兩塊板都適用。
- **英文版把大小寫敏感的 API 端點大寫掉**：剖面欄的 term 走 `.label`（拉丁文 `uppercase`），
  於是左欄印 `POST /LIBRARY/VIRTUALFOLDERS`、右欄印正確的 `POST /Library/VirtualFolders`，
  同一畫面兩種大小寫而其中一種不是真的端點。中文版因為 `text-transform: none` 沒有這個問題，
  所以一直沒被看到。`CutawayRow` 新增 `code` 變體給機器字串用。
- **索引站的「之後再說」按下去畫面毫無變化**：狀態存下去了，但只有 TMDB 那一節畫得出徽章。
  兩個審查代理與驗收本人都以為按鈕壞了而重複按。徽章同時改用新的 `source.deferred`
  （「之後再說」/「Deferred」）——原本借用的 `status.skipped` 是「已經是這樣」，那是冪等步驟的字。
- **`<summary>` 落回 Chrome 預設的 0.67px 焦點環**：`:focus-visible` 的選擇器漏了它。
- **「顯示」密碼按鈕 38.6 × 15px**，間距例外也不成立（距密碼框 11.5px < 12），不符 WCAG 2.2 AA 2.5.8。
- **窄版泊位板是 carousel**，BTH 3 與 BTH 4 整個在畫面外，而「一眼看出哪一格紅了」正是這塊板的
  用途；捲動容器還會變成一個沒有名字的 Tab 停留點。改回 shape brief 寫的 2×2。
- **精靈沒有出口**：設定跑完之後它就是設定入口（plan §6），但整頁沒有任何連結回得去，而設定頁
  三張服務卡片的「改位址或憑證」又全部連到裸 `/setup`（於是不管按哪一張都落在第 3 步
  「接手這台 Jellyfin」）。精靈新增 `?berth=1..4` 深連結、返回鍵，以及一句「不會重跑一次靠泊」。

- **入口腳本從來沒有接手過媒體根的擁有者**（`deploy/entrypoint.sh`）。`take_ownership` 的參數順序
  寫反，`/data` 那一次呼叫展開成 `chown /data berth:berth berth:berth`，一律失敗。Windows 上看不
  出來（那裡 `chown` 本來就會失敗且不影響寫入），但乾淨的 Linux 宿主上 Docker 新建的 `/data` 是
  `root:root`，Berth 連 `/data/library` 都建不出來，精靈第 3 步當場死。順帶讓腳本改讀
  `CONFIG_ROOT` / `DATA_ROOT`——它本來寫死路徑，與 Berth 自己讀的變數對不上。
- **qBittorrent 5.x 的登入被判成失敗**（`berth/adapters/qbittorrent/client.py`）。`auth/login` 成功時
  4.4.5 回 `200` + `Ok.`、5.2.3 回 `204` 空 body；失敗時 4.4.5 回 `200` + `Fails.`、5.2.3 回 `401`。
  原本的判定是「不是 `Ok.` 就是失敗」，所以**每一套用預設 image 的部署，qBittorrent 那一項健康檢查
  都永遠紅著**。判定改成只認 4.x 的 `Fails.`，兩個版本的實測回應都錄成 fixture。
- **Prowlarr 冷啟動時索引站清單超過探測逾時**（`berth/adapters/prowlarr/client.py`）。容器剛起來的
  第一次 `indexer/schema` 要讀進 627 份定義再組出 5.6 MB 回應，Windows 的 9p bind mount 上實測
  9.42 秒（第二次 0.34 秒），5 秒的探測逾時讓精靈第 5 步在乾淨部署上直接失敗。這一支端點改用自己的
  逾時。

- **牆上不認得的 `?filter=` 值不再被當成「對不到」**（M1.5 票 11 的 critique 實測）。判定原本是「不是 `review` 就是 unmatched」，所以手改網址帶一個不存在的值時，畫面顯示的是一份他沒有要的清單，而三顆篩選鍵都沒有被標成當前。兩個值各判一次，其餘回到「全部」。
- **壞掉的海報不再露出瀏覽器的破圖示**（M1.5 票 11 的 critique 與 audit）。票 04 做的 `ArtSlot`（載入失敗換成「無海報」）只被媒體庫牆用到，探索牆的卡片與 Media 詳情的身份帶各留了一份沒有 `onError` 的舊 `<img>`；兩處都改走同一份。圖片代理對沒有的圖回 404，所以這條路徑是走得到的。
- **卡片裡的就地確認不再把整排牆撐高**（M1.5 票 11 的 critique）。牆是 CSS grid 而格子預設 `stretch`，所以展開確認時同排的每一格都被拉成一樣高——390px 上量到同排多出約 300px 空白，而位移正好發生在使用者要決定一個清掉就回不來的動作時。`WALL_GRID` 加 `items-start`，只有展開的那一格自己長高。
- **標為已看 / 未看成功之後說得出來**（M1.5 票 11 的 audit）。失敗本來就有 `role="alert"`，成功只有「元素自己變了」；焦點這時已經回到那顆鍵上而它的名字剛換過，螢幕閱讀器不會重念，所以寫入成功對輔助技術是無聲的（WCAG 2.1.3）。旁邊補一個 `aria-live` 的 `sr-only` 段落。

- **Jellyfin 帳號被刪掉之後不再卡在「問不到 Jellyfin」**（M2 票 11 實測）：刪除的帳號 `GET /Users/{id}` 回 404，
  原本被當成協定不符、一路翻成 503 `jellyfin_unreachable`，session 活到 30 天期滿。現在與停用
  同一種處置：刪掉他的每一張 session、回 401 `account_disabled`（前端照「登入失效」處理，介面不變）。
  只認 `Users/{id}` 的 404——`UserViews` 的 404 可能是位址設錯，仍是「問不到」。
- **1,000 部的媒體庫上 `GET /inventory/{id}` 從 3.4 s 降到 0.66–0.68 s**（M2 票 11，plan §11.3 決定 2 的門檻是 1 s）：
  `_survey` 對每一部作品把整張帳本與 Job 各篩一次（1,000 × 13,000），改成先按作品分組、一次走完。不是 Jellyfin
  回太多，所以沒有做分段取，也沒有加快取（`docs/research/large-library.md`）。
- **不存在的下載不再讓畫面等七秒**（M2 票 12 實跑）：`GET /jobs/{hash}` 的 404 是答案，查詢不重試；只有網路層
  失敗才照預設重試三次。
- **審核佇列與待處理頁按完一列之後，焦點不再掉回頁首**（M2 票 16 的 critique）：按下去的那一顆跟著整列消失，
  鍵盤使用者每清一件就要從頭 Tab 一次。焦點改落在接替那個位置的那一列，清空了落在頁標題
  （`components/useFocusAfterRemoval.ts`，`/review`、`/issues` 與媒體庫的「待審 / 對不到」）。
- **EN 介面的佇列時間不再印成「上午10:31:36」**（M2 票 16 的 critique）：`whenText` 跟的是瀏覽器語系，改成 UI 的語言
  （同 `Timestamp`）。
- **Berth 不再刪掉使用者換進媒體庫的檔案**（M3 票 01）：把硬鏈接換成自己的一份（複製品、重新壓制的版本）之後，
  刪除範圍的「移除鏈接」、audit 撤銷與 rematch 拆舊鏈接都照路徑把它刪了。三條現在共用一個判斷——目標的 inode
  等於帳本記的或來源現在的才是 Berth 放的——都不等就不刪，`DELETE /jobs/{hash}` 與 `POST /files/rematch` 的回應
  多一格 `unmanaged`（沒刪的路徑）、`POST /review/audit/{id}/undo` 從 204 改成回 `{unlinked, unmanaged}`，時間線
  那一筆說得出是哪幾個。
- **只勾「移除鏈接」刪掉的下載，對帳不再每一輪為那幾個檔案開「鏈接遺失」**（M3 票 01）：帳本那幾列寫
  `unlinked`（新的 `LedgerStatus`）而不是 `target_missing`，同「標記為已無來源」的先例。
- **兩個分頁同時刪同一筆下載，後到的那一個回 409 `moved_on`**（M3 票 01）：原本它讀的是鎖外的舊狀態、
  compare-and-set 輸了只記一行 log，回報「刪好了」並在時間線多寫一筆 `deleted`。
- **送單失敗而 qBittorrent 其實收下了的那一筆，poller 認回來**（M3 票 02）：`torrents/add` 逾時或回應讀到一半
  斷線時 Job 停在 `submit_failed`，而 torrent 照樣在下載。poller 在客戶端看到同一個 hash 就接回 `submitted`
  （補上凍結資料夾名），之後照常走；時間線多一種事件 `recovered`。
- **程序在送單途中掛掉，重啟後那一筆不再永遠停在「已建立」**（M3 票 02）：啟動時停在 `requested` 的一律落到
  `submit_failed`（`error` 是 `interrupted: …`），qBittorrent 收下了的由上一條認回，沒收下的等人重試。
- **使用者在 qBittorrent 裡自己修好的下載，Berth 跟著接回來**（M3 票 02）：`missing_files` / `client_error` /
  `client_removed` 的 Job 在客戶端看到它好好的（自己 recheck、重新開始、把 torrent 加回去）就回到主幹，而
  Job 不在那個壞掉狀態的管線 Issue 由系統收掉（`resolved_by = system`），不再停在只剩「忽略」的那一列。
- **規劃器與 importer 處理某一筆時爆掉，畫面說得出來**（M3 票 02）：原本只進 log，那一筆看起來停在「規劃中」
  卻說不出為什麼。現在寫進 `Job.error` 與時間線（新事件 `round_failed`，同一個錯誤不重寫）。
- **「重新校驗」在 qBittorrent 5.x 上對停住的 torrent 有作用了**（M3 票 03）：原本送 recheck 再送 start，5.x 校驗完
  又把它停下來——缺檔的那一包停在 `stoppedDL`，Job 卡在「下載中」、沒有 Issue、畫面上看不出任何事。現在先 start
  再 recheck（4.4 兩種順序都成立，實測見 brief §20.2）。
- **磁碟空間低於門檻時不再送單**（M3 票 04）：服務設定裡的磁碟門檻原本只開一件「磁碟空間不足」，現在送單與
  送單的重試在要 torrent 之前先量 incomplete 那一側，不夠就拒絕（409 `low_disk_space`，一個 Job 都不建）。
  手動與之後的 RSS 同一個判斷；門檻 `0` 不量。
- **刪除過、沒清紀錄的 torrent 再送一次會被拒**（M3 票 04）：原本回傳那一筆 `removed` 的 Job 當成「本來就在了」，
  送單的人以為成功了、其實什麼都沒下載。現在是 409 `job_removed`，畫面上給一條到那一筆的連結。
- **停在審核的那一筆只有管理員能重新規劃**（M3 票 04）：一般使用者按一次就會丟掉管理員逐列改過、撤銷過的那一份。
  現在是 403 `review_needs_admin`，而 `JobOut.replannable` 依按的人算，一般使用者在那一筆上看不到那一顆。
- **逐列改了還沒套用時，「核准並入庫」擋下來並說出是哪幾列**（M3 票 06）：核准不帶表單上的值，原本會照改之前
  的那一份入庫。
- **核准、撤銷、確認 audit、修好 Issue 之後，Media 詳情的入庫狀態不必重新整理就會變**（M3 票 06）。
- **任何請求回 401 都送回登入頁，登入後回到原本那一頁**（M3 票 06）：原本只有換頁時的守衛會發現 session 死了，
  停在頁上按的每一顆都只說「失敗」。
- **動作鍵送出中按了不再送一次**（M3 票 06）：Job 的重試 / 重新規劃 / 重新入庫、送單、搜尋、重抓 TMDB 等原本
  按得到第二次；送出中的鍵改用 `aria-disabled`，焦點不再掉回頁首。
- **審核與待處理頁的無障礙小修**（M3 票 06，M2 票 16 的遺留）：逐列「改」與「修正」打開時焦點進到表單、
  緊跟著檔名；每一列的「展開」念得出是哪一件、命中區 24px；段標題的計數念成「2 件」；刪除結果那一句所在的
  live region 一直掛著；`/issues` 進頁時不再問兩次清單。
- 輪過、但一次都沒讀到的搜尋 Feed（連不上、請求預算用完）第一輪仍能選「全部下載」——下一次讀到時整份歷史照送。現在要至少讀到過一次（`feed_unread`），畫面說出上一次為什麼沒讀到。
- 重複版本「取代舊版」先比 inode：目標上是使用者換進去的檔案時拒絕（`target_taken`），不再蓋掉它。
- 套件內 Jellyfin 靠泊之後重跑偵測不再被判成既有服務。
- 第一輪預覽的計數在窄版英文撐出橫向捲動；「只追之後的」送出中不再 `disabled`（焦點會掉回頁首）；淺色主題錯誤狀態的輸入框邊框對比不足 3:1；刪掉精靈的一個媒體庫之後焦點落到下一列。
- **大批送單時 pre-plan 爆 `database is locked`**（M4 票 01）：poller 握著 SQLite 寫交易逐筆等 Job 的鎖、
  planner 握著鎖等寫鎖，planner 等滿 5 秒就放棄。poller 改成先把 qBittorrent 問完、再把這一輪的鎖照 hash 拿齊、
  最後一個交易寫完；RSS 的單集頁與補舊集、刪除時移除 torrent、重試與重新送單也都不再握著寫交易打網路
  （plan §3.3 的寫交易紀律）。
- **處理某一筆時爆掉之後，下一輪成功了錯誤就不再掛著**（M4 票 01）：原本只有狀態轉換會清 `Job.error`，
  pre-plan 算完之後那一筆還在下載，錯誤一直留在畫面上。現在下一次成功的一輪清掉它，時間線多一筆「已接回」
  （`recovered`，`from = round_failed`）。
- **RSS 自動綁定一次讀不到就永遠待綁定**（M4 票 14）：TMDB 或 Mikan 番組頁暫時讀不到（連不上、逾時、429、5xx）
  時改成 1、4、12 小時後再認，最多認四次，用完才落到「查不到」等人；待綁定那一列說出下一次在什麼時候。搜到的
  幾部裡一部讀不到不再讓整次作廢。服務回 429 或 5xx（503 以外）時錯誤從「不像那個服務」改歸「連不上」，精靈的
  偵測與一次性 RSS 連結的理由也跟著變成「連不上」。
- **發佈名帶季名的作品認不出來**（M4 票 14）：「Re：从零开始的异世界生活 第四季」這種名字原樣去搜 TMDB 搜不到。
  季名（`第N季`、`Season N`、`Nth Season`、`SN`）從搜尋詞拆掉、改當線索：只在 Mikan 寫的開播日落在 TMDB 那一季
  播出的期間時才自動綁定（TMDB 把幾季併成一季時看依播出日切出的那一輪）。
- **剛加的 Feed 按「立即輪詢」偶爾留下一句 `IntegrityError`**（M4 票 11 收尾）：背景 poller 同時挑到這個從沒輪過的
  Feed，兩輪各長一次同一個 RSS Series、後到的撞 unique，錯誤留在 Feed 的 `last_error`。同一個 Feed 現在一次只輪一輪。
- **一次送一百多個時磁碟門檻擋不住**（M4 票 03）：送單前的磁碟門檻只看剩多少，每一個送單當下都過得去，磁碟要到
  下載途中才滿。現在扣掉已送出、還沒下完的量（qBittorrent 報得出之前用索引站與 RSS 報的大小），擋下時說出在途多少。
- **暫時送不出去的那一筆要人逐筆按重試**（M4 票 03）：qBittorrent 逾時、停機、`.torrent` 那一站 5xx 時，送單失敗
  改成 1 分鐘、10 分鐘、1 小時、6 小時後自動再送，最多送五次，用完才停下等人；qBittorrent 停機的那段時間不花次數，
  服務回來的那一輪就接上。時間線說出第幾次、幾時再送。重啟時被打斷的送單也照這個規則自動再送。
- **使用者自己的 Prowlarr / qBittorrent 被當成套件內、登入被覆寫**（M4 票 05）：精靈第 2 步對使用者填的位址也用
  「沒有索引站」「免密可進」判套件內，第 6 步就以第 1 步的帳密改掉那台 Prowlarr 的登入並讓它重啟，第 4 步對免密的
  舊 qBittorrent 同樣會設 WebUI 密碼；套件內 Prowlarr 連不上時在索引站那一步改填自己的 Prowlarr 也是同一條路。
  現在只有 compose 主機名上探到的才可能是套件內，使用者填的位址一律是既有
  （Jellyfin 例外：沒跑過初始精靈的那一台上沒有任何人的帳號）。**已經被判錯的安裝沒有自動修正**：曾把自己的
  Prowlarr 或 qBittorrent 接進 Berth、而它當時被判成套件內的人，請在那個服務自己的介面確認登入帳密還是你設的
  那一組、qBittorrent 的預設下載路徑還是原本那一條。
- **既有 qBittorrent 的全域下載路徑被改成 Berth 的目錄**（M4 票 05）：第 4 步對使用者自己的 qBittorrent 也寫
  `save_path`、`temp_path` 等五個全域鍵，之後不經 Berth 加的 torrent 全部落進 Berth 的目錄。現在既有的那一台
  一個鍵都不寫，第 4 步只列現值與建議值、確認連得上；Berth 的下載照舊走自己的 `berth-*` 分類與逐個 torrent 的
  自動管理。Route 檢查的「下載路徑」對既有 qBittorrent 只看分類回報的路徑，健康頁不再把它的全域偏好報成漂移。
  **已經被改過的不會自動改回**：接過自己的 qBittorrent、在精靈第 4 步按過「套用」的人，請在 qBittorrent 的
  「選項 → 下載」把預設儲存路徑與未完成目錄改回你原本的設定。

### Security

- **`POST /api/setup/owner` 不再重建擁有者**（M4 票 18）：成立之後連登入中的管理員再打這一支都是 409
  `owner_exists`，原本任何一位管理員都能換掉擁有者。換 API key 的重新登入是 `POST /api/setup/jellyfin/connect`，
  不受影響。
- **Berth 寫進套件內 qBittorrent / Prowlarr 的介面密碼只存加鹽雜湊**（M4 票 15，brief §19 2026-09-29 ⑤）：勾了
  「沿用 Jellyfin 帳密」時那就是擁有者的 Jellyfin 密碼，照票 07 存明文會推翻「資料庫裡沒有擁有者的明文密碼」。
  雜湊只拿來比對「已經是這一組」；Berth 連套件內 qBittorrent 靠免密白名單，那一台的連線帳密因此是空的。
  migration `f3c9a1d6b2e8` 把票 07 存下的明文（套件內那一台的 `settings.services.qbittorrent` 帳密、
  `settings.setup.indexer.web_ui_password`）換成雜湊；既有 qBittorrent 的帳密是 Berth 的連線憑證，照舊存。

- **精靈在擁有者成立之前只開兩件事**（M4 票 06）：找到 Jellyfin、成為擁有者。其餘精靈端點（建立、套用、加站、
  讀別人的服務）一律 403，成立之後整組要管理員的 session。誰先到誰建立，與 Jellyfin 自己的啟動精靈相同。
- **媒體庫瀏覽由 Berth 自己擋 Jellyfin 的權限**（M1.5 票 03，plan §11.2b）。伺服器 API key 帶 `parentId` 替使用者查時
  Jellyfin 不套媒體庫權限、停用的帳號照樣代讀得到（12.1.0 實測），所以：Jellyfin 的使用者 id 只從 session 來；
  媒體庫 id 對 `GET /UserViews` 的允許清單驗過才會送出，不在清單回 404 且不問 Jellyfin；允許清單與帳號 `Policy`
  共用 60 秒快取；帳號在 Jellyfin 被停用時，他在 Berth 的每一張 session 都結束，下一個請求是 401。
- **類型與年份清單同樣先驗媒體庫**（M1.5 票 06）：Jellyfin 的 `/Items/Filters` 帶 `parentId` 時不套權限，連使用者自己的
  token 都照回（12.1.0 實測），不擋就會透出沒有權限的媒體庫有哪些類型與年份。不在允許清單回 404 且不問 Jellyfin；
  排序鍵不在這種媒體庫的選單上也在問 Jellyfin 之前拒絕，連同時送出的整份清單那一支都不送。
- **繼續觀看與下一集照樣只給你看得到的**（M1.5 票 07）：Jellyfin 的 Resume 與 NextUp 帶 `parentId` 時不套媒體庫權限、
  連使用者自己的 token 都照回（12.1.0 實測），所以首頁那一支一律不帶；媒體庫頁那一支先對允許清單驗過，不在清單回 404
  且不問 Jellyfin。
- **`/api/routes/*` 與 `/api/jellyfin/libraries` 永遠只有 admin**（票 14a，推翻票 14）。原本精靈跑完之前
  它們與 `/api/setup/*` 一樣匿名開放，而停用的 Route 不算進完成條件，所以那一刻任何人都能把紅燈 Route
  停用、再按完成。精靈第 7 步的刪除改走 `DELETE /api/setup/routes/{id}`（同一個命令、同一種拒絕）。

[Unreleased]: https://github.com/1morr/Berth/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/1morr/Berth/releases/tag/v0.2.1
[0.2.0]: https://github.com/1morr/Berth/releases/tag/v0.2.0
[0.1.0]: https://github.com/1morr/Berth/releases/tag/v0.1.0
