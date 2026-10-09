# 76 — log 裡不出現 URL 上的秘密（Mikan 個人 token 等）

**Status:** ready-for-agent

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

- [ ] 盤點結果（logger、URL 種類、錯誤訊息與 DB 欄位）寫在票 Comments
- [ ] log 裡 URL 的 query 值一律遮掉；雙向測試在測試檔內
- [ ] 錯誤訊息 / `last_error` / API 回應裡的 URL 照盤點結果處理
- [ ] 隔離環境實跑：`docker logs` 搜不到假 token，附指令輸出
- [ ] 全部檢查、pytest、vitest 綠；CHANGELOG、progress.md 已更新
