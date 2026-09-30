# 27 — 套件內 Prowlarr 不再是死路：換 key 有出口、已有站算數、登入差什麼說清楚

**Status:** ready-for-agent

**Blocked by:** 23

**讀:** `docs/research/wizard-qa-2026-10-01.md`（第 2、9、22 條）；plan §9.3 第 4 點；票 20 的 `## Comments`

## 為什麼（2026-10-01 精靈實測，全新安裝）

- **換了 API key 就沒有出口（P1，實測證實）。** 套件內的 key 只在「選」那一刻讀掛載（`berth/services/setup.py:409-412`），
  重新測試用存下的舊 key（`setup.py:462-466`）。在 Prowlarr 重新產生 key 後：連線卡仍綠、站清單消失、沒有錯誤；重新測試後
  補法講的是 qBittorrent 免密白名單（`ServiceChoice.tsx:724-726`、`resources.ts:247-248`），照做沒用；再點「套件內」卡片
  不送請求；讀清單失敗時 `modeOf` 回 null（`IndexerStep.tsx:197`），畫面只剩「之後再說」。截圖 L-P2-3-01～06。
- **已經有站時頁 4 過不去（實測證實）。** 重裝保留 Prowlarr 設定時，已有的站不在候選清單，`_indexer_settled` 要至少一條
  站的步驟（`setup.py:733-737`）；設好介面登入仍停在頁 4。選「之後再說」後完成頁說「搜尋不到任何東西」（`resources.ts:888`）。
  截圖 R-09～11。
- **加完站、沒設介面登入時沒說為什麼不能前進（實測證實）。** 登入區在兩屏之外（`IndexerStep.tsx:302-345`）。截圖 B1-13。

## 做什麼

1. 套件內 Prowlarr 每次測試都重讀掛載的 key；`auth_required` 的補法是 Prowlarr 自己的（「Berth 讀到的 key 不被接受：
   確認 `${CONFIG_ROOT}/prowlarr` 有掛進 Berth」），不是白名單。
2. 讀清單失敗時照既有 Prowlarr 的做法說讀不到，並給「重新讀取」。
3. `_indexer_settled`：Prowlarr 上已經有至少一個站（不論是不是 Berth 加的）就算站那一半完成；完成頁的「跳過」文案照實際
   站數說。
4. 前進條件差介面登入時，在前進鍵的位置說「還差：設定 Prowlarr 介面登入」並能捲到那一區。

## 驗收

- [ ] 整合測試：套件內 key 換掉後重新測試 → 讀到新 key、連上（雙向：掛載沒有 key 時仍是 `api_key_missing`）
- [ ] 整合測試：套件內 Prowlarr 已有 1 站、介面登入已設 → `current_step` 前進到 5
- [ ] vitest：讀清單失敗時有「重新讀取」；差介面登入時前進鍵位置有說明
- [ ] vitest：索引站跳過但 Prowlarr 有站時，完成頁不說「搜尋不到任何東西」
- [ ] playwright：重新產生 key 後在畫面上恢復；保留 Prowlarr 設定重裝後走到頁 5。附截圖或文字結果
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
