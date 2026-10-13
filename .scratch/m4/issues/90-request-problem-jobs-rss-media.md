# 90 — 錯誤訊息說對原因（二）：工作、RSS、作品頁

**Status:** done

**Blocked by:** 89（照它定下的寫法延伸，也避免兩張同時改 i18n 檔）

**讀:** 票 89 與它的 Comments；`docs/research/simplification-audit-2026-10-13.md` 的 S2

## 為什麼

同票 89：拒絕原因解析不出來時一律說「API 沒回應」，對 500、401 說錯。這張把 89 的做法延伸到剩下的範圍。

## 做什麼

- 照票 89 的寫法，改 jobs、rss、media（含 `api/files.ts`），以及其他還留著「解析不出來就說 API 沒回應」寫法的地方。做完時 `web/src` 不應該再有這種寫法。
- 收掉因此不再用的 i18n key（zh-Hant 與 en 成對）；斷言整句文字的測試跟著改。

## 驗收

- [x] 範圍內 500、401、離線三種失敗各說出對的原因；vitest 守，做變異驗證
- [x] 全 `web/src` 搜不到「API 沒回應」當作通用錯誤的退路；兩種尾巴（`Berth’s own API did not answer…`、`The Berth backend may be down…`）只留在真的是連不上的情況
- [x] Playwright 實跑附截圖或文字結果；**不准碰使用者的 `berth-local`**
- [x] 全部檢查、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新

## Comments

- 2026-10-13 範圍：票面說的 jobs、rss、media 之外，`web/src` 其餘留著這種寫法的也一起改（探索、媒體庫、健康頁、設定頁、設定精靈），約 40 個 i18n 值只留前半句。寫法同票 89：能畫元件的用 `RequestFailed lead=…`，只收字串的（`Field` 的 `error`、`RetryLine` 的 `message`、精靈的 `librariesFailure`、刪除確認區的空間估算）用 `problemText`。只傳 boolean 的地方改傳 error。
- 2026-10-13 驗收 2 的 grep：非測試程式碼裡 `did not answer`、`may be down`、`isn’t answering`、`自己的 API 沒有回應`、`後端可能沒在跑`、`確認 Berth 後端`、`連不上 / 讀不到 Berth 後端` 只剩 `request.offline`（真的連不上）、qBittorrent / Jellyfin / Prowlarr 各自的拒絕句，與描述舊行為的註解。
- 2026-10-13 變異驗證：(1) `problemText` 改成不看錯誤、一律回離線 → 全套 152 條紅，名字含「離線」的 0 條紅（其餘紅的是 `RequestFailed` 本身的 401 / 403 / 擁有者情境）；已還原，`requestProblem.ts` 無 diff。(2) 各組各挑兩處呼叫端改成 `error={null}` 或寫死離線句：每處 500、401 紅、離線綠，已還原。(3) code-review 後的三條各自變異過：頁 1 拿掉 `ApiKeyFailure`、`HealthSection` 退回先判斷 `isError` 的順序，各自紅。
- 2026-10-13 Playwright 實跑（`fake_setup_server.py`：downloads 8690、rss 8691、routes 8692；`skipper` 登入；`page.route` 造 500 / 401 / 斷線；沒碰 `berth-local`）：下載列表 500 →「讀不到下載列表。 Berth 的後端出錯了。再試一次；還是不行的話看 berth 容器的 log。」，401 →「讀不到下載列表。 登入已失效：重新登入 Berth，再試一次。」，斷線 →「讀不到下載列表。 Berth 的後端沒有回應：它可能沒在跑，或網路斷了。確認容器狀態後再試一次。」；RSS 頁、媒體庫路徑頁的清單三種同樣各說各的；媒體庫路徑「全部重新檢查」401 →「檢查沒有走完。 登入已失效…」加「前往登入」鍵與技術細節（截圖看過版面）。
- 2026-10-13 code-review 已處理：Standards 軸——`IndexerSites` 的 `RequestFailed`（`alert`）在摘要的 `aria-live` 裡巢狀 → 移到外面（測試守摘要裡沒有 alert）；頁 1 換 key「請求跑完、Jellyfin 沒給 key」那一支被削成「請求沒跑完。」→ 抽出 `ApiKeyFailure`，說那一步的失敗原因（同頁 3）；`api/refusal.ts`、`api/routes.ts`、`QbittorrentStep` 三處說「落回通用訊息」的註解改準；`CompleteFailure` 的 `backend` 改名 `request`。Spec 軸——`jobs.plan.off`、`jobs.timeline.off`、`rss.bound.itemsOff`、`watch.failed` 不說原因 → 接上原因；RSS 綁定與一次性連結的 TMDB 搜尋失敗什麼都不說 → `RequestFailed`；`rss.bind.mediaOff` 怪 TMDB → `mediaReadFailed` 加原因；`HealthSection` 重抓失敗會把已載入的卡換成錯誤 → 先看有沒有那一列。
- 2026-10-13 code-review 未處理：(1) 設定精靈的 `indexer.remove.failed`（「Prowlarr 可能正在重啟」）與 `routes.rereadFailed`（「讀不到 Jellyfin 現在的媒體庫」）不管錯誤是什麼都怪外部服務；媒體庫的 `inventory.narrow.failed` 不說原因。三者都不是「API 沒回應」的寫法、也不在 jobs / rss / media，要改先查後端在那兩個外部服務問不到時回什麼，另開票。(2)「`error` 為空就說檢查中，否則 `RequestFailed`」在 `SetupPage.Waiting` 與 `QbittorrentStep` 各一份，判空寫法有 `=== null || === undefined`、`!= null`、`!== null` 三種：各自短，不抽。(3) `CompleteStep` 同時收 `failure` 與 `error`（前者由後者算出）：`failure` 另外還看 TMDB 與 Route 狀態，不併。(4) `FeedSection` 輪詢與移除都失敗時只說輪詢那一個：兩顆鍵不會同時按。
