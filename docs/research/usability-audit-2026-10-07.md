# Berth 第四輪可用性審計：精靈與整體（2026-10-07）

範圍：main `107708c`（票 32–54 之後）。只審計、不改程式；改進拆票等使用者拍板。
截圖在 [`usability-audit-2026-10-07/`](usability-audit-2026-10-07/)，檔名前綴 `s1`–`s5` 對應下面的情境編號。
上一輪是 [`wizard-audit-2026-10-06.md`](wizard-audit-2026-10-06.md)（下稱「上一輪」）。這一輪沒有變的事只引用、不重寫。
各情境的原始筆記與兩份蒐證在 [`usability-audit-2026-10-07/notes/`](usability-audit-2026-10-07/notes/)：「R1」指 [`r1-code-evidence.md`](usability-audit-2026-10-07/notes/r1-code-evidence.md)（讀碼：接管表、目錄樹、功能現況、票的遺留），「R2」指 [`r2-docs-and-research.md`](usability-audit-2026-10-07/notes/r2-docs-and-research.md)（README 紙上走查、成熟產品對照，附出處）。

## 1. 結論先講

1. **套件內那一條已經接近你要的「按下去就能繼續」**：S1 全程密碼只打 2 次（建立 Jellyfin 管理員時），頁 2、頁 4 不用輸入，頁 3 進頁自己跑（約 20 秒、逐條顯示），頁 4 一顆鍵加 6 站。從送單到 Jellyfin 看得到約 16 分鐘，中間不用人動手（§3 S1）。
2. **既有服務只靠畫面就能接得進來**（S2）：
   - localhost、版本太舊、非管理員、帳密錯、沒掛 `/data` 五類錯誤，每一種畫面都說了原因和下一步，照著補法做就轉綠。
   - Berth 在你的服務上只留下它自己的物件，外加一筆 Jellyfin 裝置紀錄。
   - 混搭（既有 Jellyfin＋套件內 qBittorrent 與 Prowlarr）也一路走到入庫，被你的 Jellyfin 認到（S3）。
   - 剩下的卡點都在「離開 Berth 去改 compose」那一步：補法裡的 `${DATA_ROOT}` 要自己換成絕對路徑。
3. **上一輪說「還不能交給一般使用者」的四條，解了兩條半**：image 有了但落後 15 個 commit（`:latest` = 0.1.0，不含票 43–54）；P0-1 與 README 混用指示已修；原生 Linux / NAS 仍沒有人跑過（票 42 `needs-info`）。
4. **這一輪的新問題集中在「之後」**，也就是精靈完成後的改選、移除、重裝。精靈本身已經不是主要問題：
   - 換一台 qBittorrent 之後，健康頁還寫「已繫上」，三條 Route 卻都是「尚未檢查」。
   - 停用 Prowlarr 沒有出口，健康頁會一直紅。
   - 重裝之後帳本是空的，畫面不提 `rebuild-ledger`。
   - Berth 沒有任何卸載或清理的入口。（§3 S4）
5. **你的理想流程與 D1 的衝突比想像中小**。既有服務真正需要手動做的只有掛載，而掛載本來就沒有任何 API 改得到；Berth 也不需要任何全域設定。實際衝突只有兩點（§5）：
   - 既有 Jellyfin 沒有對應類型的媒體庫時，要不要由 Berth 建一個新的。
   - Berth 會觸發整台 Jellyfin 的「掃描所有媒體庫」。這是 D1 清單外的寫入，文件和閘門都沒列。
6. **README 是新使用者最大的障礙**：
   - 沒說 `deploy/` 從哪裡拿。只抓一個 compose 檔不夠，缺了 `preseed/` 套件內 qBittorrent 進不去。
   - 預設三個 profile 全開，已經有服務的人在看到精靈之前就會撞 port。
   - 第一部片入庫前的必讀約 2,000 字、35 個名詞，其中只有 8 個必須懂（§7）。
7. **能不能投入使用**：
   - **你自己用**：如果你的機器是 Windows Docker Desktop，可以開始用。若是 Linux / NAS，先跑票 42。
   - **一般自架使用者**：還不行。卡在取得檔案、Linux / NAS 未驗證、image 落後、撤回與重裝沒有出口（§6.3）。

## 2. 需要你拍板的決定

**2026-10-08 已拍板：E1–E7 照下表的建議，E8 由使用者提供 VMware Workstation 上的 Linux VM**（記在 brief §19「第四輪可用性審計的八項」）。下表保留當時的選項與理由。

| # | 問題 | 選項 | 建議 | 理由 |
| --- | --- | --- | --- | --- |
| **E1** | 既有 Jellyfin 沒有對應類型的媒體庫（例如只有劇集、要下載電影）時怎麼辦？現在：Berth 不建，卡片叫你先去 Jellyfin 建 | (a) 維持；(b) 頁 3 多一列「在你的 Jellyfin 新建一個媒體庫（Berth 建、名字可改）」，要勾才建；(c) 自動建 | **(b)** | 新建的媒體庫是獨立的新物件，刪掉它不動你原有的東西，屬於 D1「Berth 擁有的物件」那一級（L1，§5.2）。這是理想流程與 D1 唯一實際衝突的地方，(b) 兩邊都滿足。代價：伺服器上其他使用者會看到一個新媒體庫，所以要勾選，不要自動 |
| **E2** | Berth 會請 Jellyfin 跑「掃描媒體庫」排程任務，那是整台伺服器所有媒體庫一起掃。觸發點：同一批反查兩次沒找到，或 Issue 的「重新掃描」鍵（`berth/services/resolver.py:547-549`、`issues.py:563`）。這件事不在 D1 物件表，也不在白名單閘門裡 | (a) 改成只刷新 Berth 寫入的那個媒體庫；(b) 維持，寫進 brief §16.4 與既有服務的卡片；(c) 既有 Jellyfin 不觸發，只靠路徑通知 | **(a)**，做不到就 (b) | 既有 Jellyfin 的媒體庫可能很大，全庫掃描會吃掉 NAS 的 I/O。Jellyfin 是否有可用的單一媒體庫刷新端點**未查證**，拆票時要先查 OpenAPI。不管選哪個，D1 的清單都要補上這一項 |
| **E3** | 不想用 Prowlarr（或之後移除）時怎麼辦？現在：精靈有「之後再說」，完成後沒有出口，健康頁永遠紅、修正只教你把它起回來 | (a) 設定 → Prowlarr 加「不用 Prowlarr」，健康不再檢查、搜尋說明改走 RSS；(b) 維持 | **(a)** | Seerr 的 Radarr / Sonarr 是可以不加的，HA 的整合也是之後才加（R2 §2.7-6）。Berth 沒有索引站也能靠 RSS 運作，Prowlarr 不是必要條件 |
| **E4** | 部署檔怎麼交給使用者 | (a) release 附件：一個 zip，含 compose、`.env.example`、`preseed/`，照 Immich 的做法；(b) preseed 腳本用 compose 的 `configs.content` 內嵌，只剩一個 compose 檔（需要 Compose ≥ 2.23.1）；(c) 叫人 `git clone` | **(a)** | (b) 最接近 Jellyfin / Seerr 的「抓一個檔」，但 NAS 內建的 Compose 版本沒有查證過，有風險。(a) 沒有版本下限，也和 README 的升級步驟（「換那一版的 compose 範本」）一致 |
| **E5** | 什麼時候發 0.2.0 | (a) 現在發，含票 43–54；(b) 先修本報告的 P0 / P1 再發 | **(a)** | README 與 brief 描述的已經是 main 的行為，照 README 拉 `:latest` 卻看到舊精靈：密碼打 4 次、頁 3 要自己按、錯的 TMDB key 會被存下（S1 環境段）。43–54 都有實跑，發了只會更一致 |
| **E6** | 重裝或 DB 遺失之後怎麼把帳本找回來 | (a) Berth 偵測到媒體庫裡有它不認得的檔案時，在待處理或完成頁給一顆「從媒體庫重建帳本」（就是 `rebuild-ledger`，它只加不刪、冪等）；(b) 維持 CLI，只在 README 寫 | **(a)** | S4 重裝後的作品頁同時寫「在 Jellyfin 看」和「還沒有任何檔案入庫」，使用者很可能重複下載。目前唯一的提示是一件「無主 torrent」，按鈕也沒說按下去會做什麼 |
| **E7** | README 要不要大改 | (a) 安裝頁只留必讀（約 1,000–1,400 字），其餘搬到 `docs/`；(b) 只修不一致 | **(a)** | 四個對照產品的安裝頁都是「拿檔案 → 改 2–4 個值 → `up -d` → 連到下一頁」（R2 §1.6）。這屬於文件結構變更，按全域規則要先問 |
| **E8** | 原生 Linux / NAS 實跑（票 42）由誰提供機器 | — | 你有沒有一台可以用？沒有的話，我建議開一台 Linux VM（不是 Docker Desktop 的 VM）跑 S1 與 S2 | 一般使用者的主要客群是 NAS，這條沒跑過，結論就只能停在「未驗證」 |

## 3. 情境結果

環境：Windows 11 + Docker Desktop。Berth image 是本機用 `107708c` build 的 `berth:audit-107708c`；GHCR 的 0.1.0 不含票 43–54，所以沒用它跑。另外驗了一次 `docker pull ghcr.io/1morr/berth:latest`，拉得到，revision 是 `6bc4c1d`（0.1.0）。所有測試環境都在 repo 外（§9），沒有碰你實際在用的服務。

### S1 全新、全部選套件內

`docker compose up -d` 之後約 32 秒四個容器 healthy。

| 頁 | 使用者要做的 | 輸入 | 必按 | 機器做的 / 等待 | 截圖 |
| --- | --- | --- | --- | --- | --- |
| 1 Jellyfin | 選「套件內」→ 帳號、密碼兩次（「套件內 qBittorrent 與 Prowlarr 的介面也用這組」預設勾著）→ 建立 → 下一步 | 3 | 3 | 約 1.5 秒：初始設定、建管理員、API key「Berth」、伺服器名「Berth」 | [s1-01](usability-audit-2026-10-07/s1-01-page1-initial.jpeg)、[s1-02](usability-audit-2026-10-07/s1-02-page1-bundled-filled.jpeg)、[s1-03](usability-audit-2026-10-07/s1-03-page1-done.jpeg) |
| 2 qBittorrent | 選「套件內」→ 下一步 | 0 | 2 | 約 3 秒：連線、`/data` 探針、沿用頁 1 的密碼設 WebUI 登入 | [s1-05](usability-audit-2026-10-07/s1-05-page2-bundled-result.jpeg) |
| 3 媒體庫路徑 | 下一步 | 0 | 1 | 進頁自己跑約 20 秒：建 3 個媒體庫、3 個 `berth-*` 分類、3 條 Route 各 6/6，逐條「等待中 → 進行中」 | [s1-06](usability-audit-2026-10-07/s1-06-page3-done.jpeg) |
| 4 Prowlarr | 選「套件內」→「測試推薦站，加入通過的」→ 下一步 | 0 | 3 | 約 10 秒：加入 6 站，3 站沒通過（Nyaa 連不上；1337x、EZTV 被 Cloudflare 擋），逐站說原因；介面登入自動沿用 | [s1-09](usability-audit-2026-10-07/s1-09-page4-recommended-done.jpeg) |
| 5 TMDB | 貼 key → 測試 → 下一步 | 1 | 2 | 錯的 key：「TMDB 不接受這把 key」，重新載入後仍是「還沒填」，**沒有存下** | [s1-11](usability-audit-2026-10-07/s1-11-page5-wrong-key.jpeg)、[s1-12](usability-audit-2026-10-07/s1-12-page5-verified.jpeg) |
| 6 完成 | 完成設定 | 0 | 1 | 列出三個服務的網址與帳號，直接進探索頁、已登入 | [s1-13](usability-audit-2026-10-07/s1-13-page6-complete.jpeg) |
| **合計** | | **4（密碼 2 次）** | **12** | | 上一輪：密碼 4 次、必按 11 顆以上 |

服務端前後比對（API 讀出）：
- 套件內 qBittorrent 的 `save_path`、`temp_path`、`auto_tmm_enabled` 全程不變，只有 WebUI 帳號從 `admin` 變成擁有者（票 32 ✔）。
- Jellyfin 伺服器名從容器 ID 變成「Berth」（票 52 ✔）。

第一部片：《Night of the Living Dead》(1968)，公有領域，YTS 720p。
- 搜尋約 12 秒：列 37 筆；另有 107 筆名字對不上已略過、74 筆年份或類型對不上已收起來（票 49 ✔，[s1-16](usability-audit-2026-10-07/s1-16-search-results.jpeg)）。
- 只有一條 Movies Route，自動帶入；確認框印出資料夾名（[s1-17](usability-audit-2026-10-07/s1-17-send-confirm.jpeg)）。
- 21:45:56 送單 → 21:59:07 自動入庫（硬鏈接，link count 2）→ 約 22:02 Jellyfin 認到（TMDB 10331），共約 16 分鐘（[s1-19](usability-audit-2026-10-07/s1-19-jobs-downloading.jpeg)、[s1-21](usability-audit-2026-10-07/s1-21-title-imported.jpeg)、[s1-22](usability-audit-2026-10-07/s1-22-jobs-imported.jpeg)）。
- 健康頁三條 Route 各 6/6（票 50，[s1-20](usability-audit-2026-10-07/s1-20-health.jpeg)）。
- **入庫後 2 分 35 秒，Berth 才請 Jellyfin 掃描**；這段時間作品頁寫「Jellyfin 還在掃描」。原因是 Jellyfin 對從沒掃到過內容的空媒體庫，收到路徑通知不會有反應（brief §20.1）。Berth 要等兩次反查都沒找到，才改請整庫掃描（`resolver.py:68-71`）。這是已知設計，但空媒體庫的第一次入庫一定會碰到，而且那句「還在掃描」與事實不符（P1-9）。

### S2 全部既有，先錯後對

環境：
- 使用者自己的服務 `mine3-*` 照 linuxserver 文件的典型掛法：Jellyfin 掛 `/tv`、`/movies`，qBittorrent 掛 `/downloads`，**一開始都沒有 `/data`**。
- Berth 用官方 compose 的副本，`COMPOSE_PROFILES=` 留空。官方 compose 寫死 `name: berth`、`container_name: berth`、網路名與子網，同一台主機不能並存兩套，所以只改了這幾行（P2-14）。

| 頁 | 錯誤 | 畫面說了什麼（節錄原文） | 標在哪 | 只靠畫面修得好？ | 截圖 |
| --- | --- | --- | --- | --- | --- |
| 1 | 位址填 `localhost` | 「Berth 在容器裡，這個位址指的是 Berth 自己…改填 host.docker.internal…或它的區網 IP」＋「這一組沒有存下：測得過才存」 | 位址欄 | 可；但同一段話出現兩次（黃色提示＋紅色錯誤） | [s2-02](usability-audit-2026-10-07/s2-02-p1a-localhost.jpeg) |
| 1 | Jellyfin 10.10.7 | 「至少要 Jellyfin 12.0，這一台是 10.10.7；等也不會好。升級之後再測一次。」 | 表單下 | 可（要升級） | [s2-03](usability-audit-2026-10-07/s2-03-p1b-old-version.jpeg) |
| 1 | 非管理員 | 「這個帳號登得進 Jellyfin，但不是管理員…用這台 Jellyfin 的管理員登入。」 | 表單下，欄位沒標 | 可 | [s2-06](usability-audit-2026-10-07/s2-06-p1c-non-admin.jpeg) |
| 1 | 密碼錯 | 「Jellyfin 不認這組帳號或密碼。」 | 表單下，欄位沒標 | 可 | [s2-05](usability-audit-2026-10-07/s2-05-p1d-wrong-password.jpeg) |
| 2 | 位址填 `localhost` | 同頁 1 | 位址欄 | 可 | [s2-08](usability-audit-2026-10-07/s2-08-p2a-localhost.jpeg) |
| 2 | qBittorrent 4.3.9 | 「至少要 qBittorrent 4.4，這一台是 v4.3.9；等也不會好。」 | 表單下 | 可（要升級） | [s2-09](usability-audit-2026-10-07/s2-09-p2b-old-version.jpeg) |
| 2 | 密碼錯（只錯一次） | 「帳號或密碼不對。改好上面的欄位再測一次。」 | 帳號、密碼兩欄 | 可 | [s2-10](usability-audit-2026-10-07/s2-10-p2c-wrong-password.jpeg) |
| 2 | **沒掛 `/data`** | 「你的 qBittorrent 看不到 /data…在你原本那一份 compose（或 docker run 指令）的 qBittorrent 上多加一條掛載…原本的掛載不用動：/downloads 留著…」＋ compose 與 `docker run -v` 兩段片段 | 表單下 | **大致可**：片段是 `${DATA_ROOT}:/data`，要自己去 Berth 的 `.env` 找值。預設 `./data` 是相對路徑，貼進另一份 compose 會指到別的目錄；Windows 路徑在 YAML 裡怎麼寫也沒說 | [s2-11](usability-audit-2026-10-07/s2-11-p2d-no-data-mount.jpeg)、[s2-12](usability-audit-2026-10-07/s2-12-p2-after-fix.jpeg) |
| 3 | **Jellyfin 沒掛 `/data`** | 每個媒體庫各一則：「Jellyfin 看不到 /data/library/節目：它沒掛 /data…這一次建的目錄已經收回…多加一條掛載…」 | 每個媒體庫卡片 | 大致可；缺口同上。而且兩個媒體庫各重複一整段補法加兩段片段，其實是整台 Jellyfin 的問題 | [s2-15](usability-audit-2026-10-07/s2-15-p3-jellyfin-no-data.jpeg)、[s2-16](usability-audit-2026-10-07/s2-16-p3-after-fix.jpeg) |
| 4 | Prowlarr 1.0.1 | 「至少要 Prowlarr 1.3.2，這一台是 1.0.1.2220」 | 表單下 | 可 | [s2-17](usability-audit-2026-10-07/s2-17-p4a-old-version.jpeg) |
| 4 | API key 錯 | 「API key 不對：在 Prowlarr 的「設定 → 一般」複製 API key（不是介面登入的密碼）」 | key 欄 | 可（上一輪右欄寫錯的問題已修，票 39） | [s2-18](usability-audit-2026-10-07/s2-18-p4b-wrong-key.jpeg) |

修法實測：照畫面在原本那份 compose 加 `- C:/Users/Roxy/berth-audit3/data:/data`，`docker compose up -d <服務>` 重建，回畫面再按一次就轉綠，欄位不用重填（每個約 4 步）。失敗時不留東西：沒有探針 torrent、沒建分類，`/data` 是空的。

Berth 實際在你的服務上改了什麼（before / after diff）：

| 服務 | 前 | 後 |
| --- | --- | --- |
| Jellyfin | 媒體庫「節目」`[/tv]`、「電影」`[/movies]`；沒有 API key | 多 API key「Berth」（頁 1 登入成功就建了）；「節目」`[/data/library/節目, /tv]`、「電影」`[/data/library/電影, /movies]`。使用者、`/System/Configuration` 不變 |
| qBittorrent | `save_path=/downloads`；沒有分類 | 多 `berth-節目`、`berth-電影`；偏好、tag、帳密全部不變；沒有殘留 torrent |
| Prowlarr | 1 站（YTS） | 多 1 站（我勾的 The Pirate Bay）；YTS 與登入不變 |
| `DATA_ROOT` | 空 | 6 個空目錄：`library/{節目,電影}`、`torrent/{complete,incomplete}/{節目,電影}` |

必要操作合計：打字 9 次、必按約 16 次，另外為了修掛載離開 Berth 兩次。

### S3 混搭（既有 Jellyfin＋套件內 qBittorrent 與 Prowlarr）

brief §16.3 說這是 NAS 使用者最常見的組合。做法：
1. 把 S1 那一套重裝：搬走 `config/berth`，保留服務的 config。
2. 照 README 改 `COMPOSE_PROFILES=qbittorrent,prowlarr`，`up -d` 之後再 `docker compose stop jellyfin`。
3. 既有 Jellyfin 是 `s3-jellyfin`：媒體庫「我的電影」`/movies`、「我的劇集」`/tv`，一開始沒掛 `/data`。

| 頁 | 看到什麼 | 問題 | 截圖 |
| --- | --- | --- | --- |
| 1 既有 Jellyfin | 點「既有」立刻給兩行可複製指令，而且已經照所有選擇算好：`COMPOSE_PROFILES=qbittorrent,prowlarr`、`docker compose stop jellyfin`。登入成為擁有者 | 這段提示在成為擁有者之後就消失，完成頁也不再提醒套件內 Jellyfin 還在跑；沒說在哪個目錄執行。右欄寫「不改這台 Jellyfin 的任何設定」，下一行卻是「建立 API key『Berth』」，頁 3 還會加路徑。密碼欄空著按登入，得到的是「Berth 不收沒有密碼的 Jellyfin 帳號當擁有者」（把原因說成帳號沒設密碼） | [s3-01](usability-audit-2026-10-07/s3-01-page1-initial.jpeg)、[s3-02](usability-audit-2026-10-07/s3-02-page1-existing-done.jpeg) |
| 2 套件內 qBittorrent | 沒問密碼，介面登入「已經是這樣」 | 那一組是上一位擁有者（S1 的帳號）設的，和這一輪的擁有者不同；完成頁寫「密碼是這一台原本就有的那一組」，沒說忘了怎麼辦 | [s3-03](usability-audit-2026-10-07/s3-03-page2-bundled-already.jpeg) |
| 3 媒體庫路徑 | 預設寫入目標「新的 Berth 路徑」`/data/library/我的電影`，不動 `/movies`。第一次「建立並檢查」紅：Jellyfin 沒掛 `/data`，並說明這一次建的目錄已經收回。照補法加掛載、重建之後 6/6 | 同 S2：`${DATA_ROOT}` 的值要自己找、相對路徑（P1-6）。路徑名來自媒體庫名，所以和 S1 的 `library/movies` 不撞；但 S1 入庫的那部片在這台 Jellyfin 看不到（另一個媒體庫） | [s3-04](usability-audit-2026-10-07/s3-04-page3-movies-checked.jpeg)、[s3-05](usability-audit-2026-10-07/s3-05-page3-jellyfin-no-data.jpeg)、[s3-07](usability-audit-2026-10-07/s3-07-page3-both-green.jpeg) |
| 4 套件內 Prowlarr | 3 秒連上，6 站已經在 | 右欄還沒選就寫「你自己的 Prowlarr」（P2-1）；推薦站區只剩一顆「之後再說」，沒說明為什麼 | [s3-08](usability-audit-2026-10-07/s3-08-page4-bundled-already.jpeg) |
| 5、6 | TMDB 驗過；完成頁的 Jellyfin 網址是 `http://localhost:46096`（從 `host.docker.internal` 換成瀏覽器打得開的位址） | — | [s3-09](usability-audit-2026-10-07/s3-09-page5-tmdb-verified.jpeg)、[s3-10](usability-audit-2026-10-07/s3-10-page6-complete.jpeg) |
| 完成後的健康頁 | **四個泊位都是「尚未檢查」、「上次檢查 沒有紀錄」**，要按「立即重測」才變綠；另有一件「無主 torrent」，是 S1 那部，重裝後被當成無主（說明合理） | P2-17 | — |

合計：點擊約 20 次、輸入 4 次（位址、帳號、密碼、TMDB key），另外為了掛載離開 Berth 一次。

下載：《Nosferatu》(1922)，公有領域，YTS 720p，746 MB。
- 探索頁搜「Nosferatu 1922」是 0 筆（TMDB 搜尋不吃年份），搜「Nosferatu」，1922 版排第 2（P2-18）。
- 作品頁搜尋約 60 秒。結果寫「共 262 筆 · 逐站取了 100 筆」、「103 筆已略過」、「164 筆已經收起來」，數字彼此對不上；主表還混進同名動畫《Tsuki to Laika to Nosferatu》的各集與成人內容（P2-19）。
- 送單時下拉只列電影類型的 Route，自動選了「我的電影」（[s3-13](usability-audit-2026-10-07/s3-13-send-confirm.jpeg)）。
- 14:53:58 送單 → 15:01:19 入庫（硬鏈接）→ 15:03:57 既有 Jellyfin 認到。Berth 在 15:03:55 才請 Jellyfin 掃描，和 S1 一樣晚了約 2.5 分鐘，期間作品頁寫「Jellyfin 還在掃描」。這個媒體庫的舊路徑 `/movies` 當時是空的，所以碰到的是同一個機制（P1-9，[s3-15](usability-audit-2026-10-07/s3-15-title-imported-scanning.jpeg)、[s3-16](usability-audit-2026-10-07/s3-16-title-jellyfin-found.jpeg)）。

新舊內容並存：
- 子代理另外把一部片直接放進 `/movies`（不經 Berth），模擬原本就有的收藏。
- Jellyfin 的「我的電影」兩部並列，看不出來源（[s3-20](usability-audit-2026-10-07/s3-20-jellyfin-movies-library.jpeg)）。
- Berth 的媒體庫頁兩部都在牆上，只有 Berth 入庫的那部有「已入庫」徽章（[s3-18](usability-audit-2026-10-07/s3-18-berth-library-movies-with-existing.jpeg)）。
- 這正是 M1.5「整個媒體庫，不只 Berth 經手的」的設計。

Berth 在你的 Jellyfin 上改了什麼（before / after）：
- 多一把 API key「Berth」（登入成功當下建立）。
- `/Devices` 多一筆 Berth（AppName Berth）：R1 推論的登入裝置紀錄，這裡**實跑確認**。
- 兩個媒體庫各多一條 `/data/library/<名>`，排在第一位，原本的 `/movies`、`/tv` 不動。
- 使用者沒有增加；精靈本身不觸發掃描，要到第一次入庫後的反查才觸發（E2）。

### S4 撤回：改選、移除一個服務、重跑精靈

| 動作 | 看到什麼 | 問題 | 截圖 |
| --- | --- | --- | --- |
| 完成後打開 `/setup` | 靜默導向 `/settings/jellyfin`，沒有任何說明；設定頁五頁各自說明能改什麼、不能改什麼（Jellyfin 的來源鎖住，並說明原因） | 想「重跑精靈」的人不知道要搬走 DB；沒有文件寫這件事 | [s4-01](usability-audit-2026-10-07/s4-01-settings-jellyfin.jpeg)–[s4-05](usability-audit-2026-10-07/s4-05-settings-tmdb.jpeg) |
| qBittorrent 套件內 → 既有 | 一點「既有」就出現換台框，列出舊那台的 `berth-anime`「空的」、`berth-movies`「1 個 torrent」、`berth-tv`「空的」，以及「Berth 設的介面登入」。「移除 2 個空的 berth- 分類」有效，有 torrent 的不碰 | 移除鍵在確認換台**之前**就生效；白名單沒列 | [s4-06](usability-audit-2026-10-07/s4-06-qbt-existing-selected.jpeg)、[s4-07](usability-audit-2026-10-07/s4-07-qbt-removed-empty-categories.jpeg) |
| 換台之後 | 健康頁 BTH 3「**已繫上** 3 條 Route」，三條 Route 卻都是「**尚未檢查**」；新那台 0 個分類。要到「媒體庫路徑」逐條展開、按「重新檢查」（6 次點擊）才建分類 | 綠燈說錯；沒有「全部重新檢查」；換台成功的畫面沒指路 | [s4-09](usability-audit-2026-10-07/s4-09-health-after-qbt-switch.jpeg)、[s4-12](usability-audit-2026-10-07/s4-12-routes-after-qbt-switch.jpeg) |
| 做種中的那部電影 | 留在舊那台，Berth 不再追蹤，也沒有任何提示；Job 仍是「已入庫」，時間線不變 | 換台框只寫「1 個 torrent」，沒說之後會怎樣 | [s4-10](usability-audit-2026-10-07/s4-10-jobs-after-qbt-switch.jpeg)、[s4-11](usability-audit-2026-10-07/s4-11-job-detail-after-qbt-switch.jpeg) |
| 換回套件內 | 4 次點擊、不用密碼；缺的分類自動重建、介面登入還記著。健康頁 Route 是 **5/6**（「qBittorrent 讀得到 Berth 寫的檔案　尚未執行」），標題卻是「已繫上」 | 上一輪 #11 的另一個入口：票 50 只處理了「沿用上一次結論」，從沒問過的那一條仍是「尚未執行」卻算綠 | [s4-17](usability-audit-2026-10-07/s4-17-qbt-back-to-bundled-done.jpeg)、[s4-18](usability-audit-2026-10-07/s4-18-health-after-switch-back.jpeg) |
| 移除 Prowlarr（照 README：拿掉 profile、`up -d`、`stop prowlarr`） | 健康頁 BTH 4「阻擋」，修正只教你 `docker compose up -d prowlarr`；設定頁同時出現綠色「連線測試通過」（舊的）與紅色「讀不到站清單」；作品頁搜尋露出原始字串 `GET /api/v1/indexer: host does not resolve` | 沒有「不用 Prowlarr」（E3）；恢復後要等下一輪 5 分鐘 | [s4-19](usability-audit-2026-10-07/s4-19-health-prowlarr-stopped.jpeg)、[s4-20](usability-audit-2026-10-07/s4-20-settings-prowlarr-stopped.jpeg)、[s4-21](usability-audit-2026-10-07/s4-21-title-search-prowlarr-stopped.jpeg) |
| 重裝（搬走 `config/berth`、保留服務 config） | 約 14 次互動、密碼 1 次。頁 1 變「用你的 Jellyfin 管理員登入」，頁 2、4 的登入是「已經是這樣」，頁 3 要自己按。**冪等**：API key 1 把、媒體庫 3 個、分類 3 個、站 6 個，都沒有重複 | TMDB key 要重貼、Job 歷史全空，事前沒有預警 | [s4-22](usability-audit-2026-10-07/s4-22-rerun-page1-initial.jpeg)–[s4-31](usability-audit-2026-10-07/s4-31-rerun-page6-complete.jpeg) |
| 重裝之後那部電影 | 媒體庫頁看得到（資料來自 Jellyfin）；作品頁同時有「在 Jellyfin 看」和「**還沒有任何檔案入庫**」；下載頁是空的；待處理多一件「無主 torrent」，按鈕「認領並建立下載」沒說會做什麼；完成頁寫「跳過：沒有」。畫面沒有提 `rebuild-ledger` | E6 | [s4-32](usability-audit-2026-10-07/s4-32-jobs-after-reinstall.jpeg)–[s4-36](usability-audit-2026-10-07/s4-36-library-movies-after-reinstall.jpeg) |

`rebuild-ledger --help` 這個指令存在，沒有 dry-run，會寫 DB，所以這次**沒有執行**（未驗證）。

### S5 精靈之後打開三個套件內服務

乾淨的瀏覽器 context，沒有 cookie。

| 服務 | 看到 | 帳密 | 登入後 | 截圖 |
| --- | --- | --- | --- | --- |
| Jellyfin :8096 | 「請登入」，分頁標題「Berth」 | 擁有者那一組 | 三個媒體庫，頁首伺服器名「Berth」；沒有它自己的 onboarding | [s5-01](usability-audit-2026-10-07/s5-01-jellyfin-login.jpeg)、[s5-02](usability-audit-2026-10-07/s5-02-jellyfin-home.jpeg) |
| qBittorrent :8080 | WebUI 登入 | 擁有者那一組 | 主介面，下載在列；沒有「請改密碼」 | [s5-03](usability-audit-2026-10-07/s5-03-qbittorrent-login.jpeg)、[s5-04](usability-audit-2026-10-07/s5-04-qbittorrent-home.jpeg) |
| Prowlarr :9696 | 「SIGN IN TO CONTINUE」 | 擁有者那一組 | 6 站都在；沒有強迫設定登入的視窗 | [s5-05](usability-audit-2026-10-07/s5-05-prowlarr-login.jpeg)、[s5-06](usability-audit-2026-10-07/s5-06-prowlarr-home.jpeg) |

結論與上一輪相同：三個服務都不用再跑自己的 onboarding，一組帳密通用。完成頁說「密碼是精靈裡設的那一組」，可以直接說「與 Jellyfin 同一組」（P2-3）。

### 上一輪改進清單的驗證

| 上一輪 | 票 | 這一輪實跑 |
| --- | --- | --- |
| P0-1 全域偏好讓 Route 紅 | 32 | ✔ 兩種來源都只寫登入兩鍵（S1、S2 diff） |
| P0-2 可拉的 image | 41 | ✔ 拉得到；✘ 落後 15 個 commit（E5） |
| P0-3 原生 Linux | 42 | ✘ `needs-info`，沒跑 |
| P1-2 不寫入的確認鍵 | 38、39 | ✔ 頁 2 測過即完成；頁 4 既有表單與頁 1、2 同一個元件 |
| P1-3 套件內卡片「沒在跑」 | 35 | 這一輪沒有重現那個情境（未驗證） |
| P1-4 頁 4 右欄 | 39 | ✔ key 錯時右欄跟著測試結果（[s2-18](usability-audit-2026-10-07/s2-18-p4b-wrong-key.jpeg)） |
| P1-5 密碼一次 | 40 | ✔ S1 打 2 次；重裝時 1 次 |
| P1-6 補法改「加一條 `/data`」 | 36 | ✔ 原本的掛載不用動；✘ `${DATA_ROOT}` 佔位與相對路徑（P1-6） |
| P1-7 停掉套件內那一台 | 36 | ✔ README 的兩步實測有效（S4 移除 Prowlarr） |
| P2-1 頁 3 自動跑 | 43 | ✔ 約 20 秒、逐條進度；重裝時不自動跑（設計如此，P2-11） |
| P2-2 頁 4 一鍵 | 44 | ✔ 套件內；既有仍要「測試全部 → 勾 → 加入」（P2-10） |
| P2-3 只存驗過的憑證 | 45 | ✔ TMDB、既有服務都是 |
| P2-4 頁 2 驗 `/data` | 46 | ✔ qBittorrent；Jellyfin 沒有對稱的檢查（P1-7） |
| P2-5 換台列遺留物 | 47 | ✔ 數字準、只動空分類；白名單沒列 |
| P2-7 搜尋篩 | 49 | ✔ 37 筆 / 收起 74 筆 |
| P2-8 健康頁 5/6 | 50 | 部分：沿用的有說明，從沒問過的那一條仍算綠（P1-3） |
| P2-9 作品頁 Jellyfin 狀態 | 51 | ✔ 重開頁一致；入庫後頭 2.5 分鐘文案不實（P1-9） |
| P2-11 伺服器名稱 | 52 | ✔「Berth」 |

## 4. 精靈是不是最簡實現（C）

### 4.1 每頁的動作數

| 頁 | S1 套件內：輸入 / 必按 | S2 既有：輸入 / 必按 | S3 混搭：輸入 / 點擊 | 重裝（套件內）：輸入 / 必按 |
| --- | --- | --- | --- | --- |
| 1 Jellyfin | 3 / 3 | 3 / 4（選、測試連線、登入、下一步） | 3 / 約 6 | 2 / 3 |
| 2 qBittorrent | 0 / 2 | 3 / 3 | 0 / 2 | 0 / 2 |
| 3 媒體庫路徑 | 0 / 1 | 0 / 4（勾 2 個媒體庫、建立並檢查、下一步） | 0 / 約 7（含修掛載後重按） | 0 / 2 |
| 4 Prowlarr | 0 / 3 | 2 / 3（加推薦站另加 3） | 0 / 2 | 0 / 2 |
| 5 TMDB | 1 / 2 | 1 / 2 | 1 / 2 | 1 / 2 |
| 6 完成 | 0 / 1 | 0 / 1 | 0 / 1 | 0 / 1 |
| **合計** | **4 / 12** | **9 / 17** | **4 / 約 20** | **3 / 12** |

對照：Jellyfin 首次啟動精靈 6 個畫面、Seerr setup 4 步（Radarr / Sonarr 可不加）、HA onboarding 5 步（R2 §2.1、§2.3、§2.4）。套件內那條在步數上已經和它們同級；既有那條多出來的，主要是「測試連線」與「登入」分兩次按，以及頁 3 的勾選。

### 4.2 可以刪或合併的

| # | 現在 | 改成 | 省下 | 對齊誰 |
| --- | --- | --- | --- | --- |
| C1 | 既有 Jellyfin：先「測試連線」，通過後才長出登入表單，再按「登入」 | 位址＋管理員帳密同一個表單，一顆「連線並登入」；位址錯標位址、帳密錯標帳密 | 每次 1 按＋1 次等待 | Seerr：伺服器位址與管理員帳密同一頁、一顆 Sign In（R2 §2.3） |
| C2 | 既有 Jellyfin 頁 3 要逐個勾媒體庫 | 類型對得上的（movies、tvshows）預設勾；搭配 E1 補「沒有電影媒體庫」那一列 | N 按 | Seerr 也要選媒體庫，預設值我沒查證，**這條是建議，不是對齊** |
| C3 | 既有 Prowlarr 加推薦站：「測試全部 → 勾 → 加入 N 個站」 | 與套件內同一顆「測試推薦站，加入通過的」；Prowlarr 已經有站時，放在「進階」 | 2 按 | 套件內自己的做法（票 44） |
| C4 | TMDB：「測試 TMDB」→「前往下一個泊位」 | 「下一步」本身先測，測過才走；保留單獨的「測試」鍵 | 1 按 | Sonarr：Save 會自動再測一次（上一輪 §E） |
| C5 | 頁 3 失敗時每個媒體庫各一整段補法 | 同一台 Jellyfin 沒掛 `/data` 合併成一則，列出受影響的媒體庫 | 閱讀量 | HA：`errors['base']` 是表單層級的錯誤，不逐項重複（上一輪 §E） |
| C6 | localhost 的說明同時出現在黃色提示與紅色錯誤 | 測試失敗時把黃色提示收起來 | 閱讀量 | — |
| C7 | 既有 Jellyfin 沒掛 `/data` 要到頁 3 才知道 | 頁 1 連線成功後，用已有的 `ValidatePath` 探一次 `/data`（qBittorrent 在頁 2 已經這樣做，票 46） | 一輪來回 | 自己的做法（票 46） |

不建議刪的：
- 每頁的「前往下一個泊位」：成熟產品每步都有 Next。
- 三個服務各自選「套件內 / 既有」：2026-09-29 拿掉偵測，是因為曾經猜錯而寫壞使用者的服務（brief §19）。預選會把那條風險帶回來。

### 4.3 說明可以刪或改白的

- 頁 4 還沒選來源，右欄就寫「接法　你自己的 Prowlarr」（[s1-07](usability-audit-2026-10-07/s1-07-page4-initial.jpeg)、[s4-29](usability-audit-2026-10-07/s4-29-rerun-page4-initial.jpeg)）。
- 頁 4 的登入列，進行中寫「設定中…」，完成後寫「已經是這樣」，頁 2 同一件事寫「已完成」；底欄同時寫「還差 設定 Prowlarr 介面登入」。
- 技術細節裡的位址少了 `http://`，複製下來不能直接貼。

## 5. 接管：你的理想流程與 D1

### 5.1 理想流程 vs 現況

| 你的理想 | 現況 | 差距 |
| --- | --- | --- |
| 套件內：幾乎不用動手，按下去就能繼續 | S1：密碼 2 次、TMDB key 1 次，其餘只按「選套件內」「下一步」與頁 4 一顆鍵 | 已達成。唯一要離開 Berth 的是申請 TMDB key（設計如此，brief §16.3） |
| 既有：填位址與帳密 → Berth 檢測 | 頁 1、2、4 都是填位址與憑證 → 測試 | 已達成；Jellyfin 的「測試」與「登入」分兩按（C1） |
| 不能接入就說清楚為什麼、怎麼改 | 五類錯誤都說了原因與補法（S2） | 剩下的缺口：`${DATA_ROOT}` 佔位、Jellyfin 的 `/data` 要到頁 3 才知道（P1-6、P1-7） |
| 能接入就自動完成需要的設定 | Berth 自動建：API key「Berth」、Berth 路徑、`berth-*` 分類、勾選的站，並自動探測掛載與硬鏈接 | 見 5.2：唯一沒自動的是「既有 Jellyfin 缺某類型的媒體庫」 |
| 統一、步驟最少 | 每個服務頁同一個形狀（選來源 → 連線卡 → 這一頁的寫入），上一輪的 E-1…E-7 都做完了 | §4.2 的 C1–C7 |

### 5.2 衝突在哪、兩邊的代價、建議

成熟產品對既有服務的寫入光譜（R2 §2.6，附出處）：
- **L0**：只讀，錯了叫你去改。例：Sonarr 對 qBittorrent 的全域偏好。
- **L1**：只建自己的新物件。例：Sonarr 建分類、Seerr 建 Jellyfin API key。
- **L2**：改你已有的物件。例：Seerr 改 Sonarr 裡已有的劇、Prowlarr Full Sync。
- **L3**：寫全域或裝置設定。例：HA 的 Shelly、Reolink。
- **L4**：宣告式管理整個服務。例：Buildarr、Recyclarr。

**D1 就是 L1**，和最接近 Berth 情境的 Sonarr、Seerr 同級。那些產品讓人覺得「自動」，靠的是三件事：測過即完成、錯誤綁在欄位上、錯了教你怎麼改，而不是去寫對方的全域設定。

逐項看「自動完成需要的設定」會碰到什麼：

| 既有服務接進來需要的 | 有沒有 API 能改 | 理想流程要 | D1 允許 | 衝突？ |
| --- | --- | --- | --- | --- |
| 掛 `/data` | 沒有（容器設定在 Docker 那一層） | 自動 | — | **不是 D1 的問題**：誰都做不到，只能把補法寫到能照抄（P1-6） |
| qBittorrent 全域偏好（save path、autoTMM…） | 有 | 自動 | 不寫 | **不衝突**：Berth 一個都不需要（送單逐個 torrent 帶分類與 `autoTMM`，S1、S2 實測） |
| 服務的帳密 / 介面登入 | 有 | — | 不碰 | 不衝突：既有的本來就有人登得進去 |
| Jellyfin API key、`berth-*` 分類、Berth 路徑、勾選的站 | 有 | 自動 | 建 | 不衝突：已經自動 |
| **既有 Jellyfin 缺某類型的媒體庫** | 有（`POST /Library/VirtualFolders`） | 自動建 | 現行規則不建 | **衝突**，見 E1 |
| **Jellyfin 全庫掃描** | 有 | —（理想流程沒說） | D1 清單沒列，程式卻會做 | **D1 的實作與宣告不一致**，見 E2 |
| 既有 Jellyfin 的媒體庫加一條 Berth 路徑 | 有 | 自動 | 建（加一條，舊的不動） | 不衝突，但它是 L2（動到你已有的媒體庫）。R2 找不到成熟產品有同類寫入，D1 的保護是「要勾才加、舊路徑不動」 |

兩邊各自的代價：
- **完全照理想流程**（能接入就自動改需要的設定，包含全域）：Berth 不需要任何全域設定，所以這半句實際上沒有東西可做。若硬要寫，就回到 2026-09-26 `berth-lab` 的兩件事故：改了使用者的 qBittorrent 全域 save path、覆寫了使用者的 Prowlarr 登入（brief §19）。
- **嚴守現行 D1**：既有 Jellyfin 缺媒體庫時，使用者要離開 Berth 去 Jellyfin 建；Berth 的全庫掃描仍然是沒說的寫入。

**建議**：
- 維持 D1（L1）。
- 把「使用者勾選後在既有 Jellyfin 新建的媒體庫」納入「Berth 擁有的物件」（E1）。
- 把全庫掃描收斂成只刷新 Berth 的媒體庫，或至少寫進物件表（E2）。
- 這樣理想流程的每一句都能成立，而且不碰任何全域設定。

### 5.3 實際行為與文件不一致的地方

讀碼確認（R1 §1.8；`A/` 是 `berth/adapters/`，`S/` 是 `berth/services/`）：

| 文件寫的 | 實際 | 位置 |
| --- | --- | --- |
| brief §16.4、`CONTEXT.md` 的「Berth 擁有的物件」清單 | 另外還會做：Jellyfin 全庫掃描任務、`POST /Library/Media/Updated`、qBittorrent 每個 torrent 帶 tag `berth`、每次送單都 `ensure_category`（使用者刪掉的 `berth-*` 分類會被悄悄重建） | `A/jellyfin/client.py:233-255`、`A/qbittorrent/__init__.py:100,133`、`S/jobs.py:1102` |
| 「不動你原有的…站」 | 套件內 Prowlarr 的「移除」看的是「公開 torrent 站或推薦站」，不看是不是 Berth 加的；你自己在套件內 Prowlarr 加的公開站也按得到移除 | `S/indexer.py:514,936` |
| 白名單閘門 `test_setup_owned_writes.py` | 只守**精靈流程**；送單、入庫、反查、Issue 修復這些執行期的寫入沒有閘門。`delete_indexer` 的白名單條件比程式嚴，閘門因此給人「已經守住」的錯覺 | R1 §1.9 G1、G4 |
| README:9、`.env.example:4`、brief §16.1「四個容器掛同一個媒體根」 | 三個（Prowlarr 沒掛 `/data`） | `deploy/docker-compose.yml:118-130` |
| README「密碼只交給 Jellyfin，Berth 不存」 | 勾了沿用時，存的是擁有者密碼的 scrypt 雜湊（不是明文，但不是「不存」） | `S/steps.py:62-72` |
| brief §16.4「頁 3 的檢查失敗，Berth 路徑也留著」 | 只說對一半：Jellyfin 看不到就不加、收回目錄（S2 實測 `/data` 是空的）；只有加進去之後才失敗的檢查才會留著 | `S/jellyfin.py:594-` |

## 6. 整個程式（D）

### 6.1 從設定到日常的流程

```
docker compose up -d
  → 精靈 6 頁（§3 S1 / S2）
  → 探索（TMDB 趨勢、搜尋）→ 作品頁搜 torrent（Prowlarr，名字比對＋年份 / 類型篩）→ 送單（選 Route）
  ↘ RSS（Mikan / Nyaa / acg.rip feed；認得出就自動綁定、補舊集、新集自動送單）↗
  → qBittorrent 下載（Berth 每 5 秒讀增量）
  → 解析與計劃（純函式；高信心自動，低信心進審核）
  → 硬鏈接入庫＋帳本（inode）→ 通知 Jellyfin → 回驗（季集不一致開 Issue）
  → 媒體庫瀏覽（整個 Jellyfin 媒體庫＋Berth 狀態、繼續觀看、標已看）
  背景：健康每 5 分鐘、對帳每日 04:00
```

每個功能一句話，細節見附錄 A：

| 功能 | 一句話 |
| --- | --- |
| 探索 | TMDB 的趨勢、熱門與搜尋，一格連到作品頁 |
| 搜尋 | 用作品的多個名字各問 Prowlarr 一次，名字對不上的略過，年份或類型對不上的收起來 |
| 送單 | 送前檢查 Route 狀態與磁碟；帶 `berth-<slug>` 分類與 `autoTMM` 送進 qBittorrent |
| RSS | 訂 feed，作品 × 字幕組認得出就綁定，補舊集，新集自動送單；三層排除條件 |
| 解析 | 分類、發佈名、季集、播出日、片長 → 逐檔處置與信心；`berth bench` 守 `auto_wrong` |
| 入庫 | complete 硬鏈接到媒體庫，帳本記 inode，失敗不退回複製 |
| 審核 | 低信心逐列改後核准；medium 自動入庫的可一鍵確認或撤銷；指派對不到的檔案 |
| 健康 | 四項服務＋每條 Route 的 6 條檢查＋下載迴圈 |
| 對帳 | 比 Jellyfin、complete、媒體庫、帳本，刪掉的、少了的、被複製品取代的都可一鍵修 |
| 設定 | 精靈完成後的修改，一格泊位一頁 |

### 6.2 哪些實際跑過

| 狀態 | 功能 |
| --- | --- |
| **這一輪真服務實跑** | 精靈（全套件內、全既有、混搭、重裝）、探索、搜尋（含年份篩）、送單、真 BT 下載、解析與入庫、Jellyfin 回驗、健康、設定頁換台、換台列遺留物 |
| **真服務 e2e 守著**（`tests/e2e/`，nightly；位元組是複製再 recheck，不是真 BT；公開站是替身） | 三種作品入庫、媒體庫權限與標已看、五種對帳修復、RSS 自動綁定 / 補舊集 / 排除 / 修正（R1 §3.1） |
| **只有單元 / 整合 / 前端 e2e（Fake 後端）** | 頁 4 加站與 Prowlarr 登入（e2e 跳過頁 4）、既有 Jellyfin / qBittorrent 的 e2e、頁 2 探針、頁 3 自動跑、`rebuild-ledger`、管理員端點的 403 |
| **沒做** | 巡檢、通知（Telegram / Discord）、AI（M5 起） |

### 6.3 能不能實際投入使用

**你自己用：可以，有條件。**
- 條件：
  - 機器是 Windows Docker Desktop（這一輪全部在這裡跑）。
  - 用自己 build 的 image，或先發 0.2.0（E5）。
  - 接受沒有通知：有事只能打開網頁看。
  - 知道重裝前要備份 `config/berth`，或者知道 `rebuild-ledger`。
- 還擋著的：
  - 若伺服器是原生 Linux / NAS → 先跑票 42。
  - 若要停用 Prowlarr → E3。
  - 要換 qBittorrent 時 → 記得到「媒體庫路徑」逐條重新檢查（P1-3）。

**2026-10-08 補：你實際要跑 Berth 的機器是 Unraid**，所以上面「Windows Docker Desktop 上可以用」對你不成立，在 Unraid 實跑之前，「你自己用」也要標**未驗證**。Unraid 有幾件事和這一輪的環境不同，都沒有驗過：
- 硬鏈接：TRaSH Guides 說要在「Global Share Settings」開 `Tunable (support Hard Links)`，下載和媒體放在同一個 share（例如 `/mnt/user/data`）底下才行（<https://trash-guides.info/File-and-Folder-Structure/How-to-set-up/Unraid>）。README 現在寫「mergerfs 不行」，Unraid 的 user share 是 shfs，兩者的關係要實測；cache pool 加 mover 會不會拆散硬鏈接也沒驗過。
- 權限：Unraid 慣例是 `nobody:users`（PUID 99 / PGID 100），`.env.example` 預設是 1000。
- 部署方式：Unraid 預設沒有 docker compose，要裝 Compose Manager 外掛；多數人用 Community Apps 模板。
- 既有服務的補法：Berth 給的是 compose 與 `docker run` 片段，Unraid 使用者改的是模板裡的「Add another Path」。

**一般自架使用者：還不行。**
- 擋著的：
  1. 不知道怎麼拿到 `deploy/`（P0-1）。
  2. 原生 Linux / NAS 沒驗過（P0-2）。
  3. `:latest` 不是 README 描述的版本（E5）。
  4. 撤回與重裝沒有出口：停用服務、重裝後的帳本、卸載清單（P1-2、P1-4、P1-5）。
  5. README 太長、順序不對（P1-8）。
- 不擋上線但會被期待的：通知與巡檢（M4 本體）。

## 7. 文件好不好懂（E）

紙上走查 README:1-232、`deploy/.env.example`、compose（R2 §1）。

- **長度與術語**：
  - 第一部片入庫前的必經內容約 2,000 字，真正跳不過的不到 600 字。
  - 部署段約 35 個專有 / 技術名詞，必須懂的只有 8 個：`DATA_ROOT`、精靈每頁在做什麼、套件內 / 既有、擁有者、TMDB key、硬鏈接前提、Route，以及 compose 本身。
  - Route 與「擁有者」是 Berth 自創的詞，README 在用之前沒有定義。
- **卡住的順序**：
  1. 怎麼拿到 `deploy/`。
  2. 已經有服務的人要先改 `COMPOSE_PROFILES`，但這句在第 127 行。
  3. TMDB key 第 5 頁才要，而且要收驗證信。
  4. `DATA_ROOT` 該不該改：README:13 說改，`.env.example:9` 說試跑不用改。
  5. `TZ` 預設 `Asia/Taipei`，README 沒提。
  6. 沒寫前置需求（Compose v2）。
  7. 沒說怎麼知道起來了（`docker compose ps`）。
- **與實際對不上**：「四個容器掛同一個媒體根」實際是三個；「唯一要離開 Berth 的一步是 TMDB」只對「套件內＋公開站」成立；port 表夾在〈頁面〉標題下。
- **建議結構（E7）**：
  - README 只留：簡介、取得檔案、改 2–4 個值（`DATA_ROOT`、`TZ`、已有服務時的 `COMPOSE_PROFILES`）、`up -d`、先申請 TMDB key、精靈每頁一句話、備份一句。
  - 里程碑長段搬去 CHANGELOG。
  - 既有服務、外部服務前提、升級、疑難排解、帳密機制，各搬成 `docs/` 一頁。
  - 估計必讀約 1,000–1,400 字，是現在的 22–30%。
  - 對照：Immich 的安裝步驟約 250 英文字，`.env` 列 4 項要改（R2 §1.6）。

## 8. 問題清單

**情境欄**：S1–S5 是這一輪實跑；「碼」是讀碼確認；「紙」是文件紙上走查。

### P0：擋使用

| # | 問題 | 情境 | 證據 / 重現 |
| --- | --- | --- | --- |
| P0-1 | README 沒說怎麼拿到 `deploy/`；只抓 compose 一個檔會缺 `preseed/`，套件內 qBittorrent 從此 Berth 進不去 | 紙、碼 | `README.md:11-14`；`deploy/docker-compose.yml:90`；`deploy/preseed/qbittorrent/10-berth.sh:4-7`。重現：只下載 compose 與 `.env.example`、`up -d`，頁 2 連不上（這一條是讀碼推論，**未實跑**）。解法見 E4 |
| P0-2 | 原生 Linux / NAS 沒有人跑過（`host-gateway`、PUID / PGID、NAS 的掛載慣例） | — | 票 42 `needs-info`；README:159。**未驗證**，見 E8 |

### P1：困惑或多餘步驟

| # | 問題 | 情境 | 截圖 / 重現 |
| --- | --- | --- | --- |
| P1-1 | GHCR `:latest` = 0.1.0（`6bc4c1d`），不含票 43–54；照 README 部署看到的是舊精靈 | S1 | `docker pull` 後 `image inspect` 看 revision；E5 |
| P1-2 | 不想用 Prowlarr 沒有出口：健康頁永遠「阻擋」，修正只教你把它起回來；設定頁同時顯示舊的綠色測試結果與紅色錯誤；Prowlarr 回來後要等下一輪（約 4.5 分鐘） | S4 | [s4-19](usability-audit-2026-10-07/s4-19-health-prowlarr-stopped.jpeg)、[s4-20](usability-audit-2026-10-07/s4-20-settings-prowlarr-stopped.jpeg)。重現：拿掉 profile、`docker compose stop prowlarr`、開健康頁 |
| P1-3 | 換 qBittorrent 後健康頁 BTH 3「已繫上」，三條 Route 卻是「尚未檢查」，新那台沒有分類；沒有「全部重新檢查」，要逐條按（6 次點擊）；換台成功的畫面也沒指路。換回套件內後是 5/6（探針那一條「尚未執行」），一樣算綠 | S4 | [s4-09](usability-audit-2026-10-07/s4-09-health-after-qbt-switch.jpeg)、[s4-12](usability-audit-2026-10-07/s4-12-routes-after-qbt-switch.jpeg)、[s4-18](usability-audit-2026-10-07/s4-18-health-after-switch-back.jpeg)。換台後直接送單會怎樣**未驗證** |
| P1-4 | 換 qBittorrent 時，做種中的 torrent 留在舊那台，Berth 不追蹤也不提示；換台框只寫「1 個 torrent」 | S4 | [s4-06](usability-audit-2026-10-07/s4-06-qbt-existing-selected.jpeg)、[s4-11](usability-audit-2026-10-07/s4-11-job-detail-after-qbt-switch.jpeg) |
| P1-5 | 重裝（或 DB 遺失）後：作品頁同時寫「在 Jellyfin 看」與「還沒有任何檔案入庫」，下載頁全空，TMDB key 要重貼；唯一的提示是「無主 torrent」，按鈕沒說做什麼；沒有提 `rebuild-ledger`；重跑精靈的方法（搬走 DB）沒有文件寫 | S4 | [s4-31](usability-audit-2026-10-07/s4-31-rerun-page6-complete.jpeg)、[s4-33](usability-audit-2026-10-07/s4-33-title-after-reinstall.jpeg)、[s4-35](usability-audit-2026-10-07/s4-35-issue-orphan-expanded.jpeg)；E6 |
| P1-6 | 既有服務的補法是 `${DATA_ROOT}:/data`，使用者要自己去 Berth 的 `.env` 找值；預設 `./data` 是相對路徑，貼進另一份 compose 會指到別處；Windows 路徑的寫法沒說。可行做法：compose 把 `${DATA_ROOT}` 當環境變數傳給 Berth，畫面直接印出值；是相對路徑時，說要換成絕對路徑 | S2 | [s2-11](usability-audit-2026-10-07/s2-11-p2d-no-data-mount.jpeg)、[s2-15](usability-audit-2026-10-07/s2-15-p3-jellyfin-no-data.jpeg) |
| P1-7 | 既有 Jellyfin 沒掛 `/data` 要到頁 3 才知道（qBittorrent 在頁 2 就知道）；頁 3 每個媒體庫重複一整段補法 | S2 | [s2-15](usability-audit-2026-10-07/s2-15-p3-jellyfin-no-data.jpeg)；C5、C7 |
| P1-8 | README：必讀約 2,000 字、35 個名詞；預設三個 profile 全開，已有服務的人在精靈前就撞 port；`DATA_ROOT` 該不該改兩處說法相反；`TZ` 預設台北沒提 | 紙 | §7；E7 |
| P1-9 | 第一次入庫到空的媒體庫：Jellyfin 要約 2.5 分鐘才掃到，這段時間作品頁寫「Jellyfin 還在掃描」，實際上還沒請它掃。可行做法：媒體庫還沒有任何項目時，第一次入庫直接請它刷新 | S1 | `berth/services/resolver.py:68-71,547`；brief §20.1 |
| P1-10 | 接管清單以外的寫入，文件與閘門都沒列：Jellyfin 全庫掃描、`berth` tag、送單時重建被刪的分類、套件內 Prowlarr 的移除鍵不看是誰加的 | 碼 | §5.3；E2 |
| P1-11 | Berth 沒有「不用 Berth 了」的清理入口，也沒有文件列出要手動清的東西 | S4 | 附錄 C.2 的清單 |

### P2：打磨

| # | 問題 | 情境 | 截圖 |
| --- | --- | --- | --- |
| P2-1 | 頁 4 還沒選來源，右欄就寫「接法　你自己的 Prowlarr」 | S1、S4 | [s1-07](usability-audit-2026-10-07/s1-07-page4-initial.jpeg)、[s4-29](usability-audit-2026-10-07/s4-29-rerun-page4-initial.jpeg) |
| P2-2 | 頁 4 登入列「設定中…」→「已經是這樣」，頁 2 同一件事寫「已完成」；底欄同時寫「還差 設定 Prowlarr 介面登入」 | S1 | [s1-08](usability-audit-2026-10-07/s1-08-page4-bundled-selected.jpeg) |
| P2-3 | 完成頁寫「密碼是精靈裡設的那一組」，可以直接說「與 Jellyfin 同一組」 | S1 | [s1-13](usability-audit-2026-10-07/s1-13-page6-complete.jpeg) |
| P2-4 | localhost 的說明在黃色提示與紅色錯誤各出現一次，逐字相同 | S2 | [s2-02](usability-audit-2026-10-07/s2-02-p1a-localhost.jpeg) |
| P2-5 | 頁 1 登入失敗（密碼錯、非管理員）沒有標欄位；頁 2 密碼錯兩欄都標 | S2 | [s2-05](usability-audit-2026-10-07/s2-05-p1d-wrong-password.jpeg)、[s2-10](usability-audit-2026-10-07/s2-10-p2c-wrong-password.jpeg) |
| P2-6 | 技術細節裡的位址少了 `http://` | S2 | [s2-02](usability-audit-2026-10-07/s2-02-p1a-localhost.jpeg) |
| P2-7 | 作品頁搜尋失敗時露出原始字串 `GET /api/v1/indexer: host does not resolve` | S4 | [s4-21](usability-audit-2026-10-07/s4-21-title-search-prowlarr-stopped.jpeg) |
| P2-8 | 精靈完成後打開 `/setup` 是靜默轉址 | S4 | — |
| P2-9 | 換台框的「移除空分類」在確認換台之前就生效；之後取消換台會怎樣**未驗證** | S4 | [s4-07](usability-audit-2026-10-07/s4-07-qbt-removed-empty-categories.jpeg) |
| P2-10 | 既有 Prowlarr 加推薦站要三步，套件內一鍵（C3） | S2 | [s2-20](usability-audit-2026-10-07/s2-20-p4d-recommended-tested.jpeg) |
| P2-11 | 重裝時頁 3 不自動跑（清單已存在，設計如此），與頁 1、2、4 的「選了就自動測」不一致 | S4 | [s4-27](usability-audit-2026-10-07/s4-27-rerun-page3.jpeg) |
| P2-12 | 搜尋說明寫「通常要一分鐘左右」，實測 12 秒 | S1 | [s1-16](usability-audit-2026-10-07/s1-16-search-results.jpeg) |
| P2-13 | 套件內媒體庫建立時 `EnableRealtimeMonitor=false`（刻意的，plan §9.4），所以使用者手動丟進去的檔案不會自動出現；沒有告知 | 碼 | `A/jellyfin/client.py:634` |
| P2-14 | 官方 compose 寫死專案名、容器名、網路與子網，同一台主機不能並存兩套（例如正式一套、試用一套） | S2 | `deploy/docker-compose.yml:1-17` |
| P2-15 | 中文媒體庫名直接成為分類與資料夾名（`berth-節目`、`/data/library/節目`）；特殊字元與撞名**未驗證** | S2 | — |
| P2-16 | 文件小錯：「四個容器」實為三個；「Berth 不存密碼」實為存雜湊；brief §16.4「Berth 路徑失敗也留著」只對一半；頁 1 右欄「不改這台 Jellyfin 的任何設定」與下一行的「建立 API key」打架 | 碼、S3 | §5.3；[s3-02](usability-audit-2026-10-07/s3-02-page1-existing-done.jpeg) |
| P2-17 | 精靈剛完成就打開健康頁，四個泊位都是「尚未檢查」、「沒有紀錄」，要按「立即重測」；而完成時明明已經照頁序再驗過一次 | S3 | 重現：完成精靈後立刻開 `/health` |
| P2-18 | 探索搜尋打「片名 年份」得到 0 筆 | S3 | 搜「Nosferatu 1922」 |
| P2-19 | 作品頁搜尋的幾個筆數對不上（「共 262 · 逐站取 100 · 略過 103 · 收起 164」）；同名動畫的各集與成人內容仍留在主表 | S3 | 《Nosferatu》(1922) 作品頁搜尋 |
| P2-20 | 既有 Jellyfin 頁的「停掉套件內那一台」提示在成為擁有者之後就消失，完成頁也不提醒；密碼欄空著時的錯誤把原因說成「帳號沒設密碼」 | S3 | [s3-01](usability-audit-2026-10-07/s3-01-page1-initial.jpeg) |
| P2-21 | 重裝後套件內 qBittorrent / Prowlarr 的介面登入沿用上一位擁有者的帳號，完成頁只說「原本就有的那一組」，沒說忘了怎麼改 | S3、S4 | [s3-03](usability-audit-2026-10-07/s3-03-page2-bundled-already.jpeg) |

## 9. 改進方向

讓精靈與文件更統一、更簡潔，按影響排序：

1. **把「之後」補成和精靈同一個標準**（P1-2…P1-5、P1-11）：
   - 每個服務都能「停用」（E3）。
   - 換台之後自動重查所有 Route，並把做種中的 torrent 說清楚。
   - 重裝時偵測到不認得的媒體庫檔案，就給重建帳本的按鈕（E6）。
   - 加一頁「移除 Berth」的清單（附錄 C.2），先做成文件，之後才考慮做成按鈕。
   - 參考：HA 的 `reauth` / `reconfigure`、repair issue（上一輪 §E）；Recyclarr 的 `--preview` 加「只刪自己同步過的」（R2 §2.5）。
2. **既有服務的補法要能照抄**（P1-6、P1-7）：
   - 畫面印出真正的 `DATA_ROOT` 值。
   - 同一台缺的掛載合併成一則。
   - Jellyfin 的 `/data` 提前在頁 1 驗。
   - 參考：Sonarr 的錯誤綁 Host 欄、HA 的 `errors['base']`。
3. **精靈再省 4–5 按**（C1–C4）：Jellyfin 連線與登入合併（Seerr）、TMDB 的「下一步」先測（Sonarr Save）、既有 Prowlarr 一鍵加站、頁 3 依類型預設勾選。
4. **接管清單補齊、閘門延伸到執行期**（E1、E2、P1-10）：
   - 物件表加上：全庫掃描（或改成只刷新 Berth 的媒體庫）、`berth` tag、分類重建。
   - 白名單測試補一輪「送單 → 入庫 → 反查」的寫入。
5. **README 改成「拿檔案 → 改 2–4 個值 → up → 精靈」**（E4、E7）：
   - 參考 Immich：release 附件，`.env` 只列要改的 4 項。
   - 參考 HA：前置需求寫在安裝頁本身。

## 附錄 A：功能說明與證據

完整功能表（每個功能的邏輯、狀態、證據檔案）在 R1 §3.3，摘要見 §6.2。真服務 e2e 涵蓋：
- `tests/e2e/conftest.py`：精靈走查。
- `test_1_m1_pipeline.py`：三種作品入庫、全域 save path 不影響、伺服器名「Berth」、硬鏈接 inode。
- `test_2_m15_library.py`：權限、標已看。
- `test_3_m2_repair.py`：五種對帳修復。
- `test_4_m3_rss.py`：RSS。

邊界：
- 位元組是複製再 recheck，不是真 BT。
- 公開站是替身（`tests/e2e/sites.py`）。
- 頁 4 在 e2e 裡跳過。
- 沒有既有 Jellyfin / qBittorrent 的 e2e。

## 附錄 B：目錄樹

容器路徑固定，沒有設定可改（`berth/models/setting.py:104-114`）。slug 規則（`berth/services/jellyfin.py:1070-1079`）：
- 套件內取清單上的資料夾名，既有取媒體庫名。
- 轉小寫，保留中日文。
- 撞名時接 `-2`。

**套件內**（S1 實跑的樣子）：

```
宿主 DATA_ROOT（.env 預設 ./data，相對於 compose 檔）       容器內 /data（berth、qbittorrent、jellyfin 三個看得到；prowlarr 沒掛）
├── torrent/
│   ├── incomplete/<slug>/        ← 下載中。分類 berth-<slug> 的 downloadPath，qBittorrent 寫
│   └── complete/<slug>/          ← 下載完。分類的 savePath，qBittorrent 完成後搬過來；硬鏈接的來源，做種繼續用它
│       └── movies/Night.of.the.Living.Dead.1968.720p.BluRay.x264-[YTS.AM]/…mp4
└── library/<slug>/               ← 媒體庫。Jellyfin 媒體庫的路徑，Berth 用硬鏈接寫入
    └── movies/
        └── Night of the Living Dead (1968) [tmdbid-10331]/
            └── Night of the Living Dead (1968) [tmdbid-10331] - [BD][720p][YTS.AM].mp4
                ↑ 與 complete 裡那個檔同一個 inode（link count 2）：不佔兩份空間；刪一邊另一邊還在

劇集 / 動畫：library/tv/<作品> (<年>) [tmdbid-<id>]/Season 01/<作品> (<年>) - S01E01 - <集名> [WEB][1080p][CHT][<組>].mkv
特典：<作品資料夾>/extras/<原檔名>

宿主 CONFIG_ROOT（預設 ./config）
├── berth/          ← berth:/config；berth.db（設定、秘密、帳本、Job）。備份 Berth 就是複製這個
├── qbittorrent/    ← qBittorrent.conf（預置腳本只補兩個白名單鍵）
├── jellyfin/       ← Jellyfin 資料（升級前要備份）
└── prowlarr/       ← config.xml；同一個目錄唯讀掛進 berth:/ext/prowlarr，Berth 從這裡讀 API key
```

**既有**（S2 實跑的樣子：你原本的 `/tv`、`/movies`、`/downloads` 不動，只多掛一條 `/data`）：

```
你原本的目錄（Berth 不掛、不讀、不寫）
├── media/tv      → Jellyfin 容器內 /tv        ← 「節目」媒體庫原本的路徑
├── media/movies  → Jellyfin 容器內 /movies    ← 「電影」媒體庫原本的路徑
└── downloads     → qBittorrent 容器內 /downloads ← 你原本的 torrent，照常做種

Berth 的 DATA_ROOT → 三個容器都多掛成 /data
├── torrent/incomplete/節目/   torrent/incomplete/電影/
├── torrent/complete/節目/     torrent/complete/電影/
└── library/節目/              library/電影/     ← 被「加」成各自媒體庫的第二條路徑
                                                   Jellyfin「節目」= [/data/library/節目, /tv]
```

硬鏈接只發生在 `DATA_ROOT` 裡面（complete → library），所以你原本的媒體目錄不必與它在同一個檔案系統。但 `DATA_ROOT` 本身要建得了硬鏈接：不是 exFAT、網路磁碟或 mergerfs，也不能跨 btrfs 子卷。

## 附錄 C：接管表

### C.1 服務 × 改了什麼 × 為什麼 × 能不能撤回

「實跑」欄寫的是這一輪看到的情境；讀碼位置見 R1 §1。

| 服務 | 改了什麼 | 套件內 | 既有 | 為什麼 | 在 Berth 撤回 | 自己撤回 | 實跑 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Jellyfin | 初始設定（語言、地區、遠端存取關）、管理員帳號 | 那台沒初始化時 | 只在那台沒初始化時 | 擁有者＝Jellyfin 管理員 | 不能 | 控制台、使用者管理 | S1 |
| Jellyfin | 伺服器名「Berth」 | 沒初始化時 | 不設（Jellyfin 會清成空字串） | 用戶端不顯示容器 ID | 不能 | 控制台「一般」 | S1、S5 |
| Jellyfin | API key「Berth」 | 建 | 建（頁 1 登入成功就建） | Berth 之後的呼叫都用它 | 不能（重裝時找回同一把重用） | 「API 金鑰」頁刪 | S1、S2、S4 |
| Jellyfin | 媒體庫 | 建精靈清單上的 | 不建（E1） | 套件內沒有媒體庫 | 不能 | Jellyfin 刪 | S1 |
| Jellyfin | 媒體庫上加 Berth 路徑 | — | 頁 3 勾選的加一條，舊的不動 | 不搬既有媒體、觀看紀錄不歸零 | 不能 | 媒體庫設定移除 | S2 |
| Jellyfin | **全庫掃描任務**、路徑變更通知 | 會 | 會 | 空媒體庫的路徑通知無效 | — | — | S1（log）；**物件表沒列，E2** |
| Jellyfin | 登入（每次 Berth 使用者登入，DeviceId `berth-server`）→ 留一筆裝置 | 會 | 會 | Berth 沒有自己的密碼 | — | 「裝置」頁刪 | S3（`/Devices` 多一筆 Berth） |
| qBittorrent | 免密白名單（只放 Berth 的 IP） | 預置（缺鍵才補） | 不碰 | 4.6.1 起首次密碼只印在 log | 不能；換台框沒列 | `qBittorrent.conf` 或 WebUI「驗證」 | S4 |
| qBittorrent | WebUI 登入 | 設（沿用擁有者） | 不碰 | 不設就只剩 log 裡的臨時密碼 | 只能再設一組蓋過 | WebUI 偏好 | S1、S4 |
| qBittorrent | 全域偏好 | **不寫** | **不寫** | Berth 不需要 | — | — | S1、S2（diff 不變） |
| qBittorrent | `berth-<slug>` 分類（complete / incomplete 路徑） | 建 | 建 | 路徑開在分類上 | 換台時可移除**空的**；送單時被刪的會**悄悄重建** | qBittorrent 刪 | S1、S2、S4 |
| qBittorrent | 送出的 torrent（帶 tag `berth`） | 建 | 建 | Berth 的下載 | 刪 Job（不刪檔） | qBittorrent 刪 | S1；tag 在物件表沒列 |
| qBittorrent | 探針 torrent、探測檔（頁 2 在 `/data`，頁 3 在分類路徑） | 暫時、自清 | 暫時、自清 | 驗掛載 | 自清（斷線時可能殘留，票 54 不修） | 手動刪 | S2：失敗與成功都沒有殘留 |
| Prowlarr | 讀 API key（唯讀掛載 config.xml） | 讀 | —（貼 key） | 零輸入 | — | — | S1 |
| Prowlarr | 站 | 加勾選的 / 一鍵加通過的 | 加勾選的 | 搜尋要站 | 套件內可單站移除（**也移除得掉你自己加的公開站**） | Prowlarr 刪 | S1、S2 |
| Prowlarr | 介面登入（Prowlarr 會重啟） | 設 | 不碰 | 不設的話第一次開會強迫設 | 只能再設 | Prowlarr 設定 | S1、S5 |
| TMDB | — | 只讀 | 只讀 | — | — | — | — |
| Berth DB | Jellyfin key、既有 qBittorrent 帳密、Prowlarr key、TMDB key 明文；介面登入的密碼存 scrypt 雜湊；擁有者密碼不存明文 | | | — | — | 刪 `config/berth` | 碼 |

### C.2 完全不用 Berth 時要手動清的（S4 整理）

1. Berth：停容器；`config/berth`（含 TMDB key 與各服務 key）刪或留。
2. Jellyfin：刪 API key「Berth」；套件內建的媒體庫刪或留；既有媒體庫上加的 `/data/library/<x>` 路徑移除；伺服器名、管理員視需要改。
3. qBittorrent：刪 `berth-*` 分類（先處理裡面的 torrent）；套件內那台的 WebUI 登入與白名單（`qBittorrent.conf` 的 `WebUI\AuthSubnetWhitelist*`）。
4. Prowlarr：刪 Berth 加的站（畫面上分不出哪些是 Berth 加的）；套件內的介面登入。
5. 宿主：`DATA_ROOT/torrent`、`DATA_ROOT/library`；入庫檔是硬鏈接，兩邊都要刪才會釋放空間。

## 環境與還原

| 目錄 / 容器 | 用途 | 現況 |
| --- | --- | --- |
| `C:\Users\Roxy\berth-audit2`（專案 `berth`：`berth`、`berth-jellyfin`、`berth-qbittorrent`、`berth-prowlarr`，port 8383 / 8096 / 8080 / 9696） | S1、S4、S3 | S3 的狀態：既有 Jellyfin＋套件內 qBittorrent / Prowlarr、精靈完成；`COMPOSE_PROFILES=qbittorrent,prowlarr`，`berth-jellyfin` 停止；兩部片在做種 |
| `C:\Users\Roxy\berth-audit3`（`berth-s2`，8384）＋ `berth-audit3-existing`（`mine3-*`，47096 / 47080 / 47696） | S2 | 在跑 |
| `C:\Users\Roxy\berth-audit4-existing`（`s4-qbittorrent`，46080） | S4 | 停止 |
| `C:\Users\Roxy\berth-audit5-existing`（`s3-jellyfin`，46096） | S3 | 在跑 |
| 先前中斷那次留下的 `berth2`、`mine2-*` | — | 停止，沒刪 |
| `exist-broken`（`bad-*`） | S2 的錯誤組 | 停止 |
| 測試帳密 | 各目錄的 `CREDENTIALS.md`（repo 外） | — |

S1 開始前把 `berth-audit2` 上一次的 `config` 與 `data` 搬成 `*.prev-20261007`；S4、S3 的重裝各把 `config/berth` 搬成 `berth.s4-prev`、`berth.s3-prev`，都沒有刪。全部不需要了，可以各自 `docker compose down` 後整個目錄刪掉。

## 來源

成熟產品的出處見 R2，以及上一輪的〈來源〉。本輪新增：
- Sonarr `QBittorrentProxyV2.cs`（只有 `createCategory`，沒有 `setPreferences`）。
- Seerr `server/api/jellyfin.ts`（`POST /Auth/Keys?App=Seerr`）、`server/api/servarr/sonarr.ts`、`src/components/Setup/index.tsx`。
- HA `homeassistant/components/shelly/coordinator.py`、`reolink/host.py`。
- Immich 安裝步驟 `docs/docs/partials/_docker-compose-install-steps.mdx`。
- Buildarr、Recyclarr 文件。

完整網址：
- <https://github.com/Sonarr/Sonarr/blob/develop/src/NzbDrone.Core/Download/Clients/QBittorrent/QBittorrentProxyV2.cs>
- <https://github.com/seerr-team/seerr>
- <https://github.com/home-assistant/core>
- <https://docs.immich.app/install/docker-compose>
- <https://recyclarr.dev/wiki/yaml/config-reference/custom-formats/>
- <https://buildarr.github.io/plugins/sonarr/configuration/profiles/release>
