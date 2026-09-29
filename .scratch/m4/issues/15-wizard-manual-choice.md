# 15 — 精靈改為每個服務手動選擇：一個服務一頁、二選一、不偵測

**Status:** done

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

- [x] 三個服務頁都是先選再測；進頁與選擇之前沒有任何探測請求（vitest + playwright network 紀錄）
- [x] 選套件內而 compose 沒有那個服務：訊息說出 `COMPOSE_PROFILES` 的補法（整合測試：主機名解不到）；容器還在啟動照舊輪詢（06g 的測試改寫後綠）
- [x] 票 05 的保護改讀選擇：選既有的 Prowlarr 沒有索引站、選既有的 qBittorrent 免密可進，仍不寫帳密、不改全域偏好、不加站（05 的 repro 改寫後綠）；雙向：選套件內的照舊寫
- [x] 套件內但已初始化：Jellyfin 已有管理員 → 登入表單；qBittorrent / Prowlarr 已設過登入 → 不強迫再設（整合測試 + `berth-lab` 保留 config 重建實測）；選既有而 Jellyfin 未初始化 → 建立表單（整合測試）
- [x] 沿用 Jellyfin 帳密：預設勾選；密碼錯時 Jellyfin 驗證失敗、兩台都沒被寫（Fake 斷言）；對的時候兩台的介面登得進（`berth-lab/reset.sh bundled` 實測）
- [x] 資料庫裡沒有介面密碼的明文（測試讀 `settings` 斷言）；migration 對票 07 的舊列有測試
- [x] 步驟導出與頁面順序有純函式的單元測試（後端與 `navigation.ts`）；泊位板五格、沒有前置列
- [x] 偵測的程式碼刪乾淨（`_verdict_`、`detect_services`、`/setup/detect`、`probe_targets` grep 無殘留）；門禁測試雙向
- [x] 舊資料庫的判定轉成選擇（migration 測試：精靈跑完的、跑到一半的）
- [x] 真服務 e2e 與前端 e2e 的精靈三條（wizard / existing / cold-start）改寫且全綠；`berth-lab` bundled 與 existing 各用 playwright 走一次，附截圖或文字結果
- [x] plan §2.1、§6、§8、§12、README、CHANGELOG 同步；`/impeccable critique`、`audit` 過一輪
- [x] lint、type、test 綠燈

## Comments

**2026-09-29 實作紀錄**

- shape（`/impeccable onboard`，`.scratch/m4/service-pages-shape.md`）問了使用者兩題、都照建議：Jellyfin 在擁有者成立後
  來源鎖住（後端 409 `ChoiceRefusal.OWNER_LOCKED`），qBittorrent / Prowlarr 隨時可改；不預選，點「套件內」立即存下並測。
- 選擇存在 `settings.setup.choices`（`ServiceChoice`：`origin`、`base_url`、`test`）；`services/setup.py` 的
  `choose_service` / `retest_service` 取代 `detect_services`。還沒選的服務：`qbittorrent_diff` 不連、`build_routes` 與
  Jellyfin 的 `connect_jellyfin` / `add_berth_path` 拒絕（`tests/integration/test_setup_choice.py` 的守衛那幾條）。
- 「已經設過介面登入」怎麼認（brief §20.14 補了來源）：qBittorrent 看 `app/preferences` 的 `web_ui_username` 不是預設
  `admin`（密碼讀不回來）；Prowlarr 看 `config/host` 的 `authenticationMethod` 不是 `none` 而且有 `username`。
- 介面密碼只存 `scrypt$<salt>$<digest>`（`services/steps.hash_password`）；套件內 qBittorrent 的連線帳密清空，Berth
  連它只靠免密白名單。migration `f3c9a1d6b2e8` 的雜湊函式凍結在 migration 裡。
- 頁 3 吸收了套件內 Jellyfin 的媒體庫清單（建完才畫 Route）；頁 4 只在索引站清單讀到之後才掛 `IndexerStep`（焦點
  回歸的修法）。

**驗證**

- 後端：ruff、ruff format、mypy（371 檔）、import-linter 6 kept；pytest 見 progress.md 那一列。`test_setup_steps.py`
  （`_current_step` 純函式 12 條）做過雙向變異。
- 前端：eslint、`tsc -b`、vitest 64 檔 1011 passed。前端 e2e（wizard / existing / cold-start / settings，1280 與 390）33 條綠。
- 真服務 e2e：`real_e2e.log` **22 passed**（協調者跑的）。
- `berth-lab`（image `berth:m4-15`，兩個 compose 都改了）：
  - `bundled` 保留 config 重建：頁 1 給登入表單（已有管理員）；頁 2 qBittorrent 已設過登入 → 只說「WebUI 的帳號：
    labowner」與「更換登入」，不強迫再設；五個鍵都標「已經是這樣」。
  - `bundled` reset：沿用 Jellyfin 帳密（labowner / Harbour-owner-1）→ qBittorrent 以它登入 204、錯的密碼 401；
    Prowlarr 登入導回 `/`、錯的導到 `loginFailed=true`。資料庫：`services.qbittorrent` 帳密空、兩個 `web_ui_password_hash`
    都是 `scrypt$…`，沒有明文。
  - `existing`：三頁都選既有走完。既有 qBittorrent 的全域偏好沒被動（`save_path` `/data/downloads`、`temp_path_enabled`
    false、WebUI 帳號 homeqbit），只多了分類 `berth-tv shows`；既有 Prowlarr 的 homeprowlarr 照樣登得進。
  - `CREDENTIALS.md` 的情境 A 改成這一張的狀態：reset 之後 bundled 三台都是 labowner / Harbour-owner-1（沿用 Jellyfin
    帳密）。

**code-review（`77f075e` 起）處理掉的**

- spec：`COMPOSE_PROFILES` 那一行寫死三個服務——照著貼會把另一個已經選了既有、拿掉的套件內容器又拉起來。改成照整份選擇算
  （`signals.composeProfiles`，`signals.test.ts`）。
- spec：套件內紅燈時沒有辦法重存 compose 位址（改了 `.env` 的 port 之後「重新測試」只敲存下的那一條）。再點一次「套件內」
  就重新選（`SetupPage.test.tsx`，變異過：拿掉那個分支就紅）；README 說了。
- 還沒選的服務也會被 `qbittorrent_diff` 敲、`build_routes` / Jellyfin 的加路徑照做——補守衛與測試。

**code-review 沒處理的**

- spec（形狀偏差，已寫回 shape 文件）：換成既有時沒有獨立的確認鈕，警告貼在表單上方，按「測試連線」就是確認。
- `services/qbittorrent.py` 與 `services/indexer.py` 各有一份 `_instance_username`、`_target` 與「記下 Berth 寫的那一組
  登入」；第三個用到時抽成一個 `RecordedLogin` 值型別。
- `services/setup.py` 裡逐 `ServiceKind` 的分支（`_test_connection`、`_start_over`、`_remember_connection`）重複了三次
  switch；加第四個服務時改成一張表。
- `indexer.connect_indexer` 的失敗全部記成 `UNREACHABLE`，401（key 錯）與連不上分不出來——票 17 的防呆會碰到。
- 設定頁改選 qBittorrent 來源時沒有把 Route 的檢查標成未檢查（精靈裡會，shape 文件那一條）；設定頁的 Route 檢查會在
  下一次檢查時抓到，寫不出使用者可見的失效條件，沒改。

**audit（14/20：a11y 3、performance 3、responsive 3、theming 3、integrity 2）處理掉的**（都先寫紅燈測試，
`SetupPage.test.tsx`）

- P1：第一次的測試結果與「重測結果一樣」沒被宣告（測試那一條跟結果一起掛上）。`ServiceChoice` 放一個一直都在的
  `role="status"` 宣告區（`connection.announce`），測試中清空、有結果再寫；啟動中的自動重測不清。TestLine 拿掉 `aria-live`。
- P1：按「改位址或憑證」之後焦點被 StepFrame 的兜底交給「前往下一個泊位」，越過剛打開的表單。改成位址欄 `autoFocus`。
- P2：送出既有之後就清掉 draft，請求還在路上時表單卸下、兩格都沒勾。改成 `onChoose(input, settled)`，回應回來才清
  （呼叫端用 TanStack `mutate` 的 per-call `onSettled`）。

**audit 沒處理的**（下一次 `/impeccable harden` / `clarify` / `adapt` / `polish` 的清單）

- P2 a11y：`role="radiogroup"` 沒有名字，radio 的名字是整張卡（「既有」超過 100 字）→ 拿掉 role 或 `aria-labelledby`，
  說明改走 `aria-describedby`。Fix 與 Blocked 的 `<h5>` 在 h2 底下跳級 → h3（`ServiceChoice.tsx` Fix、
  `QbittorrentStep.tsx` Blocked）。
- P2 a11y：方向鍵在兩格之間移動就會觸發「套件內」的選擇與測試（原生 radio 的 `onChange`）；鍵盤只是瀏覽就寫入了。
- P2：鎖住的 Jellyfin 頁文案矛盾（說「精靈跑完之後在設定換位址」卻給「改位址或憑證」；表單提示「帳密在下一格」而擁有者
  已成立；回頭看說「這裡能做：重新測試」而連上時沒有那顆鈕）；打開的既有表單沒有「取消」。
- P2：五處 `truncate` 違反 DESIGN.md「不截斷」（`BerthBoard.tsx` 兩處、測試端點、`RouteStep.tsx`、`StepLine.tsx`），
  390 寬 BTH 2 的「版本 v5.2.3 · Web API 2.15.1」被截；`wrapping.test.ts` 沒守 `truncate`。ChoiceCard 焦點環用
  `working` 色（亮色 1.58:1，也違反 One Meaning Rule）。
- P3：qBittorrent 頁連不上時標題仍是「套用建議的設定」；Cutaway 的 dd 永遠 `.value`，散文用了等寬字；BerthBoard 信號
  色塊上的 `opacity-80`；鎖定原因沒 `aria-describedby` 到 radio；CopyLine 的 code 拿不到焦點、多顆「複製」同名；
  窄版 GhostButton 35 px、Checkbox 16 px 低於 44 px；單一 bundle 936 KB（gzip 265 KB）。
- false positive：`first-viewport-column-overflow`（grid 列 stretch，左欄剖面是 sticky、652 px）、`nested-cards`、中文
  「——」與泊位板空值「—」的 em-dash。

**critique（26/40，dual-agent；上一次同目標 24/40）處理掉的**（紅燈測試先行）

- P1：泊位板選了來源之後狀態字換成「套件內 / 既有」，紅格綠格讀起來一樣（違反三重編碼）。狀態字改跟信號，來源進詳情列
  （「套件內 · 版本 12.1.0」）；詳情列不再 `truncate`（audit 的 390 寬截字一併解掉）。`SetupPage.test.tsx` 的泊位板那一條。
- P1：擁有者密碼錯時整頁捲回頂端：`router.leaveOnSignOut` 把 `claimOwner` 的 401 當成 session 失效重跑守衛。加
  `CLAIM_OWNER_KEY` 例外（`router.test.tsx`，變異過：拿掉例外就紅）。這條從票 06 就在。

**critique 沒處理的**

- P1：頁 4 單站失敗的呈現（票 06e 起的行為）：Prowlarr 原文英文 `role=alert` 一次四塊、「Query successful, but no results」
  被說成連不上、補法連結是容器主機名 `http://prowlarr:9696`、失敗後主鈕數的是已經加好的站。歸票 09（索引站頁）。
- P2：換另一格的確認沒用 `ConfirmPanel`（焦點不移、Esc 無效）；確認前 radio 已選中而標題 / lede 還是舊來源；
  `switchWarning` 不分原本的來源（從既有換走也說「Berth 寫過那一台的偏好」——不實）。
- P2：頁 3 Route 檢查 15 列全綠全展開、剖面與纜繩列重複端點、每屏兩顆黃色主鈕；完成頁只有路徑表。
- 其餘（黑話、placeholder 像已填、介面登入的密碼欄不在 form 裡、頁 2「五個鍵」卻 6 列）見
  `.impeccable/critique/2026-09-29T06-57-20Z__web-src-pages-setuppage-tsx.md`。

**坑：`real_e2e.sh` 的 `CONFIG_ROOT`**

- 真服務 e2e 的腳本（這一張的 scratchpad `real_e2e.sh`）`export CONFIG_ROOT=.local/e2e-config` 之後沒有清掉，最後一步
  `cd ~/berth-trial && docker compose up -d` 繼承了它：berth-trial 的 Berth 掛到 `.local/e2e-config`，那裡的資料庫已經是
  這一張的 revision `f3c9a1d6b2e8`，berth-trial 的舊 image 起不來。協調者用
  `env -u CONFIG_ROOT -u DATA_ROOT docker compose up -d --force-recreate` 修好（這一張之後沒再動它）。
  **下次跑真服務 e2e**：還原 berth-trial 那一步前 `unset CONFIG_ROOT DATA_ROOT`（`berth-lab/reset.sh` 已經這麼做），
  或把 e2e 的變數只放在 compose 那幾行的前綴，不要 `export`。
