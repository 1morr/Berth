# RSS 來源的欄位事實：Mikan、Nyaa、acg.rip（M3 票 07 / brief §15、§20.11、§20.12、plan §8.5）

結論摘在 brief §20.12，FeedItem 的取法寫進 plan §8.5。

2026-09-25。一手資料是 `tests/fixtures/http/{mikan,nyaa,acgrip}/` 裡的 fixture（§1 有取得方式），加上
Nyaa 的原始碼、feedparser 的文件（context7）與原始碼，以及在 fixture 上實際跑 feedparser 的結果。
分析腳本在 `scripts/experiments/rss_sources.py`：票 08 的 adapter 契約測試會拿同一批 fixture 接手，
跑法與輸出摘要寫在 §7.4。

## 0. 結論

1. **三個來源都拿得到 guid、標題、發佈時間與 torrent 來源，但各自缺的東西不一樣。**
   - Mikan 沒有 magnet 與做種數，大小不準。
   - Nyaa 沒有 enclosure，大小只有人類可讀字串。
   - acg.rip 沒有 info hash、magnet 與做種數。
   逐欄對照在 §9，plan §8.5 可以照抄。
2. **info hash：Mikan 與 Nyaa 不用多發請求，acg.rip 拿不到。**
   - Mikan 的 `link`（`/Home/Episode/<40 hex>`）與 enclosure 檔名末段就是 info hash。
     124/124 筆兩者一致；抽了一個 `.torrent` 自己算 info dict 的 SHA-1，結果相同（§2.3）。
   - Nyaa 有 `nyaa:infoHash`（114/114 筆是 40 位 hex）。
   - acg.rip 的 feed 與單集頁都沒有 info hash，只能下載 `.torrent` 來算。
3. **跨 feed 以 info_hash 去重：要做，而且不必多發請求。**
   - Mikan 與 Nyaa 在輪詢時就比對。
   - acg.rip 不在輪詢時預抓：送單時 `berth/adapters/torrent.py` 本來就要下載 `.torrent` 並算出 hash，
     `jobs.hash` 是主鍵，同一個 hash 本來就只會有一筆 Job。
   - 「同一個發佈在不同站是不是同一個 info hash」**沒有驗證**（要下載 acg.rip 的 `.torrent`，
     這次沒做），帳本的「同 Media / 季 / 集 / Tags」是最後一道防線（§8）。
4. **feedparser 6.0.14（2026-07-30 發佈，目前最新）三個來源都讀得動，沒有丟欄位。但 Mikan 有兩個地方
   會安靜地讀錯。**
   - `published_parsed` 把不帶時區的 `<torrent><pubDate>` 當成 UTC，**差 8 小時**。
     要改讀 `entry.published` 字串，用 `datetime.fromisoformat` 解析後加上 UTC+8。
   - `<torrent>` 的命名空間被抹掉：`pubDate` 變成標準的 `published`，`link` 變成第二個 `links`，
     `contentLength` 變成 `contentlength`。現在不衝突；哪天 Mikan 加上標準的 `<item><pubDate>` 就會撞名（§7.3）。
   - 所以不必改用 `xml.etree`。
5. **Mikan 的 `contentLength` 與 enclosure `length` 不是位元組數。** 124/124 筆都等於
   `int(float32(描述裡的數字) × 1024^k)`，描述裡的數字又是十進位的 MB。以實際 torrent 對照，
   `543,843,968` 對上真實的 `518,645,975` 位元組，多了 4.86%（§2.4）。三個來源的大小都只當顯示用的近似值。
6. **時區**：同一個發佈（喵萌奶茶屋&LoliHouse《与你相恋到生命尽头》第 12 集）：
   - Mikan 的無時區時間減去 acg.rip 換成 UTC 的時間，是 **+7:59:59.389**。
   - 第 11 集是 +7:59:59.462。
   - torrent 本身的 `creation date` 是 08:05:49 UTC，早兩分鐘。

   Mikan 是 UTC+8，brief §20.11 成立（§5）。Nyaa 的 `-0000` 用 `email.utils.parsedate_to_datetime`
   會得到**不帶時區**的 datetime，要自己補 UTC。
7. **合集從 feed 欄位分不出來，三站都只能看標題。** acg.rip 的搜尋 feed 30 筆裡有 8 筆合集
   （7 筆多集、1 筆 BD Vol.1）；Nyaa 搜尋 feed 75 筆裡有 14 筆。寫法五花八門（`[01-12 合集]`、`(01-12) … [Batch]`、
   `第01-12話 … [合集]`、`(Season 01) … (Batch)`、`[Vol.1][BDRemux]`，§6）。Mikan 的 Classic 也夾合集。
8. **2026-09-24 的五條實測在 2026-09-25 的 fixture 上都重現了（§10）。** MyBangumi 聚合 feed 的 12 筆
   橫跨 6.6 天，4009 × 370 只剩 11、12 兩集；單一 feed 01–12 都在。Nyaa 今天從開發機仍然連不上
   （curl 與 Python 都在 TLS 握手失敗），Mikan 與 acg.rip 同時是 200。

## 1. 資料與方法

| fixture | 原網址 | 取得方式 |
| --- | --- | --- |
| `mikan/rss-bangumi.4009-370.xml` | `https://mikanani.me/RSS/Bangumi?bangumiId=4009&subgroupid=370` | curl 匿名 |
| `mikan/rss-classic.xml` | `https://mikanani.me/RSS/Classic` | curl 匿名 |
| `mikan/rss-mybangumi.xml` | `https://mikanani.me/RSS/MyBangumi?token=…` | 使用者自己下載；channel `<link>` 的 token 換成 `REDACTED`，其餘原樣 |
| `mikan/home-bangumi.4009.html` | `https://mikanani.me/Home/Bangumi/4009` | curl 匿名 |
| `mikan/home-episode.85c93c23.html` | `https://mikanani.me/Home/Episode/85c93c23143bbeb98f9c0895d31ab18ceeed4090` | curl 匿名 |
| `mikan/download.85c93c23.torrent` | `https://mikanani.me/Download/20260924/85c93c23143bbeb98f9c0895d31ab18ceeed4090.torrent` | curl 匿名 |
| `nyaa/rss-search.kamiina-botan.xml` | `https://nyaa.si/?page=rss&q=Kamiina+Botan&c=1_0&f=0` | playwright 開 nyaa.si 後在頁內 `fetch()`（§3.5） |
| `nyaa/rss-user.subsplease.kamiina-botan.xml` | `https://nyaa.si/?page=rss&u=subsplease&q=Kamiina+Botan` | 同上 |
| `acgrip/rss-search.kimi-ga-shinu.xml` | `https://acg.rip/.xml?term=Kimi+ga+Shinu+made+Koi+wo+Shitai` | curl 匿名 |
| `acgrip/rss-search.kamiina-botan.xml` | `https://acg.rip/.xml?term=Kamiina+Botan` | curl 匿名 |

全部在 2026-09-25 取得。fixture 裡的 token 只有一處：`grep -o "token=[^<&\"]*" -r mikan nyaa acgrip`
只印出 `mikan/rss-mybangumi.xml:token=REDACTED`。兩個 HTML 頁是未登入狀態（頁上是登入表單）。

另外在 2026-09-25 補查了三件事：

- 另外兩個 Mikan 番組頁，用來判定「放送开始」的日期格式（§2.7）。
- acg.rip 單集頁 `https://acg.rip/t/363901`，確認上面有沒有 info hash（§4）。
- 用 curl 與 Python 重測 Nyaa 連不連得上（§3.5）。

## 2. Mikan

### 2.1 欄位

以下三種 feed 的 item 結構逐元素相同（§2.6）：

| 元素 | 內容 | 備註 |
| --- | --- | --- |
| `<guid isPermaLink="false">` | **就是標題**（124/124 筆 `guid == title`） | 見 §2.2 |
| `<link>` | `https://mikanani.me/Home/Episode/<40 hex>` 單集頁 | 末段 = info hash（§2.3） |
| `<title>` | 發佈標題 | |
| `<description>` | 標題 + `[518.65 MB]` 大小後綴 | 124/124 筆符合 `\[([\d.]+)\s*(KB\|MB\|GB\|TB)\]$`；空格可有可無（`[388.5MB]`） |
| `<torrent xmlns="https://mikanani.me/0.1/">` | 以預設命名空間宣告的容器 | 不是前綴式命名空間 |
| `<torrent><link>` | 與 `<link>` 相同 | |
| `<torrent><contentLength>` | 整數，**不是位元組數**（§2.4） | 與 enclosure `length` 相同 |
| `<torrent><pubDate>` | ISO 8601 **不帶時區**，實為 UTC+8；小數秒位數不固定（§2.5） | item 層**沒有**標準的 `<pubDate>` |
| `<enclosure>` | `type="application/x-bittorrent"`、`length`、`url=https://mikanani.me/Download/<YYYYMMDD>/<40 hex>.torrent` | `<YYYYMMDD>` 是 UTC+8 的日期（第 11 集 `03:16` 發佈，資料夾是 `20260923`，UTC 那天還是 22 日） |
| 做種數 | **無** | |
| magnet | feed 裡**無**；單集頁與番組頁有（§2.7） | |

範例（`mikan/rss-bangumi.4009-370.xml` 第一筆，排版後）：

```xml
<item>
  <guid isPermaLink="false">[喵萌奶茶屋&amp;LoliHouse] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai - 12 [WebRip 1080p HEVC-10bit AAC][简繁日内封字幕]</guid>
  <link>https://mikanani.me/Home/Episode/85c93c23143bbeb98f9c0895d31ab18ceeed4090</link>
  <title>[喵萌奶茶屋&amp;LoliHouse] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai - 12 [WebRip 1080p HEVC-10bit AAC][简繁日内封字幕]</title>
  <description>[喵萌奶茶屋&amp;LoliHouse] 与你相恋到生命尽头 / … - 12 [WebRip 1080p HEVC-10bit AAC][简繁日内封字幕][518.65 MB]</description>
  <torrent xmlns="https://mikanani.me/0.1/">
    <link>https://mikanani.me/Home/Episode/85c93c23143bbeb98f9c0895d31ab18ceeed4090</link>
    <contentLength>543843968</contentLength>
    <pubDate>2026-09-24T16:08:01.389</pubDate>
  </torrent>
  <enclosure type="application/x-bittorrent" length="543843968"
             url="https://mikanani.me/Download/20260924/85c93c23143bbeb98f9c0895d31ab18ceeed4090.torrent" />
</item>
```

### 2.2 guid 的穩定性

guid 是標題原文，`isPermaLink="false"`。發佈者在 Mikan 上改標題時 guid 會不會跟著變，fixture 量不到：
要同一筆改標題前後各抓一次。但既然 124/124 筆的 guid 與 title 逐字相同，**合理的推論是會跟著變**。
以 `(feed_id, guid)` 去重時，一次改標題就會變成「新的一筆」再下載一次。

建議 Mikan 的 `FeedItem.guid` 改用 `link` 末段的 40 位 hex。它就是 info hash（§2.3），同一個 torrent
不會變；改標題的重發是另一個 torrent，本來就該是另一筆。

### 2.3 info hash

- `download.85c93c23.torrent`：只找出 `info` 值的原始位元組範圍再算 SHA-1，不解碼再編碼。結果是
  `85c93c23143bbeb98f9c0895d31ab18ceeed4090`，與單集頁網址末段、enclosure 檔名相同。
  - 這個 torrent 是單檔（`info` 有 `length = 518,645,975`、`name = [Nekomoe kissaten&LoliHouse] Kimi ga Shinu made Koi wo Shitai - 12 [WebRip 1080p HEVC-10bit AAC ASSx2].mkv`）。
  - 頂層另有一個非標準的 `hash` 鍵，值也是同一串，產生工具是 `created by: rin-pr/0.6.0`。這個鍵不能依賴。
- 抽查三份 Mikan feed 共 124 筆：`<link>` 末段全是 40 位小寫 hex，而且等於 enclosure 檔名與
  `<torrent><link>` 的末段，0 筆不符。
- 所以「網址末段 = info hash」有 1 份 torrent 的直接證據，另外 123 筆只有形狀一致的旁證。
  送單時 `TorrentFetcher` 反正會下載 torrent 並算出真正的 hash；兩者不同時應該記一筆事件，
  用來守住這個推論（§8）。

### 2.4 大小：`contentLength` 不是位元組

| 來源 | 值 | 對真實大小 |
| --- | --- | --- |
| torrent `info.length`（真實） | 518,645,975 B | — |
| Mikan 描述後綴 | `518.65 MB` | = 518,645,975 / 10⁶ 四捨五入，**十進位** MB |
| Mikan `contentLength` / enclosure `length` | 543,843,968 | = `float32(518.65) × 2²⁰`，**多 4.86%** |
| acg.rip `torrent:contentLength` | 518,645,760 | = `floor(518,645,975 / 1024) × 1024`，差 215 B |
| acg.rip 單集頁顯示 | `494.6 MB` | = 518,645,975 / 2²⁰，標 MB 實為 MiB |

- 124/124 筆 Mikan item 的 `contentLength == int(float32(N) × 1024^k)`，N、k 取自描述後綴。
  若改用 float64 並四捨五入，只有 21 筆對得上，所以是 float32。
- GB 級的只剩一位或兩位小數。例如 `[2.9 GB]` 對 `3,113,851,392 = float32(2.9) × 2³⁰`，誤差可以到 ±50 MB。
- 「描述數字是十進位」有兩個錨點：第 12 集用 torrent 本身；第 11 集用 acg.rip 的 `528,860,160`
  對 Mikan 的 `[528.86 MB]`。GB 級的單位沒有獨立驗證。
- 結論：Mikan 的大小取描述後綴 `N × 1000^k`，當近似值；不要拿 `contentLength` 當位元組。

### 2.5 發佈時間

- 只有 `<torrent><pubDate>`，沒有標準的 `<item><pubDate>`；時區是 UTC+8（§5）。
- **小數秒位數不固定**：Classic 100 筆裡有 0、3、5、6 位（`2026-09-25T14:39:00`、
  `2026-09-24T16:08:01.389`、`2026-09-24T23:01:18.08478`、`2026-09-25T13:24:11.894809`）；MyBangumi 有 0、3、6 位。
  位數不固定，看起來是把結尾的 0 去掉了；7 位的情形在 fixture 裡沒出現，但不能排除。
- **讀得動嗎**（Python 3.13.14，實跑）：

| 輸入 | `datetime.fromisoformat` | feedparser `_parse_date`（→ `published_parsed`） |
| --- | --- | --- |
| `2026-09-25T14:39:00`（0 位） | `2026-09-25 14:39:00` | `(2026, 9, 25, 14, 39, 0)`，當 UTC |
| `2026-09-24T16:08:01.389`（3 位） | `…16:08:01.389000` | 秒以下截掉，當 UTC |
| `2026-09-24T23:01:18.08478`（5 位） | `…23:01:18.084780` | 同上 |
| `2026-09-25T13:24:11.894809`（6 位） | `…13:24:11.894809` | 同上 |
| `2026-09-24T16:08:01.1234567`（7 位，自造） | `…16:08:01.123456`（第 7 位截掉） | 同上 |

  `fromisoformat` 在 3.11 起接受大部分 ISO 8601 形式，0 到 7 位小數都讀得動，結果是 naive datetime。
  feedparser 讀得動但一律當 UTC：`datetimes/w3dtf.py` 沒有時區時取 `timezonenames.get('', 0)`，
  也就是偏移 0。**正確讀法**是 `datetime.fromisoformat(entry.published).replace(tzinfo=timezone(timedelta(hours=8)))`。
  中國沒有日光節約時間，所以固定 +8 與 `Asia/Shanghai` 等價。
- 番組頁的表格用 `2026/09/24 16:08`，單集頁用 `昨天 16:08` 這種相對時間。兩者都不要拿來當資料來源。

### 2.6 三種 feed 是同一種格式

把每個 item 的元素樹（標籤、屬性名、子元素，遞迴）化成一個形狀來比，
`rss-bangumi.4009-370.xml`（12 筆）、`rss-classic.xml`（100 筆）、`rss-mybangumi.xml`（12 筆）
**三份都只有同一種形狀**，而且三份之間也相同。所以「聚合 feed 與單一 feed 同格式」現在有實物證據，
不再只是假設。三份的 channel `<title>` 各是 `Mikan Project - 与你相恋到生命尽头`、`… - 列表模式`、`… - 我的番组`。

### 2.7 番組頁與單集頁（票 09 自動綁定用）

兩頁的中文字都是 HTML 數字字元參照（`&#x4E0E;&#x4F60;…`），要先 `html.unescape`。每一頁都有
桌面版（`#sk-container`）與手機版（`#sk-mobile-container`）兩份，同一個值出現兩次。以下行號是 fixture 的行號。

**單集頁 `home-episode.85c93c23.html`**：反查番組 id 與字幕組 id，三處都有。

| 位置 | 內容 |
| --- | --- |
| 第 166 行 `#sk-container p.bangumi-title a.mikan-rss[href]` | `/RSS/Bangumi?bangumiId=4009&subgroupid=370`，**最直接** |
| 第 165–166 行 `p.bangumi-title a[href^="/Home/Bangumi/"]` | `/Home/Bangumi/4009#370`（片段是字幕組 id） |
| 第 181 行、第 259 行（手機版） `button.js-subscribe_bangumi_page` | `data-bangumiid="4009" data-subtitlegroupid="370"` |
| 第 169 行 `p.bangumi-info a[href^="/Home/PublishGroup/"]` | `/Home/PublishGroup/223`，文字 `LoliHouse` |
| 第 179 行、第 257 行 `a.episode-btn[href^="magnet:"]` | `magnet:?xt=urn:btih:85c93c23…&tr=…`（帶 tracker 清單） |

注意兩個 id 空間：

- **字幕組 id 370 與發佈組 id 223 不是同一個東西**。反查要用 `subgroupid`，不是 `PublishGroup`。
- Mikan 自己把 370 顯示成「LoliHouse」（番組頁第 198 行 `a.subgroup-name.subgroup-370`、第 1447 行）。
  標題寫的「喵萌奶茶屋&LoliHouse」只是發佈標題，不是 Mikan 的字幕組名。

**番組頁 `home-bangumi.4009.html`**：

| 值 | 位置（桌面版） | 內容 |
| --- | --- | --- |
| 中文標題 | 第 162 行 `#sk-container p.bangumi-title` 的文字節點（去掉裡面的 RSS `<a>`） | `与你相恋到生命尽头`；`<title>` 是 `Mikan Project - 与你相恋到生命尽头`；手機版在第 4217 行 `.m-detail-title p.title` |
| 開播日期 | 第 165 行 `p.bangumi-info`，文字以 `放送开始：` 開頭 | `7/7/2026`，格式是 **M/D/YYYY**（見下） |
| 星期 | 第 163 行 `放送日期：星期二` | |
| 總集數 | 第 164 行 `总集数：13` | |
| bgm.tv | 第 167 行 `p.bangumi-info a[href^="https://bgm.tv/subject/"]` | `https://bgm.tv/subject/541285` |
| 官方網站 | 第 166 行 | `https://kimishinu-anime.com/` |
| 番組層 feed | 第 162 行 `a.mikan-rss` | `/RSS/Bangumi?bangumiId=4009`（不帶字幕組） |
| 各字幕組區塊 | 第 1446 行 `div.subgroup-text#370` | 內有 `/RSS/Bangumi?bangumiId=4009&subgroupid=370`、訂閱按鈕的 `data-bangumiid` / `data-subtitlegroupid`；下面的表格每列有 magnet（`input.js-episode-select[data-magnet]`）、單集頁連結、大小、`2026/09/24 16:08` 更新時間 |

**「放送开始」是 M/D/YYYY**：`7/7/2026` 自己分不出順序，所以 2026-09-25 另外看了兩個番組頁：

- `https://mikanani.me/Home/Bangumi/3990`：`放送开始：7/6/2026`、`放送日期：星期一`。
  2026-07-06 是星期一；若讀成 D/M，2026-06-07 是星期日，對不上，所以是 M/D。
- `https://mikanani.me/Home/Bangumi/3900`：`4/4/2026`、星期六，與 M/D 一致。
- 4009 本身：2026-07-07 是星期二，與 `放送日期：星期二` 一致。

### 2.8 自動綁定的量測（票 09，2026-09-25）

規則在 `berth/parser/binding.py`（brief §15「綁定」）：名字正規化後**相等**（不是包含）、Mikan 的「放送开始」落在
TMDB 某一季首播前後 **14 天**內、而且只有一部這樣的作品。`scripts/experiments/rss_auto_bind.py` 對
`rss-mybangumi.xml` 的 11 個 RSS Series 走同一組函式，Mikan 單集頁、番組頁與 TMDB 都是真的（2026-09-25 實跑）。

| 結果 | 部數 | 說明 |
| --- | --- | --- |
| 有把握、對 | **10** | 逐一對過 TMDB 作品：少女怪兽焦糖味（兩個字幕組各一個 Series）、尼古喵喵、暗黑灯火、魔法少女奈叶 EXCEEDS、才女的侍从、数码宝贝 BEATBREAK、黄泉的使者、转学后班上的清纯可爱美少女、与你相恋到生命尽头 |
| 有把握、錯 | **0** | |
| 留在待綁定 | 1 | Re：从零开始的异世界生活 第四季 夺还篇：番組名帶季數與篇名，TMDB 的名字不帶，`no_candidate`。該留：TMDB 把四季收在同一部底下，要綁也要人確認是第四季 |

- **開播日期的差距是 0–1 天**（10 部：5 部同一天、5 部 TMDB 晚一天——日本深夜檔跨日）。14 天的窗口因此很寬，
  留著是為了對岸平台晚開播時 Mikan 寫它的日期；同名重拍差的是年，不會落進去。
- **相等的那一條線索幾乎都是 Mikan 的簡體番組名**，對上 TMDB 的 `zh-CN` 翻譯（快照的 `titles` 帶著各語言翻譯）；
  發佈名的羅馬字骨幹是退路。番組名與發佈名不一致很常見（`少女怪兽焦糖味` 對 `少女怪兽焦糖恋心`、`黄泉的使者` 對
  `黄泉使者`），兩個都拿去比才認得全。
- **2026-09-26 重量（M4 票 14）：11 部認得 11 部、錯 0 部**。同一份 feed、同一支腳本，規則多了季名：搜尋詞與比對的線索
  拆掉季名（`parser.seasons`），拆出來的季號只比那一季播出的期間。Re:Zero 綁上 TMDB 65942，依據是
  `season_airing {premiere: 2026-08-12, season: 4, episode: S01E78}`——Mikan 的番組 4052 是第四季第二個 cour
  「夺还篇」，TMDB 把四季全部放在第 1 季（brief §20.12）。上面那一列「該留」的判斷由此推翻：季號線索確認了是那一季播出的
  期間，不必再請人確認。其餘十部的依據與 2026-09-25 相同；尼古喵喵試跑當天讀不到的 TMDB 詳情這次讀得到。
- **Route 那一步沒量**：它看的是使用者的設定。試跑環境是 Anime、Movies、TV 三條，Anime 與 TV 都收劇集，照票 09 的
  規則上面 10 部**全部**會留在待綁定、作品預填成候選（理由 `route_ambiguous`）。

## 3. Nyaa

### 3.1 欄位

| 元素 | 內容 | 原始碼（`nyaa/templates/rss.xml`） |
| --- | --- | --- |
| `<guid isPermaLink="true">` | `https://nyaa.si/view/<數字 id>` | `url_for('torrents.view', …)` |
| `<link>` | 預設是 `https://nyaa.si/download/<id>.torrent`；**magnet 模式或該筆沒有 torrent 檔時是 magnet URI** | `{% if torrent.has_torrent and not magnet_links %}` 否則 `torrent.magnet_uri` |
| `<title>` | 發佈標題 | `torrent.display_name` |
| `<pubDate>` | RFC 822，時區固定寫 `-0000`（fixture 全部如此） | `rfc822` filter = `email.utils.formatdate(date.timestamp())` |
| `nyaa:seeders` / `nyaa:leechers` / `nyaa:downloads` | 整數字串 | `torrent.stats.*` |
| `nyaa:infoHash` | 40 位小寫 hex | `info_hash_as_hex` = `info_hash.hex()` |
| `nyaa:categoryId` / `nyaa:category` | `1_2` / `Anime - English-translated` | |
| `nyaa:size` | `240.5 MiB`，**人類可讀、二進位單位、一位小數** | `filesizeformat(True)` |
| `nyaa:comments` / `nyaa:trusted` / `nyaa:remake` | 整數 / `Yes`、`No` | |
| `<description>` | CDATA 的 HTML：`#id \| 標題 \| 大小 \| 分類 \| hash` | |
| `<enclosure>` | **無** | 模板沒有這個元素 |

- 命名空間：`xmlns:nyaa="https://nyaa.si/xmlns/nyaa"`（fixture 第 1 行；原始碼是 `url_for('site.xmlns_nyaa', _external=True)`，
  路由在 `nyaa/views/site.py` 的 `/xmlns/nyaa`）。那一頁本身說明了每個標籤，並說 `nyaa:size` 是
  「一位小數、ISO/IEC 80000-13 前綴」。
- `nyaa:size` 的格式：Jinja `do_filesizeformat(binary=True)` 是 `f"{base * bytes / unit:.1f} {prefix}"`，
  前綴 `KiB`、`MiB`、`GiB`…；小於 1024 時是 `N Bytes`，剛好 1 時是 `1 Byte`。換回位元組有 ±0.05 單位的誤差。
  fixture 裡只出現 `MiB` 與 `GiB`。
- **magnet 模式**：`nyaa/views/main.py` 用 `use_magnet_links = 'magnets' in req_args or 'm' in req_args`，
  只看參數在不在、不看值。開了之後 `<link>` 換成 magnet，channel 標題也從 `Torrent File RSS` 變成 `Magnet URI RSS`。
  adapter 要兩種 `<link>` 都接受。
- **一次最多 75 筆**：RSS 只取第一頁（`nyaa/search.py`：`# Only show first RESULTS_PER_PAGE items for RSS`），
  `DEFAULT_PER_PAGE = 75`，`config.example.py` 裡 `RESULTS_PER_PAGE = 75`。搜尋 fixture 剛好 75 筆（被截斷），
  使用者 feed 39 筆（全部）。回應帶 `Cache-Control: max-age=300`（`render_rss`）。
- 使用者 feed：`u` 或 `user` 參數，使用者不存在回 404（`main.py`）。
- 抽查兩份 fixture 共 114 筆：`nyaa:infoHash` 全是 40 位 hex；`<link>` 全等於把 guid 的 `/view/` 換成
  `/download/` 再加 `.torrent`；pubDate 全部 `-0000`；分類有 `1_2`、`1_3`、`1_4`。
- nyaa.si 實際跑的版本不一定等於 GitHub 的 master，但 fixture 的欄位與模板逐一對得上。

範例（`nyaa/rss-search.kamiina-botan.xml` 第一筆，排版後）：

```xml
<item>
  <title>[Doomdos] - Botan Kamiina Fully Blossoms When Drunk - 第12话 - [1080p BILIBILI COM WEB-DL]</title>
  <link>https://nyaa.si/download/2162858.torrent</link>
  <guid isPermaLink="true">https://nyaa.si/view/2162858</guid>
  <pubDate>Fri, 18 Sep 2026 03:54:17 -0000</pubDate>
  <nyaa:seeders>0</nyaa:seeders>
  <nyaa:leechers>1</nyaa:leechers>
  <nyaa:downloads>29</nyaa:downloads>
  <nyaa:infoHash>838d9bdb7b42d8f8b94331d77489466637a64ca0</nyaa:infoHash>
  <nyaa:categoryId>1_2</nyaa:categoryId>
  <nyaa:category>Anime - English-translated</nyaa:category>
  <nyaa:size>240.5 MiB</nyaa:size>
  <nyaa:comments>0</nyaa:comments>
  <nyaa:trusted>No</nyaa:trusted>
  <nyaa:remake>No</nyaa:remake>
  <description><![CDATA[<a href="https://nyaa.si/view/2162858">#2162858 | …</a> | 240.5 MiB | Anime - English-translated | 838d9bdb…]]></description>
</item>
```

### 3.2 guid

`https://nyaa.si/view/<id>`，id 是資料庫主鍵，標題改了也不變（這是從原始碼推的，沒有量過改標題）。

### 3.3 發佈時間

`formatdate()` 不帶 `localtime` 時輸出 UTC，並依 RFC 2822 寫 `-0000`（「時間是 UTC，但來源時區未知」）。

- feedparser 把它當 UTC，這是對的。
- Python 的 `email.utils.parsedate_to_datetime("… -0000")` 回傳 **naive datetime**，實跑得到
  `datetime(2026, 9, 18, 3, 54, 17)`、`tzinfo=None`。這是文件寫明的行為，要自己 `.replace(tzinfo=UTC)`。

### 3.4 `[Batch]`

見 §6。欄位裡沒有「合集」旗標：`trusted`、`remake`、分類都與合集無關。

### 3.5 從開發機連不上（實測）

2026-09-25 在開發機（Windows 11）重測，三個站同時連：

```text
curl https://nyaa.si/?page=rss&q=test     → curl: (35) schannel: next InitializeSecurityContext failed: SEC_E_INVALID_TOKEN (0x80090308)
python urllib（3.13）同一網址              → URLError: [SSL: WRONG_VERSION_NUMBER] wrong version number
curl https://mikanani.me/RSS/Classic       → 200
curl https://acg.rip/.xml                  → 200
```

- TLS 握手被中斷。錯誤型態是拿到了不是 TLS 的回應（`wrong version number`），
  像是網路路徑上的干擾，不是 Nyaa 拒絕服務（這是推論）。
- 使用者轉述的 fixture 取得過程：
  - Node 也是 `wrong version number`；
  - claude-in-chrome 擴充拒絕這個站；
  - 最後用 playwright 瀏覽器開 nyaa.si，在頁內 `fetch()` 取得原文。瀏覽器這條路走得通，所以問題在
    開發機上非瀏覽器的 TLS 連線，不在 Nyaa 本身。
- 對 Berth 的意義：
  - 部署環境若是同一條網路，Nyaa feed 與 Nyaa 的 `.torrent` 下載都會失敗。
  - magnet 模式（`&m`）可以省掉 `.torrent` 下載，`TorrentFetcher` 從 magnet 就拿得到 hash，但 feed 本身還是要連得上。
  - adapter 的錯誤訊息要把這種 TLS 失敗說成「連不上 nyaa.si」，不要說成「feed 格式錯」。

## 4. acg.rip

| 元素 | 內容 | 備註 |
| --- | --- | --- |
| `<guid>`（無屬性） | `https://acg.rip/t/<數字 id>` | 60/60 筆等於 `<link>` |
| `<link>` | 同上，單集頁 | |
| `<title>` | 發佈標題 | |
| `<description>` | 跳脫過的 HTML，常被截斷（結尾 `...`） | 沒用 |
| `<pubDate>` | RFC 822，帶時區 `-0700`（fixture 是太平洋夏令時間；冬天應為 `-0800`，這是推論） | |
| `<enclosure>` | `url=<link>.torrent`、`type="application/x-bittorrent"`，**沒有 `length`** | 60/60 筆 |
| `torrent:contentLength`（`xmlns:torrent="http://xmlns.ezrss.it/0.1/"`） | 位元組整數，看起來是捨到 KiB（1 筆對照：`floor(真實/1024)×1024`） | |
| `media:content`（`xmlns:media="http://search.yahoo.com/mrss/"`） | `url` 同 enclosure、`fileSize` 同 `contentLength` | 60/60 筆一致 |
| info hash / magnet / 做種數 | **無** | 單集頁 `https://acg.rip/t/363901` 也沒有 magnet 或 hash，只有 `/t/363901.torrent`（2026-09-25 查） |

- 兩份搜尋 fixture 都剛好 30 筆，推測 30 是上限；分頁參數沒有查。
- acg.rip 的原始碼不公開，以上全部來自 fixture 與單集頁。

範例（`acgrip/rss-search.kimi-ga-shinu.xml` 第三筆，排版後）：

```xml
<item>
  <title>[喵萌奶茶屋&amp;LoliHouse] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai - 12 [WebRip 1080p HEVC-10bit AAC][简繁日内封字幕]</title>
  <description>&lt;strong&gt;&lt;img src="…"&gt;…</description>
  <pubDate>Thu, 24 Sep 2026 01:08:02 -0700</pubDate>
  <link>https://acg.rip/t/363901</link>
  <guid>https://acg.rip/t/363901</guid>
  <enclosure url="https://acg.rip/t/363901.torrent" type="application/x-bittorrent"/>
  <torrent:contentLength>518645760</torrent:contentLength>
  <media:content url="https://acg.rip/t/363901.torrent" fileSize="518645760"/>
</item>
```

## 5. 時區對照

同一個發佈，喵萌奶茶屋&LoliHouse《与你相恋到生命尽头》：

```text
第 12 集
  Mikan   <torrent><pubDate> 2026-09-24T16:08:01.389          （無時區）
  acg.rip <pubDate>          Thu, 24 Sep 2026 01:08:02 -0700
          → UTC = 01:08:02 + 7:00 = 2026-09-24T08:08:02Z
  偏移 = 16:08:01.389 − 08:08:02 = +7:59:59.389 ≈ +8:00

第 11 集
  Mikan   2026-09-23T03:16:04.462
  acg.rip Tue, 22 Sep 2026 12:16:05 -0700 → 2026-09-22T19:16:05Z
  偏移 = +7:59:59.462 ≈ +8:00

第三個錨點（第 12 集的 torrent 本身）
  creation date = 1790237149 → 2026-09-24T08:05:49Z，早於兩站的發佈時間約 2 分鐘
```

兩站的秒數差不到 1 秒，應該是發佈工具（`rin-pr`）幾乎同時貼到兩站；Mikan 的值小數點後有數字，
acg.rip 捨到整秒。**Mikan 是 UTC+8**，與 brief §20.11 用另一筆（`2026-09-24T21:01:00.760219` 對 13:01 UTC）
得到的結論相同。

## 6. 合集

**三個來源都沒有表示合集的欄位**（元素清單見 §2.1、§3.1、§4），只能看標題，大小只能當旁證。
所以 `release_kind` 由解析器從標題判斷；fixture 裡這些寫法都要認得：

- `acgrip/rss-search.kamiina-botan.xml`，30 筆裡 8 筆：
  - `[❀拨雪寻春❀] … [01-12 精校合集][WebRip][HEVC-10bit 1080p][简繁日内封]`（4.52 GB）
  - `[喵萌奶茶屋&LoliHouse] … - [01-12 合集][WebRip 1080p HEVC-10bit AAC][简繁日内封字幕][Fin]`（5.79 GB）
  - `【喵萌奶茶屋】★04月新番★[… / Kamiina Botan, Yoeru Sugata wa Yuri no Hana][01-12][1080p][繁日雙語]`，
    另有 `[简日双语]` 一筆（這兩筆標題**沒有**「合集」字樣，只有 `[01-12]`）
  - `[千夏字幕組][…][第01-12話][1080p_AVC][繁體][合集]`，另有简体、HEVC 簡繁內封兩筆
  - `[LinRip] Kamiina Botan, … [Vol.1][BDRemux 1080p AVC FLAC]`（13.67 GB，BD 單卷，也是多集）
- `nyaa/rss-search.kamiina-botan.xml`，75 筆裡 14 筆，上面那幾種之外還有：
  - `[SubsPlease] … (01-12) (1080p) [Batch]`（另有 720p、480p）
  - `[NanakoRaws] … 01-12 (AT-X 1080p HEVC AAC)`、`… 01-10 (…)`（**只有集數範圍**，沒有任何合集字樣）
  - `[Judas] … (Season 01) [1080p][HEVC x265 10bit][Multi-Subs] (Batch)`
  - `[Trix] Botan Kamiina Fully Blossoms When Drunk S01 (Batch) [WEBRip 1080p AV1 Opus] …`
- `nyaa/rss-user.subsplease.kamiina-botan.xml`：39 筆裡 3 筆 `[Batch]`，其餘是單集。
- `mikan/rss-classic.xml` 也有：`[Prejudice-Studio] 尼古喵喵 Yani Neko [01-12][…]`、
  `…第01-12集…`、`[YYQ字幕组][…][01-12][…][合集]`、`… S01 | 01-13 […]`。
  Mikan 的 MyBangumi 與單一 feed 這次沒有夾到合集，但 Classic 證明 Mikan 本身收合集。

用簡單的正則掃時，`S03 - 13` 這種「季號 + 單集」會被誤認成範圍（Classic 裡的 `[NEST] 无职转生 第三季 … S03 - 13`），
解析器要分得開。

## 7. feedparser

### 7.1 版本與文件（context7 `/kurtmckee/feedparser`，2026-09-25）

- PyPI 最新是 **6.0.14**，2026-07-30 發佈，`requires_python >=3.10`（`https://pypi.org/pypi/feedparser/json`）。
  `uv run --with feedparser` 裝了 2 個套件：feedparser 與它依賴的 `sgmllib3k`。repo 是 Python 3.13。
- 命名空間（`docs/namespace-handling.rst`）：
  - 認得的命名空間用它的**慣用前綴**組 key，不管 feed 裡實際寫什麼前綴（`prism:issn` → `prism_issn`）。
  - 其他命名空間的元素是 `prefix` + `element`。
  - `namespaces` 是 `{prefix: URI}`；預設命名空間列在 `namespaces['']`。
- enclosure（`docs/uncommon-rss.rst`）：`entries[i].enclosures` 是 `{type, length, href}` 的 list。
  它不是真的 key：`keys()` 看不到它，是 `FeedParserDict` 從 `links` 裡 `rel="enclosure"` 的那幾筆推出來的。
- 日期（`docs/date-parsing.rst`）：所有日期都解析成 **UTC 的 9-tuple**。

### 7.2 原始碼補的兩點（feedparser 6.0.14，uv 快取裡的安裝檔）

- `parsers/strict.py` 的 `startElementNS`：
  - `prefix = self._matchnamespaces.get(lowernamespace, givenprefix)`，也就是不認得的命名空間用 feed 裡寫的前綴。
  - **沒有前綴的元素（預設命名空間）不加任何前綴**，直接用本地名。所以 Mikan 的
    `<torrent xmlns="https://mikanani.me/0.1/"><pubDate>` 被當成標準的 `pubdate`，走進 `_start_pubdate = _start_published`。
- `datetimes/w3dtf.py`：沒有時區時 `tzhour = timezonenames.get(parts[2], 0)`，也就是當 UTC。

### 7.3 key 對照（實跑 fixture 的結果）

| 來源 | XML | feedparser key | 值 / 注意 |
| --- | --- | --- | --- |
| 共通 | `<guid>` | `id`（`guidislink` 另給） | |
| 共通 | `<title>` | `title` | 已解開 `&amp;` |
| 共通 | `<link>` | `link`，也在 `links[0]` | |
| 共通 | `<description>` | `summary` | Mikan 的純文字被當 HTML，`&` 變回 `&amp;`；不要用 |
| Mikan | `<torrent>` | `torrent` | `''`（空字串） |
| Mikan | `<torrent><link>` | `links[1]`（第二個 `rel=alternate`，與 `links[0]` 同網址） | 命名空間被抹掉 |
| Mikan | `<torrent><contentLength>` | `contentlength` | 字串；不是位元組（§2.4） |
| Mikan | `<torrent><pubDate>` | `published` / `published_parsed` | **`published_parsed` 錯 8 小時**（當 UTC）；改用 `published` + `fromisoformat` + UTC+8 |
| Mikan | `<enclosure>` | `enclosures[0]` = `{type, length, href}`，也在 `links[2]`（`rel=enclosure`） | `length` 同 `contentlength` |
| Nyaa | `<pubDate>` | `published` / `published_parsed` | `-0000` → UTC，正確 |
| Nyaa | `nyaa:seeders` 等 | `nyaa_seeders`、`nyaa_leechers`、`nyaa_downloads`、`nyaa_infohash`、`nyaa_categoryid`、`nyaa_category`、`nyaa_size`、`nyaa_comments`、`nyaa_trusted`、`nyaa_remake` | 全小寫；前綴來自 feed 自己的 `xmlns:nyaa`（feedparser 不認得這個 URI），Nyaa 若換前綴 key 會跟著變 |
| Nyaa | （無 enclosure） | `enclosures` = `[]` | |
| Nyaa | channel | `namespaces` = `{'': 'http://www.w3.org/2005/Atom', 'nyaa': 'https://nyaa.si/xmlns/nyaa'}` | Atom 被認成預設 |
| acg.rip | `<pubDate>` | `published` / `published_parsed` | `-0700` → UTC，正確 |
| acg.rip | `<enclosure>` | `enclosures[0]` = `{type, href}`（沒有 `length`） | |
| acg.rip | `torrent:contentLength` | `torrent_contentlength` | ezrss 命名空間 feedparser 不認得，用 feed 的前綴 |
| acg.rip | `media:content` | `media_content` = `[{url, filesize}]` | 屬性名被轉小寫 |

七份 fixture 都是 `version = rss20`、`bozo = False`；每份 feed 裡所有 entry 的 key 集合都相同。

**判斷：可以直接用 feedparser**，前提是兩條規則，都要寫進票 08 的契約測試：

- Mikan 的時間只讀 `entry.published` 字串，自己補 UTC+8，不讀 `published_parsed`。
- Mikan 的 `link` 取 `entry.link`，不從 `links` 找。

Mikan 的命名空間被抹掉，**現在不會撞名**：item 層沒有標準的 `<pubDate>`，`<torrent><link>` 與 `<link>`
同值。哪天 Mikan 加上標準的 `<item><pubDate>`（RFC 822），`published` 就會被後出現的那個蓋掉。
到時 `fromisoformat` 讀 RFC 822 會丟 `ValueError`，錯得出聲，不會安靜地錯。
所以**不必**另用 `xml.etree` 讀那兩個欄位；真的要改，也是同一份位元組用
`ET.fromstring(...).iter('{https://mikanani.me/0.1/}pubDate')` 讀。

### 7.4 跑法與輸出摘要

腳本合併成一支，在 `scripts/experiments/rss_sources.py`：

```text
uv run --no-project --python 3.13 --with feedparser python scripts/experiments/rss_sources.py
```

`--no-project` 是為了不動 repo 的 `pyproject.toml` 與 `uv.lock`。輸出開頭是
`feedparser 6.0.14 python 3.13.14`，接著每份 fixture 印出 `version` / `bozo` / `namespaces` /
entry 數，以及第一個 entry 的全部 key 與值，§7.3 的表就是從這裡整理的。另外三支做 §2–§6 的交叉檢查：
bencode 算 info hash、124 筆 Mikan 的 hash / 大小 / 日期一致性、元素樹形狀、時區偏移、合集標題、日期函式。

## 8. 跨 feed 以 info_hash 去重：建議

**做，不多發請求。**

| 來源 | info hash 從哪來 | 輪詢時的成本 |
| --- | --- | --- |
| Mikan | `link` 末段（40 hex，§2.3） | 0 |
| Nyaa | `nyaa:infoHash`，轉小寫 | 0 |
| acg.rip | feed 與單集頁都沒有；要下載 `/t/<id>.torrent` 自己算 | 每筆 1 次 GET |

做法：

1. `FeedItem.info_hash` 可以是空的（`str | None`）。`rss_items.info_hash` 在知道時寫入。
2. 去重順序照票 10：同 Feed 的 guid → **info hash 已知時**比對 `rss_items.info_hash` 與 `jobs.hash` →
   帳本的「同 Media / 季 / 集 / Tags」。
3. **acg.rip 不在輪詢時預抓 `.torrent`。** 送單時 `berth/adapters/torrent.py` 的 `TorrentFetcher`
   本來就要下載 `.torrent` 算 hash（ACG.RIP 不報 hash 是票 09 寫它的理由之一），`jobs.hash` 是主鍵，
   同一個 hash 送兩次就是同一列（plan §3.3）。送單拿到 hash 之後寫回 `rss_items.info_hash`；
   若 Job 已經存在，這一筆標成重複。代價只是「會被排除的 acg.rip 項目」本來就不會抓，
   沒被排除的本來就要抓，所以沒有多出來的請求。
4. Mikan 的 URL hash 是推論（§2.3），送單時 `TorrentFetcher` 算出的真 hash 與它不同就記一筆事件，
   讓這個推論錯的時候看得見。

理由：

- 預抓 acg.rip 的 `.torrent` 會讓每輪輪詢多出 N 次請求，而且大部分是已經看過的 item。
- 送單路徑已經有同一個結果，而且 Job 主鍵已經保證不重複。

**沒有驗證的前提**：同一個字幕組貼到 Mikan 與 acg.rip 的是不是同一個 torrent（同一個 info hash）。
旁證有三個：

- 兩站時間差不到 1 秒；
- 大小對得上（acg.rip `518,645,760` = 真實大小捨到 KiB）；
- torrent 由發佈工具 `rin-pr` 產生。

直接證據要下載 `https://acg.rip/t/363901.torrent` 算 hash，這次沒做。就算不同，帳本那一層仍會擋下同集同 Tags 的第二份。

## 9. plan §8.5 的 FeedItem 各欄位從哪裡取（建議）

以 feedparser 的 entry `e` 表示：

| 欄位 | Mikan | Nyaa | acg.rip |
| --- | --- | --- | --- |
| `guid` | `e.link` 末段的 40 hex（**不用** `<guid>`，它是標題，§2.2） | `e.id`（`https://nyaa.si/view/<id>`） | `e.id`（`https://acg.rip/t/<id>`） |
| `title` | `e.title` | `e.title` | `e.title` |
| `link`（單集頁） | `e.link` | **`e.id`**（`e.link` 是下載連結） | `e.link` |
| `torrent_url` | `e.enclosures[0].href` | `e.link`，不以 `magnet:` 開頭時 | `e.enclosures[0].href` |
| `magnet` | 無（單集頁有，不需要） | `e.link`，以 `magnet:` 開頭時（`&m` / `&magnets` 或該筆沒有 torrent 檔） | 無 |
| `info_hash` | `e.link` 末段（小寫 40 hex） | `e.nyaa_infohash.lower()` | `None`（送單時由 `TorrentFetcher` 補） |
| `size`（近似位元組） | 描述後綴 `[N UNIT]` → `N × 1000^k`（**不用** `contentlength`，§2.4） | `e.nyaa_size` → `N × 1024^k`（`N Bytes` 另處理） | `int(e.torrent_contentlength)` |
| `published_at`（aware UTC） | `fromisoformat(e.published).replace(tzinfo=UTC+8)` 轉 UTC | `e.published_parsed`（UTC tuple），或 `parsedate_to_datetime` 後補 UTC | `e.published_parsed`，或 `parsedate_to_datetime(e.published)` |

不在 FeedItem 裡、但 fixture 有的：Nyaa 的 `nyaa_seeders` / `nyaa_leechers` / `nyaa_downloads` /
`nyaa_trusted` / `nyaa_remake` / `nyaa_categoryid`。Mikan 與 acg.rip 沒有做種數。

Mikan 的 RSS Series 鍵（番組 id, 字幕組 id）**不在 feed 裡**，只有單集頁有（§2.7）。
MyBangumi 聚合 feed 的每一筆第一次出現時，都要多抓一次單集頁；單一 feed 的 URL 本身就帶著兩個 id。

## 10. 2026-09-24 的五條實測，在 2026-09-25 fixture 上的佐證

1. **Mikan 聚合 feed（MyBangumi）只有最近的集數**：佐證。
   - `rss-mybangumi.xml` 共 12 筆，發佈時間 `2026-09-18T01:30:56.974082` → `2026-09-24T16:08:01.389`（UTC+8），
     跨 6.6 天、10 部作品（《与你相恋到生命尽头》第 11、12 兩集；《少女怪兽焦糖恋心》第 12 集有 LoliHouse 與 ANi 兩組）。
   - 番組 4009 × 字幕組 370 只剩第 11、12 集，同一時間的單一 feed 是 01–12。
   - 上限是依筆數（12？）還是依時間窗，一份樣本分不出來。
2. **單集頁反查得到番組 id 與字幕組 id**：佐證。`home-episode.85c93c23.html` 有三處（§2.7）；
   最直接的是第 166 行 `a.mikan-rss` 的 `/RSS/Bangumi?bangumiId=4009&subgroupid=370`。
3. **單一 feed 有整季**：佐證。
   - `rss-bangumi.4009-370.xml` 12 筆，標題 `- 01` 到 `- 12` 各一筆，時間 `2026-07-08T12:23:11.098` → `2026-09-24T16:08:01.389`。
   - 番組頁寫 `总集数：13`，第 13 集取得時還沒發佈。
   - 單一 feed 有沒有筆數上限（例如一季超過某個數字時）沒有量到；Classic 是 100 筆。
4. **acg.rip 搜尋 feed 夾合集**：佐證。`rss-search.kamiina-botan.xml` 30 筆裡 8 筆（§6）。
   Nyaa 的搜尋 feed 也一樣（75 筆裡 14 筆）。
5. **Nyaa 從開發機連不上**：2026-09-25 重現（§3.5）。curl 報 `SEC_E_INVALID_TOKEN`，
   Python 報 `WRONG_VERSION_NUMBER`，同時 Mikan 與 acg.rip 回 200。fixture 改用 playwright 瀏覽器在頁內 `fetch()` 取得。

## 11. 沒解的

- Mikan 改標題時 guid 會不會變（§2.2）：要同一筆改標題前後各抓一次。§9 的建議改用 hash，已經繞開這個問題。
- MyBangumi 的上限是筆數還是時間窗（§10-1）。
- 同一個發佈在 Mikan 與 acg.rip 是不是同一個 info hash（§8）：要下載 `https://acg.rip/t/363901.torrent`。
- Mikan GB 級大小的單位是不是十進位（§2.4）：要一個 GB 級的 torrent 對照。
- acg.rip 搜尋 feed 的 30 筆上限與分頁參數（§4）。
- Nyaa 從部署環境連不連得上：取決於使用者的網路，開發機這條不代表全部。

## 來源

- fixture：`tests/fixtures/http/mikan/`、`nyaa/`、`acgrip/`，原網址見 §1，2026-09-25 取得。
- Mikan 番組頁 `https://mikanani.me/Home/Bangumi/3990`、`https://mikanani.me/Home/Bangumi/3900`（2026-09-25，日期格式判定）。
- acg.rip 單集頁 `https://acg.rip/t/363901`（2026-09-25，沒有 magnet 與 info hash，大小顯示 `494.6 MB`）。
- Nyaa 原始碼（`https://github.com/nyaadevs/nyaa`，master，2026-09-25 讀）：
  - [`nyaa/templates/rss.xml`](https://github.com/nyaadevs/nyaa/blob/master/nyaa/templates/rss.xml)：欄位、magnet 模式的 `<link>`
  - [`nyaa/templates/xmlns.html`](https://github.com/nyaadevs/nyaa/blob/master/nyaa/templates/xmlns.html)：命名空間說明頁
  - [`nyaa/views/site.py`](https://github.com/nyaadevs/nyaa/blob/master/nyaa/views/site.py)：`/xmlns/nyaa` 路由
  - [`nyaa/views/main.py`](https://github.com/nyaadevs/nyaa/blob/master/nyaa/views/main.py)：`magnets` / `m` 參數、`u` / `user`、`render_rss`、`max-age=300`
  - [`nyaa/search.py`](https://github.com/nyaadevs/nyaa/blob/master/nyaa/search.py)：`DEFAULT_PER_PAGE = 75`、RSS 只取第一頁
  - [`config.example.py`](https://github.com/nyaadevs/nyaa/blob/master/config.example.py)：`RESULTS_PER_PAGE = 75`
  - [`nyaa/template_utils.py`](https://github.com/nyaadevs/nyaa/blob/master/nyaa/template_utils.py)：`rfc822` filter = `formatdate(date.timestamp())`
  - [`nyaa/models.py`](https://github.com/nyaadevs/nyaa/blob/master/nyaa/models.py)：`info_hash_as_hex`、`magnet_uri`
- Jinja [`src/jinja2/filters.py` `do_filesizeformat`](https://github.com/pallets/jinja/blob/main/src/jinja2/filters.py)（2026-09-25 讀）：`nyaa:size` 的格式。
- feedparser：
  - context7 `/kurtmckee/feedparser`（`docs/namespace-handling.rst`、`docs/uncommon-rss.rst`、`docs/date-parsing.rst`，2026-09-25）
  - PyPI `https://pypi.org/pypi/feedparser/json`（6.0.14，2026-07-30）
  - 6.0.14 安裝檔的 `parsers/strict.py`、`datetimes/w3dtf.py`、`mixin.py`
- Python：
  - [`email.utils.parsedate_to_datetime`](https://docs.python.org/3/library/email.utils.html#email.utils.parsedate_to_datetime)（`-0000` 回 naive）
  - [`email.utils.formatdate`](https://docs.python.org/3/library/email.utils.html#email.utils.formatdate)
  - [`datetime.fromisoformat`](https://docs.python.org/3/library/datetime.html#datetime.datetime.fromisoformat)
  - 行為都在 3.13.14 實跑確認。
- Berth：`berth/adapters/torrent.py`（送單時下載 `.torrent` 算 hash）、plan §2.3 / §2.4 / §3.3 / §8.5、brief §15、§20.11。
