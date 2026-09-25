# Shape：Media 詳情頁的「RSS 訂閱」（M3 票 19）

2026-09-26。是既有頁面上的一段，照 `/rss` 的 shape（`rss-shape.md`、`preview-shape.md`）與既有元件做。

## 開工前拍板的兩題（使用者，2026-09-26）

1. **Mikan 的番組由 Berth 代搜**（不是貼網址）：Mikan 的 `/Home/Search?searchstr=` 用英文、羅馬字、日文、繁中都搜得到
   （實測四種寫法同樣兩筆），番組頁左欄有字幕組 id、名稱、最近更新（brief §20.12）。
2. **Nyaa / acg.rip 的搜尋 feed 預先綁定**：Feed 記下作品、Route 與建它的人，長出的每一個 RSS Series 直接綁上；
   第一輪照樣停在預覽。搜到別部作品的風險由預覽與 Series 第一批審核接住。

## 位置與形狀

- 在搜尋區塊之後、季表之前：兩個都是「怎麼把它弄進來」。**只有 admin 畫**（`/rss/*` 整組 admin，後端同時 403）。
- 區塊頭：「RSS 訂閱」+ 到 `/rss` 的連結。
- **已綁在這部作品上的 RSS Series** 一列一個：來源代號（`MIKAN` / `NYAA` / `ACG.RIP`，機器字串）、字幕組、
  第一批確認狀態（還沒確認是 `assigned` 色塊「第一批待確認」，確認過不塗漆）、最近一集（發佈名 + 相對時間）。
  沒有時一句話。
- 「新增訂閱」是就地展開的確認區塊（`ConfirmPanel`，同 `SeriesBinder`），不是 dialog：
  1. 來源三選一（一顆鍵一個，按下的樣子是選定）。
  2. Route（`RoutePicker`，預選同 `preselect`）。
  3. Mikan：搜尋框預填原文標題（Mikan 的番組名來自 bgm.tv，日文原名最穩）→ 番組清單 → 字幕組清單（名稱、
     幾筆、最近更新、最新一筆發佈名；已經綁了的鎖住並說綁在哪）→「同時補下載舊集」預設勾 → 確認鍵。
     確認區塊重述**資料夾名**（綁定那一刻定死，同 `SeriesBinder`）。
  4. Nyaa / acg.rip：作品的標題集合（`GET /search/queries`，與搜尋區塊同一份）一個一顆鍵，下面一格可改的搜尋詞 →
     確認鍵「建立搜尋 feed」。建好之後就地換成那個 Feed 的第一輪預覽（`/rss` 的 `FirstRound` 重用）。
- 做完之後：Mikan 說「已訂閱，送出 N 集」；列表重讀。
