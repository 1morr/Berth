# S3 混搭筆記（既有 Jellyfin + 套件內 qBittorrent / Prowlarr）
日期 2026-10-07，Berth main 107708c（image berth:audit-107708c），瀏覽器 playwright 1280x900，zh-Hant。

## 環境準備
- s3-jellyfin：linuxserver jellyfin:version-12.1ubu2604，46096:8096，掛 ./config、./media/movies、./media/tv，起初不掛 /data。
- Jellyfin 初始精靈用 API 跑（Startup/Configuration、User、RemoteAccess、Complete），建管理員 s3admin、媒體庫「我的電影」(movies,/movies)、「我的劇集」(tvshows,/tv)。before 快照：s3-jf-before.txt。
- 審計工具事故：我的密碼 helper 與 keysrv 最初用的 18997 埠，已被另一個 listener 佔用（疑似其他並行 agent 的服務；我 taskkill 了兩個 PID 35428/59664，其中一個可能不是我的）。
- Berth 重裝：stop berth、config/berth -> config/berth.s3-prev、up -d berth。精靈從頭來（URL /setup?step=1），qBittorrent / Prowlarr 的 config 保留（S1 留下的）。

## 頁 1 Jellyfin 選既有
- 進頁：標題「先選 Jellyfin 是哪一台」，兩個 radio 都不預選；「既有」卡內文：條件（同主機、DATA_ROOT 掛 /data、能硬鏈接）、要先有對應類型媒體庫、版本下限 12.0。
- 點「既有」後立即出現：「選了既有，套件內那一台用不到了：把 .env 的 COMPOSE_PROFILES 換成第一行（jellyfin 不在裡面），再用第二行停掉已經在跑的那一台——只改 COMPOSE_PROFILES 再 docker compose up -d 停不掉它。忘了也不致命。」+ 兩行可複製：`COMPOSE_PROFILES=qbittorrent,prowlarr`、`docker compose stop jellyfin`。與 README 一致（README 的例子是 prowlarr）。
- 問題：這兩行只在「測試連線」之前（頁上選了既有、還沒登入）看得到；登入成為擁有者之後整塊消失，進到下一頁就看不到了。使用者若當下沒做，到頁 6 完成頁沒有再提醒（完成頁也沒說 berth-jellyfin 還在跑）。
- 兩行沒說在哪個目錄執行（README 說 cd deploy）。
- 位址欄只有「位址」一格，placeholder http://192.168.1.10:8096；沒提示在 Docker Desktop 該填 host.docker.internal（填 localhost 會連到 Berth 自己；S2 已測）。我直接填 host.docker.internal:46096，連上：「Jellyfin 連上了：已經有管理員」，版本 12.1.0。
- 右欄「將會做什麼」：寫「改動：不改這台 Jellyfin 的任何設定」，同時又列「建立 API key「Berth」」；頁 3 還會替媒體庫加路徑。三者說法相互緊張（「任何設定」對 API key / 媒體庫路徑嚴格說不成立）。
- 登入：我第一次送出時密碼欄是空的（我的 helper 取到空字串）→ 回「Berth 不收沒有密碼的 Jellyfin 帳號當擁有者：…先在 Jellyfin 的「控制台 → 使用者」替這個帳號設一組密碼」。問題：欄位根本沒填也得到這句，原因被誤判成帳號沒有密碼（誤導）。（我是 Jellyfin 帳號有密碼、只是沒填。）
- 第二次填對 → 「擁有者：s3admin」。動作：點既有、填位址、測試連線、填帳號、填密碼、登入、前往下一個泊位 = 7 動作、3 次輸入（位址、帳號、密碼）。
- 做得好：選了才連、測過才顯示登入欄；成功後解釋「回頭看」。

## 頁 2 qBittorrent 套件內
- 點「套件內」→ 立即連上；「已經是這樣｜WebUI 登入 audit-owner」「已完成：這個泊位的事做完了」。沒有問密碼（README 說「問一次」，因為 config 保留所以不問，符合「那一台已經設過登入就不強迫再設」）。
- 問題：WebUI 登入名是 S1 的 audit-owner，與這輪的擁有者 s3admin 不同；使用者（換了新 Berth 資料的情境）不會知道 qBittorrent 的帳號，頁面只寫帳號沒寫密碼是什麼。完成頁寫「帳號 audit-owner，密碼是這一台原本就有的那一組：這一輪精靈沒有設它」——誠實但沒給出路（若忘了密碼要怎麼辦？沒提示「更換登入」可重設，但頁上有「更換登入」鈕）。
- 動作 2（點套件內、前往下一個），0 次輸入。
- 進頁右欄「將會做什麼」同時列「套件內」與「既有」兩行，還沒選就把兩種都攤開。

## 頁 3 媒體庫路徑
- 進頁列出 Jellyfin 的兩個媒體庫（劇集、電影），一個一個 checkbox，沒預勾。勾「我的電影」→ 出現「寫入目標」radio：`/movies`（既有路徑）與 `/data/library/我的電影`（預選，「新的 Berth 路徑：按「建立並檢查」時加到這個媒體庫，原本的路徑不動」）。預設是新的 Berth 路徑，不寫進既有資料夾。
- 「按下之後會」清單說明三件事：加路徑到 Jellyfin（不重新掃描）、建 berth- 分類、探測檔+硬鏈接。透明度好。
- Berth 路徑名 = /data/library/<媒體庫名>，這裡名字是中文「我的電影」，所以磁碟上出現 data/library/我的電影、data/torrent/complete/我的電影、qBittorrent 分類 `berth-我的電影`。與 S1 的 data/library/movies 不撞（不同資料夾），S1 入庫的《Night of the Living Dead》在這個 Jellyfin 看不到。
- 第一次按「建立並檢查」→ 紅：「「我的電影」沒加上 Berth 路徑／Jellyfin 看不到 /data/library/我的電影：它沒掛 /data。Berth 建好了目錄、在裡面寫了一個檔，Jellyfin 說它看不到；這一次建的目錄已經收回（原本就在的不動）。在你原本那一份 compose（或 docker run 指令）的 Jellyfin 上多加一條掛載：berth 那一份 .env 的 DATA_ROOT 掛在 /data（${DATA_ROOT} 換成那個值）。原本的掛載不用動。重建它之後再按一次：」+ 兩種格式（compose `jellyfin: volumes: - ${DATA_ROOT}:/data` 與 docker run `-v ${DATA_ROOT}:/data`）。
- 卡點：
  1. `${DATA_ROOT}` 要自己替換；我的 .env 是相對路徑 `./data`，直接貼進另一份 compose 會變成「那份 compose 旁邊的 ./data」——要換成絕對路徑，畫面沒提這個陷阱（.env.example 預設就是 ./data，第一次試跑的人最容易踩）。我換成 C:/Users/Roxy/berth-audit2/data。
  2. 「jellyfin: volumes: - ${DATA_ROOT}:/data」這行是壓平成一行的 YAML 片段，複製後得自己拆行縮排。
  3. 只講 Jellyfin；qBittorrent 在套件內所以沒問題。
- 補掛載：改 s3-jellyfin 的 compose + `docker compose up -d`（Recreate）。Jellyfin 重啟約 10 秒。回畫面再按「建立並檢查」→ 一次全綠，6/6。 (注意 Jellyfin 重建後 /data 裡 library、torrent 看得到)
- 補一個：第一次失敗已建了 qBittorrent 分類（berth-我的電影），第二次顯示「已經是這樣」。好。
- 接著勾「我的劇集」（寫入目標：/tv 或新的 /data/library/我的劇集），按建立並檢查 → 兩條 Route 6/6。展開明細逐條檢查，含 hardlink 的 dev / inode / free。
- 動作：勾電影、按建立（紅）、[外部：改 compose、重建]、按建立（綠）、展開明細、勾劇集、按建立、前往下一個 = 約 7 次點擊，外加外部 2 步。0 次輸入。

## 頁 4 Prowlarr 套件內
- 點「套件內」→ 約 3 秒內連上，「已加入 6 站」（ACG.RIP、Anime Tosho、dmhy、Mikan、The Pirate Bay、YTS；S1 留下的），每站標語言，有「搜尋全部」、每站「搜尋」「移除」。介面登入「已經是這樣 audit-owner」（同頁 2 的情形：舊帳號、新擁有者）。
- 進頁還沒選時，右欄「接法」預設寫「你自己的 Prowlarr」、位址「—」、API key「尚未取得」——沒選就先寫成「既有」，與「不預選」矛盾。
- 「推薦站」區塊標題下只剩「之後再說」按鈕，沒有任何說明為什麼（因為 6 站都已加了）；一次點擊就能走。
- 動作 2（點套件內、前往下一個），0 次輸入。

## 頁 5 TMDB
- 用 keysrv 填，測試 → 已驗證。動作：填 1（key）、測試、前往下一個 = 3，輸入 1 次。可複製連結與申請說明齊全。

## 頁 6 完成
- 「已繫上」兩條 Route（我的電影 / 我的劇集）各列寫入目標與 complete 目錄；「各服務自己的介面」：Jellyfin `http://localhost:46096`（「用擁有者 s3admin 登入，與 Berth 同一組」）、qBittorrent `http://localhost:8080`「帳號 audit-owner，密碼是這一台原本就有的那一組：這一輪精靈沒有設它」、Prowlarr `http://localhost:9696` 同。跳過：沒有。
- 優點：Jellyfin 網址轉成使用者從瀏覽器開的 localhost:46096（不是 host.docker.internal）。
- 缺：沒有提醒「berth-jellyfin 還在跑，COMPOSE_PROFILES 還沒改」（這輪全靠頁 1 的那塊提示；它在頁 1 完成後已消失）。
- 動作 1（完成設定）。

## 選「既有」之後停掉套件內（照 README）
- `.env` 的 COMPOSE_PROFILES 改成 qbittorrent,prowlarr；`docker compose up -d` → 輸出只有 berth-prowlarr/berth/berth-qbittorrent Running；berth-jellyfin 仍 Up About an hour (healthy)（README 說的「停不掉」屬實）。`docker compose stop jellyfin` → Stopping/Stopped；再 `up -d` 後仍 Exited (0)。docker ps 確認停止。
- 畫面給的兩行與 README 一致。README 例子寫 `COMPOSE_PROFILES=prowlarr`，畫面是照這一輪選擇算好的整行（`qbittorrent,prowlarr`）——這點畫面比 README 好。

## 健康頁
- 完成後第一次進 /health：四個泊位都「尚未檢查」、「上次檢查 沒有紀錄」，要按「立即重測」才變「已繫上」（約 6 秒）。每 5 分鐘才自動跑。剛完成設定就看到整排「尚未檢查」。（Jellyfin 區顯示位址 http://host.docker.internal:46096。）
- 「無主 torrent 1 筆」：S1 時入庫的 Night Of The Living Dead 還掛在 qBittorrent（berth-movies 分類，stalledUP）；因為這輪是新的 Berth DB，被當成無主。重裝情境的真實現象，說明文字合理（「資料庫被還原過」）。
- 「請求預算」寫「重啟 Berth 會歸零」。

## 探索與搜尋
- 搜 `Nosferatu 1922` → 「沒有作品叫「Nosferatu 1922」」：TMDB 搜尋不吃年份；訊息建議「換個寫法，或試試原文標題」。改搜 `Nosferatu` 得 10+ 結果，1922 版是第 2（顯示中文標題「不死殭屍—恐慄交響曲」+ Nosferatu）。
- 作品頁 /media/movie:653；「入庫到」下拉：「尚未指定」「我的電影」，預選「我的電影」（只列 movie 的 Route，劇集那條沒出現）。電影自動選到電影那條：是。
- 搜尋時長：點「搜尋」約 60 秒（頁面自己說「這通常要一分鐘左右」）。結果「共 262 筆 · 逐站取了 100 筆」，另有「103 筆名字對不上這部作品，已經略過」，以及「另有 164 筆年份或類型對不上這部作品，已經收起來」（收起來 164）；底部「找到 262 筆，0 個關鍵字沒問到」。數字不能互相對上（262 / 100 / 103 / 164）。
- 結果中混入不相干的東西：Tsuki to Laika to Nosferatu 動畫（Anime Tosho，一堆集數）、TPB 的成人內容（標題含 Nosferatu 藝名）；全部「預估」欄為「電影」。主表 100 列，每列「送單」。
- 送單：點該列「送單」→ 列內展開確認：「入庫到「我的電影」／送出去之後，這部作品在媒體庫裡的資料夾會是：Nosferatu (1922) [tmdbid-653]／送單成功那一刻這串字就定下來，之後 TMDB 改標題也不會動它」+「確認送單」「取消」。挑的是 `Nosferatu, eine Symphonie des Grauens (1922) 720p BRRip x264 -YTS`，746 MB，13 seeders。
- 作品頁「下載」區：「下載中 … 進度 1%」，/jobs 與 /library 的卡片都顯示「下載中」。
- 下載時間：14:53:58 送單 → 15:01:19（UTC）檔案進 data/library/我的電影，約 7 分 20 秒。

## 入庫與 Jellyfin 認得
- 入庫路徑：C:\Users\Roxy\berth-audit2\data\library\我的電影\Nosferatu (1922) [tmdbid-653]\Nosferatu (1922) [tmdbid-653] - [BD][720p][YTS.AM].mp4（硬鏈接，link count 2，782 MB）。
- 作品頁入庫後：「檔案與版本｜共 1 個檔案｜正片｜…mp4｜帳本 對得上｜Jellyfin 還在掃描，Berth 下一次確認在 1 分鐘後」（15:02:33）。→ 15:04:35「Jellyfin 已收錄」。
- s3-jellyfin 實際認到的時間：15:03:57（API /Items 看到，Path 在 /data/library/我的電影/…）；檔案落地 15:01:19 → 認到 2 分 38 秒。Berth 日誌：15:03:55 POST /Library/Media/Updated、再 POST /ScheduledTasks/Running/<RefreshLibrary>，「asked jellyfin to scan its libraries」。也就是 Berth 在檔案落地約 2.5 分鐘後才叫 Jellyfin 掃；這段延遲在畫面上被呈現為「Jellyfin 還在掃描」（其實那段時間 Jellyfin 還沒被叫，不是在掃）。這是推測：日誌裡 15:01:19–15:03:55 看不到任何對 Jellyfin 的寫入請求，只有 15:02:30 我開作品頁時的 /resolve 查詢。
- 該媒體庫 EnableRealtimeMonitor=False（我用 API 建庫時 options 空；真實使用者用 UI 建庫預設通常是開，且 Windows bind mount 上 inotify 不會觸發）。
- 「在 Jellyfin 開啟」連到 http://localhost:46096/web/#/details?id=…。

## S5：新舊並存
- 為了有「舊內容」，我把 S1 已有的那個 mp4 複製成 s3-jellyfin 的 /movies/Night of the Living Dead (1968)/ 底下（模擬使用者原有電影，不經 Berth），用 Jellyfin API 叫它掃（模擬使用者按「掃描所有媒體庫」）。
- Jellyfin UI（乾淨 context，登入 s3admin）：「我的電影」媒體庫列兩張海報 Night of the Living Dead (1968)、Nosferatu (1922)，沒有任何來源標記；後端路徑一個在 /movies、一個在 /data/library/我的電影。媒體庫路徑設定現在是兩條（Berth 的排第一）。
- Berth /library/<媒體庫 id>：「我的電影」「我的劇集」兩個分頁；整庫 2 部，Night of the Living Dead 只顯示 MOVIE · 1968，沒有「已入庫」標；Nosferatu 有「已入庫」「1 個版本」。兩者都有「在 Jellyfin 開啟」「標為已看」。不是 Berth 入庫的 Night 連到 /media/movie:10331（作品詳情）。分得出來，但「已入庫」徽章只說有，沒說沒有（沒有「不是 Berth 帶來的」標示）。
- 空的庫（只有「還沒進 Jellyfin」1 筆）時頁面幾乎是空白，沒有說明。

## after 快照 diff（s3-jf-before.txt vs s3-jf-after.txt）
- Berth 在使用者 Jellyfin 上改了什麼：(1) Auth/Keys 新增 API key「Berth」（14:48:03，登入成功當下）；(2) /Devices 多一個 Berth（AppName Berth，LastUserName s3admin）；(3) 兩個媒體庫各多一條 Locations：/data/library/我的電影、/data/library/我的劇集（排在第一位，既有 /movies、/tv 照留）；(4) 沒有觸發掃描的動作在設定完成時（Scan Media Library LastExecution 仍是 14:45:06，我自己建庫時的），直到第一次入庫後 Berth 才叫它掃。(5) 用戶只有 s3admin，沒新增使用者。(6) 沒改帳密與全域偏好（只看了 MetadataPath 等）。
- 與畫面說法：「不改這台 Jellyfin 的任何設定」（頁 1 右欄）與實際（多 API key、Locations）有出入，但頁 3 的「按下之後會」清單與實際吻合。

## 動作數整理
| 頁 | 點擊 | 輸入 | 備註 |
|---|---|---|---|
| 1 | 6（既有、測試連線、登入、下一個…）| 3（位址、帳號、密碼）| 外部：改 .env + compose stop（畫面上給，但之後消失）|
| 2 | 2 | 0 | |
| 3 | 約 7 | 0 | 外部：改 compose + 重建（紅一次）|
| 4 | 2 | 0 | |
| 5 | 2 | 1 | |
| 6 | 1 | 0 | |
總計瀏覽器動作約 20 點擊、4 次輸入；外部命令列/編輯 2 組。

## 其他
- 搜尋「入庫到」下拉含「尚未指定」選項，但預選了 Route；送單前沒有再顯示會寫到哪個磁碟路徑（只顯示資料夾名與 Route 名）。
- 頁 3 的 Route 與資料夾名用 Jellyfin 媒體庫名（中文）→ 磁碟上 /data/torrent/complete/我的電影、分類 berth-我的電影。對 CJK 無問題（硬鏈接、Jellyfin 認得），但與 README 與 CONTEXT 裡「movies / tv / anime」的慣例不同，使用者之後在 qBittorrent 看到 berth-我的電影。
