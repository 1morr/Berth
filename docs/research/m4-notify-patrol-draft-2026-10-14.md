# M4 巡檢與通知：拆票前的研究與草案（2026-10-14）

拆 M4 票（plan §11.5）前，由協調者委託的子代理只讀研究整理而成。**尚未經使用者拍板**：標 ★ 的是需要使用者決定的題目，括號內是建議。拆票時以使用者的決定為準，定案後摘進 plan §11.5 與 brief。

## 1. 成熟產品怎麼做

| 產品 | 管道與每人設定 | 事件 | 測試、重試、彙整 |
|---|---|---|---|
| Seerr | 11 種 agent；每人的設定在 `UserSettings` 一對一表（`telegramChatId`、`discordIds`），`notificationTypes` 是逐 agent 的位元遮罩。Telegram 分系統 chat 與個人 chat；Discord 只走 webhook，個人 ID 只拿來 @ 人 | 13 種，例如 `MEDIA_AVAILABLE`、`ISSUE_CREATED`、`MEDIA_AUTO_REQUESTED` | 不等送出結果、不重試，失敗只記 log；`applicationUrl` 沒填時訊息不附連結 |
| Sonarr / Radarr | Connections 照觸發點勾選：On Grab、On Import、On Health Issue、On Manual Interaction Required | 同左 | 有 Test 鈕；連續失敗會退避，健康頁顯示「Notifications unavailable due to failures」；不彙整 |
| Apprise | 一條網址描述一個收件端（`tgram://{token}/{chat_id}`），Python 套件 | — | 只回成功或失敗，分不出暫時性錯誤；只能送不能收 |
| ntfy | POST 到一個 topic；`Click` 帶連結、`view` 按鈕最多 3 個 | — | 在 ntfy.sh 上 topic 名稱本身就是密碼 |

管道比較：

- **Telegram Bot API**：天生可以一對一私訊，每人一個 chat_id。bot 不能先開口，使用者要先按 Start；`t.me/<bot>?start=<碼>` 可把綁定碼帶回（碼最長 64 字元）。`getUpdates` 用輪詢收訊息，不需要對外網址；M7 要的「同一個 bot 也收訊息、訊息帶按鈕」直接做得到。限制：同一個聊天每秒 1 則。
- **Discord webhook**：設定最簡單（貼一個網址），但只能發到頻道、不能私訊；不是 bot 擁有的 webhook 不能送互動按鈕。M7 要收訊息得另做 bot gateway 或公開的 HTTPS 端點。

**建議**：每人訂閱的存法照 Seerr；觸發點與「管道失敗上健康頁」照 Sonarr；第一個管道選 **Telegram，直接以現有的 httpx 呼叫 Bot API**。Apprise 能少寫 adapter，但使用者要自己拼網址、分不出暫時性錯誤、M7 用不上。

## 2. plan「拆 M4 票時要定的」逐條

1. **`record_event` 一定要一筆 Job**：A 放寬 events（時間線被污染，游標問題仍在）；B **另立通知 outbox**（`notifications` 表：收件人、種類、彙整鍵、payload、狀態、次數、`next_attempt_at`、錯誤），與觸發它的變更同一交易寫入（§3.3 交易內不打網路），另一個迴圈負責送。建議 B：掛勾只放 `record_event`（照事件型別決定入不入列，它本身有一分鐘去重）與 `record_issue` 的 `opened`。plan §11.5「events 表上的訂閱者」要改寫。
2. **events 會被 purge，id 不能當游標**：選 B 就不需要游標。
3. ★ **Berth 自己的對外網址**（建議：`settings.notify.public_url`，照 Seerr 的 `applicationUrl`；設定頁以瀏覽器的 `location.origin` 預填、由人按存；沒填時訊息不附連結、健康頁提醒）。「可以看了」的 Jellyfin 連結：套件內又沒填 Jellyfin 對外網址時，用 Berth 對外網址的主機名加 `JELLYFIN_PORT` 推出來。另要補 `/review`、`/issues` 的單件深連結。
4. ★ **RSS 送出的 Job `user_id` 是 None，「正在下載」送給誰**（建議 C：訂閱了這種通知、而且 Jellyfin `UserViews` 看得到那條 Route 媒體庫的人；與「可以看了」同一條規則）。A 送給綁定者（自動綁定是 system，等於沒人收）；B 只送 admin。
5. ★ **「正在下載」怎麼彙整**（建議：不按輪——輪的界線會被補舊集、手動綁定打破；改為同一收件人同一種類的去抖動，安靜滿 2 分鐘才送、最多壓 15 分鐘，合成一則「N 集，作品 × 季集，Route」；「等你處理」用同一套）。
6. **「可以看了」照 `UserViews` 過濾**：Route 的 `jellyfin_library_id` 在不在那個人的 `user_views` 裡，送出時才查；查不到時留在佇列重試，**絕不退回全送**（否則洩漏）。
7. ★ **每人的訂閱存哪裡**（建議 B：`users` 加 `telegram_chat_id` 與 `notify_types`，Seerr 的做法；全域的 bot token 與對外網址放 `settings.notify`）。A 以 user id 為鍵放 `settings.notify`：整組覆寫，多人同時改會互蓋。★ 預設值（建議：admin 全開，一般使用者只開「可以看了」）。
8. **Feed 失敗拆欄**：補舊集的失敗逐個 Series 發生，拆成 `rss_series.backfill_error`；`rss_feeds` 加 `error_since`（照 Sonarr 的 `InitialFailure`，「一直失敗」要知道從何時開始）。
9. **`_still_ignored` 與 `cleared_at`**：判斷與寫入搬進 `issues`，由 `health_issues._settle` 與 `resolver.settle_verdicts` 共用；`settle_verdicts` 遇到已忽略而這次比對一致的那一列要寫 `cleared_at`。

另兩題 ★：巡檢查到的開成**新的 Issue 型別**（忽略沿用「條件持續期間有效」）；「Issue 新增」**併進「等你處理」**，少一種要訂閱的。

## 3. 拆法草案（暫編 104–113；104 已被精靈收尾票占用，實際從 105 起編）

| 票 | 標題 | Blocked by | 做什麼（使用者角度） | 驗收要點 |
|---|---|---|---|---|
| 104 | Telegram 打通：可以看了 | — | admin 填 bot token、按測試自己收到一則；以深連結綁定；入庫並在 Jellyfin 反查到時收到「可以看了」 | outbox、通知迴圈、`adapters/notify/telegram`、`UserViews` 過濾；token 不出現在 log；假 adapter 跑通全程＋一次真 bot 實測 |
| 105 | Berth 對外網址與深連結 | 104 | 訊息點下去直接開到那一件 | 網址欄位與預填、`/review`、`/issues` 單件深連結、Jellyfin 連結推導、未登入經 `?redirect=` 回到那一件 |
| 106 | 每人訂閱與設定頁 | 104 | 每個人自己選要收哪幾種、可解除綁定 | `users` 欄位 migration、預設值、i18n；先 `/impeccable shape` |
| 107 | 正在下載（彙整） | 106 | 一次綁定只收到幾則摘要 | 收件規則 C、去抖動、內容說得出作品、季集與 Route；送單失敗的不通知 |
| 108 | `_still_ignored` 搬到 issues | — | 忽略過的不一致不會每天重開 | 兩條路徑都寫 `cleared_at`；變異測試 |
| 109 | 等你處理 | 105、108 | 進審核或新 Issue 時推「有 N 件」，連到最新那一件 | 只送 admin、去抖動 |
| 110 | 管道失敗不阻塞、健康頁看得到 | 104 | Telegram 掛掉時管線照跑，健康頁說得出原因 | 暫時性錯誤 1m/10m/1h/6h 退避，永久錯誤（401、403、chat not found）不重試；狀態從 outbox 算 |
| 111 | Feed 失敗拆欄 | — | RSS 頁分得出是輪詢失敗還是補舊集失敗 | migration、`error_since` |
| 112 | 每日巡檢 | 109、111 | 缺號、同一集多份、卡住的 Job、一直失敗的 Feed 變成 Issue；放太久的事每日提醒 | `services/sweep`，04:00 對帳之後跑，重複跑不重開 |
| 113 | 週報 | 105、112 | 每週一則＋一個頁面：入庫了什麼、修了什麼、還有什麼等人 | 現算不存；頁面先 shape |

M4 驗收的真服務 e2e 與 UI 收尾（critique、audit、polish）放進 113 或另開收尾票。

## 4. 程式碼裡會影響拆法的事實（2026-10-14，main `ddc0422` 前後）

- `berth/services/jobs.py` 的 `record_event` 參數必須是 `Job`；但 `berth/models/event.py` 的 `job_hash` 本來就可以是 null。
- `berth/services/deletion.py` purge 時依 `job_hash` 刪事件；events 的 id 沒有 AUTOINCREMENT（migration `8b1e1dc5336b`），SQLite 刪掉最新幾列後可能重用 id。
- `berth/services/rss.py` RSS 送單一律 `user_id=None`，自動綁定也是；只有人親手綁定時補舊集才帶 user；`RssFeed.user_id` 只有從 Media 頁建的 Feed 才有值。
- `berth/services/resolver.py` 的 `jellyfin_item_resolved` 一筆 Job 只寫一次，可直接當「可以看了」的訊號；payload 只有 `count`，季集要從帳本讀。
- `berth/models/route.py` 有 `jellyfin_library_id`，`UserViews` 判斷只是集合比對。
- `berth/services/deeplink.py`：套件內又沒填 Jellyfin 對外網址時網址是空字串，後端組不出連結。
- `web/src/routes.tsx` 的 `/review`、`/issues` 沒有 `validateSearch`，目前沒有單件深連結。
- `berth/services/issues.py` 的 `record_issue` 回 `opened`，可當入列掛勾；partial unique 只管 open，忽略過的會被開成新的一件。
- `resolver.settle_verdicts` 不檢查忽略、也不寫 `cleared_at`（對照 `health_issues` 的 `_settle`）。
- `rss.py` 輪詢覆寫 `last_error`；補舊集是往後接、逐個 Series。
- `berth/redact.py` 只遮網址 `?` 之後的值；Telegram token 在路徑裡（`/bot<token>/`），httpx 的 INFO log 會原樣印出，104 一定要處理。
- `ServiceKind` 只有三種，`HealthSettings` 以它為鍵，不適合把管道塞進去。
- `berth/pipeline/reconciling.py` 已有「每日 04:00、每分鐘醒一次」的寫法，巡檢可照抄。
- `berth/services/review.py` 加 `issues.count_open` 算得出「N 件」；待綁定的 RSS Series 不在裡面。

行號會隨程式漂移，拆票時以 grep 重新定位。

## 來源

- [Seerr Telegram 文件](https://github.com/seerr-team/seerr/blob/develop/docs/using-seerr/notifications/telegram.md)
- [Seerr Discord 文件](https://github.com/seerr-team/seerr/blob/develop/docs/using-seerr/notifications/discord.md)
- [Seerr UserSettings.ts](https://github.com/seerr-team/seerr/blob/develop/server/entity/UserSettings.ts)
- [Seerr notifications/index.ts](https://github.com/seerr-team/seerr/blob/develop/server/lib/notifications/index.ts)
- [Seerr telegram agent](https://github.com/seerr-team/seerr/blob/develop/server/lib/notifications/agents/telegram.ts)
- [Seerr General settings](https://docs.seerr.dev/using-seerr/settings/general/)
- [Sonarr Settings（Connections）](https://wiki.servarr.com/sonarr/settings)
- [Sonarr System（通知失敗）](https://wiki.servarr.com/sonarr/system)
- [Apprise Telegram](https://github.com/caronc/apprise/wiki/Notify_telegram)
- [ntfy publish](https://docs.ntfy.sh/publish/)
- [Telegram Bot FAQ](https://core.telegram.org/bots/faq)
- [Telegram deep linking](https://core.telegram.org/bots/features#deep-linking)
- [Discord webhook](https://docs.discord.com/developers/resources/webhook)
