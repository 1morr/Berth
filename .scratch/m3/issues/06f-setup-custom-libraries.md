# 06f — 精靈：套件內 Jellyfin 的媒體庫由使用者命名、增刪，不只預設三個

**Status:** ready-for-agent

**Blocked by:** 06d（同一輪 `/impeccable onboard` shape 定下 Jellyfin 泊位的畫面）

**讀:** plan §9.3 第 3、7 步、§9.4；brief §16.3；`.scratch/m0/wizard-shape.md`（「Jellyfin 媒體庫：套件內固定 3 個」那一條）；`berth/services/jellyfin.py`（`BUNDLED_LIBRARIES`、`bootstrap`）、`berth/models/setting.py`（`MOVIES_SLUG` 等與 `metadata_fetchers`）、`berth/services/routes.py`；`web/src/setup/JellyfinStep.tsx`、`RouteStep.tsx`

## 做什麼

套件內 Jellyfin 的媒體庫現在寫死成 `Movies` / `TV` / `Anime`（`services/jellyfin.py` 的 `BUNDLED_LIBRARIES`），精靈上沒有任何地方能改；文件只寫了「套件內固定 3 個」，沒有討論過。使用者 2026-09-24 重跑精靈時拍板（brief §19）：**可以自己加、自己命名，不只預設的三個。**

慣例：Jellyfin 自己的啟動精靈「新增媒體庫」——內容類型 + 顯示名稱 + 資料夾。

- **按「開始靠泊」之前**，Jellyfin 泊位的剖面是一張可編輯的媒體庫清單，預設帶現在的三列（Movies・電影、TV・劇集、Anime・劇集）。每一列：名稱、內容類型（電影 / 劇集，Berth 只支援這兩種 `CollectionType`）、資料夾（`<library_root>/<資料夾>`，預設由名稱推導，名稱不是 ASCII 時要使用者填）。可以改名、刪列、加列；至少一列。
- 名稱與資料夾各自不可重複；資料夾名的規則與 Route 路徑的檢查一致（不能跳出 `library_root`）。
- 清單在按下之前存進 `settings.setup`（精靈狀態，plan §9.3「續行」），關掉瀏覽器回來還在。`bootstrap` 讀它，不再讀常數。**冪等**：同名的媒體庫已經存在就標「已經是這樣」，不重建；靠泊之後再改清單只影響還沒建的那幾列（已建的改名要去 Jellyfin——shape 決定畫面怎麼說）。
- **`metadata_fetchers`**：鍵仍是媒體庫 slug（它是 brief §10 的 anime 切換點，按媒體庫調），新媒體庫依內容類型給預設值（目前電影與劇集都是 `TheMovieDb`）。`MOVIES_SLUG` / `TV_SLUG` / `ANIME_SLUG` 只剩「預設清單」這一個消費點，其餘改讀清單；消費點歸零的常數刪掉。
- **第 7 步（媒體庫路徑）**：套件內那一鍵照舊替每一個建出來的媒體庫建一條 Route——它本來就從 `setup.libraries` 推導，驗證它對任意清單都成立。
- 既有 Jellyfin 的路徑不變（它本來就是列出使用者自己的媒體庫）。
- **不在這張票**：精靈走完之後從 Berth 建新的 Jellyfin 媒體庫。那時候的做法照舊：在 Jellyfin 建好，再到 `/settings/routes` 加 Route。

## 驗收

- [ ] 剖面可以改名、改類型、改資料夾、刪列、加列；空清單、重名、重複資料夾、跳出 `library_root` 的資料夾各有擋下的說法（前端測試 + services 單元測試）
- [ ] 清單存在精靈狀態裡，重新整理後還在（整合測試）
- [ ] `bootstrap` 依清單建媒體庫，類型與 `metadata_fetchers` 正確；再按一次不重建（整合測試，Fake Jellyfin）
- [ ] 第 7 步替每一個建出來的媒體庫建一條 Route，清單不是預設三列時也成立（整合測試）
- [ ] 預設三列不動時，行為與現在完全一樣（e2e 不必改就綠）
- [ ] playwright 實跑：改一個名稱、加一個「電視劇（華語）」之類的第四列、刪掉 Anime，走到第 7 步看到對應的 Route，1280 與 390，附結果
- [ ] zh-Hant 與 en 並列；plan §9.3、§9.4、`.scratch/m0/wizard-shape.md` 那一條同步
- [ ] lint、type、test 綠燈
