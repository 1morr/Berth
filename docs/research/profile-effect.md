# Route profile 的作用（M1 票 14c / brief §6.4、§20.4）

2026-09-16。腳本是 `scripts/experiments/profile_effect.py`（不連線、不寫檔）。語料是
`tests/fixtures/parser/` 本身，這一票補了 5 筆（見 §3）。

> **2026-09-17 起這是紀錄**：Route profile 已在 M1 票 14e 從資料庫、API、介面與語料整個拿掉，腳本量的
> 東西不存在了，隨同一票刪除（要看它，`git show 7d5c245:scripts/experiments/profile_effect.py`）。
> §6.1.1 的 `absolute_rule_cost.py` 仍在。

## 0. 結論

**profile 有作用，而且只有一個作用：「只有集號、TMDB 上不只一季」時，絕對編號換算出來的答案
自動入庫（`anime`，medium）還是送審核（`standard`，low）。** 它不影響命名，也不影響其他任何
分支（§1）。原本 23 筆語料量不出差別，是因為那一段一次都沒走到；補上走得到的 5 筆之後：

| 組合 | auto_correct | auto_wrong | review | medium 誤判率 |
| --- | --- | --- | --- | --- |
| 原樣（動漫走 `anime`、其餘走 `standard`） | **169** | **0** | 65 | 0/86 |
| 每筆翻轉 | 141 | 1 | 92 | 1/59 |
| 全部 `standard` | 140 | 0 | 94 | 0/57 |
| 全部 `anime` | 170 | 1 | 63 | 1/88 |

八個桶與分類別的完整報表、逐筆語料的桶、逐檔差異在附錄 A。

兩個方向都量到了真的差別：

- **動漫上 `anime` 有用**：三筆長壽 / 多季作品的絕對編號（29 個檔案）在 `anime` 下全部自動入庫而且對，
  `standard` 下全部送審核。
- **非動漫上 `standard` 擋下了一個真的錯**：《Home and Away》第 8214 集換算成 S37E32，正解是
  S37E39（§3.4）。`anime` 下它會被自動入庫到錯的那一集。

但「是不是動漫」**不是**換算會不會對的好預測：

- 同樣是非動漫，韓綜《超人回來了》E079 的換算是對的（§3.5），`standard` 把一個對的答案擋進了審核。
- 同樣是動漫，語料外的 Erai-raws《死神 千年血戰篇 相剋譚》01–14 每 cour 重數、檔名沒有季號，
  `anime` 下 14 個檔案全部自動入庫到 S01E01–14，正解是 S02E27–40（§4）。這是解析器缺陷，不進語料。

換算對不對，真正取決於「發佈的編號與 TMDB 的集數是不是同一套數法」——TMDB 的集數與官方編號
對不齊、字幕組每 cour 重數，都會讓它錯，與作品類型只是相關。

**決定（2026-09-16 使用者拍板）：移除 profile，改由兩條證據決定換算的信心**（§6）。M1 票 14d 的實作
在補了兩筆之後的 30 筆語料上量到 170 對 / 0 錯，《死神》相剋譚 14 檔送審核；欄位本身在 14e 拿掉。
規則 1（集號 ≤ 第一季集數）的代價也量了：在票 01 的真實發佈上，它擋下的檔案 85% 其實是第一季的正解，
而「標題有認不出的多餘字」分不開兩者，所以維持原形（§6.1.1，2026-09-17 使用者拍板）。

## 1. profile 被讀的地方

2026-09-15 查證（票 14a 之後的對話），`berth/` 裡讀 `Profile` 的只有三處：

| 位置 | 作用 | 這份量測量得到嗎 |
| --- | --- | --- |
| `parser/mapping.py` `_from_number` | 只有集號、TMDB 上不只一季時，`absolute_group` / `absolute_cumulative` 的信心：`anime` medium、`standard` low 並附理由 | **量得到**，本文件的主題 |
| `services/search.py` `search_titles` | `anime` 對最新一季（≥2）多問 `<英文標題> Season N` / `<標題> 第N季` | 量不到：要打真的索引站，替身量不出來（票面「不做」） |
| `services/routes.py` `_check_profile` | 電影媒體庫的 Route 不收 `anime`（`profile_unsupported`） | 不是解析行為 |

`berth/naming/` 沒有任何一處讀它：brief §7.1 的劇集與動漫是同一套模板。介面上叫它「命名 profile」
是名不副實的。

## 2. 方法

### 2.1 四種組合

腳本讀 `bench.load_corpus`，以 `dataclasses.replace(fixture, profile=…)` 產出四種組合：原樣、
每筆翻轉、全部 `standard`、全部 `anime`。計數用 `bench.score` / `bench._add` / `bench.render`，
與 `berth bench` 同一支；逐檔再跑一次 `plan` 取 `bench.bucket`，與原樣比差異。

### 2.2 側錄 `_from_number`

`mock.patch.object(mapping, "_from_number", spy)`：照常回傳，順手記下集號、回傳的策略與排第一的
候選。`_from_number` 只有兩個分支，而兩個分支產的策略不重疊——`single_season` 分支只回
`single_season`，絕對編號分支只回 `absolute_group` / `absolute_cumulative`（或什麼都沒換算出來時的
空的）——所以由回傳值就判得出走了哪一支。四種組合的側錄**逐筆相同**（腳本會印 `identical across
the four variants: yes`）：profile 不改變走哪一支，只改變信心。

### 2.3 判對錯的錨點

`expected` 寫的是正解，不是目前的行為（`tests/fixtures/parser/README.md`）。絕對編號的正解靠
**發佈以外的證據**決定：TMDB 快照裡那一集的播出日與集名，對上發佈檔名裡的日期、其他發佈組標的
季集，或官方的集數。每一筆怎麼判的寫在 §3。

## 3. 新語料與命中的分支

條件是票面兩類：**只有集號、TMDB 上 ≥2 個正規季**，而且側錄證明真的走到絕對編號分支。
每一部都先查過快照的正規季數才挑（TMDB 合併季很激進，brief §20.3）。

| 語料 | 類型 | TMDB 正規季 | 呼叫 | 分支 | 策略 | 排第一的候選 | 正解 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `anime/spy-x-family-s2-subsplease-batch` | 動漫 | 3（25 / 12 / 13） | 12 | absolute ×12 | group、cumulative | #26→S02E01 … #37→S02E12 | 同左 |
| `anime/my-hero-academia-139-subsplease` | 動漫 | 8 | 1 | absolute ×1 | group、cumulative | #139→S07E01 | 同左 |
| `anime/one-piece-1089-1104-erai` | 動漫 | 23 | 18 | absolute ×18 | group、cumulative | #1089→S22E1089 … #1104→S22E1104 | 16 集同左；2 支特別篇 unmatched |
| `tv/home-and-away-8214-bill` | 澳洲肥皂劇 | 39 | 1 | absolute ×1 | cumulative | #8214→**S37E32** | **S37E39** |
| `tv/return-of-superman-e079-limo` | 韓國綜藝 | 14（按年份） | 1 | absolute ×1 | cumulative | #79→S03E21 | 同左 |

原本 23 筆的 34 次呼叫全部是 `single_season`（`kamiina-botan` 12、`true-beauty` 16、`pokemon` 2、
`rezero`、`mizuiro`、`gto`、`kamen-rider` 各 1），與票面的記載一致。

### 3.1 SPY×FAMILY (26-37)

[nyaa 2059571](https://nyaa.si/view/2059571)，SubsPlease 的第二季合集，檔名 `Spy x Family - 26v2`。
SubsPlease 第一季是 01–25，第二季接著數。TMDB 第一季 25 集、第二季 12 集，快照的 absolute group
把 #26 放在 S02E01（`FOLLOW MAMA AND PAPA`，2023-10-07）——group 與累加兩種換算一致，12 集
正好是整個第二季。

### 3.2 我的英雄學院 139

[nyaa 1814011](https://nyaa.si/view/1814011)，SubsPlease 單集。TMDB 八季，前六季 13 + 25×5 = 138 集，
S07E01 是 `In the Nick of Time! A Big-Time Maverick from the West`（2024-05-04）。同一集在 AnimeTosho
上另有 `[EMBER] Boku no Hero Academia S07E01 [EP: 139]`，兩個獨立來源一致。

### 3.3 航海王 1089 ~ 1104

[nyaa 1818402](https://nyaa.si/view/1818402)，Erai-raws 合集，18 個檔案。**TMDB 的第 22 季（Egghead）
沿用官方集數當 `episode_number`**：S22 的集號是 1089–1155，不是 1–67。所以兩種換算在這一筆分歧：

- `absolute_group` → S22E1089（對，而且排第一，planner 採用它）。
- `absolute_cumulative` → S22E01（錯：累加的前提是每季從 1 數起）。

16 集的集名與播出日逐集對得上快照（1089 `Entering a New Chapter! Luffy and Sabo's Paths!`
2024-01-07 … 1104 `A Desperate Situation! The Seraphim's All-out Attack!` 2024-05-12）。

另外兩個檔案是特別篇 `Dai Tannou Kikaku - Shi no Gekai - Trafalgar Law` 與 `Innen no Log - Mugiwara
no Ichimi to Cipher Pol`，TMDB 是 S00E28 與 S00E29，但只有集名說得出來——照語料 README 的判準
（brief §7.6，對不到且像正片）寫成 `unmatched`。解析器目前把它們送審核（合集的集號區間被套上去、
換算不出區間尾巴而降到 low），不會自動做錯事。

### 3.4 Home and Away Episode 8214

[TPB 74753319](https://thepiratebay.org/description.php?id=74753319)。索引站標題原樣就截斷在
`…WEB-DL.H`。TMDB 把它按年份分成 39 季，**快照裡 S37E39 的集名就是 `Episode 8214`、播出日
2024-02-29**，與檔名的日期一致。累加換算得到 S37E32，差 7 集：TMDB 前 36 季的集數加起來是 8,182，
比官方編號多 7 集（S37E01 的集名是 `Episode 8176`），而累加只看集數。多出來的 7 集散在哪幾季
沒有追——快照裡集名與累加序位對不上的地方不只一處，其中有的是 TMDB 集名自己的筆誤。

這是票面要的反例：`standard` 送審核，`anime` 會把它自動入庫成另一集。

### 3.5 The Return of Superman E079

[TPB 11971639](https://thepiratebay.org/description.php?id=11971639)，正是 brief §20.4 說的韓國電視台
`Show.E079.YYMMDD` 無季寫法。TMDB 按年份分 14 季；累加 9 + 49 = 58，#79 是 S03E21，快照的集名
`79. Grow Up Slowly`、播出日 2015-05-24，與檔名的 `150524` 一致——**換算是對的**，`standard` 把它
擋進了審核。檔案清單取自 itorrents 以 infohash 抓回的 `.torrent`，檔名與大小和 TPB 的清單一致。

## 4. 語料外：死神 千年血戰篇 相剋譚 01 ~ 14

[nyaa 1950688](https://nyaa.si/view/1950688)，`[Erai-raws] Bleach: Sennen Kessen Hen - Soukoku Tan - 01 ~ 14
[1080p DSNP WEB-DL AVC AAC][MultiSub] [BATCH]`（torrent：AnimeTosho
`3592ff8c8e4873cfcce58f1391d11694d2120c43`）。以同一套側錄對它跑 `plan`：

| profile | 分支 | 排第一的候選 | 桶（相對正解） |
| --- | --- | --- | --- |
| `standard` | absolute ×14 | #1→S01E01 … #14→S01E14 | review 14 |
| `anime` | absolute ×14 | #1→S01E01 … #14→S01E14 | **auto_wrong 14** |

正解是 **S02E27–E40**：TMDB 把 Bleach 分成兩季（366 集 / 千年血戰 50 集），S02E27 `A` 播於
2024-10-05、S02E40 `MY LAST WORDS` 播於 2024-12-29，正是相剋譚的首尾兩集。

錯的原因不是絕對編號：Erai-raws 每個 cour 從 01 重數，而篇章名只寫了羅馬字 `Sennen Kessen Hen`，
TMDB 的季名是 `Thousand-Year Blood War` / `千年血戰篇` / `千年血战篇`，篇章名比對（plan §4.4）
對不上，於是掉進「只有集號」那一支，被當成絕對編號。

**票 14c 沒有收它進語料**：以動漫 Route 的 `anime` 收錄會讓 baseline 的 `auto_wrong` 從 0 變 14，
票面規定那代表找到解析器缺陷、另開票修，不在那一票改解析器。後續票見 §6。

**M1 票 14d 收進了語料**（`anime/bleach-tybw-soukoku-tan-erai`，快照 `tv-30984`，檔案清單與 AnimeTosho 的
`.torrent` 逐位元組核對過）：改解析器之前的 `berth bench` 是 `auto_wrong 14`，改完是 `review 14`。
上表從此可以用 `profile_effect.py` 重跑——但那時 profile 已經沒有讀者，四欄都是 `review 14`（§6.1）。

## 5. 找過但不算數的候選

- **韓劇的第二季以後、檔名沒有季號**（票面的首選）：《模範計程車 2》《浪漫醫生金師傅 2 / 3》
  《Penthouse 2》《機智醫生生活 2》《驅魔麵館 2》。在 TPB（apibay）、Knaben（聚合 TPB、RuTracker 等）
  與 dmhy 上找到的發佈全部帶 `S02E` / `S03E`，或者根本沒有；`Show.2.E01.YYMMDD-NEXT` 這種寫法在這三處
  都沒找到。nyaa 在這台機器上連不上（TLS 被擋），沒有查。
  以同樣形狀的名字試解析器，`Taxi.Driver.2.E01.230217…` 會讀成沒有季號、集號 1——**找得到的話
  它會是比《Home and Away》更典型的反例**（累加換算成 S01E01，正解 S02E01）。
- **《半澤直樹》第二季**（日劇，TMDB 兩季各 10 集）：MagicStar 的包檔名是 `Hanzawa Naoki Season 2 EP01`，
  DBD-Raws 的是 `[半泽直树2][01]`，兩者都被讀成第 2 季，走的是有季號提示的分支，不算數。
- **鄰居們（Neighbours）**：TPB 上的發佈多半是 `Neighbours.2014.11.14` 日期制，沒有集號；
  有集號的 `Neighbours 5876-5880` 是 2011 年的舊包，沒有採用。
- **Running Man、Knowing Bros、I Live Alone**：TMDB 只有一季，走 `single_season`。

## 6. 決定

2026-09-16 使用者拍板：**移除 profile**，想要的是「盡可能簡單，而且自動用對的方法」。§0 的數字
說明 route 層級與作品層級的「是不是動漫」都預測不了換算對錯，所以改看發佈與 TMDB 自己給的證據。

### 6.1 換算的信心：兩條證據

「只有集號、TMDB 上不只一季」時照舊做 `absolute_group` / `absolute_cumulative` 兩種換算，每個候選
預設 medium（會自動入庫），遇到下面任一條就降到 low 送審核：

1. **集號 ≤ 第一個正規季的集數。** 這個數字同時讀得成「第一季的第 N 集」與「後面某一季從 01 重數的
   第 N 集」，檔名裡沒有東西分得出來——《死神》相剋譚 01–14 就是後者。超過第一季集數的數字只剩
   跨季連號一種讀法（SPY×FAMILY 26、MHA 139、航海王 1089）。
2. **檔名帶播出日，而換算出的那一集在 TMDB 上不是那一天播的。** 日期是發佈明說的（「明說的贏推論的」，
   brief §6.4），對不上就表示換算錯了。《Home and Away》`2024-02-29` 對到的 S37E32 播於 2024-02-21；
   《超人回來了》`150524` 對到的 S03E21 正好播於 2015-05-24。`guessit` 要加 `date_year_first`，
   否則韓國電視台的 `150524` 會被讀成 2024-05-15（實測）。**沒有容忍範圍**：日播的劇差一集就是差一天，
   容忍一天等於放過差一集的換算；TMDB 沒有那一集的播出日也算對不上（沒有東西證實它）。

M1 票 14d 的實作（`mapping._doubts`）以 `berth bench` 量。票 14c 的 28 筆加上這一票的兩筆
（`anime/bleach-tybw-soukoku-tan-erai`、`anime/spy-x-family-05-subsplease`）共 30 筆：

| | 語料 | auto_correct | auto_wrong | review | medium 誤判率 |
| --- | --- | --- | --- | --- | --- |
| 原樣 profile（票 14c 收尾） | 28 筆 | 169 | 0 | 65 | 0/86 |
| 原樣 profile，加上兩筆新語料（紅燈） | 30 筆 | 170 | **14** | 65 | 14/101 |
| 兩條證據、不讀 profile | 30 筆 | **170** | **0** | 79 | 0/87 |

走到絕對編號換算的 7 筆逐筆（`profile_effect.py` 的最後一張表，四種 profile 組合完全相同）：

| 語料 | 桶 | 由哪一條 |
| --- | --- | --- |
| `anime/bleach-tybw-soukoku-tan-erai` | review 14 | 規則 1（#1–14 ≤ 第一季 366 集） |
| `anime/spy-x-family-05-subsplease` | review 1 | 規則 1（#5 ≤ 第一季 25 集）——這就是代價 |
| `tv/home-and-away-8214-bill` | review 1 | 規則 2（2024-02-29 對 S37E32 的 2024-02-21） |
| `tv/return-of-superman-e079-limo` | auto_correct 1 | 兩條都沒觸發 |
| `anime/spy-x-family-s2-subsplease-batch` | auto_correct 12 | 兩條都沒觸發 |
| `anime/my-hero-academia-139-subsplease` | auto_correct 1 | 兩條都沒觸發 |
| `anime/one-piece-1089-1104-erai` | auto_correct 16、review 2 | 兩支特別篇照舊（§3.3） |

**代價**：多季作品的第一季、檔名沒有季號的發佈（實例：2022 年的 `[SubsPlease] Spy x Family - 05`，
[nyaa 1525282](https://nyaa.si/view/1525282)）由第 1 條送審核。它在原本的 `anime` Route 上會自動入庫，
在 `standard` Route 上本來就是審核。代價有多大、能不能收窄，見 §6.1.1。

#### 6.1.1 規則 1 的代價（M1 票 14d 第 1 步，2026-09-17）

腳本是 [`scripts/experiments/absolute_rule_cost.py`](../../scripts/experiments/absolute_rule_cost.py)
（`uv run --env-file .env python scripts/experiments/absolute_rule_cost.py`，讀票 01 的快取，只印 stdout）。

**樣本**：票 01（[`anime-episode-source.md`](anime-episode-source.md)）10 部裡 TMDB 上有 ≥ 2 個正規季的 5 部——
SPY×FAMILY（25 / 12 / 13）、無職轉生（23 / 24 / 14）、鬼滅之刃（26 / 7 / 11 / 11 / 8）、進擊的巨人
（25 / 12 / 22 / 28）、航海王（23 季，第一季 61 集）。另外 5 部 TMDB 只有一季，走 `single_season`，
規則 1 碰不到（腳本照票 01 的資料再數一次，對不上就停）。票 01 的 TMDB 資料是 2026-09-09 抓的，
與 repo 快照（`tv-120089`、`tv-94664`、`tv-85937`、`tv-1429`、`tv-37854`）**逐季的集號 5 部都一致**。

**正解**：票 01 §4.1 的校準——發佈時間錨定到正篇第幾集、每個（輪次, 字幕組）取眾數偏移量——得到的
正篇序位，再照同一份研究 §4.4 以播出日對到 TMDB 的季集。`Trial` 原本沒存 Mikan 的標題，這一票讓
`collect()` 把標題帶出來（`--self-test` 照過，全跑的 7,833 筆與三欄失敗數與票 01 相同）。

**Berth 怎麼讀**：每筆發佈當成「以標題為檔名（加 `.mkv`）的單檔 torrent」丟進 `plan`，側錄 `map_episode`。
合集逐集展開：一整包 Berth 只換算區間的頭，所以每一集另外問一次 `map_episode`（集號換成那一集）。
5 部共 3,765 個檔案，逐格：

| 作品 | 其他分支 | 沒有候選 | 集號讀得不同 | A | B | 超過第一季、換算對 | 超過第一季、換算錯 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SPY×FAMILY | 232 | 0 | 13 | 364 | 0 | 0 | 0 |
| 無職轉生 | 504 | 1 | 0 | 323 | 5 | 0 | 0 |
| 鬼滅之刃 | 372 | 51 | 0 | 241 | 42 | 0 | 0 |
| 進擊的巨人 | 224 | 0 | 0 | 0 | 120 | 40 | 0 |
| 航海王 | 0 | 0 | 0 | 0 | 0 | 1,179 | 54 |
| **合計** | 1,332 | 52 | 13 | **928** | **167** | **1,219** | **54** |

「其他分支」是有季號、篇章名或 cour 標記的（規則 1 管不到）；「集號讀得不同」是票 01 的標題解析與
Berth 讀到的集號對不起來（例如 `[20] [1080p] [2022年10月番]` 被 Berth 讀成 20–10），這一集的正解
對不到 Berth 的哪一次換算，不計。

- **規則 1 擋下的，對的遠多於錯的**：A（正解在第一季）928 個、B（正解在後面某季）167 個。B 是
  《鍛刀村篇》《進擊的巨人 2 / 3》這種每 cour 重數、篇章名或季號沒被讀出來的發佈。
- **超過第一季集數那一側不需要另一條規則**：1,219 對、54 錯，54 個錯的**全部**是票 01 §4.4 說的「播出日
  對不上、退回序位」的正解（航海王 Skytree / 猪猪字幕组的 749–932，都差一集，例如 #932 → S21E932 對「正解」
  S21E931），正解本身存疑；播出日對得上的 1,219 個全對。

**收窄規則 R**：「集號 ≤ 第一季集數**而且**標題有認不出的多餘字」。多餘字的定義寫在腳本的
`extra_words`：Berth 的 `ReleaseInfo.title_candidates`（guessit 認出的標題）裡，有任何一個以
`normalize_title` 正規化之後不是這部作品的已知名字，**或者一個候選都沒有**（認不出標題就說不出「沒有
多餘字」）。已知名字的範圍量了兩種：

| 已知名字 | A 放行 | A 留在審核 | B 漏掉（自動入錯） | B 擋下 |
| --- | --- | --- | --- | --- |
| 三個主標題 + 快照的 `titles`（別名與翻譯） | 793 | 135 | **14** | 153 |
| 只有三個主標題（`title`、`title_en`、`title_original`） | 328 | 600 | **0** | 167 |

- **連 `titles` 一起比，漏 14 個**：
  - 9 個 `【推しの子】 鬼灭之刃 锻刀村篇 / Kimetsu no Yaiba: Katanakaji no Sato-hen - 01`–`09`：這個標題**本身就是**
    TMDB 的別名。`titles` 混著單季的名字（`Mushoku Tensei S3`、`Kimetsu no Yaiba: Yuukaku-hen`），標題等於
    它們不代表沒有多餘字。
  - 5 個 `[桜都字幕组] 无职转生～到了异世界就拿出真本事～ S2 / Mushoku Tensei S2 [02]`：Berth 在**季號等於方括號
    集號**時把季號丟掉（`release._numbers` 為 `The_Final_Season[28]` 寫的那一條），guessit 的標題只剩
    `Mushoku Tensei`。M1 票 14f 已修（判準改成 `Season` 緊接著方括號），這 5 個之後讀得出季號，表裡的數字是修之前量的。
- **只比三個主標題，漏 0 個——但這個 0 靠運氣**：上面那 5 個是因為 TMDB 英文標題是
  `Mushoku Tensei: Jobless Reincarnation`、比羅馬字長才被擋下。同一個字幕組的同一種寫法換成 TMDB 英文標題
  就是 `SPY x FAMILY` 的作品——腳本最後的 probe，`[桜都字幕组] 间谍过家家 S2 / Spy x Family S2 [02]`（照樣造的，
  不是真實發佈）——季號被丟掉、標題候選 `Spy x Family` 等於主標題，R 放行，換算成 S01E02，正解 S02E02。

**判準與決定**：票面判準是「R 在 B 裡一筆都沒漏、而且 A 裡放行的不是零才採用 R；漏掉任何一筆就維持
原規則 1」，「只漏極少數卻放行大量 A」要問使用者。兩種範圍一個漏 14、一個的 0 靠 TMDB 標題的長短，
**2026-09-17 使用者拍板維持原規則 1**：集號 ≤ 第一季集數一律送審核。`Spy x Family - 05` 因此在語料裡是 review。

**這個近似的限制**：

- Mikan 只給發佈標題，沒有檔案清單。真實 torrent 的檔名與索引站標題常常不同（《死神》相剋譚的標題是
  `Bleach: Sennen Kessen Hen`、檔名是 `Bleach - Sennen Kessen Hen`），合集逐集重問也看不到真正的逐檔檔名。
- 樣本是 Mikan 的中文字幕組為主，SubsPlease / Erai-raws 這種 guessit 讀得出標題的西方格式很少；在 nyaa 上
  R 放行的比例會不一樣。5 部都是動漫，非動漫沒有量。
- 正解只涵蓋票 01 校準得過的（輪次, 字幕組）——票 01 捨棄了 9,392 集（§4.4），補檔與 BD 合集大多不在裡面。
- 「沒有候選」「集號讀得不同」兩格（65 個）不計入 A / B。票 01 對不出 TMDB 座標的（`no_source`）另有一格，
  這 5 部是 0 個，所以 A / B 與對錯裡每一個都有具體的正解。

### 6.2 其他兩個讀 profile 的地方

- 搜尋的季號變體：**對所有劇集都做**（最新一季 ≥ 2 就多問 `Season N` / `第N季`），不再只給動漫。沒有量。
- 電影媒體庫不收 `anime`：欄位不在了，這條規則跟著消失。

### 6.3 後續票

- **M1 票 14d**（2026-09-17 完成）：第 1 條的代價量了、收窄不成立（§6.1.1）；解析器改用兩條證據，不再讀
  profile；《死神》相剋譚與 `Spy x Family - 05` 進語料。
- **M1 票 14e**：把 profile 從資料庫、API、精靈與設定頁、搜尋、語料與文件裡整個拿掉。這支腳本量的
  東西從此不存在，跟著刪；本文件留著當紀錄。

## 7. 已知限制

- 樣本小：走得到那一段的語料 5 筆，其中非動漫 2 筆、各只有 1 個影片。數字是「有沒有差、往哪個
  方向差」的證據，不是誤判率的估計。
- 搜尋的季號變體（§1 第二列）沒有量。
- 快照會隨 TMDB 變。《Home and Away》的錯位來自 TMDB 前幾季的集數與官方編號不一致，哪天被修正，
  §3.4 就會變成換算正確——重錄快照之後要重跑這支腳本。

## 附錄 A：四種組合的完整報表與逐檔差異

`uv run python scripts/experiments/profile_effect.py` 的輸出原樣（2026-09-16，28 筆語料）。

### A.1 原樣

```
28 fixtures, 368 files

category  files  classify  tags     confidence  auto_correct  auto_wrong  review  missed  unmatched_correct  extra_correct  subtitle_correct  skipped
anime     206    206/206   111/111  111/111     111           0           2       0       42                 24             26                1      
tv        79     79/79     57/57    55/55       55            0           2       0       0                  0              11                11     
movie     83     83/83     3/3      3/3         3             0           61      0       0                  17             0                 2      
overall   368    368/368   171/171  169/169     169           0           65      0       42                 41             37                14     

high: 0/83 wrong (0.0%)  medium: 0/86 wrong (0.0%)
```

### A.2 每筆翻轉

```
28 fixtures, 368 files

category  files  classify  tags     confidence  auto_correct  auto_wrong  review  missed  unmatched_correct  extra_correct  subtitle_correct  skipped
anime     206    206/206   111/111  82/111      82            0           31      0       42                 24             26                1      
tv        79     79/79     57/57    55/55       56            1           0       0       0                  0              11                11     
movie     83     83/83     3/3      3/3         3             0           61      0       0                  17             0                 2      
overall   368    368/368   171/171  140/169     141           1           92      0       42                 41             37                14     

high: 0/83 wrong (0.0%)  medium: 1/59 wrong (1.7%)
```

### A.3 全部 `standard`

```
28 fixtures, 368 files

category  files  classify  tags     confidence  auto_correct  auto_wrong  review  missed  unmatched_correct  extra_correct  subtitle_correct  skipped
anime     206    206/206   111/111  82/111      82            0           31      0       42                 24             26                1      
tv        79     79/79     57/57    55/55       55            0           2       0       0                  0              11                11     
movie     83     83/83     3/3      3/3         3             0           61      0       0                  17             0                 2      
overall   368    368/368   171/171  140/169     140           0           94      0       42                 41             37                14     

high: 0/83 wrong (0.0%)  medium: 0/57 wrong (0.0%)
```

### A.4 全部 `anime`

```
28 fixtures, 368 files

category  files  classify  tags     confidence  auto_correct  auto_wrong  review  missed  unmatched_correct  extra_correct  subtitle_correct  skipped
anime     206    206/206   111/111  111/111     111           0           2       0       42                 24             26                1      
tv        79     79/79     57/57    55/55       56            1           0       0       0                  0              11                11     
movie     83     83/83     3/3      3/3         3             0           61      0       0                  17             0                 2      
overall   368    368/368   171/171  169/169     170           1           63      0       42                 41             37                14     

high: 0/83 wrong (0.0%)  medium: 1/88 wrong (1.1%)
```

### A.5 走到絕對編號分支的語料，四種組合下的桶

| fixture | original | flipped | all-standard | all-anime |
| --- | --- | --- | --- | --- |
| `anime/my-hero-academia-139-subsplease` | auto_correct 1 | review 1 | review 1 | auto_correct 1 |
| `anime/one-piece-1089-1104-erai` | auto_correct 16, review 2 | review 18 | review 18 | auto_correct 16, review 2 |
| `anime/spy-x-family-s2-subsplease-batch` | auto_correct 12 | review 12 | review 12 | auto_correct 12 |
| `tv/home-and-away-8214-bill` | review 1, skipped 2 | auto_wrong 1, skipped 2 | review 1, skipped 2 | auto_wrong 1, skipped 2 |
| `tv/return-of-superman-e079-limo` | review 1 | auto_correct 1 | review 1 | auto_correct 1 |

### A.6 逐檔差異（相對於原樣）

其餘 23 筆語料在四種組合下逐檔相同。

<details><summary>逐檔清單（翻轉 31、全 standard 29、全 anime 2）</summary>

#### flipped: 31 file(s) changed

- `anime/my-hero-academia-139-subsplease` `[SubsPlease] Boku no Hero Academia - 139 (1080p) [5AA223A9].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1089 [1080p][Multiple Subtitle][BAF171ED].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1090 [1080p][Multiple Subtitle][736F400E].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1091 [1080p][Multiple Subtitle][BF370DDD].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1092 [1080p][Multiple Subtitle][27DAD42F].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1093 [1080p][Multiple Subtitle][22EF03CF].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1094 [1080p][Multiple Subtitle][26FC3E50].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1095 [1080p][Multiple Subtitle][BD701926].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1096 [1080p][Multiple Subtitle][E3728AC4].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1097 [1080p][Multiple Subtitle][D125E619].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1098 [1080p][Multiple Subtitle][704DD598].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1099 [1080p][Multiple Subtitle][34B0C384].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1100 [1080p][Multiple Subtitle][17460F25].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1101 [1080p][Multiple Subtitle][47FFCEDD].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1102 [1080p][Multiple Subtitle][E6689334].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1103 [1080p][Multiple Subtitle][4D8C331D].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1104 [1080p][Multiple Subtitle][36B2B221].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 26v2 (1080p) [29DDC85B].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 27v2 (1080p) [BE27DD09].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 28v2 (1080p) [3E12608C].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 29v2 (1080p) [2D79EE6B].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 30v2 (1080p) [B4AC037B].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 31v2 (1080p) [1AD28FA2].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 32v2 (1080p) [1FCD523A].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 33v2 (1080p) [2354E9BC].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 34v2 (1080p) [BEC338D2].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 35v2 (1080p) [511970E3].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 36v2 (1080p) [484C504A].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 37v2 (1080p) [5D0BA3FC].mkv`: auto_correct -> review
- `tv/home-and-away-8214-bill` `Home.and.Away.Episode.8214.2024-02-29.Thu.720p.WEB-DL.H.264-bill.mkv`: review -> auto_wrong
- `tv/return-of-superman-e079-limo` `The.Return.of.Superman.E079.150524.HDTV.H264.720p-LIMO.avi`: review -> auto_correct

#### all-standard: 29 file(s) changed

- `anime/my-hero-academia-139-subsplease` `[SubsPlease] Boku no Hero Academia - 139 (1080p) [5AA223A9].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1089 [1080p][Multiple Subtitle][BAF171ED].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1090 [1080p][Multiple Subtitle][736F400E].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1091 [1080p][Multiple Subtitle][BF370DDD].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1092 [1080p][Multiple Subtitle][27DAD42F].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1093 [1080p][Multiple Subtitle][22EF03CF].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1094 [1080p][Multiple Subtitle][26FC3E50].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1095 [1080p][Multiple Subtitle][BD701926].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1096 [1080p][Multiple Subtitle][E3728AC4].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1097 [1080p][Multiple Subtitle][D125E619].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1098 [1080p][Multiple Subtitle][704DD598].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1099 [1080p][Multiple Subtitle][34B0C384].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1100 [1080p][Multiple Subtitle][17460F25].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1101 [1080p][Multiple Subtitle][47FFCEDD].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1102 [1080p][Multiple Subtitle][E6689334].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1103 [1080p][Multiple Subtitle][4D8C331D].mkv`: auto_correct -> review
- `anime/one-piece-1089-1104-erai` `[Erai-raws] One Piece - 1104 [1080p][Multiple Subtitle][36B2B221].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 26v2 (1080p) [29DDC85B].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 27v2 (1080p) [BE27DD09].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 28v2 (1080p) [3E12608C].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 29v2 (1080p) [2D79EE6B].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 30v2 (1080p) [B4AC037B].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 31v2 (1080p) [1AD28FA2].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 32v2 (1080p) [1FCD523A].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 33v2 (1080p) [2354E9BC].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 34v2 (1080p) [BEC338D2].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 35v2 (1080p) [511970E3].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 36v2 (1080p) [484C504A].mkv`: auto_correct -> review
- `anime/spy-x-family-s2-subsplease-batch` `[SubsPlease] Spy x Family - 37v2 (1080p) [5D0BA3FC].mkv`: auto_correct -> review

#### all-anime: 2 file(s) changed

- `tv/home-and-away-8214-bill` `Home.and.Away.Episode.8214.2024-02-29.Thu.720p.WEB-DL.H.264-bill.mkv`: review -> auto_wrong
- `tv/return-of-superman-e079-limo` `The.Return.of.Superman.E079.150524.HDTV.H264.720p-LIMO.avi`: review -> auto_correct

</details>
