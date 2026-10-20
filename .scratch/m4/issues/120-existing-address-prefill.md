# 120 — 既有路線：頁 2、頁 4 位址預填頁 1 的主機

**Status:** needs-triage

**Blocked by:** None

**讀:** 票 103（`103-wizard-copy-leftovers.md`:59，使用者決定這一輪不做）、票 104 的 Comments；critique 第 7 項

## 為什麼

既有路線的使用者要把同一個主機名打三次（頁 1 Jellyfin、頁 2 qBittorrent、頁 4 Prowlarr）。使用者在票 103 收尾時決定這一輪不做；票 104 的 critique 再提一次。這張只是記下來，等使用者決定要不要做。

## 做什麼（若要做）

頁 1 選既有、Jellyfin 已連上時，頁 2／4 既有表單的位址照 Jellyfin 的主機預填，port 用該服務的預設（qBittorrent 8080、Prowlarr 9696）；只預填、不送出；使用者改過就不再覆蓋。動手前查成熟產品（例如 *arr 的連線表單）的慣例並寫明採用誰的。

## 驗收（若要做）

- [ ] 預填值正確、使用者改過就不再覆蓋；套件內路線不受影響（vitest，zh-Hant 與 en）
- [ ] playwright 實跑既有路線
