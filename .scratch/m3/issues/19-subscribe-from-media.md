# 19 — 從 Media 頁訂閱

**Status:** done

**Blocked by:** 11（三種來源）、12（Mikan 綁定時補舊集）

**讀:** plan §7（Media 詳情）、§11.4；brief §13（Media 詳情的「RSS 訂閱」）、§15（「從 Media 頁訂閱」）

## 做什麼

次要入口（brief §15）：在 Media 詳情頁選一個來源，建一條單一 feed，並**預先綁定這部作品**。

- **Mikan**：選番組與字幕組 → 建 `/RSS/Bangumi?bangumiId=&subgroupid=` 的 Feed → 長出的 RSS Series 直接綁到這部作品與所選的 Route → 照票 12 補舊集（預設勾選）。番組怎麼找（Mikan 搜尋頁或使用者貼網址）在 shape 時決定，要先查 Mikan 有沒有可用的搜尋入口，查到的補進 brief §20。
- **Nyaa / acg.rip**：以這部作品的標題（與 `services/search.py` 同一份標題集合）組搜尋 feed 網址 → 建 Feed → 走票 11 的第一輪預覽。
- 已經有 RSS Series 綁在這部作品上時，詳情頁顯示它們（來源、字幕組、是否確認、最近一集），可以連到 `/rss`。
- 綁定走票 08 的同一個命令，凍結 `folder_name` 的規則相同。

## 驗收

- [x] 從詳情頁訂閱一部 Mikan 作品 → Feed、RSS Series 已綁定、舊集已送單（整合測試）
- [x] 從詳情頁建 Nyaa 或 acg.rip 搜尋 feed → 出現第一輪預覽
- [x] 詳情頁列出已綁在這部作品上的 RSS Series
- [x] 只有 admin 看得到訂閱入口
- [x] playwright 實跑，1280 與 390，附結果
- [x] lint、type、test 綠燈

## Comments

2026-09-26 實作。playwright 實跑 `rss-subscribe`（1280）與 `rss-subscribe-390`：詳情頁以原文標題搜 Mikan →
選番組 4009 → LoliHouse（370）→ 訂閱並補舊集，送出 12 集、列表多一列 `MIKAN · 喵萌奶茶屋&LoliHouse · 第一批待確認`；
再以英文標題建 acg.rip 搜尋 feed，第一輪就地預覽「會送出 30 · 綁定之後送 0」，選「只追之後的」；`/jobs` 12 筆。
兩種寬度各四張整頁截圖在 `web/test-results/rss-subscribe-*/`。

code-review（Standards / Spec）處理了：`subscribe_mikan` 就地綁定那一條的反向命令不是 `delete_feed`（改成不宣告單一
反向）；預先綁定漏了別的 Feed 先長出、還在待綁定的同鍵 Series（補測試與 `_waiting_series`）；完成那一句只給螢幕
閱讀器（改成看得見）；鎖住的字幕組說出綁在哪一部（作品 id）；README 的 project 數；brief 補「讀不到就拒絕」。

未處理（判斷題，留著）：
- `media/SubscribePanel.tsx` 的 `Options<T>` 與 `rss/WorkChoices.tsx` 的 `Choices` 同形；泛型化 `Choices` 要動 `/rss`
  兩處呼叫端，留到下一次再碰它時。
- 「資料夾名將定下來」那兩行是第三份（`SeriesBinder`、`OneshotSection`、這裡），同上。
- `_series_view` 每一列多兩個查詢（最近一筆 Item 與它的 Feed），`/rss` 的 Series 清單是 N+1；Series 數量是幾十個的量級。
- `subscribe_search` 依 `FeedKind` 分派到 adapter 是 `rss.py` 第三處 `match kind`。
- 預先綁定的 Feed 帶到**已經綁在別部作品上**的同鍵 Series 時不改綁：那是人或自動綁定做過的決定，Item 照它送。
