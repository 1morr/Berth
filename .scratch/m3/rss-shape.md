# /rss 頁的 shape（M3 票 08，2026-09-25）

`/impeccable shape` 的產出。三題照建議拍板（使用者同日）；其餘照 DESIGN.md 既有規則定，不另開新語彙。

## 1. 工作與對象

- **誰**：admin（整頁只有 admin，`/rss/*` 在門禁 `ADMIN_PREFIXES`）。模式是 Operate。
- **什麼時候打開**：加一個 Mikan 聚合 feed 的那一次；之後只在「有新的 RSS Series 等綁定」時回來。
  平常它在背景輪詢，人不盯著它（PRODUCT.md Operating Context）。
- **主要任務**：把待綁定的 RSS Series 綁到作品與 Route，讓它底下留著的集數送出去。

## 2. 版面（拍板：單頁堆疊，待綁定在最上）

由上而下，窄版同一順序：

1. **待綁定**（有才出現）：`h2` 是 `.label` + 計數，旁邊一塊 `assigned` 的「N 待綁定」——
   需要你的事浮到摘要層（DESIGN.md Needs-You Floats Up）。每列：`title_raw`（`.value wrap-anywhere`）、
   Mikan 番組 id × 字幕組 id、留著的集數；一顆「綁定」。展開區是鍵與 Mikan 番組頁的連結（認不出是哪一部時
   去那一頁看，實作時加）。
2. **Feed**：新增表單（網址、名稱選填；間隔預設 15 分，不在表單上）、每一列是名稱、網址（`token=` 只留前四碼：
   聚合 feed 的 token 就是憑證，實作時加）、上次輪詢時間、上一輪的問題（有才就地展開原文；塗 `assigned` 不塗
   `blocked`：抓不到 Feed 或幾筆單集頁抓不到都是下一輪再試，code-review 時改）、「立即輪詢」（按完一行說這一輪
   長出了什麼）、「刪除」（就地確認）。
3. **RSS Series**：已綁定的列，中性不塗漆（Usual Stays Unpainted）：作品名、Route、季號 / offset（有才寫）、
   「解除綁定」（就地確認）。
4. **最近的 Feed Item**：最近 50 筆，每列發佈名、發佈時間、狀態色塊——`unbound` 是中性「待綁定」（它的
   series 已經在第 1 段塗過漆，不重複塗）、`matched` 且有錯誤時 `blocked` 並就地展開原文、`downloaded` 是中性
   「已送單」並連到 `/jobs/:hash`。（實作與 code-review 時改：`matched` 帶原文是 `assigned` 的「送不出去」——
   卡住、下一輪再送，原因多半要人去修；DESIGN.md 的卡住是 `assigned`。）

頁寬：決策與清單的 `max-w-[80rem]`。

## 3. 綁定（拍板：在那一列就地展開）

- 「綁定」展開同一列：作品搜尋框（預填 Series 的標題骨幹，打 `GET /discover/search`）→ 結果清單（單選）→
  選到之後打 `GET /media/{id}` 拿「將會是」的資料夾名 → Route 下拉（只列收得下這種作品的、啟用中的）→
  確認區塊重述**資料夾名**與「將送出 N 集」→ 「綁定並送出」。
- 焦點照 `useInPlaceConfirm`：展開進確認區、`Esc` 收回觸發鍵。綁定成功那一列會從待綁定段消失，焦點照
  `useFocusAfterRemoval` 落在接替的那一列（或段落標題），同一層 `aria-live` 說結果。
- 送單被拒（Route 紅燈、磁碟門檻）不擋綁定：綁定本身成立，那幾筆 Item 留在 `matched` 帶著原文，
  下一輪輪詢再送（失敗就地展開在 Item 那一列）。

## 4. 刪除 Feed（拍板：Item 一起刪、Series 留著）

RSS Series 是「作品 × 字幕組」，不屬於某一個 Feed。刪 Feed 連它的 Item 一起刪，Series 與綁定不動；
重新加回同一個網址會重新長出 Item，已送的 Job 以 info hash 認回、不重送。所以 `delete_feed` 標
`reversible`，反向是 `add_feed`。就地確認說出會刪掉幾筆 Item。

## 5. 狀態與範圍

- 空：沒有 Feed 時整頁只有 Feed 段與一句「加一個 Mikan 的『我的番組』RSS」；待綁定段不出現。
- 典型：1–3 個 Feed、10–40 個 Series、待綁定 0–5 個。Item 清單固定取最近 50。
- 錯誤：Feed 網址不是認得的來源（這一票只認 `mikanani.me`）在欄位下方說；輪詢失敗記在那一列。
- 讀取中：不動的 `deck` 色條，同其他頁。

## 6. 不做（留給後面的票）

排除條件（10）、自動綁定（09）、補舊集（12）、季號與 offset 的編輯（13）、一次性連結（18）、
Feed 的編輯與停用（`PUT /rss/feeds/{id}` 沒有消費者就不做）。
