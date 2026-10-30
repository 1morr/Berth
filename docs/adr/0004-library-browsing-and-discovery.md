# 媒體庫像 Jellyfin 那樣瀏覽：一庫一頁、Berth 代理圖片、探索頁只放 TMDB 牆

Berth 的媒體庫頁牆上是整個 Jellyfin 媒體庫疊上 Berth 狀態，播放跳 Jellyfin。決定：

- **一個 Jellyfin 媒體庫一頁**（Jellyfin 自己的慣例），只列這位使用者 `UserViews` 裡有的。一個 Jellyfin 媒體庫可有多條 Route（brief §4.3），也可有 Berth 路徑以外的舊路徑，照 Route 分頁會讓同一批作品出現在兩頁；Route 退成卡片上入庫狀態的來源。
- **帳號停用要跟上**：Berth session 活 30 天、只在登入時向 Jellyfin 驗證，而 API key 代讀被停用的帳號照常回資料（brief §20.8，12.1.0 實測）。所以瀏覽時取 `UserViews` 允許清單一併讀 `GET /Users/{id}` 的 `Policy`（同一份短時間快取），帳號被停用就結束 Berth 的 session。不縮短 session，因為管理類頁面（下載、設定）也會一起被迫重新登入。
- **圖片由 Berth 代理**，快取鍵用 `tag`。直連 Jellyfin 最簡單，但瀏覽器要連得到它，HTTPS 的 Berth 配 HTTP 的 Jellyfin 是 mixed content，也要依賴深連結的主機推導；縮圖後一張約 45 KB，代理的頻寬可接受。
- **探索頁（`/`）只放 TMDB 牆**，繼續觀看與下一集只在媒體庫頁（2026-09-24 推翻原本「首頁上方放繼續觀看與下一集」）。登入後預設落在媒體庫；精靈剛完成、或這個人看得到的媒體庫裡 Berth 入庫的東西一筆都沒有時落在探索（下載中不算）。

來源：brief §19 舊列「M1.5 拆票前的四條」「M2 後的全面審查」①「精靈與探索的試跑回饋」及該節「M1.5 拆票前的四條待決」四個理由（原文在 `docs/archive/m1.md`、`docs/archive/m2.md`、`docs/archive/m3.md`）。
