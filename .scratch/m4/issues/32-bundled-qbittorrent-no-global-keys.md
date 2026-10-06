# 32 — 套件內 qBittorrent 不寫全域鍵；全域偏好不再影響 Route

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S5、§A1 BTH 2 列、§E「簡化方案」E-1、改進清單 P0-1）；brief §19「精靈審計後的八項」D2、§16.3、§16.4、§4.1、§20.2；plan §8.1、§9.3、§9.5

## 為什麼（2026-10-06 審計）

- **會擋送單（實測）**：使用者在套件內 qBittorrent 把全域 `save_path` 改成 `/data/my-downloads`，三條 Route 從 6/6 變 1/6「阻擋」、送單被拒。Route 檢查對套件內那一台另外現查全域 `save_path`，Berth 卻根本不用這個鍵：送單時每個 torrent 都帶分類與 `autoTMM=true`。既有那一台不看全域，同一段 docstring 自己寫了理由。
- **錯誤指錯對象**：錯誤掛在「qBittorrent 的路徑 Berth 看得到 `/data/torrent/complete/movies`」底下，內容講的卻是另一個目錄，還叫使用者「把它建回來」。截圖 s6-05。
- **D2 拍板**：套件內也不寫 `save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`。頁 2 差異表、設定頁漂移表、「還原建議設定」跟著拿掉。理由同 M4 票 22 拿掉 `temp_path`。

## 做什麼

1. 套件內 qBittorrent 的精靈寫入只剩 WebUI 登入。白名單預置不動。
2. Route 檢查對兩種來源都只看分類路徑（complete 與 incomplete），拿掉現查全域 `save_path` 那一段。
3. 拿掉頁 2「將會寫入的鍵」差異表、設定頁的漂移表與「還原建議設定」、健康頁的「設定被改過」，以及它們的 API、i18n 與測試。
   `POST` 還原那一支屬於對外 API 的破壞性刪除（D2 已拍板），要記進 CHANGELOG。
4. 已存在 `setup.qbittorrent.steps` 裡的三鍵步驟紀錄變成孤兒：寫資料 migration 清掉，或改成寬鬆讀取；選哪一種記在偏差。
5. 已經被 Berth 寫過全域鍵的安裝**不改回去**：Berth 沒有存原值，不知道使用者原本設的是什麼。
6. 文件同一個 commit 改：brief §16.3 表格的 qBittorrent 列與「還原建議設定」那一條、§16.4、plan §8.1 與 §9.3、README 的「套用五個建議鍵」。
   brief §16.3 頂端「待改寫」那句裡 D2 的部分拿掉。

## 驗收

- [x] 整合測試（雙向）：套件內 qBittorrent 的全域 `save_path` 改成不存在的目錄，Route 仍是綠的；分類路徑看不到時才轉紅，錯誤講的是分類路徑
- [x] 閘門測試：精靈走完套件內與既有兩種流程，Fake qBittorrent 收到的 `setPreferences` 只有 WebUI 登入的鍵。在測試檔內做雙向變異驗證：造一次寫 `save_path` 要變紅，改無關命名不變紅
- [x] 舊的三鍵步驟紀錄經 migration 或寬鬆讀取後，頁 2 與設定頁都打得開（整合測試用一筆舊格式資料）
- [x] 前端：頁 2 與設定頁不再出現差異表、漂移表、「還原建議設定」；zh-Hant 與 en 的鍵一起刪
- [x] playwright 實跑：把套件內 `save_path` 改掉後，健康頁 Route 仍是綠的，送一筆單成功；附截圖
- [x] brief、plan、README、CHANGELOG 已改；progress.md「偏差與決定」記一行
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**實作（2026-10-06）**：
- 頁 2 的纜繩只剩 `web_ui_password`（`QbittorrentStep` 少三個值），套件內與既有的「做完了沒」收成同一條
  （`setup._qbittorrent_secured`：登入那一條 `ok` / `skipped`）。`services/qbittorrent.py` 的差異、漂移比對整段刪掉，
  `read_qbittorrent_diff` 改名 `read_qbittorrent`；HTTP 路徑 `GET /setup/qbittorrent/diff` 不改名（對外介面，票面只授權刪
  還原那一支）。
- Route 檢查一（`_download_path`）看分類回報的兩個路徑：save path 與分類自己的 `download_path`（票 22 之前的分類沒有就
  不看）。`_Checker` 不再需要 qBittorrent 的來源。健康檢查不再讀 `app/preferences`。
- 第 4 點選**寬鬆讀取**（偏差已記）：`SetupQbittorrent.steps` 讀的時候丟掉不認得的 key；退役的失敗代碼
  `save_path_missing` 讀成 `unexpected`（`RETIRED_FAILURES` 明列，其餘不認得的照樣讀不進來）。健康那一列的 `drift`
  靠 `extra="ignore"` 自然丟掉。整合測試 `test_health_api.py::TestRecordsFromBeforeTicket32` 用一筆舊格式資料打開頁 2、
  設定頁、健康與 Route；`test_models.py::TestRetiredStepFailures` 雙向。
- 設定頁的 qBittorrent 改讀頁 2 那一支；`GET /settings/qbittorrent/diff` 也拿掉（它只服務漂移表），CHANGELOG 記為破壞性。
- 閘門 `tests/integration/test_qbittorrent_login_only.py`：套件內（套用、重按、設定頁換登入）與既有（套用兩次）各走到
  建 Route、送一筆單，`setPreferences` 收到的只有 `web_ui_username` / `web_ui_password`；鍵名寫死在測試裡。變異：
  把 `WEB_UI_USERNAME_KEY` 換成 `save_path` 會紅、換帳號與 `DEFAULT_WEB_UI_USERNAME` 不紅。
- 測試替身：`applied_qbittorrent`（全域 save path = complete 根目錄）刪掉，全部改用 `FakeQbittorrentClient()` 本身——它的
  全域 save path 是 Berth 看不到的 `/downloads`，所以每一條 Route 測試都順便守著「全域路徑不影響 Route」。
- 演練 server：`drifted` 情境拿掉，換成 `global-path`（`import` + 套件內全域 save path 改成 `/data/my-downloads`）。
- 頁 2 的按鈕形狀（「套用這 N 項」現在只數登入、重裝時是「套用這 0 項」）照舊，留給票 38。

**playwright 實跑**（`scripts/fake_setup_server.py --scenario global-path`）：健康頁三條 Route 6 / 6、qBittorrent 已繫上，沒有
「設定被改過」；按「立即重測」之後新的一輪仍全綠；SPY×FAMILY 頁送一筆到 Anime「已送出」；設定 → qBittorrent 只剩健康、
位址與憑證、介面登入、磁碟門檻，沒有表格與還原鍵。截圖在 session scratchpad（`t32-01-health-routes-green.png`、
`t32-02-submitted.png`、`t32-03-settings-qbittorrent.png`），沒有進 repo。替身 qBittorrent，不是真的容器——真服務 e2e 是票 34。

**code-review（`/code-review 12d441d`，兩軸 opus）**：
- 已處理：`SetupStep.failure` 的寬鬆讀取原本吞掉任何不認得的代碼，收窄成 `RETIRED_FAILURES` 並補雙向單元測試；英文
  `switchWarning.qbittorrent` 的主謂一致；`DESIGN.md` 的「設定漂移的泊位格」；一處 `type: ignore` 補理由；後端對已刪欄位的
  「不存在」斷言拿掉（型別產生器已經守著）；`fake_qbittorrent` 只轉呼叫、還要 `type: ignore`，拿掉改直接建構；
  `QbittorrentStep.tsx` 的 `writes` 改 `bundled`；測試常數 `DIFF` / `EXISTING_DIFF` 改名；過時的「第 4 步」「逐鍵」「五個鍵」
  「漂移還原」註解。
- 未處理（判斷題）：HTTP 路徑與 handler `get_qbittorrent_diff` 的名字不改（對外路徑，改名是另一次破壞性變更）；i18n
  `qbittorrent.apply` 的 `{{keys}}` 參數名不改（按鈕整個由票 38 重做）；前端 vitest 對「沒有差異表、沒有還原鍵」的斷言
  留著——它們就是本票的驗收條件；`plan.md` T0.8 那一列是 M0 的歷史紀錄，不改。
