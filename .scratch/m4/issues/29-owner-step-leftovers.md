# 29 — 頁 1 的剩餘問題：重試保留語言、媒體庫語言跟介面、帳號規則先擋

**Status:** done

**Blocked by:** 23、28（都改頁 1 與 `setup/owner`）

**讀:** `docs/research/wizard-qa-2026-10-01.md`（第 16、17、18 條）；plan §9.3 第 1 點、§9.4；票 18 的 `## Comments`

## 為什麼（2026-10-01 精靈實測）

- **初始化中途失敗後重試，語言與遠端存取被預設值蓋掉（既有 E12，實測證實）。** `_owner_signs_in` 只要 `admin_user` 是
  ok/skipped 就回真（`berth/services/setup.py:740-753`），重新整理後表單變「登入」、只送帳密，後端補上 `DEFAULT_STARTUP`
  （zh-TW、TW、不開遠端，`berth/api/setup.py:140-148`），重試的 `configuration`、`remote_access` 以預設值重寫。實測：選
  English (US)＋開遠端存取，讓 `POST /Startup/RemoteAccess` 回 500 一次，重試後 Jellyfin 變成 zh-TW／TW／關。截圖 E12-07～10。
- **套件內媒體庫的 metadata 語言寫死 zh-TW／TW（全新，實測證實）。** `jellyfin.py:86-87,885-886`；頁 1 卻說語言跟著介面。
  英文介面建的三個媒體庫都是 zh-TW。截圖 B10-09。
- **不合法的 Jellyfin 帳號只說「那一段沒做完」（全新，實測證實）。** 含 `< > & " / \` 的帳號被 Jellyfin 400
  （`POST /Startup/User`），前端沒有帳號規則（`web/src/setup/OwnerStep.tsx`、`resources.ts:135`）。截圖 B2-05～07。
  同類：頁 1 修剪帳號前後空白，登入頁不修剪（B2-15）。

## 做什麼

1. 初始化還沒完成（`StartupWizardCompleted=false`）時，重試仍用「建立」表單並保留使用者上一次選的語言與遠端存取（存進
   `setup.jellyfin`，或從 Jellyfin 目前的設定讀回）；只有真的已完成才改成「登入」。
2. 套件內媒體庫的 metadata 語言與國家跟頁 1 寫進 Jellyfin 的初始設定一致（套件內是介面語言）。
3. 查證 Jellyfin 12.x 的帳號規則（原始碼或實測），前端先擋並說出規則；登入頁與頁 1 用同一個修剪規則。

## 驗收

- [x] 整合測試：`admin_user` 之後某步失敗 → 重試時 `configuration`、`remote_access` 用的是使用者原本的選擇（雙向：第一次就
      成功的照舊）
- [x] 整合測試：英文介面的套件內媒體庫建成 en-US／US；繁中建成 zh-TW／TW
- [x] vitest：不合法帳號在送出前被擋；頁 1 與登入頁的修剪一致
- [x] 帳號規則的查證結論寫進 brief §20.7，附來源
- [x] playwright：重現 E12 的中途失敗（反向代理讓 RemoteAccess 回 500 一次）→ 重試後 Jellyfin 是使用者選的語言。附截圖或文字結果
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**2026-10-03 實作紀錄**

- 重試：`_owner_signs_in` 改看 `complete` 那一步（或測試說 `setup_completed`），不再看 `admin_user`。寫給還沒初始化
  那一台的選擇存在 `setup.jellyfin.startup`（`SetupStartup`），`GET /setup/status` 帶出 `jellyfin_startup`，建立表單照它
  重填；換一台 Jellyfin 時（`_start_over`）清掉——重填的只是同一台的重試（code-review spec 軸抓到）。
- 媒體庫語言：讀 `GET /System/Configuration`（新的 `JellyfinClient.metadata_defaults`），不另外存一份。也涵蓋重裝保留
  config 的那一台（頁 1 什麼都沒寫）。只在真的要建媒體庫時讀。**英文建成 `en`／`US`**，不是驗收字面的 `en-US`：
  `en-US` 是 UICulture，metadata 語言照 `jellyfinStartup.ts` 的那一組是 `en`。
- 帳號規則：v12.1 原始碼＋一次性容器實測（`scripts/experiments/jellyfin_username_rules.py`，brief §20.7）。前端
  `web/src/setup/jellyfinUsername.ts`：`trimUsername`（頁 1、登入頁、重新登入那一格共用）與 `usernameProblem`（只在建立時擋）。
  票面沒寫的：只有空白的密碼 `/Startup/User` 也回 400，建立時就地說「Jellyfin 不收只有空白的密碼」。

**實跑（playwright，工作樹 build 的 image `berth:qa-t29`，port 22383；一次性的全新 Jellyfin 12.1 `t29-jellyfin` 在
failproxy 後面，`POST /Startup/RemoteAccess` 回 500 一次；設定都在 scratchpad，用完全刪；沒碰 berth-existing、berth-trial）**

1. 選既有 `http://host.docker.internal:22097` → 測試連線 → 建立表單。帳號 `cap<tain` → 送出前就擋：「Jellyfin 的帳號只能用
   文字、數字、空格與 - _ ' . @ + 這幾個符號，也不能只是「.」或「..」。」
2. 選「英文（美國）」＋開遠端存取 → 送出 → 502，「Jellyfin 那一段沒做完」（proxy 擋下 RemoteAccess）。
3. 拿掉失敗旗標、重新整理 → 仍是「建立管理員並登入」，語言 `en-US`、遠端存取勾著（截圖 29-04）。
4. 再送 → 擁有者成立。proxy 日誌：第二輪 `POST /Startup/User` 403（管理員已在）、`/Startup/Configuration` 204、
   `/Startup/RemoteAccess` 204、`/Startup/Complete` 204。以管理員讀 Jellyfin：`UICulture en-US`、`PreferredMetadataLanguage en`、
   `MetadataCountryCode US`、`EnableRemoteAccess True`。

**code-review 未處理的發現**

- 四個欄位（語言、metadata 語言、國家、遠端存取）住在 `JellyfinStartup`、`SetupStartup`、`JellyfinStartupOut`、`OwnerIn` 四個型別
  （standards 軸，Data Clumps）：分屬 services、models、API 的輸出與輸入，各層不能互相 import；轉換改成 `asdict` / `model_dump` 一行。
- `FakeJellyfinClient.culture` 是位置 tuple，`metadata_defaults` 依賴它的順序（原本就有的形狀）。
- `SetupStartup` 在 `Complete` 之後仍留著（擁有者成立後頁 1 不再畫表單，沒有影響）。
