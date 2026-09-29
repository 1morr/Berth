# 15 — 精靈改為每個服務手動選擇：一個服務一頁、二選一、不偵測

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（05–07 已做完；08、09 被這張擋）

**讀:** brief §16.3、§16.4、§19 2026-09-29「精靈改為每個服務手動選擇」那一列、§20.14；plan §9.3（整節）、§9.4、§9.5；`.scratch/m4/wizard-manual-choice-decision.md`；票 05、06、07 的 Comments（沒處理的 code-review 發現有幾條就在這張要動的程式上）；開工先 `/impeccable onboard` shape 服務頁

## 為什麼

2026-09-29 使用者在全新環境試跑後拍板（brief §19）：Jellyfin、qBittorrent、Prowlarr 各一頁，進頁後使用者自己選
「套件內」或「既有」，不再偵測。現在的偵測（`services/setup.py` 的 `_verdict_*`，票 05 補過一次）只能靠「免密可進」
「沒有索引站」這類跡象猜服務是誰的，猜錯就寫到使用者的服務；Seerr 與 Sonarr / Radarr 接服務也全都是手動填、
按 Test（brief §20.14）。

## 做什麼

1. **選擇存下來，取代判定**：`settings.setup` 替每個服務記使用者選的來源；從此「套件內 / 既有」由它決定。整段刪掉
   偵測：`_verdict_*`、`detect_services`、`ServiceProbe.configured` 的釘住、`POST /setup/detect`、`probe_targets`、
   前端的偵測步驟與泊位板上方的前置列。票 05 的保護（既有不寫帳密、不改全域偏好、不替它加站）改讀選擇；還沒選的
   服務，寫入命令一律拒絕（票 05 Comments 的「沒有判定時預設 `BUNDLED`」一併消失）。舊資料庫的判定轉成選擇，
   寫 migration。
2. **服務頁的共同形狀**（plan §9.3〈服務頁的共同形狀〉）：頁首二選一；「既有」旁說明同主機、同容器路徑的條件
   （Jellyfin、qBittorrent）與要從 `COMPOSE_PROFILES` 拿掉哪一個；套件內連 compose 主機名、既有填那個服務要的憑證；
   選完就測，套件內測不過分「主機名解不到 → 把它加回 `COMPOSE_PROFILES` 再 `docker compose up -d`」與「容器還在啟動
   → 照舊輪詢到 2 分鐘」兩種說法。回頭改選擇的行為 shape 時定，寫進 plan §9.3。
3. **Jellyfin 頁就是擁有者**（票 06 的流程保留，拿掉它前面的偵測）：表單跟著那一台的 `StartupWizardCompleted` 走——
   未初始化給建立（選既有也一樣），已有管理員給登入（套件內重裝保留 config 也一樣）。套件內 Jellyfin 的媒體庫清單與
   建立移到頁 3（這張只搬，照現在的行為跑；改成按鈕觸發是 08）。
4. **套件內但已設過介面登入**：qBittorrent / Prowlarr 不強迫再設。先查證怎麼認得出「已經設過」（qBittorrent
   `app/preferences`、Prowlarr `config/host` 各回什麼），結論與來源補進 brief §20.14。
5. **「沿用 Jellyfin 帳密」**：套件內 qBittorrent / Prowlarr 的介面登入預設勾選；勾選時帳號是擁有者、密碼打一次，
   先以 `POST /Users/AuthenticateByName` 向 Jellyfin 驗過再寫；取消勾選是票 07 的欄位。設定頁的「介面登入」一區同一個勾選。
6. **介面密碼只存雜湊**（brief §19 2026-09-29 ⑤）：Berth 寫進套件內兩台的介面密碼只記帳號與加鹽雜湊，夠比對
   「已經是這一組」；migration 把票 07 存下的明文（`settings.services.qbittorrent` 套件內那一台的密碼、
   `SetupIndexer.web_ui_*`）換成雜湊。先確認 Berth 連套件內 qBittorrent 真的只靠免密白名單、沒有拿那組密碼登入；
   既有 qBittorrent 的 WebUI 帳密是 Berth 的連線憑證，照舊存（brief §16.2）。
7. **頁面與順序**：Jellyfin → qBittorrent → 媒體庫與路徑 → Prowlarr 與索引站（併成一頁：套件內讀 key、介面登入、
   現在的加站畫面；既有貼 API key，不加站）→ TMDB → 完成。步驟由狀態導出的規則照 plan §9.3〈續行與跳過〉改寫；
   泊位板五格、沒有前置列；「重新偵測這個服務」換成出問題那一頁的「重新測試」。門禁 `SETUP_OPENING_PATHS` 跟著改。
8. **文件同步**：plan §2.1（`settings.setup` 的欄位）、§6 setup 那一列、§8 與 §12 裡的精靈步號；README 的精靈段；
   CHANGELOG（精靈重做、舊判定轉成選擇、介面密碼改存雜湊）。

## 驗收

- [ ] 三個服務頁都是先選再測；進頁與選擇之前沒有任何探測請求（vitest + playwright network 紀錄）
- [ ] 選套件內而 compose 沒有那個服務：訊息說出 `COMPOSE_PROFILES` 的補法（整合測試：主機名解不到）；容器還在啟動照舊輪詢（06g 的測試改寫後綠）
- [ ] 票 05 的保護改讀選擇：選既有的 Prowlarr 沒有索引站、選既有的 qBittorrent 免密可進，仍不寫帳密、不改全域偏好、不加站（05 的 repro 改寫後綠）；雙向：選套件內的照舊寫
- [ ] 套件內但已初始化：Jellyfin 已有管理員 → 登入表單；qBittorrent / Prowlarr 已設過登入 → 不強迫再設（整合測試 + `berth-lab` 保留 config 重建實測）；選既有而 Jellyfin 未初始化 → 建立表單（整合測試）
- [ ] 沿用 Jellyfin 帳密：預設勾選；密碼錯時 Jellyfin 驗證失敗、兩台都沒被寫（Fake 斷言）；對的時候兩台的介面登得進（`berth-lab/reset.sh bundled` 實測）
- [ ] 資料庫裡沒有介面密碼的明文（測試讀 `settings` 斷言）；migration 對票 07 的舊列有測試
- [ ] 步驟導出與頁面順序有純函式的單元測試（後端與 `navigation.ts`）；泊位板五格、沒有前置列
- [ ] 偵測的程式碼刪乾淨（`_verdict_`、`detect_services`、`/setup/detect`、`probe_targets` grep 無殘留）；門禁測試雙向
- [ ] 舊資料庫的判定轉成選擇（migration 測試：精靈跑完的、跑到一半的）
- [ ] 真服務 e2e 與前端 e2e 的精靈三條（wizard / existing / cold-start）改寫且全綠；`berth-lab` bundled 與 existing 各用 playwright 走一次，附截圖或文字結果
- [ ] plan §2.1、§6、§8、§12、README、CHANGELOG 同步；`/impeccable critique`、`audit` 過一輪
- [ ] lint、type、test 綠燈

## Comments
