# 06f — 精靈：套件內 Jellyfin 的媒體庫由使用者命名、增刪，不只預設三個

**Status:** done

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

- [x] 剖面可以改名、改類型、改資料夾、刪列、加列；空清單、重名、重複資料夾、跳出 `library_root` 的資料夾各有擋下的說法（前端測試 + services 單元測試）
- [x] 清單存在精靈狀態裡，重新整理後還在（整合測試）
- [x] `bootstrap` 依清單建媒體庫，類型與 `metadata_fetchers` 正確；再按一次不重建（整合測試，Fake Jellyfin）
- [x] 第 7 步（06d 之後是第 5 步）替每一個建出來的媒體庫建一條 Route，清單不是預設三列時也成立（整合測試）
- [ ] 預設三列不動時，行為與現在完全一樣（e2e 不必改就綠）——**後端 docker e2e 沒跑**，見 Comments；前端 e2e 綠
- [x] playwright 實跑：改一個名稱、加一個「電視劇（華語）」之類的第四列、刪掉 Anime，走到第 7 步看到對應的 Route，1280 與 390，附結果
- [x] zh-Hant 與 en 並列；plan §9.3、§9.4、`.scratch/m0/wizard-shape.md` 那一條同步
- [x] lint、type、test 綠燈

## Comments

**做法**：清單是 `SetupJellyfin.bundled`（`BundledLibrary`：`name`、`collection_type`、`folder`；預設三列是 `models.DEFAULT_BUNDLED_LIBRARIES`），`PUT /setup/jellyfin/bundled` 存，拒絕是 `BundledLibraryRefusal`（八種，帶 `row`）。規則是 `services.jellyfin.check_bundled_libraries`，前端 `web/src/setup/libraryRules.ts` 同一組在送出之前逐格擋；剖面停手 600ms 就存，按「開始靠泊」先存一次再跑。資料夾限 `library_root` 底下一層（分隔符號、`.`、`..` 是「跳出」，往下鑽也擋：`tv` 與 `tv/anime` 會重複掃）。`MOVIES_SLUG` 等三個常數與 `BUNDLED_LIBRARIES` 刪掉；`metadata_fetchers` 預設變空、鍵是資料夾，沒寫的落回 `DEFAULT_METADATA_FETCHERS[類型]`。

**紅燈與變異**：後端單元 26 條、整合 8 條（自訂清單建庫、fetcher 依資料夾與類型、靠泊後加列只建新的、建好的列鎖住、Jellyfin 裡改名後不重建、Route 對任意清單成立、API 存取與 422）；前端規則 20 條、頁面 7 條。變異各自轉紅後還原：路徑照名稱算、fetcher 鍵照名稱、拿掉建好列的檢查、Route 只認固定名稱、只比名稱不比路徑（後端）；不擋靠泊鍵、有問題照樣存、靠泊前不先存、建好的列可編輯、改名一律重推資料夾、拒絕不帶列號（前端）。

**playwright 實跑（fake `bundled`，全新精靈）**：
- 1280：剖面預設三列；Movies 改「電影」時資料夾清空並說「名稱不是英文字母時，資料夾要自己填」，填 `films`；加第四列「電視劇（華語）」（新列名稱欄拿到焦點、資料夾同樣要自己填，填 `tv-zh`）；刪 Anime。停手後 `GET /setup/jellyfin` 的 `bundled` 就是這三列，重新整理還在。靠泊：纜繩寫「電影 · TV · 電視劇（華語）」，完成訊息說「3 個媒體庫」，三列變「已建立」鎖住並說去 Jellyfin 改。qBittorrent 套用後到第 5 步自動建出三條 Route：電影 → `…/library/films` `berth-電影`、TV → `…/tv`、電視劇（華語）→ `…/tv-zh`，全綠。
- 390：回頭到泊位 1，三列鎖住、加一列「紀錄片・電影・docs」，沒有水平溢出；「重新跑一次」只建「紀錄片」（那條纜繩寫「紀錄片」），第 5 步「建立 1 條」補上第四條 Route，全綠。
- 截圖在 `.local/screens/m3-06f/`（不進版控）。`pnpm -C web e2e` 四條綠（`wizard.spec` 走預設三列，沒改）。

**後端 docker e2e（`tests/e2e`）沒跑**：這台機器上使用者的 `berth-trial-*` 那一套正在跑，e2e 用同一個固定 IP 與 port，得先停掉它。`tests/e2e/conftest.py` 只改了 import（`BUNDLED_LIBRARIES` 刪掉，改讀 `DEFAULT_BUNDLED_LIBRARIES`，資料夾就是原本的 slug）；預設三列時的 bootstrap、Route 與 fetcher 由沒改過的整合測試守著。票 06h（精靈驗收）會跑它。

**code review 處理了的**：Jellyfin 裡改了名之後重跑會在同一個資料夾再建一個（「已經在 Jellyfin 上」改成名稱或路徑任一對上，bootstrap 與鎖讀同一支 `_already_built`，紅燈先行）；services 為了讓 api 組 model 而做的轉出拿掉，改收 `LibraryDraft` Protocol；`slug` 一詞不再拿來指資料夾（CONTEXT.md 的 slug 是 Route 的）；README 的 BTH 3 列、plan §2.1 與 §9.3 漏改的三處；拒絕的列號由 `bundledRefusalOf` 帶出，路徑拼接收成 `pathUnder`，型別別名只宣告一次。

**code review 未處理的發現**：
- `BundledLibraryIn`（api）、`LibraryDraft`（Protocol）、`BundledLibrary`（model）、`BundledLibraryView`（多一個 `built`）四個形狀相近：分層規則下 api 與 models 各自要一份，View 是 read 狀態的慣例（`LibraryView` 同形）。
- 前後端兩份規則沒有共用 fixture 當閘門，各自的測試案例逐條對得上；哪一邊改了規則另一邊不會紅。後端是閘門，前端只是提早說。
- 重跑時有新建也有已存在的，纜繩只列新建的名字（沿用舊行為），已存在的那幾個在剖面上標「已建立」。
- 在 Jellyfin 刪掉的媒體庫，清單上那一列會解鎖、重跑會照清單建回來；要不要建回來由清單決定。
- `DEFAULT_METADATA_FETCHERS` 兩種類型的值一樣：票面要「依內容類型給預設值」。
- 欄位名 `folder` 與 CONTEXT.md 的 **Folder Name**（作品資料夾）同字；這裡是媒體庫目錄，UI 寫「資料夾」。
