# 24 — 頁 3 的前進條件跟畫面一致：重裝不卡、刪掉的 Route 不長回來、換台不殘留

**Status:** ready-for-agent

**Blocked by:** 23

**讀:** `docs/research/wizard-qa-2026-10-01.md`（第 1、6、7、8 條）；plan §9.3 第 3 點、§9.5；票 19 的 `## Comments`

## 為什麼（2026-10-01 精靈實測）

- **重裝後頁 3 永遠過不去（P1，實測證實）。** `_libraries_built` 只認 `setup.jellyfin.steps` 裡 `libraries` 那一條
  （`berth/services/setup.py:693-701`），只有建媒體庫的 `bootstrap_jellyfin` 會寫；前端只在清單有未建的列時才呼叫它
  （`web/src/pages/SetupPage.tsx:244`、`web/src/setup/RouteStep.tsx:138,169`）。保留 Jellyfin 設定、只清 Berth 重跑
  → 媒體庫全「已建立」→ Route 全綠但 `current_step` 停在 3，沒有前進鍵。截圖 R-07、R-08。
- **刪掉紅的 Route 後沒有前進鍵（既有，實測證實）。** 刪除後前端只重讀 Route 清單、不重讀 status（`SetupPage.tsx:508,526-528`），
  後端已到頁 4，畫面要重新整理才出現下一步；被刪的媒體庫還勾著。截圖 E6-14～16。
- **套件內：刪掉的紅燈 Route 又長回來（實測證實）。** 套件內的選擇是快照裡每一個 movies/tvshows 媒體庫
  （`berth/services/routes.py:818-836`），路徑不在 `/data` 的媒體庫刪了 Route 之後，下一次「建立並檢查」又建出來；
  在 Jellyfin 刪了媒體庫，Berth 的快照也不刷新（套件內不進頁重讀）。截圖 R-04～06。
- **換一台 qBittorrent 後頁 3 殘留上一台的結果（既有，實測證實）。** Route 標「尚未檢查」卻仍寫 0/6、2/6、泊位卡「失敗」，
  展開是上一台的整段錯誤（`routes.py:259-264` 只把 health 改 unknown，沒清 detail）。截圖 E8-04、E8-05。

## 做什麼

1. **套件內媒體庫那一步不靠「有沒有呼叫過 bootstrap」**：清單上全部已建立時，按「建立並檢查」也要讓 `libraries` 那一條
   有結論（skipped）；做法自選（前端照呼叫、後端判定改看快照），但前後端的條件要同一個來源。
2. **刪 Route 之後重讀 status**（其他會改 `current_step` 的動作一併檢查）；被刪 Route 的媒體庫取消勾選。
3. **套件內也重讀 Jellyfin 媒體庫**（進頁與「建立並檢查」前），自動建 Route 的範圍排除使用者刪過的媒體庫，或只對
   「Berth 這次建的媒體庫」建 Route——選一個，決定寫進 plan §9.5；Jellyfin 裡已刪的媒體庫不再出現。
4. **換台時清掉舊的檢查細節**：health 改 unknown 時一併清 `health_detail_json`，畫面不顯示上一台的通過數與錯誤。

## 驗收

- [ ] 整合測試：套件內 Jellyfin 的媒體庫已全部存在（重裝情境）→ 建立並檢查後 `current_step` 前進到 4（雙向：清單有未建的
      照舊建）
- [ ] 整合測試：套件內刪掉一條紅 Route → 再按建立並檢查不會重建它；Jellyfin 裡刪掉的媒體庫不再列入
- [ ] 整合測試：換 qBittorrent 之後 Route 的檢查細節是空的
- [ ] vitest：刪除 Route 後重讀 status、前進鍵出現；被刪的媒體庫取消勾選
- [ ] playwright：重裝情境（保留 Jellyfin config、清 Berth config）走到頁 4；既有情境刪紅 Route 後不重新整理就能前進。
      附截圖或文字結果
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
