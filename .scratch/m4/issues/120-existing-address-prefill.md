# 120 — 既有路線：頁 2、頁 4 的位址提示跟著頁 1 的主機

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** 票 103（`103-wizard-copy-leftovers.md`:59）、票 104 的 Comments；`web/src/setup/signals.ts` 的 `EXAMPLE_ADDRESS`；`web/src/setup/ServiceChoice.tsx`（:731 `placeholder`）；`web/src/i18n/resources.ts` 的 `routes` 刪除被拒那幾句（約 :3005-3008，含 `{{usage}}`）

## 為什麼

既有路線的使用者要把同一個主機名打三次（頁 1 Jellyfin、頁 2 qBittorrent、頁 4 Prowlarr）。使用者在票 103 決定那一輪不做，票 104 的 critique 再提一次。

協調者審查（2026-10-20）縮小範圍，使用者同意：**只改 placeholder，不預填值**。預填值的風險是用容器名的人——頁 1 填 `http://jellyfin:8096`，照搬主機會預填出錯的 `http://jellyfin:8080`，使用者沒注意就送出反而多一次失敗。placeholder 只是提示，欄位仍空著，錯了也不會被送出。

## 做什麼

1. 頁 1 選既有、Jellyfin 已存下位址時，頁 2／頁 4 既有表單位址欄的 placeholder 用 Jellyfin 位址的 scheme 與主機，port 換成該服務的預設（qBittorrent 8080、Prowlarr 9696）。頁 1 沒有既有 Jellyfin 位址、或位址解析不了時，照舊用 `EXAMPLE_ADDRESS`。欄位的值不動、不送出、不影響套件內路線。
2. 順手修 M4 票 115 的中文排版：Route 刪除被拒那幾句 `{{usage}}指著…`，`usage` 結尾是「RSS Feed」時中英之間少一個空格（「1 個 RSS Feed指著」）。改寫句子讓 `{{usage}}` 後面接標點而不是中文字（例如「還有 {{usage}}，所以它刪不得」），zh-Hant 三句一起改，en 不動。

## 不做

- 預填欄位的值；猜 port 以外的路徑；後端改動。

## 驗收

- [ ] 頁 1 是既有 `http://nas.local:8096` 時，頁 2 位址 placeholder 是 `http://nas.local:8080`、頁 4 是 `http://nas.local:9696`，欄位值是空的（vitest）
- [ ] 頁 1 是套件內、或沒有可用位址時，placeholder 照舊是 `EXAMPLE_ADDRESS`（vitest）
- [ ] Route 刪除被拒的 zh-Hant 句子裡 `{{usage}}` 後面接標點（vitest，以結尾是 RSS Feed 的 usage 斷言沒有「Feed指」）
- [ ] 全部檢查、vitest、前端 e2e（`existing`）綠；CHANGELOG、progress.md 已更新
