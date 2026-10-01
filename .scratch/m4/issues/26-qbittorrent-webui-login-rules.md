# 26 — qBittorrent WebUI 登入：密碼規則先擋、400 說對原因、失敗不留半套

**Status:** done

**Blocked by:** 23

**讀:** `docs/research/wizard-qa-2026-10-01.md`（第 3、20 條）；brief §20.2（qBittorrent）；plan §9.3 第 2 點；
`web/src/setup/interfaceLogin.ts`

## 為什麼（2026-10-01 精靈實測，全新安裝）

- **密碼短於 6 字元時卡在頁 2（P1，實測證實）。** qBittorrent 5.x 的 WebUI 密碼至少 6 字元，精靈沒有這條規則；沿用較短的
  Jellyfin 密碼時 `setPreferences` 回 400，畫面說「這個位址上回應的不是 qBittorrent」（`protocol_mismatch`，
  `berth/adapters/http.py:149-150`），補法連結 `http://qbittorrent:21080` 瀏覽器開不了；帳號已寫進去、密碼沒有
  （`berth/services/qbittorrent.py:373-377`）。截圖 B2-09、B2-10、B2-13。
- **失敗後的殘留（實測證實）。** 取消「沿用 Jellyfin 帳密」後上一次的錯誤還在；失敗後表單收回成「帳號：xxx」，看起來已設好
  （`qbittorrent.py:362-367`）。截圖 B2-11、B2-14a。

## 做什麼

1. 查證 qBittorrent 4.4–5.x 的 WebUI 帳密規則（原始碼或實測，腳本放 `scripts/experiments/`），結論補 brief §20.2。
2. 前端照規則先擋（沿用 Jellyfin 密碼時也要檢查，太短就說「qBittorrent 要至少 N 字元，這組密碼不能沿用，請另設」）。
3. 後端：`setPreferences` 帶登入的 400 歸成專屬理由，人話說「qBittorrent 不收這組帳密：<規則>」。
4. 帳號與密碼一起成功才記錄；失敗時不記帳號，表單不收回。補法不給瀏覽器開不了的內部位址。

## 驗收

- [x] 查證結論與來源寫進 brief §20.2
- [x] vitest：短密碼（沿用與另設兩種）在送出前被擋，文案 zh-Hant 與 en 並列（雙向：夠長的通過）
- [x] 整合測試：Fake qBittorrent 對登入回 400 → 專屬理由、`web_ui_username` 不被記下
- [x] vitest：取消沿用後舊錯誤清掉；失敗後表單仍是可編輯狀態
- [x] playwright 對套件內 qBittorrent 實跑短密碼與正常密碼。附截圖或文字結果
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**實測（2026-10-01）**：`scripts/experiments/qbittorrent_webui_login_rules.py` 對 4.4.5 與 5.2.3：4.4.5 什麼都收；
5.2.3 擋帳號 < 3、含冒號、密碼 < 6，帳號合規而密碼太短時帳號已經寫進去（兩種鍵序都一樣）。票面「5.x 至少 6 字元」
不精確：5.2.0 才開始驗（release-5.1.4 原始碼沒有），brief §20.2 照實測寫。

**playwright 對套件內 qBittorrent 5.2.3 實跑**（`berth-qa/bundled`，工作樹 build 的 image，用完刪掉；qa-* 已 down、
compose 換回原 image）：

- 頁 1 以 4 字元密碼建擁有者 → 頁 2 沿用時填同一組：欄位下說「qBittorrent 的密碼至少要 6 個字元，這組 Jellyfin
  密碼不能沿用；請取消勾選，另設一組。」，沒有發出 `POST /setup/qbittorrent/apply`。
- 繞過前端直接 POST 4 字元密碼：那一條 `failed` / `login_rejected`、原文
  `WebUI password must be at least 6 characters long`；`web_ui_username` 套用後與重讀都是空字串，qBittorrent 的 conf
  沒有寫進帳號。
- 重新整理：失敗列說規則、補法不給連結、欄位開著；取消沿用後那一列清掉。
- 改填合規的自設帳密：四條都過、欄位收成「帳號：tkqbit」；從白名單外的宿主打 `auth/login`，新的那組 204、錯的 401。
- 截圖在 `.local/qa26/`（不進版控）。

**code-review 未處理的發現**

- 帳號被拒（前端照同一套規則先擋，只剩直接打 API）或兩次 `setPreferences` 之間斷線時，qBittorrent 留下「原本的
  帳號＋新密碼」。Berth 不記、那一條照舊沒設好，重送一組就蓋過去；註解已寫明，沒有做補償寫入。
- 人話列出三條規則，被拒的是哪一條只在技術細節的英文原文裡（票面「<規則>」）；要分條得比對 qBittorrent 的英文
  句子，沒做。
- 範圍：補法除了「不給開不了的位址」，還給了開得了的那一個（`QbittorrentOut.web_port`、`prowlarrWeb` 泛化成
  `serviceWeb.ts`）；`PreferencesRejectedError` 套在 `setPreferences` 所有的 400 上（是 `ProtocolMismatchError`
  的子類，其他鍵行為不變）。
- 判斷題，沒動：`QbittorrentOut.of` 與 `IndexerSetupOut.of` 同形；3 / 6 / 冒號在前端 `LOGIN_RULES`、Fake 與兩句
  i18n 各寫一次；`LoginRules.noColon` 只有一個實例；帳號錯誤抽了 `usernameError`，密碼的三元式在沿用與自設各一份。
- 真服務 e2e（`tests/e2e/`）沒跑：它的 compose 用 `deploy/docker-compose.yml` 的容器名 `berth-*`，與使用者正在用的
  berth-trial 撞名。`harness.py` 的 WebUI 密碼是 13 字元，不受新規則影響。
