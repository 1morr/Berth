# 07 — 套件內 qBittorrent / Prowlarr 的介面帳密：各自的泊位、各自的欄位

**Status:** ready-for-agent

**Blocked by:** 06

**讀:** brief §16.3（qBittorrent 預置的免密白名單）、§20.7（Prowlarr `config/host`）；plan §9.2、§9.3 第 4、6 步；`berth/services/qbittorrent.py:~241`、`berth/services/indexer.py:~380`（現在寫介面帳密的兩處）

## 為什麼

現在的「同一組帳密也套用到 qBittorrent 與 Prowlarr 介面」是第 1 步的一個勾選框。2026-09-26 在 `berth-lab/bundled`
取消勾選實測：Berth 靠「Berth 容器 IP 免密白名單」照常連 qBittorrent，但**使用者自己打開 qBittorrent 的 WebUI
只剩容器 log 裡每次重啟都換的臨時密碼**，精靈一個字都沒提；Prowlarr 則是介面完全沒登入，第一次打開時它自己要人設。

06 把第 1 步改成「Jellyfin 擁有者」之後，這個勾選框沒有地方放了。

## 做什麼

1. qBittorrent 泊位（套件內）加「WebUI 帳密」欄位：預設帶入擁有者那一組（可改），文案說清楚這是 qBittorrent
   自己的登入、Berth 自己不需要它（免密白名單）。留空的選項要說出後果（只能看容器 log 的臨時密碼），
   或乾脆不給留空——shape 時定並寫理由。
2. Prowlarr 泊位（套件內）同樣。
3. 既有服務的這兩個泊位**沒有**這一格（05 的規則：不寫既有服務的帳密）。
4. 設定頁（票 m3/06i 的五頁）同一格重用，改完之後再寫一次。

## 驗收

- [ ] 套件內：在泊位裡設的帳密之後能登入 qBittorrent WebUI 與 Prowlarr 介面（`berth-lab` 實測 + 整合測試）
- [ ] 既有：兩個泊位沒有帳密那一格，Fake 上斷言沒有寫入（整合測試）
- [ ] 設定頁改帳密後舊的失效、新的有效（整合測試）
- [ ] plan §9.3 第 4、6 步與 brief §16.3 表格同步
- [ ] lint、type、test、前端 e2e 綠燈

## Comments
