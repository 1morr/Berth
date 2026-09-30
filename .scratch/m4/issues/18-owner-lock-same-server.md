# 18 — 擁有者鎖定做實：只能換到同一台 Jellyfin、不能重建擁有者、版本在測連線時就擋

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-review-2026-09-30.md`（測試環境、錯誤設定對照表）；brief §19（精靈手動選擇）、§16.4、
§20.14；plan §9.3〈服務頁的共同形狀〉、§9.5；票 15 的 `## Comments`（`OWNER_LOCKED` / `JELLYFIN_OWNED` 那幾條）

## 為什麼（2026-09-30 精靈審查，兩個測試員各自重現）

- **擁有者成立後，Jellyfin 還能換成另一台，而且會存下來。** 既有 Jellyfin 頁按「改位址或憑證」→ 填另一台
  （`host.docker.internal:58097` → `:48096`，或反過來）→ 測試連線：200、`state: ok`，`/api/setup/status` 的
  `base_url` 變成新那台；擁有者仍顯示原本的帳號，而那個帳號、Berth 的 API key、媒體庫快照都在舊那台。
  畫面同一時間寫著「來源在擁有者成立之後就鎖住了」「換一台等於換擁有者，所以精靈裡鎖住了」。
  成因：改位址不重做這一頁（`berth/services/setup.py:277`），測試只打匿名的 `/System/Info/Public`
  （`setup.py:394-401`），一定綠。
- **`POST /setup/owner` 不擋「擁有者已存在」**（`setup.py:181-204`）：成立之後任何一位管理員直接打這支就能換掉
  擁有者。UI 沒有入口，但這是權限的洞。
- **Jellyfin 版本在測連線時就讀到了，卻要到登入才擋**：10.10.7 測連線是綠燈「連上了，已經有管理員 · 版本
  10.10.7」，按登入才 502，下面是英文 `Jellyfin 10.10.7 is older than 12.0`，前一句還說「它回的原文在下面」
  （其實是 Berth 自己的字串）。
- **按鈕與文案**：三個服務共用「改位址或憑證」（`web/src/setup/ServiceChoice.tsx:588-591`、`resources.ts:208`），
  Jellyfin 沒有憑證欄，提示卻寫「管理員帳密在下一格」（`resources.ts:258`），擁有者成立後沒有下一格；
  「這裡能做：重新測試這一台」但畫面上沒有重新測試鈕；狀態列「Jellyfin 連上了：連上了，已經有管理員」重複。
- **替還沒初始化的既有 Jellyfin 跑初始精靈時**，語言與地區寫死 zh-TW / TW、開啟遠端存取（`berth/services/jellyfin.py:71-73`、
  `:680-684`），沒問使用者。

## 做什麼

1. **「同一台」的判準**：先查證 Jellyfin `/System/Info/Public` 的 `Id`（ServerId）是不是跨重啟、跨換網址都穩定
   （`mattpocock-skills:research` 或對 berth-existing 的兩台實測；結論補進 brief §20）。
2. **擁有者成立後改 Jellyfin 位址**：新位址的 ServerId 與擁有者成立時記下的不同 → 拒絕、不存，理由是新的
   `ConnectionReason`（或沿用既有的拒絕列舉）；相同 → 存下並重新驗證 Berth 的 API key（打一支要驗證的端點），
   key 失效就要求擁有者重新登入。設定頁的「Jellyfin」換位址走同一條規則。
3. **`POST /setup/owner` 在擁有者已存在時回 409**；設定頁要換 API key 的「重新登入」是另一支，不受影響。
4. **版本在測連線時就擋**：`/System/Info/Public` 讀到版本低於 12.0 → `VERSION_UNSUPPORTED`，說「至少 12.0，你的是 X」
   （與票 17 Prowlarr 的句型一致）；登入那一段保留同一判斷作為後備。
5. **文案**：Jellyfin 那一格的按鈕叫「改位址」、拿掉「管理員帳密在下一格」；「這裡能做」只列畫面上真的有的動作
   （要嘛加一顆重新測試，要嘛拿掉那句）；狀態列去重複。
6. **替既有 Jellyfin 初始化時的語言與遠端存取**：**使用者 2026-09-30 拍板：在畫面上問**。既有 Jellyfin 還沒初始化、
   擁有者表單是「建立」時，多兩個欄位：語言與地區（預設帶精靈當下的 UI 語言）、是否開啟遠端存取（預設不開，說明 Berth
   從同一台主機的容器連進來不需要）。套件內那一台照舊不問（它是 Berth 的，沿用 UI 語言、不開遠端存取）。

## 驗收

- [x] ServerId 判準的查證結論寫進 brief §20，附來源或實測紀錄
- [x] 整合測試：擁有者成立後把位址換到 ServerId 不同的 Fake → 拒絕、`base_url` 不變；換到同一台的新網址 → 存下並
      重驗 key（雙向：同一台過、不同台擋）
- [x] 整合測試：擁有者已存在時 `POST /setup/owner` 回 409，擁有者不變
- [x] 整合測試：`/System/Info/Public` 回 11.x 時測連線就是 `version_unsupported`，訊息帶目前版本與下限；剛好 12.0 通過
- [x] vitest：Jellyfin 那一格的按鈕文字、沒有「管理員帳密在下一格」；zh-Hant 與 en 並列
- [x] 既有 Jellyfin 建立擁有者時問語言與地區、遠端存取（整合測試：送出的值真的寫進 `/Startup/Configuration` 與
      `/Startup/RemoteAccess`；vitest：欄位只在既有且未初始化時出現），決定記進 progress.md「偏差與決定」
- [x] playwright 對 `berth-existing` 實跑（另起一份受測 Berth，見研究檔）：10.10.7 在測連線就紅；擁有者成立後改到另一台
      被擋、畫面說明為什麼；改回同一台通過。附截圖或文字結果
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**2026-09-30 實作紀錄**

- ServerId：`/System/Info/Public` 的 `Id` 是 Jellyfin 的 `SystemId`，存在 `<DataPath>/device.txt`（v12.1 原始碼）；對
  `bad-jellyfin-elsewhere` 實測換網址、`docker restart`、`--force-recreate` 都不變，`ServerName` 在重建後會變
  （brief §20.15，`scripts/experiments/jellyfin_server_id.py`）。
- 換位址的規則在 `setup.choose_service` → `_same_jellyfin`：新位址要先答出同一個 `Id` 才存，另一台 409 `other_server`、
  不回答 409 `unverified`；存下之後同一次測試以 Berth 的 key 打 `/Auth/Keys` 重驗，被撤了是 `auth_required`。
  擁有者成立之後**每一次**測試都比 `Id`、驗 key（存下的位址後面換了一台也抓得到）。票 18 之前的擁有者沒記 `Id`：
  重新測試時記下測到的那一台；換位址時先問**原本那一台**（spec review 抓到：原本拿新位址自己的回答當標準，鎖是開的）。
- `POST /setup/owner` 已有擁有者 → 409 `owner_exists`，在碰 Jellyfin 之前就擋。
- 版本在 `_test_jellyfin` 就擋（`version_unsupported`，套件內也當場紅）；補法「至少要 X，這一台是 Y」由
  `connection.fix.outdated*` 插值，Prowlarr 的同一句一起換成這個句型（`VERSION_FLOOR`）。
- 語言與地區是一組預設（`web/src/setup/jellyfinStartup.ts`：zh-TW / zh-HK / zh-CN / en-US / en-GB / ja / ko），名字用
  `Intl.DisplayNames`。套件內那一台不問：UI 語言、不開遠端存取（原本開）。媒體庫自己的 metadata 語言照舊 zh-TW。
- key 被撤時的重新登入：頁 1 在擁有者成立後、測試是 `auth_required` 時出一格（`owner.reSignIn`），設定頁的「管理員登入」
  對套件內的那一台也在這時出現；換到 key 就重測連線。

**實跑（playwright，受測 Berth 是宿主上的 `berth serve` + 這一版的前端，port 28383，config/data 在 scratchpad，用完停掉刪掉；
對 berth-existing）**

1. 既有、`http://localhost:58096`（10.10.7）→ 測試連線：紅，「連得上，但版本比 Berth 支援的下限舊」，手動步驟
   「至少要 Jellyfin 12.0，這一台是 10.10.7；等也不會好。升級之後再測一次。」擁有者表單不出現。
2. 改 `http://localhost:58097`（12.1）→ 綠「已經有管理員」（不再是「連上了，已經有管理員」）→ 管理員登入成為擁有者。
   回頭看頁 1：只有一顆「改位址」，沒有「改位址或憑證」；「這裡能做 / 不在這裡做」說鎖到同一台、換一台 Berth 不支援。
3. 「改位址」→ 表單提示「這裡只確認位址連得到、版本夠新。」→ 填 `http://localhost:48096`（ok-jellyfin）→ 被擋：
   「沒有存：548d38d28268 是另一台 Jellyfin，不是擁有者所在的那一台。…」；`/api/setup/status` 的位址仍是 `:58097`。
4. 改 `http://127.0.0.1:58097`（同一台）→ 存下、`ok` / `setup_completed`。
5. 直接打 `POST /api/setup/owner`（登入中）→ `409 {"reason":"owner_exists"}`。

playwright MCP 的瀏覽器被別的 session 佔著，改用 `web/node_modules/@playwright/test` 的 chromium 寫一支腳本跑（repo 外）。
第一次跑時帳密欄位切錯一欄，登入被拒、什麼都沒建，重置受測 Berth 之後重跑。

**code-review 未處理的發現**

- 版本下限在後端常數、`VERSION_FLOOR`、`choice.existing.floor.*` 三處（票 17 就記過）：沒有閘門綁在一起。
- `_Outcome.detail` / `ChoiceRefusal.detail` 一欄多義（版本、伺服器名、`ConnectionReason`），前端 `refusedDetail` 靠理由分辨。
- `_test_and_record` 是三個服務共用的，夾著 Jellyfin 專屬的 ServerId 回填（票 18 之前的擁有者才走得到）；回填沒有移除條件。
- `kind === 'jellyfin'` 的特判散在 `TestLine`、`Fix`、`detailLabel`。
- `JellyfinStartup` 的預設值從 API 一路傳到 `_Runner`：前端建立時一定帶值，預設只給測試與舊呼叫端。
- `onChoose` 的收尾從 `onSettled` 改成 `onSuccess`：三個服務的既有表單在沒送到時都留著（原本收起），不只 Jellyfin 被拒時。
- 登入那一段的版本後備仍把 `unsupported_message` 的英文當 `detail` 顯示；前句改成「下面是那一步的錯誤訊息」，英文原文的
  層次留給票 21。
