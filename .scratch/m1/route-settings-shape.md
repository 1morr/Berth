# Shape：Route 設定頁 `/settings/routes`（票 14）

`/impeccable shape`，2026-09-15。**延伸既有的設定 surface**（`.impeccable/surfaces/web-src-pages-healthpage-tsx.md`、
`.scratch/m0/health-shape.md`），視覺世界沿用「泊位調度板」，不選新世界、不跑 concept 輪。
開放決定由使用者當場回答，記在 §7。

## 1. Job and audience

**Visitor mode: Operate。只有 admin。** 人會打開這一頁的時刻：

- **多一顆碟**：在 Jellyfin 替媒體庫加了第二條路徑，要讓 Berth 也寫得進去（brief §4.3）。
- **某條 Route 紅了或要退役**：看出是哪條纜繩斷了；修好後重新檢查、啟用；不用了就停用或刪除。
- **精靈跑完之後改名稱**（profile 選擇已隨票 14e 拿掉）。

桌機為主；手機上要看得到狀態、做得到停用與重新檢查（PRODUCT.md 的裝置假設）。

## 2. Outcome and proof

**主要任務**：一眼看出每條 Route 寫到哪裡、還繫著嗎、有多少東西用著它；新增一條並當場知道五條纜繩綠不綠。

**證據**（只放實測值）：名稱、slug · category、寫入目標、Jellyfin 媒體庫名、`N 筆下載 · M 個入庫檔案`
（後端算）、五條纜繩的實測值與服務原文、最後成功時間。

**只有 Berth 說得出來的**：這條 Route 為什麼刪不得（誰指著它）；Jellyfin 現在回報哪些路徑、哪幾條已經是別條 Route 的。

## 3. Selected direction

同一塊板、同一組元件（`RouteCheckList`、`StepLine`、`ConfirmAction`、`Notice`、`Field`、`Checkbox`）。

- **頁頂**：標題「設定」加一條子分頁列「服務 | 媒體庫路徑」，兩頁共用；當前頁用 `NAV_BOX_ACTIVE` 的重橫線與 `deck` 底。
- **Route 清單**：每條一個原生 `<details>` 列（健康頁 `RouteRow` 的形狀）。summary 一行：狀態色塊、
  停用時多一塊中性「停用」色塊、名稱、category、寫入目標、引用數、`管理 / 收起`。
- **展開區，由上而下**：編輯（名稱、啟用）→ 五條纜繩與「重新檢查」→ 刪除。
  - 沒有東西指著它：`ConfirmAction` 的二次確認，說清楚會發生什麼（qBittorrent 的分類與目錄留著）。
  - 有東西指著它：**不給刪除鍵**，直接寫「N 筆下載、M 個入庫檔案指著它，刪不得；停用它，新的送單就不會再選到」。
- **清單下方「新增 Route」**：按下去就地展開，這時才向 Jellyfin 現查媒體庫 → 選媒體庫 → 選它回報的路徑
  （已經有 Route 的路徑列出來但選不了，寫明「已是 TV」）→ 名稱（預填媒體庫名）→
  「建立並檢查」。結果回到清單：新的那一列展開、纜繩就位；紅燈時說「維持停用，修好掛載後重新檢查再啟用」。

**焦點時刻**：紅的那一條纜繩，與「刪不得」的理由和出路。

**實作後果**：
- 精靈泊位 4 配合「只新增不改不刪」：已經有 Route 的媒體庫在勾選表上鎖住；每條 Route 底下有同一個刪除元件。
- 健康頁 Route 區塊對 admin 多一條「到 Route 設定」。

## 4. Scope and boundaries

**做**：`/settings/routes`、兩頁共用的子分頁列、精靈泊位 4 的兩處配合、健康頁那一條連結。

**不做**：改 slug 或寫入目標（使用者拍板：換目標 = 新增一條、刪掉舊的）、清掉 qBittorrent 分類、批次動作、
排序、Issue、M1.5 的媒體庫瀏覽。

**不能動**：四個信號色與 `on-signal`、泊位板、`RouteCheckList` / `StepLine` 的形狀。

## 5. States and ranges

| 東西 | 最小 | 典型 | 最大 |
| --- | --- | --- | --- |
| Route | 0 | 3–4 | < 10 |
| 一條 Route 的纜繩 | 5 | 5 | 5 |
| Jellyfin 媒體庫 | 1 | 3 | ~10 |
| 一個媒體庫的路徑 | 1 | 1–2 | ~4 |

- **載入中** / **Berth 後端不回應**：與服務設定頁同一種 `Notice`。
- **0 條 Route**：指回精靈泊位 4（Route 一般由精靈建）。
- **Jellyfin 現查失敗**（`jellyfin_unreachable`）：只有新增區塊說 Jellyfin 連不上加原文，清單照常。
- **沒有可選的路徑**（全部被佔用）：說「先在 Jellyfin 替這個媒體庫加一條路徑」。
- **建立被拒**（422）：`library_missing` / `library_unsupported` / `target_not_in_library` / `target_taken` 各一句。
- **啟用被拒**（409 `route_unhealthy`）：維持停用、那一列展開、紅的纜繩就地說原因。
- **刪除被拒**（409 `route_in_use`，清單之後才有人送單的競態）：同樣說原因與出路。
- **檢查中 / 建立中**：按鈕換成進行中的字，纜繩清單 `aria-busy`。

## 6. Interaction and layout

- 單欄 `max-w-3xl`，與服務設定頁同寬。窄版 summary 自然換行、表單單欄；這一頁沒有唯一的主要動作，所以不做黏底。
- 紅燈或停用中的列預設展開；綠燈收起。展開與否用模板字自己說出來（`<summary>` 是 flex，三角形會被吃掉）。
- 狀態三重編碼：色塊 + 模板字 + 位置。「停用」不是四個信號之一，用中性色塊（The Role Is Not A State Rule 的同一個道理）。
- 非同步結果 `aria-live`；失敗 `role="alert"`。鍵盤全程可做，原生 `details` / radio / checkbox，不引入 Radix。
- 長路徑換行（`break-words`），不截斷、不橫向捲動。

## 7. Constraints and open decisions

React 19 + TS + Tailwind v4 + TanStack Router / Query + react-i18next；zh-Hant 與 en 並列；WCAG 2.2 AA 深淺兩主題。
API：`GET /api/routes`、`POST /api/routes`、`PUT|DELETE /api/routes/{id}`、`POST /api/routes/{id}/check`、
`GET /api/jellyfin/libraries`。

**票 14 開工時使用者拍板**：精靈第 7 步只新增不改不刪；新建或重新啟用時紅燈 → 建立但維持停用；PUT 只改名稱、profile、啟用（票 14e 起只剩名稱與啟用）。

**shape 的三個決定（2026-09-15 使用者回答）**：

1. 兩頁共用一條子分頁列，頁首的「設定」仍只有一個入口。
2. 綠燈收起、紅燈（與停用）就地展開。
3. 「新增 Route」在清單下方，按下去才就地展開、才現查 Jellyfin。
