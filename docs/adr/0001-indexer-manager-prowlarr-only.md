# 索引站只接 Prowlarr，不支援 Jackett 與通用 Torznab

套件預設打包 Prowlarr，搜尋、加站、移除、測站都走它的 REST API（`/api/v1/*`）。最初的決定是「Jackett 以 Torznab 端點接入」，2026-10-06 精靈審計（D3）改成只支援 Prowlarr，並拿掉通用 Torznab 端點；已存 `torznab` 的安裝由資料 migration 處理，精靈頁 4 回到待處理，泊位名改「Prowlarr」。

理由：Prowlarr 有文件化的 REST API，可一鍵加索引站、列出與移除；通用 Torznab 只能搜尋，加站與測站要使用者自己去 Jackett 做，精靈的「推薦站、先測試、通過才加入」流程套不上。代價：只有 Jackett、或只有單站 Torznab 網址的使用者沒有路可走（審計量到的對照見 `docs/research/wizard-audit-2026-10-06.md` §D）。同一輪使用者也選了「Berth 帶自己的 Jellyfin 與 Emby 並存」：不支援 Emby、不改回 Jackett。要再支援 Jackett，等於同時維護兩套加站與健康檢查路徑。

來源：brief §19 舊列「索引站管理器」「精靈審計後的八項」D3（原文在 `docs/archive/m0.md`、`docs/archive/m4.md`）；Jackett 的查證留在 brief §20.7。
