# 04 — Jellyfin 的圖由 Berth 代理

**Status:** done

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

- [x] 媒體庫牆上已在 Jellyfin 裡的作品顯示 Jellyfin 的 Primary 圖，經 Berth 代理
- [x] 圖片回應帶長期快取標頭；其他 `/api` 回應仍是 `no-store`（兩邊都有測試）
- [x] 沒登入取圖是 401；只收白名單裡的圖片類型與尺寸規格，其餘拒絕（有測試）
- [x] Jellyfin 回 404 或連不上時卡片顯示佔位，牆不壞
- [x] Berth 端要不要另存一份圖，量過再決定並寫下理由（預設不存，靠瀏覽器快取）
- [x] plan §6 補上這一支；brief §20.8 若有新事實則補上
- [x] playwright 實跑：牆上的海報載入、重新整理後命中快取（附網路面板的文字結果）；390px 與深淺兩主題
- [x] lint / type / test 全綠並貼指令輸出

## Comments

- 2026-09-17 網址：`GET /api/jellyfin/items/{item_id}/images/{image_type}?size=&tag=`。路徑與 `tag` 沿用 Jellyfin 的
  `/Items/{id}/Images/{type}?tag=`，尺寸改成 TMDB `w342` 那種具名規格（`poster` = `fillWidth=342&fillHeight=513`，
  與同一面牆上 TMDB 的 `w342` 同寬），白名單現在只有 `Primary` / `poster`；item id 與 `tag` 要是 32 位小寫十六進位
  （item id 會進 Jellyfin 的路徑）。向 Jellyfin 取圖不帶 API key。卡片網址由 API 那一層組（`api/jellyfin.image_url`），
  services 的卡片只帶 `poster_tag`。
- 2026-09-17 量測（`scripts/experiments/jellyfin_images.py`，一次性 12.1.0，研究 §6.1）：`quality=90&format=Webp` 23 KB、
  `quality=96` 51 KB；不帶 `format` 時 Berth 的 `Accept: */*` 拿到 JPEG 33 KB，所以固定送 WebP。40 張 6 條並行：直連冷
  2,067 ms / 熱 161 ms，經過 Berth 冷 2,241 ms / 熱 403 ms。Jellyfin 自己存縮好的圖（`resized-images` 100 檔 2.6 MB），
  冷的那一次由它縮圖主導——**Berth 端不另存**。量測抓到每個 httpx client 各建一個 SSL context（約 14 ms CPU、卡事件
  迴圈），經過 Berth 的熱圖原本 993 ms（每張 140 ms）；改成整個程序共用一個（`adapters/http.py`，單元測試守著）。
- 2026-09-17 實跑（`fake_setup_server.py --scenario library`，`deckhand`；替身 Jellyfin 回 SVG 海報）：Movies 第 1 頁
  101 格裡 99 格載入代理海報（`naturalWidth` 342），`Harbour Film 007`（有 tag、圖不見 → 404）與 TV 的 `Home Videos 2019`
  （沒有圖）印「無海報」，沒有破圖。重新整理後 100 個圖片 Resource Timing 裡 99 個 `transferSize: 0`，唯一走網路的是那張
  404（`no-store`）。chrome-devtools 網路面板（TV，第一次 → 重新整理）：

  ```
  第一次   reqid=18 GET /api/jellyfin/items/1827a63b…/images/Primary?size=poster&tag=a92822ab… [200]
           Request Headers: accept, cookie, sec-fetch-dest:image …
           Response Headers: cache-control:private, max-age=31536000, immutable
                             content-security-policy:default-src 'none'; style-src 'unsafe-inline'; sandbox
                             x-content-type-options:nosniff
  重新整理 reqid=33 GET 同一個網址 [200]
           Request Headers: referer（只有這一個：沒有送出，從快取拿）
           Resource Timing：5 張圖 transferSize 0；/api/inventory/item-tv transferSize 3921（no-store，照樣重問）
  ```

  「待審」篩選下已在 Jellyfin 的 Slow Horses 也有海報（從 `library_index` 的 tag）。1280 / 390 × 深淺兩主題：橫向捲動 0，
  390px 一欄兩格、海報 159px 寬載入 342px 的圖；「無海報」沿用 `ink-dim` token（深 `oklch(0.78 …)`、淺 `oklch(0.45 …)`）。
  截圖在 `.local/screens/ticket04-*.png`（不進版控）。**「Jellyfin 連不上」只有兩層各自的測試**（後端 503、前端 `onError`
  換佔位），沒有在瀏覽器裡實跑。
- 2026-09-17 超出票面、已做：圖片 200 另帶 `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; sandbox`
  與 `nosniff`（GitHub raw 的慣例）——圖是 Jellyfin 那一端的內容卻從 Berth 的網域送出，直接開一張 SVG 不能帶著 Berth 的
  session 跑 script；`library_index` 改帶 Primary tag（篩選後的牆要畫海報，fixture 以 `--record --only` 重錄）；
  `PosterSlot` 的載入失敗佔位也套在 TMDB 海報上。
- 2026-09-17 code-review 處理了的：**Spec**——快取鍵不含縮圖參數（尺寸、`quality`、`format` 在伺服器端，網址快取一年），
  改了數字網址不變；API 測試改成逐一斷言字面值（`342, 513, 90`，契約測試斷言 `format=Webp`），旁邊寫明「改數字就換
  `ImageSize` 的值」，變異驗證改 quality 或尺寸都會紅。SSL context 的修正分成自己的 commit、CHANGELOG 另記一條。
  **Standards**——`read_image` 重寫的 `ServiceError` 轉換改用 `jellyfin_access.reachable()`（原 `_reachable`）；驗 tag 的
  pattern 叫 `JELLYFIN_ID` → `HEX32`；DESIGN.md「沒有海報」→ i18n 的「無海報」；progress.md 的偏差與決定在收尾 commit 補。
- 2026-09-17 **沒處理**（判斷題）：`PosterSlot` 是第三份海報元件（`MediaTile`、`Poster` 各一份）——收成一份會一起改探索頁與
  詳情頁的失敗行為，不在這張票；`image_url` 寫死 `/api/jellyfin/...`（`main.API_PREFIX` 在 api 之外，round-trip 測試抓得到
  不一致）；`fill_width/fill_height/quality` 一起傳（照 Jellyfin 的查詢參數，adapter 忠實翻譯）；`JellyfinImageType` /
  `ImageSize` 各一個成員（網址快取一年，形狀先定下）；`/jellyfin` 前綴分在 `api/routes.py`（管理員的媒體庫清單）與
  `api/jellyfin.py`（圖）；CLAUDE.md「原型不留」與 `scripts/experiments/` 留腳本的先例措辭不一致（改 CLAUDE.md 要走
  writing-for-agents，留給使用者決定）。
