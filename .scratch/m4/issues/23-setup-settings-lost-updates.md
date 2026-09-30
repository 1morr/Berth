# 23 — 精靈設定不再互相蓋掉：命令只改自己的欄位

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（24–30 都會碰 `settings.setup`，這張先做）

**讀:** `docs/research/wizard-qa-2026-10-01.md`（第 5 條）；plan §9.3〈續行與跳過〉；`berth/services/settings.py`（`write_settings` 與
`update_settings`）；票 20、21 的 `## Comments`（頁 4、5 已改用 `update_settings`）

## 為什麼（2026-10-01 精靈實測，全新安裝 L-P2-1，實測證實）

- 套件內服務「啟動中」時，前端不分頁每 3 秒打 `POST /setup/services/{kind}/test`（`web/src/pages/SetupPage.tsx:377-384`）。
  後端 `_test_and_record`、`choose_service` 是「開頭讀整份 `setup` → 打網路（最多 5 秒）→ `write_settings` 整列寫回」
  （`berth/services/setup.py:285-314,344-357`）；`apply_qbittorrent`、qBittorrent 的 `set_interface_login` 同樣
  （`berth/services/qbittorrent.py:235-278,300-322`）。
- 實測：Jellyfin 在啟動中時，在頁 2 把既有 qBittorrent 測到通過並按確認；12 秒後 status 裡的 qBittorrent 被寫回上一次
  的失敗，重新整理後頁 2 顯示舊的失敗。使用者以為做完了。兩個分頁同時操作同理。

## 做什麼

1. 精靈裡所有改 `settings.setup`（以及 `services.*`）的命令，改成**在寫鎖內重讀、只合併自己負責的那一段**，網路請求
   放在讀之前或之後，不再拿著舊的整份設定跨過網路請求。沿用 `update_settings` 或同形的做法；不新增一層抽象。
2. 盤點 `setup.py`、`qbittorrent.py`、`jellyfin.py`、`routes.py` 裡還在用 `write_settings` 寫 `setup` 的地方，全部改掉；
   `write_settings` 若沒有其他呼叫者就刪。
3. 前端的啟動中輪詢只打**畫面上等著的那一個服務**，不是所有 `waiting` 的服務（減少重疊的機會，但正確性不靠它）。

## 驗收

- [ ] 整合測試：模擬輪詢與頁 2 套用交錯（輪詢在網路請求中途時套用完成）→ 套用的結果留著（雙向：把合併改回整列覆寫會紅）
- [ ] 整合測試：兩個不同服務的測試交錯寫入，兩邊的結果都在
- [ ] `write_settings` 寫 `setup` 的呼叫點歸零（或只剩有理由的，註明）
- [ ] playwright 重現 L-P2-1 的步驟（`docker pause` 套件內 Jellyfin 讓它進入啟動中，同時在頁 2 完成）→ 重新整理後頁 2
      仍是完成。附截圖或文字結果
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
