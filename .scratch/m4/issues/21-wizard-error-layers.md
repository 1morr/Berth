# 21 — 精靈的錯誤訊息分層：人話在上、原文收進技術細節，舊結果不殘留

**Status:** ready-for-agent

**Blocked by:** 18, 19, 20（它們各自新增或改寫錯誤理由；這張把整個精靈的錯誤呈現統一，放最後以免來回衝突）

**讀:** `docs/research/wizard-review-2026-09-30.md`（對照成熟產品那一節）；plan §7（i18n）、§9.3；`PRODUCT.md`、`DESIGN.md`；
先跑 `/impeccable shape` 決定「技術細節」的呈現

## 為什麼（2026-09-30 精靈審查）

成熟產品（*arr、Home Assistant config flow）的做法是：已知的失敗用錯誤代碼，由前端翻成人話、掛在造成它的欄位上；
原始例外只在未知情況下出現。Berth 現在把後端字串直接當標題：

- **原文直出**：`GET /configuration: 401`（TMDB）、`GET /api/v1/system/status: 401`、`/movies is not visible from the Berth
  container ([Errno 2] …)`、`category 'berth-tv-shows' already points at …`、`POST /Library/VirtualFolders/Paths: 404`；
  每條 Route 檢查下列出 `torrents/createCategory`、`Library/VirtualFolders → stat()`、`Environment/ValidatePath`、`link()`、
  `dev=69 · inode=…`；qBittorrent 偏好表用原始鍵名 `temp_path_enabled`；媒體庫類型顯示 `movies` / `tvshows`。
  出處：`web/src/components/RouteCheckList.tsx:39-55`、`StepLine.tsx:56-58`、`QbittorrentStep.tsx:237-241`、
  `JellyfinExisting.tsx:227-239`。
- **說錯原因**：TMDB 401 的手動步驟是「確認這台機器連得到 api.themoviedb.org」，右欄同時「憑證 已取得」、泊位卡
  「失敗 · 憑證 待驗證」；`/setup/routes` 的 422（選擇無效）顯示「Berth 後端可能沒在跑」（`web/src/pages/SetupPage.tsx:492-495`）；
  qBittorrent 登入失敗在 `sign_in` 被吞掉（`berth/services/qbittorrent.py:118-131`），之後在 category 那一條以 403 爆出、
  卻給「分類衝突」的補法（`routeChecks.ts:45`）。
- **沒說**：精靈裡「選服務」的請求失敗（409 `jellyfin_owned`、422、5xx、斷線）完全不顯示（`SetupPage.tsx:165-173`）。
- **舊結果不清**：換到另一台 Jellyfin 後，上一台的版本錯誤還掛著；切到「既有」後泊位卡仍寫「失敗 · 套件內」、右欄列
  套件內的動作；Prowlarr 狀態列停在上一次；取消「沿用 Jellyfin 帳密」後「這不是 qaowner 的 Jellyfin 密碼」還在，舊密碼
  被帶進新欄位、確認欄還沒填就報「不一樣」；刪除 Route 後「已刪除」一直留著。
- **套件內／既有文案混用**：既有 qBittorrent 連線失敗時標題變成「套用建議的 qBittorrent 設定……這台 qBittorrent 是套件內的，
  Berth 直接改它的偏好」；選既有但還沒測試前，「將會做什麼」列的是套件內的動作。
- **IP 被封**：「到它自己的介面解除」做不到（同一台主機的瀏覽器也被封，qBittorrent 也沒有解除封鎖的介面）；沒說要等多久，
  連錯前沒有預警；帳密錯的結果標成「要求帳密」、標題寫「連不上」。
- **版本衝突的雙色**：qBittorrent 4.3.9 同一畫面連線卡綠「連上了」、泊位卡紅「太舊」；升級指令給的是套件內的
  `docker compose pull qbittorrent`，對既有那一台不適用（`QbittorrentStep.tsx:248-251`）。
- **小瑕疵**：「套用這 5 個鍵」實際 6 項；頁首「共 6 步」而泊位板 5 格；1280 寬時 BTH 5 的狀態字被右緣切掉一半；
  「Movies、TV和Anime」少空格。

## 做什麼

1. **錯誤代碼**：後端的失敗（Route 檢查、qBittorrent diff / apply、加 Berth 路徑、TMDB、Prowlarr connect、選服務）一律回
   封閉的代碼＋少量參數（路徑、版本、HTTP 狀態），前端依代碼選 i18n 文案；未知例外才用一個通用代碼帶原文。
2. **呈現**：一行人話（發生什麼＋下一步）掛在造成它的欄位或那一條檢查上；原文、HTTP 狀態、端點、errno、inode 收進可
   展開的「技術細節」。設定頁的 Route 列表與健康頁用同一個元件，一起改。
3. **舊結果**：換來源、換位址、重新測試、改欄位時，清掉這一格上一次的結果與錯誤。
4. **文案依來源**：套件內與既有各自一套標題、說明、手動步驟；補法指令只給適用的那一種。
5. **IP 封鎖**：查證 qBittorrent 預設的連錯次數與封鎖時間（`web_ui_max_auth_fail_count`、`web_ui_ban_duration`，補進
   brief §20.2），說「等 N 分鐘，或重啟 qBittorrent」；Berth 自己數連續失敗，第 3 次起預警「再錯 N 次會被封」。
6. **雙色衝突**：連線通過但版本太舊時，連線卡也是警示色，不是綠。
7. 上面的小瑕疵。

## 驗收

- [ ] 閘門（`tests/` 或 vitest）：精靈與設定頁的錯誤元件只接受代碼、不把後端字串當標題；**雙向變異**：造一個直接渲染原文的
      元件會紅，改一次無關的格式不會紅
- [ ] vitest：每個錯誤代碼都有 zh-Hant 與 en 文案（缺一條就紅）
- [ ] vitest：換來源 / 換位址 / 重新測試後，上一次的錯誤不在畫面上
- [ ] vitest：既有 qBittorrent 連線失敗時標題與說明是既有的那一套
- [ ] playwright 對 `berth-existing` 實跑錯誤組每一台（見研究檔的對照表），附截圖：主文沒有英文原文與 HTTP 狀態碼，
      「技術細節」展開看得到；TMDB 假 key 說 key 不對
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
