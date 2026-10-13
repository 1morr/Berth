# 64 — 替既有 Jellyfin 新建媒體庫（勾了才建），類型對得上的預設勾選

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/usability-audit-2026-10-07.md` §2 E1、§4.2 C2、§5.2、§8 P2-15；brief §16.4（接管＝只建立與管理 Berth 擁有的物件、既有 Jellyfin 不搬媒體庫）、§19「第四輪可用性審計的八項」E1；CONTEXT.md 的 Jellyfin Library、Berth path、Existing service；`tests/integration/test_setup_owned_writes.py` 的白名單（閘門）

## 為什麼

- 既有 Jellyfin 只有劇集媒體庫、使用者想下載電影時，現在 Berth 不建，卡片叫使用者先去 Jellyfin 建。
- 這是使用者理想流程（「能接入就自動完成需要的設定」）與 D1 唯一實際衝突的地方。
- 使用者拍板 E1：頁 3 多一列「新建一個媒體庫」，勾了才建。新建的媒體庫是獨立物件，納入「Berth 擁有的物件」，推翻 §16.4「既有不建媒體庫」。
- 審計 S2：頁 3 要逐個勾媒體庫；中文媒體庫名直接成為分類與資料夾名（`berth-節目`、`/data/library/節目`），特殊字元與撞名沒驗過。

## 做什麼

1. **先 `/impeccable shape`** 頁 3 既有那一側的新列：類型、名稱、資料夾。說清楚「這個媒體庫在你的 Jellyfin 上，所有使用者都看得到」。
2. 既有 Jellyfin 的頁 3 可以新增「新建媒體庫」列（類型＋名稱，路徑是 `/data/library/<slug>`），勾了才在「建立並檢查」時建。
   - 與套件內建媒體庫同一條路徑（同名的不重複建）。
3. 類型對得上 Route 用途的既有媒體庫（movies、tvshows）預設勾選；其他不勾。
4. **接管定義改寫**：brief §16.4 物件表、CONTEXT.md 的 Existing service，都加上「使用者勾選後新建的媒體庫」。
   - 寫入白名單閘門放行「既有 Jellyfin 上、勾選的、在 library root 底下的新媒體庫」，做雙向變異：沒勾也建、建在 library root 外都要紅。
5. 媒體庫名的 slug：中日文、空白、`/`、同名，各一個單元測試。照結果決定要不要改規則，改了就記進偏差。

## 驗收

- [x] 整合測試：勾了才建、同名不重複、預設勾選的規則；白名單閘門雙向（`tests/integration/test_setup_new_library.py`、`test_setup_owned_writes.py`）
- [x] slug 的單元測試（中文、特殊字元、撞名；`tests/unit/test_library_slug.py` 與 `web/src/setup/newLibrary.test.ts` 讀同一份例子）
- [x] vitest 與實跑：只有劇集媒體庫的既有 Jellyfin，頁 3 新建電影媒體庫 → 6/6 → 入庫一部電影，附截圖（`64-new-library-on-existing-jellyfin/`，見 Comments）
- [x] 全部檢查、test、前端 e2e 綠燈；brief §16.4、CONTEXT.md、README guide、CHANGELOG 同步；progress.md 記一行

## Comments

- 2026-10-14 shape：`.scratch/m4/existing-new-library-shape.md`（使用者三題照建議：勾選表最後一張、預設不勾、類型預設那台沒有的、名稱預填；撞名就地擋；照 C2 預設勾）。
- 實跑（UTC，獨立 compose 專案 `berth-t64`，與其他 worktree 的 e2e 不共用名字、port、網段與 volume；跑完 `down --volumes`）：Jellyfin 12.1.0 選既有、還沒初始化（頁 1 由擁有者建管理員），之後在它上面建一個劇集媒體庫「劇集」（`/data/media/tv`）；qBittorrent 5.2.4 套件內。頁 3：「劇集」預設勾好、預設寫入 `/data/library/劇集`；勾「新建一個媒體庫」→ 類型預設電影、名稱「電影」、資料夾 `/data/library/電影`（`1-page3-new-library-ticked.png`）。按「建立並檢查」→ 兩條 Route 都 6/6，那一張收回成沒勾，「電影」出現在清單上、已有 Route（`2-page3-built-6of6.png`）。16:59:51 Oppenheimer（YTS 1080p）送進 `電影` Route → 17:00:01 入庫 → 17:01:52 Jellyfin 已收錄（`3-movie-imported.png`）。
- code-review（Standards、Spec 兩軸）已處理：新程式碼裡三處「既有不建媒體庫」的舊說法；「這條路徑是別的媒體庫的」後端收成 `path_holder`；`NewLibraryPlan` 改成 `NewLibraryInput & { path }`；名稱錯誤改查表；import 排序；前後端 slug 例子改共用一份檔（之前只靠註解）。Spec 軸：slug 相撞的兩個媒體庫都預設勾會一按就 `path_taken`、整段停下——前端改成同一條新 Berth 路徑只給清單上前面那一個（vitest 一條）；新媒體庫的寫入目標原本取 Jellyfin 回報的第一條，同名略過時可能是使用者原本的資料夾——改用畫面算的那一條（偏差兩條，progress.md）；「沒有新建」的文案改成與後端的 422 對得上。
- code-review 沒處理的：(1) 既有那一台的新建沿用 `Bundled*` 一族的名字（`BundledLibraryRejectedError`、`BundledLibraryRefusal`、`jellyfin.bundled.list.*` 的 i18n），拒絕的形狀與理由相同所以共用，名字沒跟著改——要改得連 API 的 `BundledLibraryRefusalOut` 一起，是對外介面。(2) `POST /setup/jellyfin/libraries` 收清單而 UI 只送一個：與 `libraries/paths` 同一種形狀。(3) `forget` 找不到媒體庫時目標記成空字串：那時它已經不在清單上，畫面不會畫它。
