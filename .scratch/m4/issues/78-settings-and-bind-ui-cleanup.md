# 78 — 設定頁與 RSS 綁定：拿掉精靈留下來的選項與說明

**Status:** done

**Blocked by:** None — can start immediately（與 76 並行；與 77 都改 `web/src/i18n/resources.ts`，後合併的那張解衝突）

**讀:** brief §15「補舊集」與決定表「補舊集維持預設全補（2026-09-26）」；M3 票 12、19；M4 票 07、15、06i；`web/src/rss/SeriesBinder.tsx`、`web/src/media/SubscribePanel.tsx`、`web/src/settings/ServiceConnection.tsx`、`web/src/settings/InterfaceLoginSection.tsx`、`web/src/setup/ServiceChoice.tsx`；`berth/services/rss.py` 的 `bind_series`、`subscribe_mikan`（`backfill`、`passed_before`）

## 為什麼（2026-10-09 使用者本機試用）

1. **RSS 綁定的「同時補下載舊集」**：
   - 2026-09-26 使用者已經拍板「綁定時一律補齊舊集，不加開關」（brief 決定表）。
   - 但手動綁定（`SeriesBinder`）與作品頁訂閱（`SubscribePanel`）還留著票 12 的勾選。結果是自動綁定一律補、手動卻可以不補，兩邊不一致。
2. **Jellyfin 設定頁的「位址與憑證」**：
   - 照搬精靈的二選一卡片（`ServiceChoice`），卡片鎖住，下面再補一句「來源換不了」。看起來能選、實際不能選。
   - 左卡很空、右卡全是精靈用的長說明。
   - 段首的「與設定精靈那一頁的頁首是同一塊…」是寫給開發者看的。
3. **qBittorrent／Prowlarr 設定頁的「介面登入」**：
   - 「沿用 Jellyfin 帳密」是精靈的概念（頁 1 剛打過 Jellyfin 密碼）。在設定頁讀起來像「沿用上次的設定」。
   - 只有一格密碼框，看不出改的是帳號、密碼，還是兩個都改；也看不出帳號能不能改。
   - 上面那段「不設的話 WebUI 只剩臨時密碼」是精靈的說明，設定頁已經設過了。

## 做什麼

1. **補舊集不再有開關**：
   - 前端：`SeriesBinder` 與 `SubscribePanel` 拿掉勾選。
     - 按鈕改成「綁定並送出」（en 同義）。整季幾集要讀了才知道，按鈕不寫數字；送出後的結果照舊說送了幾集。
     - `backfillOn` / `backfillOff` 這類只為勾選存在的 i18n key 一起刪。
   - 後端：刪 `backfill` 參數（services、API schema、`web/src/api` 型別）與 `RssSeries.passed_before`，連同所有讀它的分支（`_backfill` 的略過判斷、`subscribe_mikan`）。
   - Alembic migration：drop `passed_before` 欄位，downgrade 加回。使用者已同意：已存了值的 Series，當初略過的舊集補回來。
     **實際行為（2026-10-09 實作時使用者拍板）**：補漏以 `(feed_id, guid)` 去重，已經寫成 `passed` 的不會被補漏補回，所以 migration 自己放回去——只放回因 `passed_before` 而略過的那幾筆（Mikan Feed 上、Series 的 `passed_before` 有值、發佈早於它），綁著的回 `matched`（下一輪輪詢去重後送出）、解綁的回 `unbound`；「只追之後的」那種 `passed` 不動。downgrade 只加回空欄位、不改回 `passed`。
   - 同一 commit 改 brief §15（刪「取消勾選時…」那一句）與 plan 相關段落，progress.md「偏差與決定」記一行。
2. **Jellyfin 設定頁改成唯讀摘要**：
   - 不再畫二選一卡片，改成一張摘要：來源（套件內／既有）、位址、版本、連線狀態，加一句為什麼不能換成另一台。
   - 只有「既有」才有改位址與 API key 的表單；套件內的位址固定，沒有可改的東西。
   - 刪掉段首那句開發者說明。
   - 「重新檢查」與存完重測照舊（`onConnected`）。
   - qBittorrent／Prowlarr 的設定頁仍可換來源，二選一保留，不在這張改。
3. **設定頁的介面登入改成一般的改帳密表單**（qBittorrent 與 Prowlarr 共用 `InterfaceLoginSection`）：
   - 拿掉「沿用 Jellyfin 帳密」。
   - 欄位：「目前的帳號：X」、帳號（預填目前的帳號）、新密碼、再輸入一次。
   - 按鈕「儲存」，下面一行「改了之後舊的那一組就不能再用」。
   - 拿掉精靈用的那段 lede（「不設的話…臨時密碼」）。
   - 精靈裡的「沿用」不動。後端的 `reuse_owner` 只剩精靈在呼叫，照舊保留。
   - 驗證規則（長度、冒號、兩次一致）與送出後的結果說明照舊。
4. **UI 走 `/impeccable`**：先 `shape` 兩個設定區塊，收尾 `critique` / `polish`。

## 驗收

- [x] 手動綁定與作品頁訂閱都沒有補舊集勾選，一律補；`backfill` 參數與 `passed_before` 欄位已刪，migration 升降都測過；brief、plan、progress.md 同步
- [x] Jellyfin 設定頁不再出現二選一卡片：套件內只有摘要；既有的有摘要與改位址／API key 表單；開發者說明已刪
- [x] qBittorrent 與 Prowlarr 設定頁的介面登入是「帳號、新密碼、再輸入一次、儲存」，沒有「沿用」；精靈裡的「沿用」照舊
- [x] 相關 pytest 與 vitest 已改寫，舊勾選的測試已刪；zh-Hant 與 en 文案並列
- [x] Playwright 實跑三個畫面並附截圖，用隔離環境（專案名 `berth-t78`、另一組 port）；**不准碰使用者的 `berth-local`**
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；CHANGELOG `[Unreleased]` 已記

## Comments

- **2026-10-09 實作（使用者拍板的偏離）**：
  - Jellyfin「既有」的表單只有位址一格：Jellyfin 沒有使用者填的 API key，Berth 用管理員登入換一把，換 key 在同一頁「管理員登入」區。驗收第二條的「API key」照此解讀。
  - 作品頁 Mikan 訂閱的鍵是「訂閱並送出」（那一塊的動詞是訂閱），手動綁定才是「綁定並送出」。
  - qBittorrent／Prowlarr 連線區共用的那句開發者說明一起改成給使用者看的說法，二選一本身不動。
  - 隔離實跑：Docker Desktop 沒在跑，啟動它會把 `berth-local` 有 restart policy 的容器一起拉起來，所以不起 compose，改用 `scripts/fake_setup_server.py`（config root `berth-t78-healthy` / `berth-t78-rss`，port 8678 / 8679，跑完收掉）。截圖在 `.playwright-mcp/t78-*.png`（不進版控）：RSS 綁定（1280 / 390）、Jellyfin 套件內摘要（1280 / 390）、既有摘要與改位址（e2e `existing` 拍的，1280 / 390）、qBittorrent 介面登入（空、驗證錯誤、已儲存、目前帳號 390）。
- **code-review（`3e09ddf` 起）處理了的**：Jellyfin 摘要補「等待中」倒數，設定頁照精靈每 3 秒自己重測（之前設定頁的倒數不會動）；migration 測試加一筆非 Mikan Feed 的反例並做過變異驗證（拿掉 `kind = 'mikan'` 會紅）；兩處過時註解；shape 文件與實作對齊。
- **code-review 沒處理的（判斷題）**：
  - `InterfaceLoginFields` 與 `NewLoginFields` 各組一次 `rule`（前者還要 owner 給沿用的錯誤句）。
  - `ServiceConnection` 判 `kind === 'jellyfin'` 三次（標題、lede、內容）；拆成 Jellyfin 專用的 section 要把兩支 mutation 也複製一份，暫不拆。
  - `InterfaceLoginSection` 傳的 `reuse: false` 在 `owner` 為空時本來就會是 false，留著是寫明意圖。
  - `whyBundled` / `whyExisting` 第一句相同、`rss.bind.willSendSeason` 與 `rss.subscribe.season` 近似：文案各自完整，不拼字串。
  - 設定頁還沒設過登入時帳號不再預填擁有者（票 07 的精靈行為），本票要的是「預填目前的帳號」。
- **沒動的既有問題**：390 寬的整頁截圖裡「管理員登入」區看起來疊在一起，是 `STICKY_ACTION` 黏底按鈕被整頁截圖拍在捲動位置上，不是版面錯。
