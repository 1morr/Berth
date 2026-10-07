# S4 撤回：實跑筆記（2026-10-07，main 107708c，image berth:audit-107708c）

截圖目錄：`docs/research/usability-audit-2026-10-07/s4-NN-*.jpeg`（36 張）。環境：`C:\Users\Roxy\berth-audit2`，三個套件內服務；使用者自己的 qBittorrent = `s4-qbittorrent`（v5.2.3，46080，掛同一個 DATA_ROOT 於 /data）。

## 基線（動作前）

| 物件 | 狀態 |
| --- | --- |
| 套件內 qBittorrent | 分類 berth-anime / berth-movies / berth-tv（路徑 /data/torrent/complete/<x>，沒有 incomplete 子路徑）；1 個 torrent（Night of the Living Dead 1968，berth-movies，stalledUP 做種）；白名單 172.28.0.2/32；全域 save_path=/downloads |
| s4-qbittorrent | 0 分類、0 torrent、無白名單 |
| Jellyfin | API key「Berth」×1；媒體庫 Anime / Movies / TV（/data/library/*）；伺服器名 Berth；使用者只有擁有者 |
| Prowlarr | 6 站（ACG.RIP、Anime Tosho、dmhy、Mikan、The Pirate Bay、YTS）；forms 登入 = 擁有者帳號；無 tag / 下載器 / application / proxy |
| Berth | 精靈完成；3 條 Route 6/6；1 個 Job（已入庫） |

## 步驟 1：完成後回精靈

| 動作 | 畫面 | 截圖 |
| --- | --- | --- |
| 開 `/setup`（未登入） | 被帶到 `/login?redirect=%2Fsetup`；登入後落在 `/settings/jellyfin`。已登入再開 `/setup`、`/setup?step=2` 都被導向 `/settings/jellyfin`。沒有任何一句話說「精靈已完成，設定在這裡」，只是默默轉走 | — |
| 設定頁 Jellyfin | 標題「Jellyfin 設定」。健康卡、「位址與憑證」（套件內可選、「既有」disabled，說明「擁有者是這一台 Jellyfin 上的帳號，所以來源換不了；同一台換了位址可以在這裡改，另一台伺服器會被擋下」）、「Jellyfin 對外網址」。可改：位址（同一台）、對外網址。不能改：來源、擁有者。沒有「重新登入換 API key」鍵（只在 key 被刪時才提示） | s4-01 |
| 設定頁 qBittorrent | 健康、位址與憑證（套件內 / 既有可切）、介面登入（改帳密，預設沿用 Jellyfin 帳密，要打一次 Jellyfin 密碼）、磁碟空間門檻 | s4-02 |
| 設定頁 媒體庫路徑 | Route 清單（狀態、媒體庫、分類、寫入目標、n 筆下載、n 個入庫檔案）、每條「管理」（改名、啟用/停用、儲存＝重跑檢查、重新檢查、刪除；有下載/檔案指著就刪不得，只給「停用這條 Route」）、「新增 Route」 | s4-03 |
| 設定頁 Prowlarr | 健康、位址與憑證（套件內/既有）、索引站清單（逐站搜、移除）、加站（推薦、其他公開站 78）、介面登入。**沒有「不用 Prowlarr」** | s4-04 |
| 設定頁 TMDB | 換 key＋測試（新的測得過才換）。沒有「移除 key」 | s4-05 |

## 步驟 2：qBittorrent 套件內 → 既有（s4-qbittorrent）

動作數：點「既有」radio（1）→（選擇性）點「移除 2 個空的 berth- 分類」（1）→ 填位址、帳號、密碼（3 次輸入，1 組密碼）→ 點「測試連線」（1）。合計 6 次互動、3 次輸入。位址用 `http://host.docker.internal:46080`。

選了「既有」（還沒填位址）當下就出現的換台框，逐字：
- 「選了既有，套件內那一台用不到了：把 .env 的 COMPOSE_PROFILES 換成第一行（qbittorrent 不在裡面），再用第二行停掉已經在跑的那一台——只改 COMPOSE_PROFILES 再 docker compose up -d 停不掉它。忘了也不致命。」＋兩個可複製指令 `COMPOSE_PROFILES=jellyfin,prowlarr`、`docker compose stop qbittorrent`
- 「換一台 qBittorrent：這一頁要重做，媒體庫與路徑也要重新檢查——分類要建在新的那一台上。」
- 「Berth 在原本那一台建的，換了之後留在那裡：」分類 berth-anime「空的」、分類 berth-movies「1 個 torrent」、分類 berth-tv「空的」、「Berth 設的介面登入　audit-owner」，按鈕「移除 2 個空的 berth- 分類」（s4-06）
- 按下移除：訊息「空的 berth- 分類已移除。」，清單剩 berth-movies（1 個 torrent）。宿主實查：舊 qBittorrent 剩 berth-movies 一個分類、torrent 不動（s4-07）。**沒有任何一個鍵移除介面登入或白名單**（白名單 172.28.0.2/32 沒被列出）。
- 測試連線後：「qBittorrent 連上了：連線測試通過」，版本 v5.2.3；「介面登入」整區消失（既有不管登入）（s4-08）。Berth 在新那台加了一個探測 torrent 並刪掉（log 可見 add / info / delete）；新那台**沒有被建分類**（0 分類）。

換台之後 Berth 的各處：
- 健康頁：BTH 2 qBittorrent「已繫上」位址 http://host.docker.internal:46080；**BTH 3 頭部仍寫「已繫上　3 條 Route」，下方三條 Route 卻都是「尚未檢查」**，沒有「6 / 6 通過」（s4-09）。
- 媒體庫路徑設定頁：三條都「尚未檢查」，展開後每條纜繩「尚未執行」。沒有「全部重新檢查」，要每條各展開按「重新檢查」（共 6 次點擊）。重新檢查才在新那台建 `berth-<x>` 分類並寫探測檔；六條纜繩全「已完成」，健康頁回到 6/6（s4-12、13、14）。
- 做種中的電影：仍在**舊** qBittorrent 的 berth-movies，Berth 沒有任何提示（不是「無主 torrent」，因為 Berth 已經不看舊那台）。Job 頁仍是「已入庫 1」，Job 展開的時間線與 info hash 完全不變，沒說「做種的 torrent 在另一台」。媒體庫頁、Jellyfin 播放不受影響（硬鏈接在 /data/library）。新那台看不到這個 torrent，所以沿用既有那台的做種要使用者自己處理（s4-10、11）。
- Berth 的 poll log：換台後仍對新那台查 hash（探測 torrent 的 hash），沒有去找已入庫 Job 的 hash。

## 步驟 3：換回套件內

動作：設定 qBittorrent 頁，目前是既有時 radio 被收起 → 點「改位址或憑證」（1）→ 點「套件內」（1）→ 換台框 → 點「移除 3 個空的 berth- 分類」（選擇性，1）→ 點「改用套件內的那一台」（1）。4 次點擊，0 次輸入（免密碼）。

換台框（s4-16）：「換一台 qBittorrent：Berth 沒改過你那一台的偏好；這一頁要重做，媒體庫與路徑也要重新檢查——分類要建在新的那一台上。」「Berth 在原本那一台建的，換了之後留在那裡：」berth-anime / berth-movies / berth-tv 全「空的」（s4-16），按「移除 3 個空的 berth- 分類」，成功後 s4-qbittorrent 回到 0 分類（宿主實查）。
換回後（s4-17、18）：
- 套件內那台缺的 berth-anime / berth-tv **自動被重建**（宿主實查三個分類回來，路徑相同）；做種的電影原封不動。
- 介面登入區回來，「目前的帳號是 audit-owner」（Berth 記著雜湊；先前沒被清）。不必重打密碼。
- 健康頁 Route：**自動重跑，但是 5 / 6**；展開：「qBittorrent 讀得到 Berth 寫的檔案　尚未執行」其餘「已完成」，頭部卻是「已繫上」。（與 2026-10-06 審計 #11 同一件：週期檢查迴圈不跑探針那一條。）
- 舊 Job 沒有「回來」，因為它從頭到尾沒消失；Job 與時間線都不變。

## 步驟 4：移除 Prowlarr（README 的做法）

動作（使用者端）：`.env` 把 COMPOSE_PROFILES 改成 `jellyfin,qbittorrent` → `docker compose up -d`（輸出：只列 Running，**沒有停掉 prowlarr**，與 README 一致）→ `docker compose stop prowlarr`。

Berth 的反應（先不按任何鍵看，再「立即重測」）：
- 健康頁（s4-19）：BTH 4 變「阻擋」，卡片「阻擋　Prowlarr　http://prowlarr:9696　最後成功 55 秒前　上次檢查 2 秒前　連續失敗 1 次」「這一輪的健康檢查沒通過：Prowlarr 沒有回應，或回了錯誤。」「修正」：「這個服務是這套 compose 起的，所以先確認那個容器還在跑…」三條指令 `docker compose ps prowlarr` / `up -d prowlarr` / `logs --tail=50 prowlarr`。**修正指令教使用者把他剛移除的服務再起來；沒有「我不用它了」的選項。**
- 設定 → Prowlarr（s4-20）：頂部健康卡「阻擋」，但「位址與憑證」區的綠色狀態列仍是「Prowlarr 連上了：連線測試通過」「連上了　prowlarr:9696　測試結果　連線測試通過」（陳舊的），同頁「索引站」區塊顯示「失敗：讀不到這一台 Prowlarr 的站清單，所以說不出它有幾站。Prowlarr 的主機名解不到：它的容器沒在跑、不在這套 compose 裡，或位址打錯了。」。同一頁一邊說連上、一邊說讀不到。沒有「不用 Prowlarr」或「移除」的鍵；可選「既有」換位址（要 API key），也沒有空值出口。
- 作品頁搜 torrent（s4-21，/media/movie:19185 按「搜尋」）：「連不上　連不上索引站。可能是那個容器沒起來，或位址填錯了。　GET /api/v1/indexer: host does not resolve　前往設定：Prowlarr　找到 0 筆，0 個關鍵字沒問到。」帶出原始 API 路徑字串。
- 待處理（/issues）：沒有開 Prowlarr 的項目；主導覽的「健康」沒有紅點或數字。
- 使用者要讓 Berth 不再把它當紅燈的路：目前找不到。只有 ①把 Prowlarr 再起來 ②在設定頁改指向另一台既有的 Prowlarr（要 API key）。精靈頁 4 有「之後再說」，但精靈完成後不再出現，而且那是「還沒接」不是「不接」。（沒有實測把 Prowlarr 的位址改成空值或錯值會怎樣，畫面上沒有可填空的欄位。）

恢復：`.env` 加回 prowlarr、`docker compose start prowlarr`、`docker compose up -d`。Berth **自己恢復**，但要等下一輪 5 分鐘週期：Prowlarr 22:31:35 起，Berth 在 22:36:02 的下一輪才對 `/api/v1/system/status` 與 `/api/v1/indexer` 回 200，期間（約 4.5 分鐘）頁面仍是「阻擋」（我只在 22:33 看過一次仍阻擋；沒有重測）。重啟 Prowlarr 後沒有任何自動提示「再按一次立即重測」。

## 步驟 5：重裝（保留服務 config，搬走 config/berth）

操作：`docker compose stop berth` → `mv config/berth config/berth.s4-prev` → `docker compose up -d berth`（容器 healthy，alembic 從頭跑 migration）。

重新登入：session cookie 失效，要重登一次（用擁有者帳密，因為 Berth 沒有自己的帳號）。精靈 `/setup` 重新開頭（`/setup?step=1`）。

| 頁 | 表單變成什麼（逐字重點） | 互動次數／輸入 | 截圖 |
| --- | --- | --- | --- |
| 1 Jellyfin | 先要選「套件內／既有」（和第一次一樣）。選「套件內」後自動測連線：「Jellyfin 連上了：已經有管理員」，頁標題變「用你的 Jellyfin 管理員登入」（不是建立），只有「帳號／密碼／登入」；沒有「同時設 qBittorrent / Prowlarr 介面登入」的勾（因為不是新建）。登入後：「擁有者：audit-owner …」＋「將會做什麼　不改這台 Jellyfin 的任何設定 / 建立 API key『Berth』」 | radio 1、輸入 2（帳號＋密碼，1 次密碼）、登入 1、下一個泊位 1 = 4 次互動 | s4-22、23、24 |
| 2 qBittorrent | 選「套件內」→ 自動測連線，並顯示「qBittorrent WebUI 的帳號：audit-owner　更換登入　已經是這樣」「WebUI 登入　audit-owner　已完成」「這個泊位的事做完了。WebUI 登入設好了；Berth 沒有改這台 qBittorrent 的全域偏好」。**不用重打密碼** | radio 1、下一個 1 = 2 | s4-25、26 |
| 3 媒體庫路徑 | 「媒體庫清單　3 個已建立」，**不自動開始**（因為清單裡的媒體庫已存在，不算「第一次來」），要按「建立並檢查」；按下後 3 條 Route 6/6；分類「建或核對…（已經有的不改路徑）」。沒有新增重複的 Jellyfin 媒體庫（仍 3 個）、分類（仍 3 個） | 按鈕 1 + 下一個 1 = 2；等待約 25 秒 | s4-27、28 |
| 4 Prowlarr | 進頁時右側摘要先顯示「接法　你自己的 Prowlarr　位址　—　API key　尚未取得　已加入　0」（還沒選就顯示「你自己的」，與下一步的選擇矛盾）。選「套件內」→ 測試通過、「索引站 6」「已加入 6 站」、「Prowlarr 介面登入：必填　Prowlarr 介面的帳號：audit-owner　已經是這樣」。沒有重複加站（仍 6 站）。「推薦站」區塊有「之後再說」 | radio 1、下一個 1 = 2 | s4-29、30 |
| 5 TMDB | 空表單「還沒填」（key 存在被搬走的 berth.db，所以丟了）；要重新貼 key＋「測試 TMDB」 | 輸入 1（key）、測試 1、下一個 1 = 3 | — |
| 6 完成 | 「五個泊位都走過了…」，列 3 條 Route「已繫上」、各服務自己的介面連結：Jellyfin「用擁有者 audit-owner 登入，與 Berth 同一組。」；qBittorrent / Prowlarr「帳號 audit-owner，密碼是這一台原本就有的那一組：這一輪精靈沒有設它。」；結果：Route 數 3、跳過「沒有」。**完全沒提到 media 庫裡已經有入庫檔案、Berth 的帳本是空的** | 完成設定 1 | s4-31 |

總計：6 頁、約 14 次互動、**密碼只打 1 次（頁 1）**、另貼 1 次 TMDB key（Berth 重裝等於丟掉 TMDB key）。等待時間約 1 分鐘。

重裝之後的外部服務：
- Jellyfin API key：仍是 **1 把**「Berth」（建立時間 13:39，沒有新增）→ Berth 找回舊的同名 key 重用，沒重複。
- Jellyfin 媒體庫：3 個，沒重複；qBittorrent 分類：3 個，沒重複；Prowlarr：6 站，沒重複；電影 torrent 原封不動；磁碟上硬鏈接與下載目錄不變。
- `config/berth.s4-prev` 留在原處（舊的 berth.db），新舊並存沒有衝突。

之前入庫的那部電影在新 Berth：
- 媒體庫頁（Movies）：看得到「活死人之夜 MOVIE · 1968」，有「在 Jellyfin 開啟」「標為已看」（來自 Jellyfin 疊加，不靠帳本）（s4-36）。
- 作品頁 /media/movie:10331（s4-33）：有「在 Jellyfin 看（開新分頁）」「標為已看」，但「檔案與版本」寫「**還沒有任何檔案入庫。**」；「入庫到　尚未指定」；「資料夾將會是　Night of the Living Dead (1968) [tmdbid-10331]」。畫面上矛盾：一邊能播，一邊說沒入庫；使用者再搜一次就可能重複下載（沒有提示）。
- 下載頁：「還沒有送過任何下載。」整個 Job 歷史消失（s4-32）。
- 待處理（s4-34、35）：新出一件「無主 TORRENT　Night Of The Living Dead (1968) [BluRay] [720p] [YTS.AM]　qBittorrent 上有 Berth 不認得的 torrent · 偵測於 2026/10/7 下午10:40:28」，展開只有 hash，有「認領並建立下載」與「忽略」。這是唯一的修復路徑；**畫面沒提 `berth rebuild-ledger`，也沒提「這是重裝造成的」**，按鈕沒說按了會做什麼（沒有按，未驗證）。
- `docker compose exec berth berth rebuild-ledger --help` 存在：`usage: berth rebuild-ledger [-h]`，沒有 dry-run、沒有其他選項；子命令說明「Grow the ledger back from the library: every file the ledger does not know is matched to complete by inode and read back through the naming templates. Files that do not match become unmanaged_library_file issues. Deletes nothing.」README「帳本重建」節說「只加不減」「重跑冪等」「服務開著也能跑」。因為它會寫資料庫、沒有 dry-run，**我沒有執行**。

## 還原實測表（Berth 改過的東西能不能還原）

欄位：換台＝qBittorrent 套件內→既有；移除服務＝Prowlarr 從 compose 拿掉；重裝＝搬走 config/berth 後重跑精靈。

| 物件 | 在哪 | 換台之後 | 移除服務之後 | 重裝之後 | Berth 裡有路可以撤嗎 | 使用者自己去哪撤 |
| --- | --- | --- | --- | --- | --- | --- |
| `berth-*` 分類（建在 qBittorrent） | 舊/套件內 qBittorrent | 留在舊那台；換台框列出「空的」「n 個 torrent」，一鍵移除空的（實測 OK，不動有 torrent 的） | —（Prowlarr 與分類無關） | 保留，精靈頁 3 核對、不重複 | 只有換台那一個框可以移除空的；沒有單獨入口、有 torrent 的移不掉 | qBittorrent 刪分類（torrent 先移走） |
| 分類在新那台（Route 重檢查時建） | 新 qBittorrent | 要到「媒體庫路徑」逐條按「重新檢查」才建（此前新那台 0 分類） | — | — | 只有換台框（再換走時列出），單獨沒有 | qBittorrent 刪分類 |
| 做種中的 torrent | 舊 qBittorrent，berth-movies | 留在舊那台，Berth 不追、不提示 | — | 變成 /issues 的「無主 TORRENT」，可「認領並建立下載」 | 無（換台時換台框只寫「1 個 torrent」） | qBittorrent 手動處理 |
| 硬鏈接與下載目錄 /data/torrent/complete/*、/data/library/* | 宿主 DATA_ROOT | 留在 | 留在 | 留在 | 無（Berth 沒有刪除全部或解除管理的功能；Route 有檔案時刪不得） | 手動刪資料夾（先確認 Jellyfin 沒在用） |
| qBittorrent WebUI 登入（audit-owner） | 套件內 qBittorrent 偏好 | 留在套件內那台；換台框列出「Berth 設的介面登入」但不能移除 | 無關 | 保留；精靈顯示「已經是這樣」不必重打 | 只能「更新登入」蓋過 | qBittorrent 偏好 |
| qBittorrent 免密白名單 172.28.0.2/32 | 套件內 qBittorrent 的 qBittorrent.conf | 留在，換台框沒列 | 無關 | 留在 | 無 | 編輯 `config/qbittorrent/qBittorrent/qBittorrent.conf`（WebUI\AuthSubnetWhitelist*） |
| qBittorrent 全域偏好 | — | Berth 沒寫（save_path 仍 /downloads，autoTMM 仍 false） | — | — | — | — |
| Jellyfin API key「Berth」 | Jellyfin | Berth 重裝時重用同名 key，不新增 | 無關 | 仍 1 把 | 無 | Jellyfin 控制台 → API 金鑰 |
| Jellyfin 媒體庫 Movies/TV/Anime（套件內由精靈建） | Jellyfin | 無關 | 無關 | 保留，精靈不重複建 | 無（Berth 內鎖住） | Jellyfin 刪媒體庫 |
| Jellyfin 管理員帳號、伺服器名「Berth」、語言地區 | Jellyfin | 無關 | 無關 | 保留 | 無 | Jellyfin 使用者管理、控制台「一般」 |
| Prowlarr 6 站 | Prowlarr | 無關 | Prowlarr 容器停了，站還在它自己的 config | 保留，頁 4 顯示「已加入 6 站」不重複 | 設定→Prowlarr 每站「移除」（套件內可，既有不行）；移除整個服務沒有入口 | Prowlarr 刪站 |
| Prowlarr 介面登入（forms, audit-owner） | Prowlarr config.xml | 無關 | — | 保留「已經是這樣」 | 只能「更新登入」蓋過 | Prowlarr 設定 → 一般 |
| TMDB key、各服務 API key、Route、Job/帳本、RSS | Berth 的 `config/berth/berth.db` | Route 的 `berth-*` 分類要重建 | 見下 | **全丟**（搬走即丟），TMDB 要重貼；Job 歷史消失；帳本空 | — | 備份 `config/berth`；舊檔可 `berth.s4-prev` 留作參考，沒有匯入工具 |
| Route 狀態 | Berth DB | 換台後「尚未檢查」，6 次點擊重檢 | Prowlarr 不影響 | 精靈頁 3 重建 | — | — |
| 探測 torrent / 探測檔 | qBittorrent、/data | 自清（實測有 add + delete，無殘留；沒測 Berth 中途崩潰） | — | 自清 | 自清 | — |

## 「完全不用 Berth 了」要手動清的清單

Berth 沒有「卸載」或「清除我在各服務留下的東西」的入口（設定頁 5 頁、/health、/issues 都沒有）。使用者要自己：

1. 停掉並移除 Berth 容器；保留或刪除 `${CONFIG_ROOT}/berth`（含 berth.db，內有 TMDB key、各服務 API key）。
2. **Jellyfin**
   - 控制台 → API 金鑰：刪除「Berth」。
   - 媒體庫：Movies / TV / Anime（套件內由精靈建）刪或保留；若要保留，檔案已經被硬鏈接入 /data/library/*。
   - 伺服器名稱「Berth」、管理員帳號（擁有者）、語言地區：視情況在控制台改。
   - （若是既有 Jellyfin）精靈替既有媒體庫多加的 `/data/library/<資料夾>` 路徑：媒體庫設定移除。
3. **qBittorrent**
   - 刪 `berth-anime`、`berth-movies`、`berth-tv` 分類（torrent 先移走或刪除；做種中的會留在）。
   - WebUI 登入（audit-owner＋密碼）：偏好改回自己要的。
   - 免密白名單 `172.28.0.2/32`（套件內那台）：`qBittorrent.conf` 的 `WebUI\AuthSubnetWhitelist` 與 `...Enabled`，或刪掉整個套件內那台。
   - 全域偏好：Berth 沒寫，不必處理。
4. **Prowlarr**
   - 刪 Berth 加的站（套件內 6 站：全留或逐站刪；Berth 沒記哪些是它加的在畫面上，只有舊 DB 的 `SetupIndexer.added_sites`）。
   - 介面登入（forms、audit-owner）：Prowlarr 設定 → 一般。
   - 掛載的 API key：套件內由 compose 掛載，無需處理。
5. **宿主目錄**：`DATA_ROOT` 下 `torrent/incomplete`、`torrent/complete/{movies,tv,anime}`、`library/{movies,tv,anime}`；入庫的檔案是硬鏈接，兩邊刪一邊另一邊還在。
6. 如果 compose 套件整個不要：`docker compose down` 加刪 `CONFIG_ROOT` 與 `DATA_ROOT` 之前先確認要留的媒體。

## 問題清單

編號依序；「影響」是我的判斷，優先序交給主對話。

1. **健康頁 BTH 3 頭部「已繫上　3 條 Route」與下方 3 條「尚未檢查」並存**（換 qBittorrent 之後）。重現：設定→qBittorrent 選既有、測試連線成功，開 /health。截圖 s4-09。原文：BTH 3「已繫上」；Route「尚未檢查」。影響：使用者看到綠燈以為沒事，但新那台沒有分類，送單會失敗（沒有實測送單）。
2. **換台之後 Route 要逐條手動重新檢查**：「媒體庫路徑」沒有「全部重新檢查」，三條要展開三次按三次（6 次點擊）；換台框只說「媒體庫與路徑也要重新檢查」沒說去哪、怎麼做。換台成功畫面（s4-08）也沒有「下一步：到媒體庫路徑重新檢查」的連結。
3. **換台框沒提做種中的 torrent 會怎樣**：只寫「berth-movies　1 個 torrent」。使用者看不出：Berth 不會再追它、Job 仍顯示已入庫、新那台沒有它；Job 詳情（s4-11）沒有一句「這個 torrent 在原本那一台」。
4. **介面登入、免密白名單留在舊那台，換台框只列介面登入、不能移除**；白名單沒列。使用者看不到要自己改 qBittorrent.conf 的那一條。
5. **移除 Prowlarr 沒有出口**：設定頁沒有「我不用 Prowlarr 了」；健康頁「修正」只教你把它起來（`docker compose up -d prowlarr`）；健康頁 BTH 4 一直「阻擋」。使用者只能讓 Berth 一直紅。（第一次接觸者從 README 與設定頁都找不到這條路；精靈的「之後再說」只在精靈）。s4-19、20
6. **設定→Prowlarr 同頁前後矛盾**（Prowlarr 停掉時）：「Prowlarr 連上了：連線測試通過」「測試結果　連線測試通過」與「索引站　失敗：讀不到…」、頂部「阻擋」並存（陳舊的綠色測試結果沒有加時間）。s4-20
7. **Prowlarr 回來後恢復延遲最多 5 分鐘**，期間仍「阻擋」，沒有「Prowlarr 好像回來了」的提示；使用者要自己按「立即重測」。（實測約 4.5 分鐘。）
8. **作品頁搜尋失敗顯示原始 API 字串**：「GET /api/v1/indexer: host does not resolve」。s4-21
9. **重裝後作品頁自相矛盾**：有「在 Jellyfin 看」「標為已看」，卻寫「檔案與版本　還沒有任何檔案入庫」，「入庫到　尚未指定」。使用者可能重複搜尋下載同一部。s4-33
10. **重裝後完全沒有指向 `berth rebuild-ledger` 的提示**：精靈完成頁（s4-31）「跳過　沒有」；/issues 只出一件「無主 TORRENT」，按鈕「認領並建立下載」不說會做什麼，也沒說這是重裝的後果。下載頁「還沒有送過任何下載」（s4-32）。README 的 `rebuild-ledger` 節在「帳本沒了」的情況下，但精靈沒告訴使用者「偵測到 /data/library 有 Berth 不認得的檔案，要不要重建帳本」。我沒有執行該指令，所以不知道它能不能補回作品頁的檔案列。
11. **重裝丟掉 TMDB key 與所有 Job 歷史，精靈沒有預警**：頁 1 起就沒有「偵測到 config 是新的，但三個服務是已經初始化的」的說明；頁 5 是空表單。使用者的「重裝」其實就是「搬走 config/berth」（README〈秘密與備份〉說備份 Berth 就是複製 `config/berth`，沒說重裝的後果）。
12. **精靈頁 4 進頁時右側摘要「接法　你自己的 Prowlarr」**，使用者尚未選擇。（前一輪審計可能已記；這輪確認仍在。）s4-29
13. **精靈頁 3 重裝後不自動開始**（因為清單已存在，不是「第一次來」），與頁 1、2、4 的「選了就自動測」不一致；使用者要多按一次「建立並檢查」。這是預期行為（頁文說明有），但第一次接觸者可能以為卡住。
14. **健康頁 Route 5 / 6（探針那一條「尚未執行」）卻「已繫上」**：換台回套件內後由週期迴圈重跑的結果（s4-18）；2026-10-06 審計 #11 的同一件，未修。
15. **`/setup` 在精靈完成後無聲導向 `/settings/jellyfin`**：沒有說明。使用者以為要「重跑精靈」時只看到 Jellyfin 設定頁。（重跑精靈的唯一方式是搬走 DB，沒有任何文件寫這件事，README 只提「重裝」）。
16. **qBittorrent 換台框的位置**：它在選「既有」後、填位址之前就出現，並且列的是「舊那一台」的現況，但同一頁後面的位址欄還沒填；「測試連線」之前如果按「移除 2 個空分類」就已經改動舊那台（我實測：按了之後 Berth 的 Route 仍指著那些分類，直到換台完成）。若使用者按了移除又取消換台，Route 指著不存在的分類（我沒有測取消後的狀態；健康迴圈會不會重建也沒測）。

## 做得好的

- 換台確認框真的列出 Berth 留在舊那台的東西（分類各有幾個 torrent、介面登入），而且「移除空分類」按鈕實測有效、數字準（2 個空、1 個有 torrent）、只動空的、有 torrent 的不碰；換回後再列、再移除也一致。
- 沒有任何一個動作改到 qBittorrent 全域偏好（save_path、autoTMM 全程不變）。
- 重裝（保留各服務 config）在三個服務上都冪等：Jellyfin API key 沒新增、媒體庫沒重複、分類沒重複、Prowlarr 站沒重複、qBittorrent / Prowlarr 介面登入「已經是這樣」不重打密碼；密碼全程只打 1 次。
- 重裝後 Berth 自己偵測到 berth-movies 裡有它不認得的 torrent，並放進 /issues 提供「認領並建立下載」。
- 換回套件內時缺的分類自動重建、介面登入記著不必重打。
- 換台時探測 torrent 自清（add 後 delete，宿主上無殘留）。
- 移除 Prowlarr 時，健康頁給出可複製的排查指令、錯誤原因寫「主機名解不到」；Prowlarr 回來後 Berth 自己恢復，不需重啟。
- 設定頁 5 頁每頁都有說明「能做／不能做」，Jellyfin 頁說清楚來源為什麼鎖住。

## 沒跑到／未驗證

- 沒有執行 `berth rebuild-ledger`（無 dry-run、會寫 DB），所以不知道它在重裝後能否補回作品頁的檔案列與 Job；也沒按「認領並建立下載」，不知道它做什麼。
- 沒有測：換台途中取消（按了「移除空分類」之後選擇「取消」，Route 與分類的狀態）；既有 qBittorrent 上 Berth 建的分類被使用者自己刪掉之後的反應；換台後直接送單（新那台沒分類時）是否失敗、錯誤訊息；移除 Prowlarr 後把位址改成空值的可能性；Prowlarr 在 `docker compose down` 之後再 `up` 的情形。
- 重裝只測了三個都選「套件內」；沒測重裝時選「既有」（若 Jellyfin 是既有，頁 3 會不會重複加路徑）。
- 「Berth 如何找回舊的 Jellyfin API key」只看到結果（仍 1 把、同建立時間），沒有看 Berth 的原始碼或 log 確認是用名稱找回還是 Jellyfin 回傳重複。
- 帳號／密碼：全程用憑證小伺服器填寫，沒寫進任何輸出；s4-qbittorrent 的密碼在 `C:\Users\Roxy\berth-audit4-existing\CREDENTIALS.md`。

## 環境恢復

三個服務套件內、精靈完成；`COMPOSE_PROFILES=jellyfin,qbittorrent,prowlarr`；Prowlarr 在跑；Berth 是重裝後的新 DB（舊的在 `config/berth.s4-prev`，未刪）；/issues 還有 1 件「無主 TORRENT」（我沒處理）；`s4-qbittorrent` 已 `docker stop`、目錄 `C:\Users\Roxy\berth-audit4-existing`；Berth 帳本與 Job 歷史已被重裝清空（電影檔與 torrent 仍在）。
