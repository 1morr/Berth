# 主流媒體自動化工具怎麼限制對公開站台的請求：Prowlarr / Sonarr / AutoBangumi

2026-09-26。為了 Berth 要設計「RSS 輪詢、每日 backfill、批次缺集搜尋」三者共用的
per-site request budget，查了 Prowlarr、Sonarr 原始碼（GitHub，GPL）與官方文件、
AutoBangumi 官方文件。找不到的一律標「未找到」，不用記憶猜版本相關細節。

## 1. Prowlarr 的 Query Limit / Grab Limit（每個 indexer 兩個獨立配額）

1. 每個 indexer 有 **Query Limit**（查詢/RSS 次數上限）與 **Grab Limit**（送出下載次數
   上限）兩個獨立欄位，配一個共用的 **Limits Unit**，只能選 `Day`（預設）或 `Hour`，
   沒有「每分鐘」。使用者在 issue 裡抱怨過這個粒度：例如要限 4 次/分鐘，換算成「每小時
   16 次」的話，Prowlarr 會在第 1 分鐘就把 16 次用光，剩下 59 分鐘完全不查，比不設限
   更糟。
   來源：[Prowlarr Quick Start Guide](https://wiki.servarr.com/prowlarr/quick-start-guide)、
   [issue #2023](https://github.com/Prowlarr/Prowlarr/issues/2023)。
2. 計數方式是**滾動窗（rolling window）**，不是整點/整天歸零的日曆窗。`IndexerLimitService`
   的 `AtQueryLimit`/`AtDownloadLimit` 呼叫
   `_historyService.CountSince(indexer.Id, DateTime.Now.AddHours(-intervalLimitHours), eventTypes)`；
   `CalculateIntervalLimitHours` 在 Unit=`Hour` 時回傳 1，其餘（含預設 `Day`）回傳 24——
   也就是「過去 N 小時內」而非「今天 00:00 起」。Query Limit 算
   `HistoryEventType.IndexerQuery` + `IndexerRss`；Grab Limit 只算 `ReleaseGrabbed`，
   兩種配額互不干擾。
   來源：[`IndexerLimitService.cs`](https://github.com/Prowlarr/Prowlarr/blob/develop/src/NzbDrone.Core/Indexers/IndexerLimitService.cs)。
3. 打到上限時，`CalculateRetryAfterQueryLimit`/`CalculateRetryAfterDownloadLimit` 會找出
   窗內最舊一筆歷史紀錄，算出「那筆紀錄時間 + intervalLimitHours − 現在」當作還要等多久，
   這個秒數就是實際會看到的「Disabled for HH:MM:SS」。真實案例：
   `Request Limit reached for BitSearch. Disabled for 01:00:00`。
   來源：[`IndexerLimitService.cs`](https://github.com/Prowlarr/Prowlarr/blob/develop/src/NzbDrone.Core/Indexers/IndexerLimitService.cs)、
   [issue #2635](https://github.com/Prowlarr/Prowlarr/issues/2635)。
4. 兩種配額打滿後的行為不同：Query Limit 打滿只是那次搜尋跳過該 indexer；Grab Limit
   打滿後官方文件說法是，之後再送查詢會讓 *Arr 應用端丟出未處理例外，不是乾淨地跳過。
   來源：[Prowlarr Quick Start Guide](https://wiki.servarr.com/prowlarr/quick-start-guide)。

## 2. Cardigann 各站定義的 `requestDelay`（Prowlarr/Indexers repo, `definitions/v11/`）

四個常見動畫站裡，**只有 nyaa 設了預設節流**，其餘三個完全沒有：

- `nyaasi.yml`：`requestDelay: 2`（每次請求間隔 2 秒）。
  [連結](https://github.com/Prowlarr/Indexers/blob/master/definitions/v11/nyaasi.yml)
- `mikan.yml`（`id: mikan`，目標 `mikanani.me`）：無 `requestDelay` 欄位。
  [連結](https://github.com/Prowlarr/Indexers/blob/master/definitions/v11/mikan.yml)
- `dmhy.yml`：無 `requestDelay` 欄位。
  [連結](https://github.com/Prowlarr/Indexers/blob/master/definitions/v11/dmhy.yml)
- `acgrip.yml`：無 `requestDelay` 欄位。
  [連結](https://github.com/Prowlarr/Indexers/blob/master/definitions/v11/acgrip.yml)

也就是說，Prowlarr 對 mikan、dmhy、acg.rip 這三個站完全不強制任何請求間隔，唯一的節流
管道是第 1 節提到、預設「不限」且要使用者手動填數字的 Query/Grab Limit。

## 3. Sonarr：RSS Sync Interval 與 indexer 錯誤退避

1. RSS Sync Interval 官方文件明寫：最小 10 分鐘、最大 120 分鐘，設 0 停用自動 RSS 同步。
   來源：[Sonarr Settings](https://wiki.servarr.com/sonarr/settings)。
2. **預設值未在 wiki／原始碼中找到明確數字**；多個獨立論壇討論串（跨新舊版本）一致把
   15 分鐘當作「標準」用法（例如使用者原本設 15 分鐘、被建議「這已經很標準」）。這是社群
   共識而非原始碼常數，誠實標注為未確認的預設值。
   來源：[forums.sonarr.tv 討論串](https://forums.sonarr.tv/t/sonarr-not-automatically-searching-for-new-episodes/26900)。
3. 「Search All Missing / 自動缺集搜尋」是否批次化、序列化或有延遲：**未找到**具體說明。
   查過 [Sonarr System wiki](https://wiki.servarr.com/sonarr/system) 與多個論壇討論串，
   均只談 RSS 同步機制，沒有描述缺集搜尋本身的批次執行邏輯。
4. Indexer 連線／伺服器錯誤的退避走共用的 `ProviderStatusServiceBase`
   （`IndexerStatusService` 只是薄子類別）。逐級加重停用時間，`EscalationBackOff.Periods`
   （秒）為 `0, 60, 300, 900, 1800, 3600, 10800, 21600, 43200, 86400`，即
   0秒、1分、5分、15分、30分、1小時、3小時、6小時、12小時、**封頂 24 小時**。啟動後有
   15 分鐘寬限期不計退避；若站台回應帶了類似 Retry-After 的「最短等待」值，會把等級往上跳
   到「該等級時間 ≥ 這個最短等待」為止；連續成功一次會把等級降一階並解除停用。
   來源：[`EscalationBackOff.cs`](https://github.com/Sonarr/Sonarr/blob/develop/src/NzbDrone.Core/ThingiProvider/Status/EscalationBackOff.cs)、
   [`ProviderStatusServiceBase.cs`](https://github.com/Sonarr/Sonarr/blob/develop/src/NzbDrone.Core/ThingiProvider/Status/ProviderStatusServiceBase.cs)、
   [Sonarr System wiki](https://wiki.servarr.com/sonarr/system)（印證「up to 24h」封頂）。

## 4. AutoBangumi（EstrellaXD/Auto_Bangumi）

1. `rss_time`（輪詢間隔）預設 **900 秒（15 分鐘）**；順帶一提 `rename_time` 預設 60 秒。
   來源：[官方 config 文件](https://www.autobangumi.org/en/config/program.html)。
2. 輪詢模式是**聚合 RSS**：一支 URL 涵蓋使用者訂閱的所有番，不是逐番各開一支 feed 輪詢。
   來源：[AutoBangumi GitHub README](https://github.com/EstrellaXD/Auto_Bangumi)。
3. 官方唯一一篇跟 mikanani.me「連線問題」相關的 FAQ 講的是**區域封鎖／DNS 汙染**（換替代
   域名、架 Cloudflare Worker 反向代理、掛 VPN），不是限速建議。**未找到**官方對「如何
   避免被 mikan 限速或封 IP」的建議——封鎖與限速是兩個不同問題，不能混為一談。
   來源：[官方 Network 疑難排解](https://www.autobangumi.org/en/faq/network.html)。

## 5. mikanani.me / nyaa.si / acg.rip 的限速或封鎖事故報告

1. **mikanani.me：未找到**具體的「被限速」或「被封 IP」事故報告（issue、論壇貼文）。
   唯一相關資料是第 4 節的區域封鎖 FAQ，性質不同，不能當限速證據。
2. **nyaa.si：未找到**具體事故報告，但有兩點間接證據：(a) 四站中只有 nyaa 的 Cardigann
   定義設了 `requestDelay`，暗示維護者觀察到它對高頻請求較敏感（見第 2 節）；(b)
   [Prowlarr issue #2635](https://github.com/Prowlarr/Prowlarr/issues/2635) 描述的是
   「被 Cloudflare 保護的 indexer 回 429，但 Prowlarr 目前的退避時間不夠長」，雖然範例站台
   是 BitSearch 不是 nyaa，但反映了同一類「Cloudflare 保護的公開 indexer」風險，可類推。
3. **acg.rip：未找到**任何限速或封鎖相關資料。
4. 通用背景（非這三站專屬）：Cloudflare 的 429 內部常對應錯誤碼 1015，代表「單一來源
   送太快」，官方建議是聯繫站方解除限制，說明若站台掛在 Cloudflare 後面、對它做高頻輪詢
   有被通用防護擋下的風險——但這是 Cloudflare 的通用機制，不是這三站的專屬案例。
   來源：[Cloudflare Error 429 文件](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/error-429)。

## 對 Berth 的意涵

1. **滾動窗 + 事件時間戳計數是可直接抄的模式**：Prowlarr 用「過去 N 小時內的請求數」而
   非整點歸零，retry-after 用「最舊一筆時間 + 窗長 − now」精確算出。Berth 的 per-site
   budget 可以照抄這個算法，不必發明新的。
2. **查詢與下載要分開計數**：RSS 輪詢、backfill、批次缺集搜尋都屬於「查詢」，可共用同一個
   查詢預算；實際送出下載/建立 job 是另一種資源消耗，應該是獨立的第二個預算，不要混在一起。
3. **粗粒度窗口的教訓（issue #2023）**：只給 Day/Hour 兩檔會讓配額在窗口重置瞬間被一次
   打滿，Berth 設計 budget 時應允許更細的粒度（例如以分鐘為單位或用 token bucket），
   不要複製 Prowlarr 的兩檔設計。
4. **預設節流極薄，不能假設 upstream 已經擋好**：四個常用來源裡只有 nyaa 有 2 秒的預設
   間隔，mikan（Berth 主要來源之一）、dmhy、acg.rip 完全靠使用者自設、預設「不限」的
   Query/Grab Limit。Berth 必須自己實作 budget，不能依賴 Cardigann 定義的 `requestDelay`。
5. **「配額用盡」與「站台出錯/回 429」要用兩條獨立邏輯**：Sonarr 把兩者分開——
   `IndexerLimitService` 算配額精確的 retry-after，`EscalationBackOff` 針對連線/服務錯誤
   逐級加重且封頂 24 小時。Berth 的三個呼叫方共用同一個站點 budget 時，也該分開「等窗口
   讓出名額」與「錯誤退避、逐次加重」兩個計時器，不要共用一個。
