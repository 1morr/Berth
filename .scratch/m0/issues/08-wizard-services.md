# 08 — 精靈第 4–6 步：qBittorrent、索引站、TMDB

**Status:** ready-for-agent

**Blocked by:** 04、05

**讀:** plan §9.3（第 4–6 步）、§8.1、§8.3、§8.4、§9.2、§11.1（T0.6）；brief §16.3、§20.7；票 04 的實驗結論

## 做什麼

精靈的三個服務設定步驟，形狀都一樣：畫面先說「將會做什麼」，按一顆按鈕，顯示逐項結果，可重按。

第 4 步 qBittorrent：顯示建議偏好與現值的差異，套用時只寫不同的鍵；套件內另設 WebUI 密碼。第 5 步索引站：套件內 Prowlarr 勾選預設公開站清單並逐站驗證；既有走 Prowlarr 位址 + key 或任意 Torznab 端點。第 6 步 TMDB：內建專案 key，可覆寫，一顆「測試」。

qBittorrent adapter 的版本差異一律依票 04 的實測結果實作，不憑文件猜。

## 驗收

- [ ] `GET /api/setup/qbittorrent/diff` 列出建議值與現值的差異：`temp_path_enabled`、`temp_path`、`save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`
- [ ] `POST /api/setup/qbittorrent/apply` 只寫有差異的鍵；勾了「同一組帳密」時一併設定 WebUI 密碼
- [ ] 既有 qBittorrent 的 temp path 未啟用只列警告不阻擋
- [ ] webapi 版本低於 2.8.4 拒絕接入並提示升級
- [ ] qBittorrent adapter 的契約測試對 4.4 與 5.x 兩組錄製回應都綠燈，涵蓋 `paused` / `stopped` 與 `savePath` / `save_path` 的差異
- [ ] 套件內 Prowlarr：Nyaa.si、dmhy、AniDex、Anime Tosho、ACG.RIP、Mikan、1337x、YTS、EZTV、The Pirate Bay 預設全勾，以 `indexer/schema` 取定義、`indexer` 新增、`indexer/test` 驗證，逐站顯示成功或失敗
- [ ] 既有：可填 Prowlarr 位址 + API key，或任意 Torznab 端點 + key，兩者都有「測試」按鈕
- [ ] TMDB 步驟用內建專案 key，可用 `settings.services.tmdb.api_key` 覆寫，「測試」呼叫 `configuration` 驗證
- [ ] 三步都可重按且結果一致；重按不會重複新增索引站
- [ ] qBittorrent、Prowlarr、TMDB 三個 adapter 各有 `Fake` 與契約測試
- [ ] 每顆按鈕失敗時給出可複製的手動步驟

## Comments
