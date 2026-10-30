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

## 從 brief 搬來（§20.4）

從 design-brief §20.4 搬來的原文（整節，不改字；brief 只留結論與來源）。


**解析庫現況（2026-09）**

| 庫 | 語言 | 狀態 | 欄位 | CJK / 字幕組 |
| --- | --- | --- | --- | --- |
| [guessit](https://github.com/guessit-io/guessit) | Python | 活躍，v4.4.0（2026-07） | title / season / episode / absolute_episode / version / release_group / source / screen_size / video_codec / subtitle_language / edition / other 等極完整 | 弱：[#929](https://github.com/guessit-io/guessit/issues/929) 仍開著，fansub 括號格式常錯 |
| [anitopy](https://github.com/igorcmoura/anitopy) | Python | 停滯（2022） | anime_title / episode_number / release_group / release_version / video_resolution 等 | 無專門處理 |
| [anitomy](https://github.com/erengy/anitomy) | C++ | develop 分支重寫中（C++23） | 同上 | 無專門處理 |
| [anitomyscript](https://github.com/skiptirengu/anitomyscript) | JS/WASM | 2019 版本，落後上游 | 同上 | 無 |
| [@ctrl/video-filename-parser](https://github.com/scttcper/video-filename-parser) | TS | 活躍，v5.11（2026-07），Radarr 風格 | title / year / resolution / sources / videoCodec / revision / group / edition / languages；TV 模式 seasons / episodeNumbers | 無 |
| [parse-torrent-title](https://github.com/clement-escolano/parse-torrent-title) | JS | 活躍 | title / season / episode / resolution / codec / source / group，可擴充 handler | 無 |
| [dreulavelle/PTT](https://github.com/dreulavelle/PTT)（pip `parsett`） | Python | 活躍 | 西方 scene 命名 | 無 |
| torrent-name-parser | Rust | 停滯（2023） | 基本欄位 | 無 |

**結論**：沒有現成庫能處理中文字幕組命名，CJK 詞典一定要自己維護；西方命名交給 guessit（Python）或 @ctrl/video-filename-parser（TS）。可直接借鑑的 CJK regex 有兩處：

- **AutoBangumi `tokenizer/classic.py`**（[repo](https://github.com/EstrellaXD/Auto_Bangumi)，`backend/src/module/parser/analyser/tokenizer/classic.py`）：`_CJK_SUBTITLE_TAG`（简/繁/日/双语/内嵌/内封/外挂/多国）、`_SUBTITLE`（CHS/CHT/GB/Big5/JPSC/JPTC/Multi-Subs/PGS）、`_CHINESE_SEASON`（第N季/期，含中文數字）、`_CHINESE_EPISODE`（第N话/集）、`_FULL_COLLECTION` / `_COLLECTION`（全N话/合集/全集/总集篇/特典）、`_SPECIAL_CJK`（番外/特別篇）、`_MOVIE_CJK`（劇場版/電影版）、`_PREFIX`（★1月新番★）、`_RECRUIT`（招募廣告）、`_REGION`（僅限港澳台）、`_SOURCE`（Baha/B-Global/Bilibili/CR/AT-X/Abema/AMZN/NF/…）、`_CODEC`、`_AUDIO`。
- **Sonarr `Parser.cs`**（[raw](https://raw.githubusercontent.com/Sonarr/Sonarr/develop/src/NzbDrone.Core/Parser/Parser.cs)）：約 8 條中文動漫 pre-substitution（以 `[一-鿌]` 剝離中文標題、LoliHouse / Lilith-Raws / Skymoon-Raws 無括號格式、GM-Team 多括號格式、`第?(\d+)(话|集)?( END|完| Fin)?`），以及韓劇 `\.E(\d{2,4})\.\d{6}\.(.*-NEXT)$ → S01E$1` 規則。

**AutoBangumi 現況（main，2026-08）**

- 解析輸出 `ParsedRelease`：`title_en / title_zh / title_jp / group / season / episode / episode_end / media_type(EPISODE|MOVIE|OVA|OAD|SPECIAL|PV|OPENING|ENDING) / release_kind(SINGLE|RANGE|BATCH|COLLECTION) / resolution / source / subtitle / codecs / audio / version / tags / evidence`。§6.3 的欄位設計與此對齊。
- LLM 解析支援 OpenAI / Anthropic / Gemini，兩種模式：`primary`（LLM 為主但仍合併規則層的結構提示）與 `fallback`（只在規則層失敗或只得到弱標題時呼叫）；有記憶體快取、斷路器、併發上限。§6.10 的設計與其 `fallback` 模式一致，並多加了 schema 驗證與預算。
- `offset_detector.py`：以 TMDB 各集 `air_date`、播出間隔 > 6 個月切「虛擬季」，算出 season_offset 與 episode_offset。
- 明確限制：**不支援合集/批次**（FAQ：「AB 目前不支持解析合集」）、OVA 與電影 RSS 不支援、路徑必須是 `Title/Season X/`。這三點正是本系統 §6.6 要超越的地方。
- RSS 預設過濾 regex `720|\d+-\d+`（排除 720p 與區間合集）；建議一部作品只訂一個字幕組；繁簡二選一靠 Mikan 訂閱時選或 filter。§15 的 Rule 預設沿用「排除合集、字幕組白名單」。

**真實內容樣本（都取自現場列表，作為 benchmark v0 的種子）**

- 單集：`[Erai-raws] Yani Neko - 07 [1080p NF WEB-DL AVC AAC][MultiSub][A5D38B89]`；`[三明治摆烂组] … - 08 - [繁日内嵌][AVC 8bit 1080P]` 與同集的 `[简日内嵌]`、`[简繁日内封]` 三個 torrent（內嵌 vs 內封的實例）；`【楓葉字幕組】[寵物小精靈/ 寶可夢地平線烈空坐飛升][089][繁體][1080P][MP4]`；`【悠哈璃羽字幕社】[碧蓝航线 微速前进 S2_Azur Lane - Bisoku Zenshin! S2][x264 1080p][CHT]`；`[DHR Fansub][Little Busters!_リトルバスターズ!][04][JPN&BIG5][720P][AVC_Hi10P_AAC][MKV]`；`[LoliHouse] Re:Zero … - 81 v2 WebRip 1080p HEVC-10bit AAC`。
- 合集 / BD：`[7³ACG] 葬送的芙莉莲/Sousou no Frieren S01 | 01-28+SPx11 [简繁字幕] BDrip 1080p x265 OPUS 2.0`（28 集 + 11 個 SP）；`[7³ACG] 日常/Nichijou S01 | 01-26+SPx1 …`；`…★百姓贵族★29~40(完)★1920x1080★…★繁体中文`（`★` 分隔、`完` 標記）；`jibaketa TVB Honzuki no Gekokujou - S1 S2 S3 BD 1920x1080 x264 AACx2 SRT TVB CHT`（多季合一）；`Solo Leveling S01 + S02 BDRIP …`。
- 外掛字幕：`sub/スレイヤーズTRY第01話(DVD 640x480).gb.ass` / `.big5.ass`；`[11番小队][十二国记]…tc.ass`；Mikan 的「生肉/不明字幕」標記。
- 西方劇集：RARBG 季包 `Show/Subs/Episode 1/2_English.srt, 3_English.srt, 2_French.srt`（[renamer README](https://github.com/img02/Rarbg-Subtitle-Renamer)）；Sonarr Daily 型 `Some.Daily.Show.2021.03.04.1080p.HDTV.x264-GROUP`；`S01E01E02` 多集檔。
- 電影：`Oppenheimer (2023) [1080p] [BluRay] [5.1] [YTS.MX]/Oppenheimer.2023.1080p.BluRay.x264.AAC5.1-[YTS.MX].mp4` + `www.YTS.MX.jpg` + `YTSProxies.com.txt`；Jellyfin 官方多片段 `Movie Name-cd1.mkv`（parttype：cd/dvd/part/pt/disc/disk）。
- 韓劇：`Show.E01.YYMMDD.1080p…-NEXT` 無季編號（Sonarr 特別處理），`E01-16 COMPLETE (HDTV NEXT)` 全季字幕包。
- **已證實（2026-09-10，M1 票 05，抓真實 torrent metadata）**：BD 包的附屬資料夾名兩家不同，社群轉述的那一串只對了一半。
  - [VCB-Studio 魔王2099](https://share.dmhy.org/topics/view/726629_VCB-Studio_2099_Demon_Lord_2099_10-bit_1080p_HEVC_BDRip_Fin.html)（223 個檔案）：`SPs/`、`CDs/`（每張碟一個子資料夾，內含 flac 與 webp）、`CDs/…/Scans/`、`Scans/`（`BDBOX`、`Vol.1`…）。**沒有** `Fonts/` 與 `Menu/`。
  - [DBD-Raws 不死者之王 第二季](https://share.dmhy.org/topics/view/668157_DBD-Raws_Overlord_Overlord_S2_01-13TV_SP_1080P_BDRip_HEVC-10bit_FLAC_MKV.html)（106 個檔案）：`SP/`（帶 SP 編號，每個配 `.sc.ass` / `.tc.ass`）、`PV/`、`NCOP&NCED/`、`menu/`（小寫）、`Fonts/Fonts.zip`（字型是壓縮檔不是散檔）。
  - 兩份都成了 §6.9 的語料（`tests/fixtures/parser/`），分類規則因此有真實輸入可以釘。

**只有集號、TMDB 上多季的真實發佈（2026-09-16，M1 票 14c，[研究](../research/profile-effect.md)）**：
§6.4「只有集號 → 絕對編號」那一支在 v1 的 23 筆語料上一次都沒走到（34 次全是 TMDB 只有一季），
補了 5 筆走得到的才量得出 Route profile 的作用。

- **動漫的跨季連號換算得對**：SubsPlease `Spy x Family - 26`–`37`（S02E01–12）、`Boku no Hero Academia - 139`
  （S07E01）、Erai-raws `One Piece - 1089 ~ 1104`。**TMDB 的航海王第 22 季沿用官方集數當 `episode_number`**
  （S22E1089–1155），所以只有 absolute group 換對，各季累加換成 S22E01 是錯的。
- **非動漫的「集號」可能是另一套數法**：《Home and Away》`Episode.8214.2024-02-29` 累加換成 S37E32，
  但 TMDB 的 S37E39 集名就是 `Episode 8214`、播於同一天——TMDB 前 36 季比官方編號多收 7 集。
  韓國電視台的 `The.Return.of.Superman.E079.150524` 累加換成 S03E21，播出日與檔名一致，是對的。
- **字幕組每 cour 重數、篇章名只寫羅馬字時會被當成絕對編號**：Erai-raws
  `Bleach - Sennen Kessen Hen - Soukoku Tan - 01 ~ 14` 換成 S01E01–14，正解 S02E27–40（TMDB 季名是
  `Thousand-Year Blood War` / `千年血戰篇`，比不到羅馬字）。
- **`guessit` 預設把韓國電視台的 `YYMMDD` 讀錯**：`150524` 讀成 2024-05-15（本機 guessit 實測），要加
  `date_year_first`——官方說明「If short date is found, consider the first digits as the year」
  （[guessit 文件](https://guessit-io.github.io/guessit)的 `-Y, --date-year-first`；設定檔裡是 `date_year_first`）。
  加上之後讀成 2015-05-24，`2024-02-29` 這種四位數年份不受影響。
- 韓劇第二季以後、檔名沒有季號的 `Show.2.E01.YYMMDD` 在 TPB、Knaben、dmhy 都沒找到，公開索引站上的
  第二季發佈全部帶 `S02E`。
- **「集號 ≤ 第一季集數就送審核」擋下的多半是對的**（2026-09-17，M1 票 14d，[研究 §6.1.1](../research/profile-effect.md)，
  `scripts/experiments/absolute_rule_cost.py`）：M1 票 01 那批以發佈時間判定正解的 Mikan 發佈，取 TMDB 上 ≥ 2 季的
  5 部（SPY×FAMILY、無職轉生、鬼滅之刃、進擊的巨人、航海王），每筆當成以標題為檔名的單檔 torrent 丟進 `plan`、
  合集逐集展開。走到絕對編號換算的檔案裡，集號 ≤ 第一季集數的**正解在第一季 928 個、在後面某季 167 個**；
  超過第一季集數的 1,219 對、54 錯，錯的 54 個正解全是播出日對不上、退回序位的那種，本身存疑。
  「標題有認不出的多餘字」（guessit 的標題候選不等於作品的已知名字）分不開兩者：連 TMDB 的 `titles` 一起比，
  放行 793 個第一季、漏掉 14 個後面季的——`Kimetsu no Yaiba: Katanakaji no Sato-hen` 本身就是 TMDB 別名，
  `Mushoku Tensei S2 [02]` 的季號被 Berth 丟掉（季號等於方括號集號時；M1 票 14f 已修，這 5 個之後
  讀得出季號、不再走到絕對編號換算）；只比三個主標題，放行 328 個、一個不漏，
  但無職轉生那 5 個是因為 TMDB 英文標題 `Mushoku Tensei: Jobless Reincarnation` 比羅馬字長才擋下，同一種寫法換成
  英文標題就是 `SPY x FAMILY` 的作品就會入錯。近似的限制：Mikan 只有標題沒有檔名、樣本以中文字幕組與動漫為主。

**Jellyfin 動漫命名的社群痛點**

- One Piece / Detective Conan 這類長篇：TVDB arc 順序 vs 絕對編號長期無解（[r/jellyfin](https://www.reddit.com/r/jellyfin/comments/1sny587/one_piece_tvdb_arc_order_vs_absolute_episode)、[tvdb-plugin#91](https://github.com/jellyfin/jellyfin-plugin-tvdb/issues/91)）。本系統只承諾「與 TMDB 一致」，不承諾符合任何一種社群偏好。
- Split-cour 被 Jellyfin 併成一季的抱怨很多（[r/jellyfin](https://www.reddit.com/r/jellyfin/comments/1r5sk02/any_way_to_have_anime_seasons_shown_in_parts_like)）；本系統不對抗 provider，只做正確對應。
- Sonarr FAQ 也承認 Bleach TYBW 這類新 arc 只有在編號與 TVDB 對上時才會自動匹配；絕對編號缺失時需等 TVDB 更新。

**mediainfo（pymediainfo 7.0.1，2026-09-11 對真檔案實測）**

- `pip install pymediainfo` 的 wheel **內含 libmediainfo**，不需要系統套件（[README](https://github.com/sbraz/pymediainfo)）；在這台 Windows 上 `MediaInfo.can_parse()` 直接回 `True`。
- `MediaInfo.parse(path)` 回一份 track 清單，`track.to_data()` 是那一條的所有欄位。**同一個 `duration` 在不同 track 上型別不同**：General 上是整數毫秒（`2023`），Video 上是字串（`"2000.000000"`）——照抄任一邊的型別去讀另一邊都會拿到錯的值。
- 布林是字串 `"Yes"` / `"No"`（`forced`、`default`）；語言是兩碼（`ja` / `en` / `zh`），`other_language` 另有一組別名。繁簡分不出來，所以字幕軌的繁簡只寫在 `title` 裡（與 §20.1 的 Jellyfin 同一個限制）。
- 讀得完但不是媒體的檔案（例如一個 `.txt`）**不會丟例外**，回的是一份只有 General 的清單——所以「有沒有影像軌」才是「這是不是一個影片」的判準，而不是例外。
- 證據：`tests/fixtures/mediainfo/two-second-episode.mkv`（ffmpeg 造的 17 KB Matroska：10 bit AVC + 兩條標了語言的音軌 + 兩條標了 forced / default 的字幕軌）與 `tests/unit/test_mediainfo.py`。
