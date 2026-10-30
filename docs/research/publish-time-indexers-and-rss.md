# 發佈時間：索引站與 RSS

從 design-brief §20.11 搬來（原文不改字）。

### 20.11 發佈時間：索引站與 RSS（2026-09-24 查證）

播出日比對（M3 票 14）與之後可能的「發佈離播出多近」都要一個發佈時間。試跑環境（Prowlarr 預設公開站）實測：

- **Prowlarr 搜尋結果每一筆都有 `publishDate`**（ISO 8601、UTC）：搜「Kamiina Botan」534 筆，Mikan 261、Anime Tosho 100、dmhy 80、The Pirate Bay 63、ACG.RIP 30，缺值 0。Berth 的 adapter 已經解析成 `published_at`（`adapters/indexer/prowlarr.py`；M4 票 37 前另有 `torznab.py`，Torznab 的 `pubDate` 是 RFC 822），但**之後沒有任何地方用到**：不在搜尋結果的 API 裡，送單也沒存。【實測】**M3 票 14 起接上**：搜尋結果帶 `published_at`、送單存進 `jobs.published_at`，規劃時做播出日比對（plan §4.4）。
- **ACG.RIP 的 RSS** 是標準的 `<item><pubDate>`，RFC 822 帶時區（`Thu, 24 Sep 2026 06:01:00 -0700`）。【實測 `https://acg.rip/.xml`】
- **Mikan 的 RSS 沒有標準的 `<item><pubDate>`**：日期在 `https://mikanani.me/0.1/` 命名空間的 `<torrent><pubDate>`，ISO 8601 **不帶時區**（`2026-09-24T21:01:00.760219`）。同一個發佈在 ACG.RIP 是 13:01 UTC，所以 Mikan 的值是 **UTC+8**；當成 UTC 讀會差 8 小時。【實測 `https://mikanani.me/RSS/Classic`，與 ACG.RIP 同一筆對照】
- Nyaa 的 RSS 從試跑機器連不上（連線失敗），沒有量到。**2026-09-25 補量**（§20.12）：`<pubDate>` 是 RFC 822 的 `-0000`，即 UTC。
- **發佈時間是「這一筆條目」貼出的時間，不是這一集的首發**：重新上傳、合集、聚合站晚收錄都會讓它偏晚（Anime Tosho 上 SubsPlease 同一包的 01 與 12 兩個單集檔相隔 4 分鐘）。它只保證「那一集在它之前已經播出」，所以適合當下限（規則一：早於播出日就一定算錯），不適合量「多新」。SubsPlease《上伊那牡丹》01–12 合集在 Anime Tosho 是 2026-08-15，TMDB 第一季末集 2026-06-27。【實測】
