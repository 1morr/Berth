# 04 — Jellyfin 的圖由 Berth 代理

**Status:** ready-for-agent

**Blocked by:** 03

**讀:** plan §6（門禁與 `Cache-Control: no-store` 那一條）、§11.2b；brief §19（M1.5 拆票前的四條：圖片由 Berth
代理）、§20.8（圖片）；`docs/research/library-browsing.md` §6、§7（卡片圖）；`.scratch/m1.5/library-shape.md`

## 做什麼

媒體庫牆的海報改用 Jellyfin 的圖。瀏覽器只連 Berth，由 Berth 向 Jellyfin 取圖（brief §19 拍板）：瀏覽器不必連得
到 Jellyfin、HTTPS 的 Berth 配 HTTP 的 Jellyfin 也沒有 mixed content。

幾個已知的坑：

- `/api` 底下每個回應都帶 `Cache-Control: no-store`（門禁補的，plan §6）。圖片不能照這條——網址帶了 Jellyfin
  的 `ImageTags`，換圖時網址就會變，所以可以長期快取；例外只開給圖片這一支。
- `tag` 只是快取鍵，錯的 tag 一樣回圖（研究 §6）。網址一定要帶 DTO 裡的 `ImageTags`，不然換了圖畫面不會跟著換。
- Jellyfin 的圖本身匿名可取；Berth 這一支仍在門後（要登入），不逐張檢查可見性。
- 縮放由 Jellyfin 做（`fillWidth` / `fillHeight` / `quality` / `format`）。尺寸不要讓前端任意指定，只收幾個固定
  規格，免得一個網址就能讓 Jellyfin 重算任意尺寸。

之後的劇照、橫卡（票 07、08）沿用這一支。還沒進 Jellyfin 的卡片維持 TMDB 海報。

## 驗收

- [ ] 媒體庫牆上已在 Jellyfin 裡的作品顯示 Jellyfin 的 Primary 圖，經 Berth 代理
- [ ] 圖片回應帶長期快取標頭；其他 `/api` 回應仍是 `no-store`（兩邊都有測試）
- [ ] 沒登入取圖是 401；只收白名單裡的圖片類型與尺寸規格，其餘拒絕（有測試）
- [ ] Jellyfin 回 404 或連不上時卡片顯示佔位，牆不壞
- [ ] Berth 端要不要另存一份圖，量過再決定並寫下理由（預設不存，靠瀏覽器快取）
- [ ] plan §6 補上這一支；brief §20.8 若有新事實則補上
- [ ] playwright 實跑：牆上的海報載入、重新整理後命中快取（附網路面板的文字結果）；390px 與深淺兩主題
- [ ] lint / type / test 全綠並貼指令輸出
