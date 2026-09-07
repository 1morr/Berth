# 06 — 精靈第 3 步：Jellyfin（套件內全自動 + 既有接入）

**Status:** ready-for-agent

**Blocked by:** 05

**讀:** plan §9.4、§9.5（既有 Jellyfin）、§8.2、§11.1（T0.6）；brief §16.3、§16.4、§20.7

## 做什麼

精靈第 3 步的兩條路徑。套件內：按一顆按鈕，Berth 跑完 plan §9.4 的九步序列，畫面逐步顯示進度與結果。既有：連線表單 + 測試連線 + 以管理員帳密登入建立 API key + 列出媒體庫與各自路徑 + 兩顆需二次確認的按鈕（加入 Berth 路徑、安裝 MergeVersions）。

既有 Jellyfin 的紅線：絕不自動建立媒體庫、不改既有 `LibraryOptions`、不呼叫 `DELETE /Items/*`、不建議搬媒體庫路徑。

## 驗收

- [ ] `POST /api/setup/jellyfin/bootstrap` 跑完 §9.4 全序列，結束時 Jellyfin 有 Berth 管理員、Movies / TV / Anime 三個媒體庫（`EnableRealtimeMonitor=false`、`SeasonZeroDisplayName=Specials`、zh-TW metadata）、MergeVersions 已安裝
- [ ] API key 建立後存入 `settings.services.jellyfin`
- [ ] 安裝插件後重啟 Jellyfin 並輪詢 `/System/Info/Public` 直到恢復；逾時給明確錯誤與可複製的手動步驟
- [ ] `MergeMoviesTask` 與 `MergeEpisodesTask` 的 `Id`（不是 `Key`）存進 settings
- [ ] 重按 bootstrap 不會重複建立媒體庫或重複安裝插件
- [ ] 既有路徑：連線表單可測試連線、以管理員帳密登入取得 API key、列出媒體庫與路徑；掛 TVDB 插件的媒體庫顯示警告
- [ ] 既有路徑：「加入 Berth 路徑」對選定媒體庫呼叫 `POST /Library/VirtualFolders/Paths?refreshLibrary=false`，舊路徑原地不動
- [ ] 既有路徑：「安裝 MergeVersions」需二次確認並說明會重啟 Jellyfin
- [ ] Jellyfin adapter 的 `Fake` 覆蓋兩條路徑，契約測試綠燈
- [ ] 任一步失敗時畫面給出可複製的手動步驟，且該步可單獨重試

## Comments
