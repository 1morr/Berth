# 09 — 精靈第 7–8 步：媒體庫 → Route、硬鏈接檢查、完成

**Status:** ready-for-agent

**Blocked by:** 06、08

**讀:** plan §9.3（第 7–8 步）、§9.5（檢查與訊息）、§8.6、§2.2（routes）、§11.1（T0.6）；brief §4、§16.4

## 做什麼

從 Jellyfin 媒體庫建立 Library Route，每個 Route 立刻在 qBittorrent 建 category 並跑三項檢查，全綠後寫 `settings.setup.completed` 結束精靈。這張票也帶進 fs adapter —— 它是唯一會動 library 的模組。

套件內 Jellyfin 自動由三個媒體庫建三個 Route（movies / tv / anime，anime 用 `anime` profile）；既有 Jellyfin 由使用者勾選媒體庫，每個媒體庫可選「加入 Berth 路徑」產生的新路徑或既有路徑之一作為寫入目標。

## 驗收

- [ ] 套件內：自動建立三個 Route，各有 slug、名稱、Jellyfin 媒體庫 id、目標路徑、category、profile
- [ ] 既有：勾選媒體庫並選定寫入目標後建立 Route，兩種選法都跑同樣的檢查
- [ ] 每個 Route 在 qBittorrent 建立 `berth-*` category；category 已存在但 save path 不同時回報衝突且不覆寫
- [ ] 檢查一：qBittorrent 的全域 save path 與各 category 路徑在 Berth 內 `stat` 得到
- [ ] 檢查二：Jellyfin 回報的媒體庫路徑在 Berth 內 `stat` 得到
- [ ] 檢查三：在 Route 目標寫探測檔 → `POST /Environment/ValidatePath` 確認 Jellyfin 看得到同一路徑 → 從 complete 根目錄對探測檔 `link()`，確認同 device、同 inode，之後清乾淨
- [ ] 任一檢查失敗時指出「哪個容器少了哪個掛載」並附該容器的 compose `volumes:` 修正片段；`EXDEV` 另附「兩個目錄在 Berth 內是不同掛載」的說明
- [ ] fs adapter 的 `link`、`stat`、`same_inode`、`link_test`、`free_space`、`is_within` 有單元測試
- [ ] 寫入路徑不在任一 Route 的 `target_path` 底下時 fs adapter 拒絕（防路徑逃逸）
- [ ] `POST /api/setup/complete` 寫 `settings.setup.completed`，之後 `setup/*` 需登入、`/` 不再導向精靈
- [ ] 精靈全程可重跑，Route 重建不產生重複列

## Comments
