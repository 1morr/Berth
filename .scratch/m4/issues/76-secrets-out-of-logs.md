# 76 — log 裡不出現 URL 上的秘密（Mikan 個人 token 等）

**Status:** done

**Blocked by:** None — can start immediately（使用者要求排在 71b 之後、77 之前；安全問題先做）

**讀:** 日誌設定（`berth/logs.py`）與 HTTP 客戶端建構（adapters 的 http 模組、`services/clients.py`）；brief 裡 secrets 與 log 的規定（搜 `secret`、`log`）；`docs/guide/backup-and-reinstall.md`〈secrets〉；RSS 訂閱的 feed URL 怎麼存

## 為什麼（2026-10-09 使用者本機實測）

- 使用者訂閱 Mikan 的 MyBangumi RSS 之後，`docker logs berth` 出現：
  `HTTP Request: GET https://mikanani.me/RSS/MyBangumi?token=<使用者的個人 token> "HTTP/1.1 200 OK"`
- 來源是 httpx 自己的 INFO log，它記錄完整網址。拿到 log 的人（貼 log 求助、log 收集器、截圖）就能讀使用者的 Mikan 訂閱。
- 同類風險：任何 query string 帶 key / token / passkey 的 URL，例如私有 tracker 的 RSS passkey、Prowlarr 的 `apikey`、Jellyfin 的 `api_key`。

## 做什麼

1. 先盤點：哪些 logger 會印出對外請求的 URL 或 header（httpx、httpcore、uvicorn access log、Berth 自己的 log）。哪些 URL 可能帶秘密：RSS feed、Prowlarr、Jellyfin、qBittorrent、TMDB 的 `api_key`。
2. 修根：log 裡的 URL 一律把 query string 的值遮掉，例如 `token=***`。不靠列舉參數名稱，因為私有站的參數名稱各家不同。
   - 做法自己定，理由寫在 Comments：例如在 Berth 的 log 設定裡加 filter 或 formatter，或者把 httpx 的請求 log 降級，改由 Berth 自己記一行不帶 query 的版本。
3. 錯誤訊息與畫面同理：`ServiceError` 之類的錯誤若帶完整 URL、而且會寫進 DB（`last_error`）或回給前端，也要遮。照實盤點，有就修，沒有就在 Comments 寫明查過。
4. 測試（雙向，寫在測試檔內）：
   - 帶 `?token=abc` 的請求跑過一次，抓到的 log 文字裡沒有 `abc`；
   - 不帶 query 的 URL 照常完整出現（證明不是把整行吃掉）。
5. 本機實跑：在 `C:\Users\Roxy\berth-local` 那一套之外另起一套隔離的環境（專案名 `berth-t76`、另一組 port、資料放 repo 外），用一個帶假 token 的 RSS URL 跑一輪，`docker logs` 搜不到 token。**不准碰使用者正在用的 `berth-local`。**
6. 已經寫進 log 的舊 token 無法回收：在 CHANGELOG `[Unreleased]` 註明「之前版本的 log 可能含 RSS token，建議重新產生 Mikan token」，README 不必提。

## 驗收

- [x] 盤點結果（logger、URL 種類、錯誤訊息與 DB 欄位）寫在票 Comments
- [x] log 裡 URL 的 query 值一律遮掉；雙向測試在測試檔內
- [x] 錯誤訊息 / `last_error` / API 回應裡的 URL 照盤點結果處理
- [x] 隔離環境實跑：`docker logs` 搜不到假 token，附指令輸出
- [x] 全部檢查、pytest、vitest 綠；CHANGELOG、progress.md 已更新

## Comments

### 盤點（2026-10-09）

**會印網址的 logger**

| logger | 印什麼 | 走哪個 handler | 處理 |
| --- | --- | --- | --- |
| `httpx` | INFO `HTTP Request: GET <整條網址> "HTTP/1.1 200 OK"`，含 `params=` 拼出來的 query | root 的 JSON handler | `json_line` 遮 |
| `httpcore` | 只有 DEBUG（不含標頭值）；root 是 INFO，不印 | root | 同上，降 level 也照遮 |
| `uvicorn.access` | 對 Berth 的請求路徑加 query | uvicorn 自己的 handler，`propagate=False` | logger 上掛 filter |
| `uvicorn.error` | 啟動訊息、ASGI 未處理例外的 traceback | 經 `uvicorn` 的 handler，不到 root | 同上，traceback 先格式化遮好放 `exc_text` |
| `berth.*` | `extra={"error": message(exc)}` 這類 | root | `json_line` 遮 message、traceback、字串 extras |

沒有任何 logger 在 INFO 印請求標頭。

**哪些網址帶秘密**

- RSS feed：Mikan 聚合 feed 的 `?token=`（票的起點）。加 Feed 只認 Mikan、Nyaa、acg.rip 三個主機，私有站 passkey 目前進不來，但遮罩不認參數名，之後加了也照遮。
- TMDB v3 key：`params={"api_key": ...}`，httpx 的 log 印出來（已實測遮掉）。
- Prowlarr 搜尋結果的 `downloadUrl`：`http://prowlarr:9696/<id>/download?apikey=<Prowlarr key>&link=...`（fixture 為證）；送單時 `TorrentFetcher` 去抓它，httpx 印、錯誤訊息也帶。
- Jellyfin（`Authorization: MediaBrowser Token=`）、Prowlarr API（`X-Api-Key`）、qBittorrent（cookie、登入走表單 body）都不在網址上。

**錯誤訊息與 DB 欄位**

`ServiceError` 的訊息帶網址的地方：`HttpSession` 的 `"<method> <path>: ..."`（RSS 的 `path` 就是整條 feed 網址）、`TorrentFetcher` 的下載連結、`json_body` 的 `response.request.url`（含 `params=`）。它流到 `rss_feeds.last_error`、`Job.error` 與時間線 payload、健康檢查的 error、搜尋逐站的 error、API 的 4xx `detail`、log extras——幾十個寫出去的地方，所以遮在 `ServiceError.__init__`（所有子類都經過它）。實跑：連不上的 Feed 的 `last_error` 是 `GET http://127.0.0.1:9/RSS/MyBangumi?token=***: connection refused`。

查過、沒改的：
- `rss._note_failure`、`jobs` 的整輪失敗寫 `f"{type}: {failure}"`，收的是任意例外。httpx 的例外都在 `HttpSession`、`TorrentFetcher` 裡翻成 `ServiceError`，目前沒有已知帶網址的例外走到這兩處；沒有 repro 就不加。
- `IndexerRejectedError.messages`（Prowlarr 回的逐條理由，`services/indexer.py` 寫進畫面與資料庫）不經過 `args`：code-review 後在它的建構子另外遮。
- RSS 頁的 Feed 網址：前端 `maskToken` 本來就把 `token=` 遮到前四碼，`/rss` 整組是 admin。

### 做法與理由

- `berth/redact.py` 的 `redact_queries`：純函式、只 import `re`。`?` 之後每一段的值換成 `***`，沒等號的段落整段換掉，參數名留著（讀 log 還看得出是哪種請求）；網址後緊接的 `:` `,` `.` `)` 不算值（`HttpSession` 的訊息是「GET <url>: ...」）；冪等（log 與錯誤訊息兩層都遮）。
- 遮在 formatter（`json_line`）而不是把 httpx 的 log 降級：每一個 logger 的每一格都經過它，包括之後才加的 logger；逐格遮而不是整行 JSON，否則值的範圍吃到跳脫引號時那一行就不是 JSON。
- uvicorn 的兩個 logger 不經過 root，`configure_logging` 在它們身上掛 filter（冪等）。Berth 的 API 目前沒有帶秘密的 query 參數，但規則是「log 裡的網址一律遮」，一起做。filter 先逐格遮 `args`（uvicorn 的 access formatter 要把它拆成五格），格式化出來還有沒遮到的值（`?a=` 在格式字串、值在 `args`）才整句格式化好再遮、清空 `args`；格式字串本身不先遮，否則 `?a=%s` 的占位符被吃掉、那一行印不出來。

### 實跑（隔離環境）

image `berth:t76`（這個分支），repo 外的 compose（`name: berth-t76`、只有 berth、`18383:8383`、資料在 session scratchpad），`berth-local` 四個容器沒動。容器裡把精靈標成跑完、加兩個 Feed（Mikan `?token=t76FAKEtoken0deadbeef`；連不上的 `http://127.0.0.1:9/RSS/MyBangumi?token=t76FAKEerr0cafe`），等 `rss_poller` 輪；另打一次 `GET /api/health?token=t76FAKEtoken0deadbeef`。

```
$ docker logs berth-t76 2>&1 | grep -c t76FAKE
0
$ docker logs berth-t76 2>&1 | grep -E "token=|mikanani|could not be fetched"
INFO:     172.18.0.1:45646 - "GET /api/health?token=*** HTTP/1.1" 200 OK
{"time": "2026-10-09T01:07:48.808+00:00", "level": "INFO", "logger": "httpx", "message": "HTTP Request: GET https://mikanani.me/RSS/MyBangumi?token=*** \"HTTP/1.1 200 OK\""}
{"time": "2026-10-09T01:08:18.862+00:00", "level": "WARNING", "logger": "berth.services.rss", "message": "rss feed could not be fetched", "feed": 2, "error": "GET http://127.0.0.1:9/RSS/MyBangumi?token=***: connection refused"}
$ sqlite3 /config/berth.db 'select name, last_error from rss_feeds'
[('t76 fake', ''), ('t76 unreachable', 'GET http://127.0.0.1:9/RSS/MyBangumi?token=***: connection refused')]
```

跑完 `docker compose down --volumes`、刪目錄與 image。

這一輪在 code-review **之前**。code-review 改了 uvicorn 的 filter（見下）；要重跑時電腦中斷、Docker Desktop 沒在跑，沒自己啟動（會連帶拉起 `berth-local`）。

**code-review 之後重跑（2026-10-09，`495957a`）**：協調者啟動 Docker Desktop 之後，從這個 commit 重 build `berth:t76`，確認 image 裡的 `berth/logs.py` 是修過的 filter（`masked := redact_queries`），同一套隔離 compose。兩個 Feed：Mikan `?token=t76FAKEtoken0deadbeef`；連不上的 `http://127.0.0.1:9/RSS/MyBangumi?a=%s&token=t76FAKEerr0cafe`（格式字串進 `berth.services.rss` 的 extras 與 `last_error`）。另打五個請求：`/api/health?token=…`、`?a=%s&token=…`、`?a=%s&b=%d&token=…`、`?a=%25s%25d&token=…`、不帶 query 的 `/api/health`。

```
$ docker logs berth-t76 2>&1 | grep -c t76FAKE
0
$ docker logs berth-t76 2>&1 | grep -E "/api/health|mikanani|could not be fetched"
INFO:     172.18.0.1:40936 - "GET /api/health HTTP/1.1" 200 OK
INFO:     172.18.0.1:50340 - "GET /api/health?token=*** HTTP/1.1" 200 OK
INFO:     172.18.0.1:50346 - "GET /api/health?a=***&token=*** HTTP/1.1" 200 OK
INFO:     172.18.0.1:50350 - "GET /api/health?a=***&b=***&token=*** HTTP/1.1" 200 OK
INFO:     172.18.0.1:50364 - "GET /api/health?a=***&token=*** HTTP/1.1" 200 OK
INFO:     172.18.0.1:50372 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:43128 - "GET /api/health HTTP/1.1" 200 OK
{"time": "2026-10-09T02:15:50.882+00:00", "level": "INFO", "logger": "httpx", "message": "HTTP Request: GET https://mikanani.me/RSS/MyBangumi?token=*** \"HTTP/1.1 200 OK\""}
{"time": "2026-10-09T02:15:50.930+00:00", "level": "WARNING", "logger": "berth.services.rss", "message": "rss feed could not be fetched", "feed": 2, "error": "GET http://127.0.0.1:9/RSS/MyBangumi?a=***&token=***: connection refused"}
$ docker logs berth-t76 2>&1 | grep -ciE "logging error|Traceback|not all arguments"
0
$ select name, last_error from rss_feeds
('t76 fake', '')
('t76 unreachable', 'GET http://127.0.0.1:9/RSS/MyBangumi?a=***&token=***: connection refused')
```

access log 帶 `%s`、`%d` 的四個請求都印出來了（uvicorn 的 access formatter 照樣拆得開 `args`），沒有 `Logging error`；不帶 query 的整條出現（第一行是等健康的迴圈、最後一行是容器的 healthcheck）。跑完 `docker compose down --volumes`、刪目錄與 image；`berth-local` 四個容器沒動。

### 票外發現（沒修，待使用者決定）

- **`/api/search` 把 Prowlarr 的 API key 交給一般使用者**：搜尋結果的 `download_url` 是 Prowlarr 的代理下載連結，帶 `?apikey=<Prowlarr key>`；`/search` 不在 `gate.ADMIN_PREFIXES`，任何登入的 Jellyfin 使用者都拿得到，前端只把它原樣送回送單 API。這是資料欄位不是 log 或錯誤訊息，修法要動送單流程（例如伺服器端記下連結、前端只拿不透明的 id），建議另開票。

### code-review（`3e09ddf` 起，Standards 與 Spec 兩軸）

處理了：
- **filter 遮格式字串會讓那一行印不出來**（Standards）：`?a=%s` 的占位符被遮掉、參數數量對不上，`TypeError`。改成上面「做法」那一條，測試 `test_a_placeholder_after_a_question_mark_still_formats` 先紅後綠。
- `IndexerRejectedError.messages` 沒遮（兩軸）：建構子遮，`test_prowlarr_reasons_are_masked_too`。
- brief〈日誌〉的宣稱比閘門大（Standards）：收窄成「log 與 `ServiceError` 的訊息」，並寫明任意例外的原文不遮與理由；guide 同步。
- `_SELF_PRINTING` 的註解說兩個都 `propagate=False`（Standards）：改成照 uvicorn 預設 `log_config` 的實際樣子。
- 測試缺口（Spec）：補 `uvicorn.error` 的 traceback 經 formatter 印出來不帶 token、`ServiceError` 建構子直接遮（`.torrent` 下載連結、`json_body` 那種）、access log 遮完 `args` 仍是五格。新加的三條各做過一次變異（拿掉對應的遮罩，只紅那一條）。

沒處理（記著）：
- `redact_queries(x) if isinstance(x, str) else x` 出現三處（Duplicated Code，判斷題）：各一行，抽 helper 換不到什麼。
- 遮過頭：`?` 前緊貼字的散文（`100%?ok`）、query 後緊接的非空白文字（全形標點）會被一起遮。只多遮、不漏。
- 遮不到的形狀：userinfo（`https://user:pass@`）、路徑裡的 passkey（`/rss/<passkey>/`）、`?` 前是空白或引號的孤立 query（`"?token=x"`）、值最後一個字元是 `:,.;)]` 時那一個字元。票只要求 query；Berth 目前接的三個 RSS 站都不是這幾種。
- `json_line` 只遮字串型別的 extras：`extra=` 塞 dict、`httpx.URL` 時經 `default=str` 原文出去。目前呼叫端都傳字串。
- `rss._note_failure`、`jobs` 整輪失敗的 `型別: 原文` 不遮：見上面〈查過、沒改的〉，brief 已寫明。
- `test_logs.py` 混了 log 格式的單元測試與走 respx 的 adapter 案例（判斷題）：留在同一檔，雙向測試照票要求寫在一起。
