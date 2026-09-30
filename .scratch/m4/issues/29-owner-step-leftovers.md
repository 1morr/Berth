# 29 — 頁 1 的剩餘問題：重試保留語言、媒體庫語言跟介面、帳號規則先擋

**Status:** ready-for-agent

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

- [ ] 整合測試：`admin_user` 之後某步失敗 → 重試時 `configuration`、`remote_access` 用的是使用者原本的選擇（雙向：第一次就
      成功的照舊）
- [ ] 整合測試：英文介面的套件內媒體庫建成 en-US／US；繁中建成 zh-TW／TW
- [ ] vitest：不合法帳號在送出前被擋；頁 1 與登入頁的修剪一致
- [ ] 帳號規則的查證結論寫進 brief §20.7，附來源
- [ ] playwright：重現 E12 的中途失敗（反向代理讓 RemoteAccess 回 500 一次）→ 重試後 Jellyfin 是使用者選的語言。附截圖或文字結果
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
