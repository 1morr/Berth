# 08 — 精靈第 4–6 步：qBittorrent、索引站、TMDB

**Status:** done

**Blocked by:** 04、05

**讀:** plan §9.3（第 4–6 步）、§8.1、§8.3、§8.4、§9.2、§11.1（T0.6）；brief §16.3、§20.7；票 04 的實驗結論

## 做什麼

精靈的三個服務設定步驟，形狀都一樣：畫面先說「將會做什麼」，按一顆按鈕，顯示逐項結果，可重按。

第 4 步 qBittorrent：顯示建議偏好與現值的差異，套用時只寫不同的鍵；套件內另設 WebUI 密碼。第 5 步索引站：套件內 Prowlarr 勾選預設公開站清單並逐站驗證；既有走 Prowlarr 位址 + key 或任意 Torznab 端點。第 6 步 TMDB：內建專案 key，可覆寫，一顆「測試」。

qBittorrent adapter 的版本差異一律依票 04 的實測結果實作，不憑文件猜。

## 驗收

- [x] `GET /api/setup/qbittorrent/diff` 列出建議值與現值的差異：`temp_path_enabled`、`temp_path`、`save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`
- [x] `POST /api/setup/qbittorrent/apply` 只寫有差異的鍵；勾了「同一組帳密」時一併設定 WebUI 密碼
- [x] 既有 qBittorrent 的 temp path 未啟用只列警告不阻擋
- [x] webapi 版本低於 2.8.4 拒絕接入並提示升級
- [x] qBittorrent adapter 的契約測試對 4.4 與 5.x 兩組錄製回應都綠燈，涵蓋 `paused` / `stopped` 與 `savePath` / `save_path` 的差異
- [x] 套件內 Prowlarr：Nyaa.si、dmhy、AniDex、Anime Tosho、ACG.RIP、Mikan、1337x、YTS、EZTV、The Pirate Bay 預設全勾，以 `indexer/schema` 取定義、`indexer` 新增、`indexer/test` 驗證，逐站顯示成功或失敗
- [x] 既有：可填 Prowlarr 位址 + API key，或任意 Torznab 端點 + key，兩者都有「測試」按鈕
- [x] TMDB 步驟用內建專案 key，可用 `settings.services.tmdb.api_key` 覆寫，「測試」呼叫 `configuration` 驗證
- [x] 三步都可重按且結果一致；重按不會重複新增索引站
- [x] qBittorrent、Prowlarr、TMDB 三個 adapter 各有 `Fake` 與契約測試
- [x] 每顆按鈕失敗時給出可複製的手動步驟

## Comments

實作與驗證（2026-09-08）：

- **對真的服務錄了新的 fixture**：qBittorrent 4.4.5 與 5.2.3 各起一個容器錄
  `app/version`、`app/webapiVersion`、`app/preferences`、`torrents/categories`；Prowlarr 2.5.2.5491
  錄了 `indexer/schema`（十個預設站）、新增成功與兩種 400、`config/host`、單站 Torznab 的 `?t=caps`；
  TMDB 打真的 `api.themoviedb.org` 錄了 `configuration` 與 401。來源與規則寫在
  `tests/fixtures/http/README.md`。
- **十個站在這台機器上五成五敗**（`nyaasi` 查得到但沒有結果、`Anidex` 與 `animetosho-xyz` 連不上、
  `1337x` 與 `eztv` 被 CloudFlare 擋）。這正是 UI 要撐住的組合，`--scenario bundled` 的假 Prowlarr
  照這一輪的訊息演。
- **`POST /api/v1/indexer` 自己會先連站**（brief §20.7 已補）：逐站成敗來自新增那一支，
  `indexer/test` 給已經存在的站用。`?forceSave=true` 不會跳過這個檢查。
- 實跑驗證：`--scenario bundled` 走完泊位 1→3（含十站逐站結果與 TMDB 測試）、
  `--scenario outdated` 看版本閘門。深淺兩主題各 121–125 組文字對比全部 ≥ 4.5:1（最低 5.22:1），
  390px 寬版面完整可用。

超出票面、但 plan / brief 已要求而順手做掉的：

- **Prowlarr 介面登入**（brief §16.3，使用者決定一起做）：勾了「同一組帳密」時以
  `PUT /api/v1/config/host` 設 Forms 登入，等它自行重啟回來；它是自己一條纜繩（`prowlarr_login`），
  失敗不影響已經加好的站。
- **第 5、6 步的「之後再說」**（plan §9.3 的續行與跳過）。
- **套件內 Prowlarr 的 API key 在探測時就存進 `settings.services.indexer`**：不存的話第 5 步
  會拿空 key 去打真的 Prowlarr，直接 401。

留給後續的票：

- 完成頁「列出跳過了什麼、在哪裡補」是票 09 的第 8 步。
- `QbittorrentCategory` / `categories()` 與 `pause_parameter` 目前只有契約測試在用——它們是本票
  驗收「涵蓋 `paused` / `stopped` 與 `savePath` / `save_path` 的差異」的載體，消費者分別在票 09
  （category）與 M1（送單）。
- 既有 Prowlarr 的「測試」只驗位址與 key，不檢查它有哪些站；要不要在健康頁列出來由票 10 決定。
