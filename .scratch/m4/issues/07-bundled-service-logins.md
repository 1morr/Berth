# 07 — 套件內 qBittorrent / Prowlarr 的介面帳密：各自的泊位、各自的欄位

**Status:** done

**Blocked by:** 06

**讀:** brief §16.3（qBittorrent 預置的免密白名單）、§20.7（Prowlarr `config/host`）；plan §9.2、§9.3 第 4、6 步；`berth/services/qbittorrent.py:~241`、`berth/services/indexer.py:~380`（現在寫介面帳密的兩處）

## 為什麼

現在的「同一組帳密也套用到 qBittorrent 與 Prowlarr 介面」是第 1 步的一個勾選框。2026-09-26 在 `berth-lab/bundled`
取消勾選實測：Berth 靠「Berth 容器 IP 免密白名單」照常連 qBittorrent，但**使用者自己打開 qBittorrent 的 WebUI
只剩容器 log 裡每次重啟都換的臨時密碼**，精靈一個字都沒提；Prowlarr 則是介面完全沒登入，第一次打開時它自己要人設。

06 把第 1 步改成「Jellyfin 擁有者」之後，這個勾選框沒有地方放了。

## 做什麼

1. qBittorrent 泊位（套件內）加「WebUI 帳密」欄位：預設帶入擁有者那一組（可改），文案說清楚這是 qBittorrent
   自己的登入、Berth 自己不需要它（免密白名單）。留空的選項要說出後果（只能看容器 log 的臨時密碼），
   或乾脆不給留空——shape 時定並寫理由。
2. Prowlarr 泊位（套件內）同樣。
3. 既有服務的這兩個泊位**沒有**這一格（05 的規則：不寫既有服務的帳密）。
4. 設定頁（票 m3/06i 的五頁）同一格重用，改完之後再寫一次。

## 驗收

- [x] 套件內：在泊位裡設的帳密之後能登入 qBittorrent WebUI 與 Prowlarr 介面（`berth-lab` 實測 + 整合測試）
- [x] 既有：兩個泊位沒有帳密那一格，Fake 上斷言沒有寫入（整合測試）
- [x] 設定頁改帳密後舊的失效、新的有效（整合測試）
- [x] plan §9.3 第 4、6 步與 brief §16.3 表格同步
- [x] lint、type、test、前端 e2e 綠燈

## Comments

**2026-09-28 實作紀錄**

- shape（`.scratch/m4/service-logins-shape.md`）問了使用者兩題，都照建議：兩格都必填；帳號預填擁有者名字、密碼打兩次。
- 登入跟著泊位的「套用」「加入」送（`login`），設定頁走 `PUT /setup/{qbittorrent,indexers}/login`；必填由步驟導出（沒設過的那一條是 `pending`，精靈停住）。既有服務帶登入回 422。細節與偏差見 progress.md。
- 整合測試：`test_setup_qbittorrent.py`、`test_setup_source.py`（套件內設登入後替身只認新的一組、`set_interface_login` 舊的失效新的有效、沒登入精靈不走、既有 422 且沒寫）、`test_setup_api.py`（兩支 PUT、空白帳號 / 空密碼 422、帳號去空白）。前端：vitest（泊位必填、預填、回頭看收起、設定頁兩區、連不上貼原文）、`interfaceLogin.test.ts`；前端 e2e 的 wizard / existing / settings（1280 與 390）。
- 驗證：
  - 真服務 e2e 22 passed（18 分 37 秒）；`harness.qbittorrent_session` 改用精靈第 4 步泊位上設的那一組（`WEB_UI_LOGIN`），不再讀容器 log 的臨時密碼。跑之前依使用者指示在 `berth-trial` `docker compose down`（它的四個 Created 容器佔了同名容器與 `berth` 網路），跑完 `docker compose create` 還原、未啟動。
  - berth-lab `bundled`（`berth:m4-07`，playwright 走精靈）：第 4 步帳號預填 `labowner`，設完 qBittorrent `auth/login` 對那一組 204、錯的 401；第 6 步（只勾 Nyaa.si、dmhy；Nyaa 在這台是 SSL 失敗，與本票無關）設完 Prowlarr `/login` 對那一組 302 到 `/`、錯的 `loginFailed=true`、匿名打介面被導去登入頁。再打兩支 `PUT …/login` 換成新的一組：qBittorrent 舊的 401 新的 204，Prowlarr 舊的 `loginFailed` 新的 302 到 `/`。精靈停在 TMDB 之前（完成要貼真的 TMDB key，沒做），所以設定頁的 UI 在 lab 上沒走，由前端 e2e 的 `settings` 驗。lab 現在的帳密記在 `berth-lab/CREDENTIALS.md`。

**code-review 沒處理的發現**

- `QbittorrentOut.web_ui_login` 與 `writes_preferences` 目前值相同（都是「套件內」）：意思不同（有登入那一格 / 寫全域偏好），留著兩個欄位。
- `_refuse_existing` 在 `qbittorrent.py`、`indexer.py` 各一份（訊息不同）；`probe.origin is ServiceOrigin.BUNDLED` 在 `setup.py` 出現三次。
- Berth 寫下的那一組登入，qBittorrent 借 `QbittorrentSettings.username/password`（Berth 本來就拿它登入），Prowlarr 在 `SetupIndexer.web_ui_*`：兩邊住處不同，靠註解說明。
- 剖面「WebUI 登入」那一列還沒設時說「將設為下面填的那一組」，沒帶名字（shape 寫的是「將設定 · 名字」；名字就在下方欄位）。
- 票 07 之前以舊流程設過 Prowlarr 登入的安裝，`SetupIndexer.web_ui_*` 是空的（票 06 的 migration 拿掉了 `login_password`），設定頁那一區會說「還沒有設過」，實際上 Prowlarr 有登入；再設一次就對了。
