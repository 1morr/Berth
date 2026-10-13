# 101 — `POST /setup/qbittorrent/apply` 對既有那一台一律 422

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `berth/services/qbittorrent.py` 的 `apply_qbittorrent` 與 `_refuse_existing`；`berth/api/setup.py` 的 `post_qbittorrent_apply`、`put_qbittorrent_login`；M4 票 38 的 Comments 與 progress.md 票 38 那一條偏差；brief §16.4；`tests/integration/test_setup_existing_untouched.py`

## 為什麼

- 票 38 拿掉既有 qBittorrent 的「確認，不改任何設定」之後，前端只在套件內那一台呼叫這一支（`QbittorrentStep` 的介面登入）。
- 既有那一台現在：帶登入回 422；**不帶登入時照樣再連一次、記密碼那一條 `skipped`**。後者沒有任何消費點，只是一條直接打 API 才走得到的死路徑，記下的 `skipped` 也沒有人讀。
- 同一個資源的另一支 `PUT /setup/qbittorrent/login` 對既有那一台已經一律 422。兩支說法應該一致。
- 使用者 2026-10-14 同意：改成一律 422，低優先。

## 做什麼

1. `apply_qbittorrent`：既有那一台不管帶不帶登入，在連線與寫入任何東西之前就拒絕（沿用 `_refuse_existing` 與它的訊息）。刪掉 docstring 裡「直接打 API 時只是再連一次」那一段。
2. API 照舊把 `ValueError` 轉成 422；不新增失敗代碼。
3. 測試：
   - `test_setup_existing_untouched.py` 那一條改成兩種都 422、`qbittorrent.writes == []`，而且沒有連線（替身記下的呼叫為空）。
   - 雙向：套件內那一台不帶登入照舊回 200、密碼那一條 `pending`（`test_setup_api.py` 現有那一條守著，確認它仍綠）。
4. CHANGELOG `[Unreleased]` 的 Changed（或 Removed）記一筆破壞性變更。

## 驗收

- [ ] 整合測試（雙向）：既有那一台帶或不帶登入都 422，沒有連線、沒有寫入；套件內不帶登入照舊 200
- [ ] 前端不必改（確認 `web/src` 沒有對既有那一台呼叫這一支的路徑）
- [ ] CHANGELOG 已記
- [ ] 全部檢查（`pre-commit run --all-files`）、test 綠燈；progress.md 已更新
