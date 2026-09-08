# Shape：健康頁 `/health` 與服務設定頁 `/settings/services`（票 10）

`/impeccable shape`，2026-09-08。視覺世界沿用票 05 鎖定的「泊位調度板」
（`.impeccable/surfaces/web-src-pages-setuppage-tsx.md`），不重新選世界。三個開放決定由使用者
當場回答，記在最後一節。

## 1. Job and audience

**Visitor mode: Operate。**

平常沒有人看這一頁。人會打開它的時刻只有兩種（PRODUCT.md `## Operating Context`）：

- **「有東西壞了」**：Jellyfin 播不出新集、下載卡住、送單失敗。他要的第一個答案是「壞的是哪一項」，
  第二個是「我現在要做什麼」。
- **「我剛改了什麼」**：重開 NAS、換了 qBittorrent 的密碼、在 Jellyfin 那邊動了媒體庫路徑之後，
  回來確認 Berth 還接得上。

兩種人都可能是 `user` 而不是 `admin`——診斷是唯讀資訊，人人看得到；動作只有 admin 有（brief §11）。
桌機為主，但手機要讀得完（PRODUCT.md `## Operating Context` 的裝置假設）。

## 2. Outcome and proof

**主要任務**：在一眼之內知道四項哪一項紅了，讀出原因原文，拿到那一項的修正步驟。

**證據**（畫面上只放實測值，與精靈同一條規矩）：

- 服務：版本號（`10.11.11`、`v5.2.3 · Web API 2.15.1`）、索引站數量、最後成功時間、連續失敗次數。
- Route：五條纜繩逐條的實測值——qBittorrent 報的 save path、Jellyfin 報的媒體庫路徑、
  `dev=… · inode=… · free=…`。
- 失敗：服務回的**英文原文**，加上「哪個容器少了哪個掛載」的 compose 片段（brief §16.4）。

**只有 Berth 說得出來的那句話**：三個容器的掛載視圖只有它同時看得到。「Jellyfin 看不到 Berth 剛寫進
Route 目標的檔案」這句話 qBittorrent 說不出口、Jellyfin 也說不出口。

## 3. Selected direction

**沿用泊位調度板，而且是同一塊板。** 精靈的四個泊位（Jellyfin / qBittorrent / 來源 / 媒體庫路徑）
與健康檢查的四項是同一組東西——精靈問「接上了沒」，健康頁問「還繫著嗎」。所以健康頁的第一個
viewport 就是那塊板，只是每一格的狀態現在由 `health_checker` 每 5 分鐘寫一次。

這與票 07 登入頁「不畫泊位板」的決定不衝突：登入時一個泊位都還沒開始，搬過來只是壁紙；
這裡四個泊位全都有真實狀態。

- **焦點時刻**：紅的那一格。板上紅色只代表阻擋（法定色規則），紅格底下就是它的原文與修正步驟。
- **署名互動的延伸**：精靈的「靠泊序列」在這裡變成「複驗序列」——按「立即重測」時逐條纜繩重新繫上。
  同一個 `StepLine` 元件、同一組信號色。
- **實作後果**：Route 的五條纜繩重用 `setup/StepLine.tsx` 與 `setup/routeChecks.ts`（含 compose
  修正片段）。兩者要從 `setup/` 移到共用位置——健康頁不是精靈的一部分。

## 4. Scope and boundaries

**做**：兩個路由。

- `/health`：唯讀診斷。四格泊位板 + 每項的明細 + 「立即重測」（任何登入者都按得動，它只是重跑檢查）。
- `/settings/services`：只有 admin。逐服務「測試連線」、qBittorrent 的漂移差異表與「還原建議設定」。

**不做（anti-goals）**：

- **不在這裡改位址與憑證**。精靈跑完之後它就是設定入口（plan §6），連線表單只有那一份。
  設定頁對每個服務給一條「到精靈改」的連結，不複製四份表單。
- 不做 Reconciler、Issue 清單、磁碟空間趨勢（brief §13 的「健康與問題」其餘部分屬 M2）。
- 不做通知、不做歷史曲線、不做自動修復。

**不能動**：精靈的任何一頁、`web/src/index.css` 的七個色彩 token 與四個信號色。

## 5. States and ranges

| 東西 | 最小 | 典型 | 最大 |
| --- | --- | --- | --- |
| 服務 | 3（固定） | 3 | 3 |
| Route | 0（還沒建） | 3（套件內） | 使用者的媒體庫數，實務上 < 10 |
| 一條 Route 的纜繩 | 5（固定） | 5 | 5 |
| 漂移的鍵 | 0 | 0 | 5 |

**狀態**：

- **從來沒檢查過**（Berth 剛啟動、迴圈還沒跑第一輪）：四格 `neutral`，一句「尚未檢查」加重測按鈕。
- **尚未設定**（索引站被跳過）：那一格 `neutral` 而不是紅——跳過是允許的（plan §9.3）。
- **全綠**：四格 `secured`，Route 明細收起。這一頁應該很短。
- **一項紅**：那一格 `blocked`，明細就地展開；其餘三格不動（票 10 驗收）。
- **漂移**：qBittorrent 那一格 `assigned`（需要你），不是紅——服務好好的，只是有人改了建議值。
- **不新鮮**：`checked_at` 落後超過一個間隔（5 分鐘）時，時間標記自己說出來。
- **重測中**：按鈕進 `working`，板上不換 spinner。

## 6. Interaction and layout

- **層級**：泊位板（四格等寬）→ 每項一個區塊，順序與板上一致 → 區塊內是「實測值 + 最後成功時間」，
  紅的才有原文與修正步驟。
- **拓撲**：桌機單欄，最大寬度與精靈一致；泊位板在窄版折成 2×2。Route 明細是可展開的列。
- **回饋**：重測是一次 `POST /api/health/check`，回來就整頁換值；失敗只換那一項。
- **鍵盤**：展開的 Route 明細用原生 `<button>` + `aria-expanded`，不引入 Radix（票 05 的決定仍然成立）。
- **無障礙**：狀態三重編碼（色塊 + 模板字標籤 + 位置），紅燈原文放在 `role="alert"`；
  時間用 `<time datetime>`，相對說法（「3 分鐘前」）之外要留得住絕對時間。

## 7. Constraints and open decisions

- React 19 + TS + Tailwind v4 + TanStack Router / Query + react-i18next；zh-Hant 與 en 並列。
- WCAG 2.2 AA 是驗收條件，深淺兩主題都要達標。
- API 已經在後端做好：`GET /api/health/detail`、`POST /api/health/check`、
  `GET /api/settings/services`、`POST /api/settings/services/{kind}/test`、
  `GET|POST /api/settings/qbittorrent/diff|apply`。
- **開放決定已由使用者回答（2026-09-08）**：
  1. **兩個路由**，不是一頁兩區塊。頁首因此長出導覽（`健康` / `設定`），`設定` 只對 admin 顯示。
  2. **開頁不自動重測**：只顯示上一輪加「立即重測」。理由是那一輪檢查會在 qBittorrent 建 category、
     在媒體庫寫探測檔——GET 一個頁面不該有副作用，重整頁面更不該。
  3. **Route 綠燈收起、紅燈就地展開**。全綠時這一頁短到一眼看完，那正是它該有的樣子。
