# 04 — 命令標記補齊（二）：服務、設定、搜尋與帳號；拆掉豁免表

**Status:** done

**Blocked by:** 03

**讀:** 同 03；brief §16.4（既有服務不被改動：精靈對外部服務的寫入多半不可逆）

## 為什麼

接續 03。這一半大多是精靈、設定與外部服務的命令，寫到別人服務上的通常回不去，要特別小心別標成可逆。標完之後豁免表整個刪掉，以後每個 service 命令一出生就被守。

## 做什麼

1. 標完其餘模組的公開命令：`auth`、`bench`、`clients`、`deeplink`、`discover`、`downloads`、`events`、`health`、`hints`、`jellyfin`（含 `save_bundled_libraries`）、`jellyfin_access`、`jellyfin_images`、`qbittorrent`、`routes`、`search`、`settings`、`setup`、`steps`、`tmdb`、`tracking`、`watch`、`watch_area`、`watching`（約 76 個；沒有公開命令的模組直接拿掉）。
2. 刪掉 `BEFORE_M3` 與用到它的分支，測試 docstring 改成「每個 service 模組都被守」。CLAUDE.md〈架構規則〉那一句同步改（不再有豁免表）。
3. 判不出等級的寫進 Comments，不要猜。

## 驗收

- [x] `BEFORE_M3` 不存在，所有 service 模組的公開命令都有標記，`test_command_marks` 綠
- [x] 寫到外部服務、回不去的命令標成 `irreversible`，有測試列出它們
- [x] CLAUDE.md 架構規則那一句與測試對得上
- [x] 全部檢查、pytest 綠；progress.md 已更新

## Comments

- **「改設定」定案**（票 03 交下來的）：照 brief §14 / plan §11.6 字面標 `irreversible`，就算再改一次改得回去；
  `notify.set_bot_token` / `set_mine` / `set_berth_url`、`indexer` 的加站、移除、跳過與介面登入、
  `qbittorrent.set_interface_login` 改標，`Effect.IRREVERSIBLE` 的定義與 brief §14 各補一句。不算設定、維持可逆的：
  `search.remember_names`（跟著使用留下的偏好）、`rss.set_feed_interval` / `set_feed_routes`（Feed 自己的屬性，
  加 Feed 本身可逆）、`rss.set_exclusions` 等排除條件（brief §14「記憶」要 AI 寫回的）。Spec 審查提醒
  「Feed 的 Route」與「改 Route」字面上容易混，**請使用者確認這條界線**。
- **閘門擴到類別方法**：code-review 兩軸都抓到 `JellyfinAccess.mark_played`（API 直接呼叫、標為未看清掉觀看次數）
  在類別上、測試看不到。現在看公開類別的公開 async 方法（底線開頭的類別與方法不算），雙向變異加一組；
  `Downloader.poll`、`ReconcileRunner.start` 等 14 個跟著標。`mark_played` 標已看與標未看同一支，照最壞的標
  `irreversible`：M6 要讓 AI 標已看得先拆。
- **判斷依據**：
  - 登入 Jellyfin（`auth.sign_in`、`jellyfin.resolve_interface_login`）標 `irreversible`：每次登入記一筆裝置
    「Berth」，Berth 刪不掉（brief §16.4、§20.22）；同一位再登入是換掉自己那一筆。
  - Route 的檢查（`check_route(s)`、建立、修改）與 `health.check_health`：會重建被刪的 `berth-*` 分類（Berth
    不刪分類），探針校驗到 100% 觸發使用者的「完成時執行外部程式」；健康迴圈不跑探針，但照樣重建分類。
  - `setup.retest_service` / `choose_service`：頁 2 的 qBittorrent 探針在 5.x 觸發「加入時執行」
    （Spec 審查抓到，原本標可逆）。`health.check_service` 只登入、讀版本，標可逆（改健康紀錄）。
  - `jellyfin_access`（context manager）標可逆：帳號停用時登出他每一台裝置；`auth.read_session` 刪的只有過期列，
    `Effect.READ` 的定義補了這一句。`remember_libraries`、`reread_libraries`、`discover.image_base` 存的是外部現況的
    抄本，照 TMDB 快取的先例標 `read`。
  - `poll_downloads`、`record_poll_failure`、`forget_route_checks`、`record_setup_results` 標可逆：只照現況推 Job、
    開收 Issue、寫紀錄，不排通知（票 03 的判準）。
- **code-review 未處理的**（判斷題）：
  - `settings.write_settings` / `update_settings` 照最壞的標 `irreversible`，而呼叫它們的 `read` / 可逆命令
    （`image_base`、`record_poll_failure`…）寫的是快取或紀錄分組——零件的等級看呼叫端，與票 03 的
    `jobs.transition`、`guarded` 同一個問題；它們不會變成工具，票 05 的登錄表可考慮給零件豁免或改私有。
  - `aclose`、`wait`、`KeyedLocks.hold` 這類生命週期與鎖也得標（`read`），同上。
  - 兩條清單測試只釘住現有名單：新加的設定命令標成可逆不會紅。要守住得有「這支寫設定」的機器判準，現在沒有。
  - 理由註解在幾個檔案裡相似（「改設定 brief §14 永遠要人」），都指回 brief 一處，沒抽。
- 判不出等級的：沒有。
