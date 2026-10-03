# 28 — 擁有者成立前的空窗：不能提早登入、目標不能被悄悄換掉

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-qa-2026-10-01.md`（第 14、15 條）；brief §19（擁有者、擁有者鎖）；plan §9.3 第 1 點、§9.4；
`berth/api/gate.py`、`berth/services/auth.py`；票 18 的 `## Comments`

## 為什麼（2026-10-01 精靈實測，接管既有 E12，實測證實）

- **`/auth/login` 提早發 session。** `/auth/login` 永遠匿名（`berth/api/gate.py:41-49`），`sign_in` 只要
  `services.jellyfin.base_url` 非空就把帳密交給 Jellyfin（`berth/services/auth.py:67-80,148-169`），頁 1 一選 Jellyfin 就寫了
  base_url。實測：擁有者未成立時，bad-jellyfin-elsewhere 的非管理員 guest 拿到 200＋session、`/api/jobs` 200；管理員拿到
  admin、`/api/routes` 200。畫面上不會發生，直接打 API 會。
- **匿名改目標，帳密送到新位址。** 擁有者成立前 `POST /setup/services/jellyfin` 匿名開放（`gate.py:57-64`），
  `POST /setup/owner` 不帶位址、用當下存的那一台（`berth/services/setup.py:214-222`）。實測：頁 1 顯示 :58097 的登入表單時，
  另一邊匿名把目標改成 :48096 → 原頁送出的帳密打到 :48096，畫面仍寫 :58097。截圖 E12-01、E12-02。

## 做什麼

Jellyfin、Seerr、Home Assistant 的首次設定都是「誰先到誰建立」，這一點不改；要堵的是「提早能登入」與「目標被偷換」。

1. 擁有者成立前，`/auth/login` 一律拒絕（前端 `/login` 本來就導回 `/setup`）。
2. `POST /setup/owner` 帶上畫面當時測過的 `base_url` 與 ServerId（`/System/Info/Public` 的 `Id`，brief §20.15）；與存下的
   不同就 409，畫面說「Jellyfin 的位址在你填表時被換過，重新測試再送」。未初始化的 Jellyfin 也有 Id，同一條規則。
3. 兩個人同時成立擁有者（程式碼疑點：先檢查、再打網路、最後寫，沒有鎖）：寫 `setup.owner` 時在寫鎖內再確認一次沒有擁有者，
   後到的回 409 `owner_exists`。

## 驗收

- [x] 整合測試：擁有者未成立時 `/auth/login` 拒絕（非管理員與管理員都是）；成立後照舊（雙向）
- [x] 整合測試：`/setup/owner` 帶的 base_url／ServerId 與存下的不同 → 409、Jellyfin 沒被呼叫；相同 → 照舊成立
- [x] 整合測試：兩個成立擁有者的請求交錯 → 只有一個成立，另一個 409
- [x] vitest：409（目標被換）的人話與「重新測試」
- [x] playwright 或 curl 對 `berth-existing` 重現 E12 的兩個步驟，都被擋下。附文字結果
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**2026-10-01 實作紀錄**

- 登入：`auth.sign_in` 在擁有者成立前丟 `OwnerPendingError` → `/auth/login` 403（與門禁擋精靈其餘端點同一句），
  Jellyfin 不被問。「成立了沒」搬成 `SetupSettings.owner_established()`：`services.auth` import `services.setup`
  會循環（setup 用 `auth.open_session`）。
- 目標：`ServiceTest.server_id` 記 Jellyfin 答的 `Id`，`GET /setup/status` 每列帶出；`POST /setup/owner` 的
  `base_url`、`server_id` 必填，與存下的不同或存下的沒有 ServerId → 409 `target_changed`。之後序列釘在
  `JellyfinTarget`：連它的位址、第一步答的 ServerId 不同就停（帳密那幾步不跑）；收尾時位址已被改選就不寫 key；
  寫擁有者時在寫鎖內比位址（不比 ServerId：同時的重測沒連上會把它清成空字串）並確認沒有擁有者。
- 前端：表單帶目標、以 `base_url`＋`server_id` 為 key；`owner.refused.target_changed` 旁一顆「重新測試」，按下去
  先收掉那一句再重測。

**實跑（curl＋playwright；受測 Berth 是工作樹 build 的 `berth:t28-wip`，`-p 28384:8383`，config/data 在 scratchpad，
用完 container、image、資料都刪了；對 berth-existing，帳密從 `.creds.env` 讀、沒有印出）**

1. 匿名選既有 `http://host.docker.internal:58097`（bad-jellyfin-elsewhere）→ ok、`owner_signs_in`、ServerId
   `9fda94c0…`。
2. E12 第 1 步：擁有者未成立時 `/auth/login`——guest（非管理員）與 badadmin（管理員）都是
   `403 {"detail":"finish step 1 of the setup wizard first"}`、沒有 cookie；`/api/jobs`、`/api/routes` 401。
3. E12 第 2 步：記下畫面上那一台（:58097、`9fda94c0…`）→ 另一邊匿名改成 :48096（ok-jellyfin，ServerId
   `bae87d7f…`）→ 帶原本那一台送 `/setup/owner` → `409 {"reason":"target_changed"}`、沒有 cookie、owner 仍空、
   current_step 1。兩台 Jellyfin 的日誌在這段時間都沒有 `Authentication request`（bad-jellyfin-elsewhere 稍早
   票 18 的登入行還在，這條 grep 抓得到）。
4. playwright（真的 UI）：頁 1 顯示 :48096 的登入表單，另一邊匿名改成 :58097，填假帳密送出 → 「Jellyfin 的位址在你
   填表時被換過，帳密沒有送出去。…」與「重新測試」；按下去 → 卡片與剖面變成 :58097、那一句消失、兩格清空。console
   只有那一次預期中的 409。截圖 `.playwright-mcp/t28-target-changed.png`（gitignored）。
5. ok-* / bad-* 只被問過公開的 `/System/Info/Public`，沒有寫入，不必還原。

**code-review 未處理的發現**

- Standards：`setup.is_owner_established` 只剩一行轉呼叫（Middle Man）——它是 `api/gate.py`、`api/health.py` 進
  services 的入口，留著。
- Standards：`server_id` 一欄走過 `ServiceTest` → `ServiceView` → `ServiceOut` 三層（Shotgun Surgery，輕微）：
  現有分層的固定成本。
- Spec：`owner_established` 搬家是順手的重構（理由見上）；表單以目標為 key、清掉打好的帳密是票面沒寫的延伸，plan
  §9.3 已記。
- 已處理：plan、brief §19 / §20.15、CHANGELOG 補上；`_Runner` 改收 `JellyfinTarget | None`、不用空字串哨兵；收尾把
  key 寫回舊位址（spec 軸）；存下的測試沒有 ServerId 時比對退化成只比位址（spec 軸）。

**2026-10-01 暫停（使用者重開機，協調者要求；未 commit，全部留在工作樹）**

- 做完：上面的實作、文件（plan §6 / §9.3、brief §19 一列與 §20.15、CHANGELOG、progress.md 的 session 紀錄與偏差）、
  code-review 兩軸與修正、E12 實跑。票的前五個驗收條件已達成；`Status` 先改回 `ready-for-agent`，等最後一格。
- 最後一次程式碼修改（`_aimed_at` 要求有 ServerId、`_run` 收尾不寫給改選的位址、`test_setup_jellyfin.seed` 寫
  `JellyfinSettings.base_url`）之後：
  - vitest：77 檔 1190 條全綠。
  - 前端 e2e：32 passed、1 failed——`submit.spec.ts`「從作品頁送單，一路走到已入庫」，`browserType.launch: Timeout
    180000ms exceeded`（chromium 啟動逾時，還沒進到測試內容；當時完整 pytest 在並行跑）。**還沒查完**，判斷多半是
    環境負載，但未經單獨重跑證實。前一輪（加空 ServerId 規則之前）同一套 33 條全綠。
  - 完整 pytest：跑到一半被停掉，沒有結果。這一版只有局部檔案跑過（test_setup_owner / api / lost_updates /
    jellyfin、test_auth_api / service 綠）。
  - `pre-commit run --all-files`：最後一次修改之前綠，之後沒重跑。
- 實跑環境已收：`t28-berth` container、`berth:t28-wip` image、scratchpad 資料都刪了；沒起 qa-*；ok-* / bad-* 沒有
  寫入，不必還原。
- 下一步（依序，不要並行，避免再搶資源）：
  1. `uv run pre-commit run --all-files`
  2. `uv run pytest`（完整）
  3. `pnpm -C web test`
  4. `pnpm -C web build && pnpm -C web e2e`；若 `submit` 還紅就看 `web/test-results/` 的 error-context 查原因。
  5. 全綠後把最後一格打勾、`Status: done`，一個 commit（建議 `fix: keep the owner claim on the jellyfin the page tested`，
     body 交代 `owner_established` 搬到 `SetupSettings` 是為了避開 auth↔setup 循環）。

**2026-10-03 續（重開機後，依序、不並行）**

- `uv run pre-commit run --all-files`：綠。
- 完整 `uv run pytest`：第一次 37 failed + 2 errors。37 條是 `test_jellyfin_access.py` 的 `signed_in` 在沒有擁有者時
  登入，被這張票的規則擋下（暫停前那次完整跑加了 `-x`，停在第一條，沒看到它們）——helper 先 `own(session)`；
  2 個 error 是我加的 `-p no:logging` 讓 `caplog` 不存在，照 README 不加參數就沒有。重跑：**3474 passed**。
- pre-commit 重跑綠；`pnpm -C web test`：77 檔 1190 條綠。
- `pnpm -C web build && pnpm -C web e2e`：**33 passed**，`submit` 也綠。上一輪它的紅是 `browserType.launch` 逾時
  （chromium 沒起來，還沒進到測試內容），當時與完整 pytest 並行；單獨跑就過，判斷是資源搶佔，不是這張票的回歸。
