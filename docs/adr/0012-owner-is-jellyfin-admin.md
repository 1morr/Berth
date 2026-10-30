# 擁有者就是 Jellyfin 管理員：精靈第 1 步連 Jellyfin，擁有者鎖在同一台 Jellyfin

Berth 沒有自己的帳號（brief §11）。原本精靈第 1 步「建立 Berth 管理員」的帳密身兼精靈門鎖、套件內 Jellyfin 管理員、qBittorrent 與 Prowlarr 介面登入三職，接既有服務時它在精靈結束後登不進 Berth。**照 Seerr：第 1 步就是連 Jellyfin**——套件內建立 Jellyfin 管理員，既有的以它的管理員登入；成功的人就是擁有者，精靈從那一刻起要登入。

- **誰先到誰建立**不變（Jellyfin、Seerr、Home Assistant 的首次設定都是這樣）。要堵的是提早登入與目標被換：擁有者成立前 `/auth/login` 一律拒絕；`POST /setup/owner` 帶畫面上測過的位址與 ServerId，與存下的不同就不送帳密、請使用者重新測試。
- **擁有者成立之後 Jellyfin 的位址只能換到同一台伺服器**（`/System/Info/Public` 的 `Id`，brief §20.15），另一台與不回答的新位址一律不存；`POST /setup/owner` 不再重建擁有者（409）；版本在測連線時就擋。換媒體伺服器等於重裝（Seerr 同）。
- **替還沒初始化的既有 Jellyfin 建擁有者時**，語言與地區、遠端存取在畫面上問（預設 UI 語言、不開遠端存取）；套件內的不問（沿用 UI 語言、不開遠端存取）。
- **密碼只問一次**：頁 1 預設勾「套件內 qBittorrent 與 Prowlarr 也用這組」，精靈期間只留在前端記憶體、不落地，到頁 2、頁 4 照舊先向 Jellyfin 驗過再寫。

來源：brief §19 舊列「精靈改為 Jellyfin 優先」「擁有者鎖到同一台 Jellyfin」「擁有者成立之前沒有人登得進來」「精靈審計後的八項」D4（原文在 `docs/archive/m3.md`、`docs/archive/m4.md`）；審查紀錄 `docs/research/wizard-review-2026-09-30.md`。
