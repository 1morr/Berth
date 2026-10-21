# 126 — 「正在下載」：RSS 每輪每部作品一則

**Status:** done

**Blocked by:** 125

**讀:** plan §11.5〈通知〉；brief §15；`berth/services/rss.py` 的 `poll_feed`、`_submit`、`_submit_waiting`（一輪在哪裡開始與結束）；送單的命令（`services/jobs.py` 的 `add_download` 一帶）；M4 票 03（大批送單）

## 為什麼

試跑時一次 Mikan 綁定 11 分鐘送出 144 個 torrent（plan §11.5）。每個 torrent 一則的話，手機會被洗版。人在場自己按下載時，也不需要再被告知一次。

## 做什麼

1. RSS 一輪（一個 Feed 的一次輪詢、補漏或綁定後的補送）送出的 Job，依收件人與作品合成一則：「芙莉蓮 S02E03–E05 正在下載（Route 名）」；這一輪結束時寫入，與送單的交易同進退的原則照 plan §3.3。
2. 人手按的下載（搜尋結果、作品頁）也送給其他訂閱者，但不送給按的人。
3. 收件人規則同票 125（訂閱、Discord ID、`UserViews`）。

## 驗收

- [x] 一輪送出同作品 3 集與另一部 2 集 → 每位收件人 2 則，季集範圍正確（pytest）
- [x] 一次綁定送出上百個 torrent（Fake）→ 每位收件人每部作品一則（pytest）
- [x] 手動下載：按的人不收、其他訂閱者收（pytest）
- [x] 沒送成功的（`submit_failed`）不算進「正在下載」（pytest）
- [x] 全部檢查、pytest 綠；CHANGELOG、progress.md 已更新

## Comments

- 2026-10-22 實作（session 紀錄見 progress.md）。寫入在新模組 `services/downloading`：`rss` 與手動送單都要呼叫它，放進 `notify` 會成環（`notify` → `waiting` → `rss`、`notify` → `issues` → `jobs`）。`notify` 只多了一句文案、`_BY_LIBRARY` 多一種、`_render` 照種類取標題。
- **一輪**是 `download_round`：一個 Feed 的一次輪詢（含輪裡的自動綁定、預先綁定、補漏）、人按的綁定、訂閱、「全部下載」、放行、改 Feed 的 Route 當場綁上的那幾部、手動送單。`bind_series` 拆成命令與 `_bind`，輪裡的綁定記在外面那一輪。輪結束時依作品 + Route 合成、commit；輪中途出例外照寫已經送出去的（torrent 已在 qBittorrent）。
- 季集從發佈名猜（`plan.guess_from_title`，從 `rss.library_copy` 抽出、兩處共用）；猜不到的那一筆不寫進範圍（120 集的測試快照只有 12 集，訊息說 `S01E01–E12`）。
- code-review 已改：
  - `download_round` 例外路徑裡寫通知也失敗時，原本的例外會被蓋掉（Standards 軸）。改成記 log、丟回原本的例外。
  - `download_round` 是新模組公開的命令卻沒有 `@command`：`test_command_marks` 認 coroutine function，`asynccontextmanager` 包過的不是，所以沒紅（Standards 軸）。補上標記；閘門的漏洞見下面。
  - `add_manual_download` 原標 `IRREVERSIBLE`，與同樣排「正在下載」的 `bind_series` 等（`REVERSIBLE`）不一致（Standards 軸）。改 `REVERSIBLE`：等級看命令的主效果，撤銷是刪 Job。
  - 「立即輪詢」、「只追之後的」、`subscribe_search` 當場那一輪原本沒記按的人（Spec 軸）。`poll_feed` 多 `user_id`，API 傳入；補 `subscribe_mikan` 與立即輪詢的測試。
  - 120 個 torrent 的測試補上季集範圍的斷言（Spec 軸）。
- code-review 未處理（決定或歸屬）：
  - **`test_command_marks` 看不到 async context manager**：新模組裡公開的 `@asynccontextmanager` 不標也不紅。這張手動補了標記，閘門沒改。
  - **「放行」、「全部下載」、改 Route 的 `presser` 傳遞沒有測試**（綁定、訂閱、立即輪詢、`POST /jobs` 有）。API 拿掉 `user_id=` 不會紅。
  - **收件人查詢有三份**（`notify.queue_ready`、`notify._queue_waiting`、`downloading.queue_downloading`）：同一個「有 Discord ID 而且訂了這一種」。抽成一支要動 `notify`，與同時開工的那一張票衝突，留給之後。
  - **兩種內容存法不同**：「可以看了」存合好的範圍、「正在下載」存逐筆季集，`_render` 一律再合一次（冪等）。形狀是沒有型別的 dict。
  - **`moment` 與 `batch` 成對傳**過 `_prebind`、`_auto_bind`、`_bind_to_feed_route`、`_bind`、`_subscribe`；`subscribe_mikan` 與 `_subscribe` 參數整份重複一次。可以讓 `DownloadRound` 帶時間，沒改。
  - **關機時被 cancel 的那一輪**已送出的沒有這一則（`download_round` 只接 `Exception`，cancel 時不碰資料庫）。
  - **人按「重試」、自動重送成功的**不補「正在下載」：不是一輪。
  - 立即輪詢撞上同一個 Feed 正在跑的背景輪詢時共用那一輪，用先開始那一輪的 `presser`。
