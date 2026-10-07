# S1 + S5 實跑筆記（2026-10-07，main 107708c，image berth:audit-107708c）

截圖：`docs/research/usability-audit-2026-10-07/s1-*.jpeg`、`s5-*.jpeg`。帳密在 `C:\Users\Roxy\berth-audit2\CREDENTIALS.md`（擁有者 `audit-owner`），此檔不記密碼。
注意：playwright 的 run_code 會把程式碼原樣回顯，所以頁 1 與 S5 填測試密碼時密碼出現在工具輸出；TMDB 真 key 改用本機一次性 http server + 腳本 fetch，全程未回顯。

## 0. 環境重置與部署
- `docker compose down` → config/data 搬成 `config.prev-20261007` / `data.prev-20261007` → 重新複製 compose / .env（只確認 DATA_ROOT=./data、CONFIG_ROOT=./config）/ preseed。
- `docker compose up -d`：指令本身 0.9 秒（image 已在本機）；4 個容器全 healthy 約 32 秒（21:37:24 到 21:37:56）。
- README 路徑：`docker pull ghcr.io/1morr/berth:latest` 拉得下來（上一輪是空的）。digest sha256:8b93295c…；`org.opencontainers.image.version=0.1.0`、created 2026-10-06T21:47:31Z、revision 6bc4c1d。
  - 該 revision 是 0.1.0，不含票 43–54。一般使用者照 README 拿到的是舊精靈，這一輪看到的行為與他們看到的不同。未用它跑。
- 起始狀態：qBittorrent save_path=/downloads、temp_path=/downloads/incomplete（未啟用）、auto_tmm=false、web_ui_username=admin、無分類；Jellyfin `/System/Info/Public` ServerName=容器 ID `8986e24a594e`、StartupWizardCompleted=false。
- qBittorrent 的臨時密碼只印在容器 log；從宿主 `curl localhost:8080/api/v2/...` 回 403 Forbidden（Berth 靠 preseed 白名單進 API）。

## 1. 逐頁表格（S1，全選套件內）
時間為本機時間，起點：開 http://localhost:8383 = 21:38:14。

| 頁 | 使用者動作 | 輸入欄位次數 | 按鈕（看到/必按） | 自動做的事 / 等待 | 畫面關鍵文字 |
|---|---|---|---|---|---|
| 登入前 | 直接進 `/setup?step=1`（未完成就導向精靈） | 0 | ZH/EN、BTH 1 | — | 標題「設定精靈」「泊位 BTH 1 · 第 1 個，共 5 個泊位」「先選 Jellyfin 是哪一台」；兩張卡「套件內 / 既有」，不預選 |
| 1 Jellyfin | 點「套件內」→ 填帳號、密碼、再輸入密碼 →（勾選框預設已勾）→「建立管理員並登入」→「前往下一個泊位」 | 3 欄（密碼 2 次） | 看到：2 radio + 1 勾選 + 建立 + 下一步（+ ZH/EN）；必按：套件內、建立、下一步 = 3 | 點套件內後自動測連線：「Jellyfin 連上了：還沒跑過自己的初始精靈」。按建立後約 1.5 秒完成（POST /Startup/Configuration、User、RemoteAccess、Complete、AuthenticateByName、POST /Auth/Keys?app=Berth） | 勾選框「套件內 qBittorrent 與 Prowlarr 的介面也用這組」說明「到那兩頁自動帶入，不用再打一次密碼…密碼只留在這個分頁的記憶體裡，不存進 Berth、也不寫進瀏覽器——重新整理之後會再問一次」。完成後：「擁有者：audit-owner」、「已經有管理員」、右欄「不存下：你的密碼（只交給 Jellyfin）」 |
| 2 qBittorrent | 點「套件內」→「前往下一個泊位」 | 0 | 看到 2 radio + 上一個 + 下一步（完成後多一顆「更換登入」）；必按 2 | 點完 radio 約 3 秒內自動：連線測試通過、WebUI 登入設為 audit-owner（沿用頁 1，沒再問密碼）。log：setPreferences x2，另有探針 torrent add/recheck/delete | 「qBittorrent WebUI 的帳號： audit-owner」「更換登入」「已完成 WebUI 登入」「這個泊位的事做完了。WebUI 登入設好了；Berth 沒有改這台 qBittorrent 的全域偏好，它的下載走自己的分類。」 |
| 3 媒體庫路徑 | 只按「前往下一個泊位」進頁，什麼都不用按；完成後再按下一步 | 0 | 看到：重新讀取 Jellyfin 媒體庫、建立並檢查中…（進行中 disabled）、上一個、（完成後）重新檢查 3 條 Route、下一步；必按 1（下一步） | 進頁自動建立並檢查，約 17–20 秒（log 21:41:21 到約 21:41:38）：建 Jellyfin 媒體庫 Movies / TV / Anime、qBittorrent 建三個 berth-* 分類、每條 Route 探測檔＋硬鏈接＋qB 探針 | 進行中逐步清單：「進行中 建立清單上的媒體庫」，每條 Route 顯示「等待中」→進行中；結束「已繫上 Movies berth-movies /data/library/movies 6 / 6 通過」x3；媒體庫清單「3 個已建立」 |
| 4 Prowlarr | 點「套件內」→ 按「測試推薦站，加入通過的」→ 看結果 →「前往下一個泊位」 | 0 | 看到：2 radio、「測試推薦站，加入通過的」、「之後再說」、進階「展開」、更換登入、上一個、下一步；必按 3（套件內、測試推薦站、下一步） | 點套件內：連線測試通過；介面登入自動沿用頁 1（「沿用頁 1 的 Jellyfin 帳密（audit-owner），設定中…」→「已經是這樣」）。按推薦站鍵後約 10 秒：加入 6 站、3 站沒通過 | 「加入 6 站 · 3 站沒通過測試」「已加入dmhy、Anime Tosho、ACG.RIP、Mikan、YTS、The Pirate Bay」；未通過：Nyaa.si「連不上：DNS、TLS 或站本身掛了…」、1337x / EZTV「被 Cloudflare 擋住：這個站擋掉自動化的請求，要在 Prowlarr 設 FlareSolverr 才過得去。」。已加入列表每站標語言（ACG.RIP 中文(中國)、Anime Tosho 英文(美國)、dmhy 中文(台灣)、Mikan 中文(中國)、TPB 英文(美國)、YTS 英文(美國)）、每站「搜尋」「移除」、「還沒搜」標籤 |
| 5 TMDB | 貼 key →「測試 TMDB」→ 下一步（先試一次錯的） | 錯 key 1 次 + 真 key 1 次（理想路徑 1 次） | 看到：複製、顯示、測試 TMDB、上一個；必按 測試 + 下一步 = 2 | 即時測 `GET /3/configuration` | 錯 key（32 個 0）：「失敗 驗證憑證 TMDB 不接受這把 key。」「TMDB 不收這把 key：多半是貼錯、少貼了幾個字，或貼到帳號密碼。到 TMDB 的 API 設定頁重新複製「API 金鑰」或「API 讀取存取權杖」再測：」；右欄「憑證 還沒填」。重新載入頁面後仍是「還沒填」，錯的沒被存下（票 45 OK）。真 key：「已完成 驗證憑證」，右欄「憑證 已取得」，BTH 5「已驗證」 |
| 6 完成 | 按「完成設定」 | 0 | 完成設定、上一個泊位；必按 1 | — | 「五個泊位都走過了。按下完成之後精靈就關閉，之後的修改在設定頁。」三條 Route 摘要；「各服務自己的介面：平常用不到它們：Berth 替你接好了…」Jellyfin `http://localhost:8096`「用擁有者 audit-owner 登入，與 Berth 同一組。」；qBittorrent `http://localhost:8080`「帳號 audit-owner，密碼是精靈裡設的那一組。」；Prowlarr `http://localhost:9696` 同上；「這一輪的結果… 跳過 沒有」。按完直接進探索頁，已是登入狀態（audit-owner） |

總計（理想路徑）：點擊約 13 次（3 個 radio、建立、推薦站、測試 TMDB、下一步 x5、完成，再加勾選框預設已勾不用點）；打字欄位 4 個（帳號、密碼、再輸入密碼、TMDB key）；**密碼只打 2 次（建立時的兩次），頁 2/4 全自動套用（票 40 OK）**。精靈總時間約 7 分鐘（含我讀畫面）；機器等待合計約 1.5 秒 + 3 秒 + 20 秒 + 10 秒。

## 2. 服務狀態前後（API 讀出）
- qBittorrent 全域偏好（票 32）：save_path `/downloads`、temp_path `/downloads/incomplete`、temp_path_enabled false、auto_tmm_enabled false、category_changed_tmm_enabled false，頁 2 後、頁 3 後皆與起始相同；唯一變動 web_ui_username admin → audit-owner。分類頁 3 後：berth-movies / berth-tv / berth-anime（savePath `/data/torrent/complete/<x>`、download_path `/data/torrent/incomplete/<x>`）。OK
- Jellyfin：ServerName 8986e24a594e → 「Berth」（票 52 OK；分頁標題與 Jellyfin 頁首也是 Berth），StartupWizardCompleted true；VirtualFolders：Anime(tvshows /data/library/anime)、Movies(movies /data/library/movies)、TV(tvshows /data/library/tv)。
- Prowlarr：6 站（ACG.RIP zh-CN、Anime Tosho en-US、dmhy zh-TW、Mikan zh-CN、TPB en-US、YTS en-US，皆 public torrent、enabled）；host 設定 authenticationMethod forms、authenticationRequired enabled、username audit-owner。
- 頁 2 在套件內 qB 上有 add/recheck/delete 探針 torrent（log 可見），結束後 torrents 清單為空。

## 3. 精靈之後：第一部片
時間線（本機）：
- 21:45 完成精靈、進探索頁（本週趨勢 39 部）。
- 探索頁搜尋「Night of the Living Dead」得 20 部結果，第一筆「MOVIE · 1968 活死人之夜」→ `/media/movie:10331`。作品頁「搜尋 torrent」區：關鍵字 5 個（原名＋中文＋德/義/法名）、「入庫到 尚未指定 Movies」、「資料夾將會是 Night of the Living Dead (1968) [tmdbid-10331]」。
- 按「搜尋」約 12 秒（說明文字寫「通常要一分鐘左右」）。結果：「找到 37 筆，0 個關鍵字沒問到」、「5 個關鍵字都有回應」、「另有 107 筆名字對不上這部作品，已經略過。」＋底部「另有 74 筆年份或類型對不上這部作品，已經收起來。」（票 49：列表 37 筆、收起來 74 筆）。
- 送單：點 790 MB 那列的「送單」→ 行內確認「入庫到「Movies」／送出去之後，這部作品在媒體庫裡的資料夾會是：Night of the Living Dead (1968) [tmdbid-10331]／送單成功那一刻這串字就定下來，之後 TMDB 改標題也不會動它。」＋「確認送單」「取消」。只有一條 Movies Route，沒有選擇，自動帶入。21:45:56 確認，該列變「已送出」＋連結「看下載列表」；作品頁「下載」區出現一筆「已送出 … 進度 —」。
- `/jobs`：「在路上 1」「下載中」進度 54%（21:54）。
- 下載：qBittorrent 21:48 約 16%，21:59:02 100%；送單到 100% 約 13 分。
- 入庫：13:59:07 UTC（21:59:07）job planned、importing、imported（下載完成後 1 分內，無人工）。檔案 2 個硬鏈接（link count 2）：`/data/library/movies/Night of the Living Dead (1968) [tmdbid-10331]/Night of the Living Dead (1968) [tmdbid-10331] - [BD][720p][YTS.AM].mp4`。
- 作品頁（票 51）：21:59:42 開頁，「檔案與版本 1 · 正片 …mp4 · 帳本 對得上 · Jellyfin 還在掃描，Berth 下一次確認在 4 秒前」。Jellyfin 掃描由 Berth 在 22:01:42（入庫後 2 分 35 秒）才送出（log「asked jellyfin to scan its libraries」）。22:02:15 重開作品頁：「Jellyfin 已收錄」（開頁當下查 Jellyfin，與媒體庫一致）。
- Jellyfin API：Movie 1 部，ProviderIds Tmdb=10331、Imdb=tt0063350，路徑為上面那個檔案。Jellyfin 看得到。
- `/jobs` 入庫後：「在路上 0 / 需要人 0 / 已入庫 1」，「沒有在路上的下載：送出去的都入庫或移走了。」
- 總時長：送單 21:45:56 → 下載完成/入庫 21:59:07（13 分 11 秒）→ Jellyfin 收錄約 22:02（共約 16 分）。

## 4. 健康頁 /health（票 50）
- 精靈完成後約 4 分鐘：BTH1–5 皆「已繫上 / 已驗證」；三服務「已繫上」；下載迴圈「上次輪詢 3 秒前 · 有下載時每 5 秒」、連續失敗 0；請求預算每站 5/60（搜尋 5）；Route Movies/TV/Anime 各「6 / 6 通過」。講真話，6/6。「每 5 分鐘自動檢查一次 · 上次檢查 4 分鐘前」。

## 5. S5：三個服務自己的網頁（乾淨 browser context，無 cookie）
| 服務 | 登入畫面 | 用哪組帳密 | 登入後 |
|---|---|---|---|
| Jellyfin :8096 | 「請登入」使用者/密碼/記住我/使用快速連線/忘記密碼；分頁標題「Berth」；無 onboarding | audit-owner + 擁有者密碼 | 首頁「我的媒體：Anime、Movies、TV」共 3 個媒體庫，頁首伺服器名「Berth」；無設定精靈或強迫視窗 |
| qBittorrent :8080 | WebUI 登入（Username / Password） | audit-owner + 擁有者密碼 | 進主介面，列表有該筆下載；無 onboarding；沒有「請改密碼」提示 |
| Prowlarr :9696 | 「SIGN IN TO CONTINUE」登入表單；無強迫設定登入視窗 | audit-owner + 擁有者密碼 | 6 站都在（Added 9:42pm）；無 onboarding |

三服務都不需再跑自己的 onboarding；一組帳密通用（完成頁也這樣寫）。

## 6. 票驗證結論
- 票 32（套件內 qB 不寫全域鍵）：OK，前後比對一致。
- 票 40（密碼只打兩次）：OK。
- 票 43（頁 3 進頁自動跑、逐條進度）：OK，約 20 秒，有「等待中/進行中」。
- 票 44（一鍵加推薦站）：OK，約 10 秒，6 加入、3 沒通過，原因逐站說明。
- 票 45（錯 key 不存）：OK（重新載入仍「還沒填」）。
- 票 49：列表 37 筆，另有 74 筆收起、107 筆名字對不上略過。
- 票 50：Route 6/6。
- 票 51：作品頁開頁即與 Jellyfin 一致；但剛入庫時顯示「還在掃描」，而 Jellyfin 掃描延遲 2.5 分鐘才觸發。
- 票 52：伺服器名「Berth」OK。

## 7. 問題與觀察（含判斷成分，請主對話定奪）
- P1（輕）頁 4 進頁、尚未選套件內/既有時，左欄寫「接法 你自己的 Prowlarr / 位址 — / API key 尚未取得」（s1-07）。使用者還沒選就標「你自己的」，誤導。
- P2（輕）頁 4 登入列：進行中寫「沿用頁 1 的 Jellyfin 帳密（audit-owner），設定中…」，設好後文案是「已經是這樣」（先前頁 2 是「已完成」），同一件事兩種說法；且推薦站鍵按完前底欄同時寫「還差 加入至少一個站 / 設定 Prowlarr 介面登入」，後者其實已在自動進行。
- P3（輕）完成頁 qBittorrent / Prowlarr 寫「密碼是精靈裡設的那一組」，沒有明說就是頁 1 打的 Jellyfin 密碼；對有勾選框的人可直接說「與 Jellyfin 同一組」。
- P4（中）作品頁剛入庫的窗口：入庫 21:59:07，Jellyfin 掃描請求 22:01:42（延遲 2 分 35 秒）。21:59:42 作品頁寫「Jellyfin 還在掃描」，但那時 Berth 尚未要求 Jellyfin 掃描，文字與事實不符（實為尚未開始）。需判斷 resolver 的延遲是否刻意（debounce）。
- P5（輕）送單後作品頁 main 文字最前面出現「已下載過」（innerText 中 `已下載過 | 活死人之夜`），但當時才剛送出、下載 0%。我沒在截圖看到該元素（s1-18 停在列表中段），無法確認是徽章還是別的；若是徽章，語意偏早。
- P6（資訊）搜尋說明「通常要一分鐘左右」，實測 12 秒（6 個站）；文案偏悲觀，不算錯。
- P7（資訊）GHCR `:latest`（0.1.0 / 6bc4c1d）可拉，但不含票 43–54。一般使用者照 README 部署會看到舊精靈（密碼 4 次、頁 3 要按鈕、錯 key 被存等）。是版本落差，發版前要重審。
- P8（資訊）full-page 截圖中 sticky 底欄（上一個/下一步）疊在內容中間（s1-05、s1-06、s1-09 等），應是 playwright fullPage 擷取 sticky 的假象；一般視窗沒有重疊。未用真人捲動驗證。
- P9（輕）頁 2 在套件內 qB 做探針 torrent（add/recheck/delete），畫面只寫「設定 WebUI 登入 · 只建 Berth 自己的分類」，沒提探針；頁 3 的說明有寫。log 可見三組 hash 的探針，頁 2 與頁 3 各占多少我沒逐一對應。
- P10（資訊）頁 4 完成後畫面按鈕偏多（6 站各有「搜尋」「移除」、進階、之後再說），必按只有 3；推薦路徑有黃色主鍵，不算問題，但第一次看會多想。

做得好：
- 頁 1 勾選框說清楚密碼去向與不落地；頁 2/4 零輸入；頁 3 進頁自動跑並逐條顯示；頁 4 一鍵；錯 key 不存且訊息可操作；Jellyfin 名稱 Berth；完成頁列三個服務網址與帳號；三服務之後不再強迫 onboarding；Route 6/6，送單到入庫到 Jellyfin 全程不需人工；搜尋把不相關的 181 筆（107+74）收掉只剩 37 筆。

## 8. 沒跑到 / 未驗證
- 沒用真人捲動確認 sticky 底欄；P5 徽章未確認；頁 2 探針文案；TMDB v4 token 格式；ZH/EN 切換未逐頁比對。
- 未測重新整理後密碼再問一次的流程（頁 1 之後重新整理再進頁 2/4）。
- 未驗 Jellyfin 播放與 Web UI 內的作品詳情；僅以 API 與首頁媒體庫數確認。
- 未用 GHCR 0.1.0 image 跑。
- 環境保留：berth 專案 4 容器 up、精靈完成、電影已入庫；qBittorrent 仍在做種（stalledUP）。
