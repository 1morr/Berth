# 26 — qBittorrent WebUI 登入：密碼規則先擋、400 說對原因、失敗不留半套

**Status:** ready-for-agent

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

- [ ] 查證結論與來源寫進 brief §20.2
- [ ] vitest：短密碼（沿用與另設兩種）在送出前被擋，文案 zh-Hant 與 en 並列（雙向：夠長的通過）
- [ ] 整合測試：Fake qBittorrent 對登入回 400 → 專屬理由、`web_ui_username` 不被記下
- [ ] vitest：取消沿用後舊錯誤清掉；失敗後表單仍是可編輯狀態
- [ ] playwright 對套件內 qBittorrent 實跑短密碼與正常密碼。附截圖或文字結果
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
