# 解析語料

`berth bench` 的輸入（plan §4.6、brief §6.9）。每一筆都是**真實 torrent 的檔案清單**，
不是手寫的假路徑——手寫的路徑只會證明解析器與自己的想像一致，而這一層存在的理由正是
想像會出錯（M1 票 01 就是這樣漏掉兩種羅馬數字寫法的）。

## 一筆長什麼樣

```json
{
  "id": "anime/frieren-7acg-bd-batch",
  "source_url": "https://share.dmhy.org/topics/view/725809_….html",
  "torrent_name": "[7³ACG] 葬送的芙莉莲/Sousou no Frieren S01 | 01-28+SPx11 [简繁字幕] BDrip 1080p x265 OPUS 2.0",
  "tmdb": "tv-209867",
  "context": { "media": "tv:209867", "season_hint": null, "episode_offset": null },
  "files": [{ "path": "Sousou no Frieren 2023 S01E01-[1080p][BDRIP][x265.OPUS].mkv", "size": 1234567890 }],
  "expected": [
    { "path": "…", "kind": "video", "action": "import", "season": 1, "episode": 1,
      "tags": { "source": "BD", "resolution": "1080p", "subs": ["CHS", "CHT"], "group": "7³ACG" },
      "min_confidence": "high" }
  ]
}
```

- `id` 的前綴就是分類（`anime` / `tv` / `movie`），報表照它分組。檔案位置與 `id` 一致。
- `torrent_name` 是**索引站上的發佈標題**（Berth 從搜尋結果拿到的那一個），不是 torrent
  內部的根資料夾名。CJK 的資訊（字幕語言、季號、合集標記）幾乎都寫在這裡。
- `files[].path` 是**相對於 torrent 內容根**的路徑：多檔 torrent 不含最外層資料夾，
  單檔 torrent 就是檔名。大小是 torrent metadata 裡的位元組數，沒有四捨五入。
- `expected` 逐檔一筆，順序與 `files` 相同。`tags` 缺席表示這一筆不比對 tag（字幕、extras、
  可忽略的附屬檔）。
- `target` 是相對於 Route 目標路徑的目標路徑（plan §5）。`import` / `extra` / `subtitle`
  三種處置**一定要寫**，其餘一定沒有——季集對了但檔名錯了，Jellyfin 那一端還是入錯，
  而多版本的判定、繁簡的分辨與多集檔的表示法全都只寫在檔名裡。同一筆語料裡兩個檔案
  不可以指到同一條路徑：那是衝突（brief §6.4 第 5 點），不是正確答案。
- `min_confidence` 是期望的信心下限。**不參與比對**：信心低於期望不是做錯事，那件事由報表的
  `review` 與 high / medium 誤判率各自回答。

## v0 語料（2026-09-10，M1 票 05）

20 筆：動漫 8、非動漫劇集 8、電影 4（brief §20.4 的樣本清單）。檔案清單是抓 `.torrent`
metadata 解出來的（dmhy 與 AnimeTosho）或索引站 API 給的（apibay 的 `f.php`），
**沒有下載任何內容**。每一筆的 `source_url` 就是出處。

| id | 為什麼是它 |
| --- | --- |
| `anime/frieren-7acg-bd-batch` | plan §4.6 拿它當範例。`S01 \| 01-28+SPx11` 合集、檔名是顯式 `S00Exx` / `S01Exx`、简繁字幕 BD |
| `anime/rezero-lolihouse-v2` | `- 81 v2` 的版本後綴；简繁**內封**；集號 81 落在 TMDB 併成一季的 85 集裡 |
| `anime/pokemon-horizons-fysub` | `【】` 括號、`[135-136]` 區間、三位數集號、BIG5 → CHT |
| `anime/mushoku-tensei-s3-kitauji` | **全形羅馬數字**季號（`无职转生Ⅲ`，U+2162）；檔名沒有解析度 |
| `anime/overlord-s2-dbd-raws` | 全形 `Ⅱ` + `第二季`、`全集`、简繁**外掛**（`.sc.ass` / `.tc.ass` 側掛字幕）、`Fonts/` `PV/` `menu/` `NCOP&NCED/` `SP/` 五種資料夾 |
| `anime/dragon-ball-daima-ktxp` | `★10月新番` 前綴、`（字幕社招人内详）` 招募廣告、`第01话`、GB → CHS |
| `anime/mushoku-tensei-s3-comicat` | **半形羅馬數字**不以空白收邊（`Mushoku Tensei III:`）；`[7月新番]` 檔期前綴 |
| `anime/kamiina-botan-chiyanabi` | `第01-12話` 區間 + `[合集]`；12 個檔案對上 TMDB 的 12 集 |
| `tv/the-bear-s03-successfulcrab` | 西方季包；兩個廣告 `.txt` 要被忽略 |
| `tv/squid-game-s02-flux` | 韓劇；檔名帶集標題（`S02E03.001.`） |
| `tv/squid-game-s02-y2flix` | 韓劇；`.srt` 側掛字幕與影片同主幹；結尾 `-[y2flix.cc]` 的組名 |
| `tv/librarians-next-chapter-elite` | 單集；`Screens/*.png` 與 `.nfo` 要被忽略 |
| `tv/fleabag-s01-s02-rzerox` | **多季**一包（`Season 1/` `Season 2/` 資料夾）；集標題是 `Episode N` 這種佔位 |
| `tv/true-beauty-cn-batch` | 韓劇 + 中文命名；`EP01`–`EP16` 無季號；`HD1080P` 這種 guessit 認不出的解析度；`【合集】` 開頭**不是**組名 |
| `tv/kamen-rider-zeztz-jibaketa` | 日本特攝 + 粵語代理商版；`- 50 END`；內封繁體 |
| `tv/gto-2026-magicstar` | 日劇；`EP08` 無季號；四種語言的側掛 `.srt`（`.Cht` / `.Chs` / `.Eng` / `.Jpn`） |
| `movie/oppenheimer-yts` | brief §20.4 點名的 YTS 佈局；`.txt` 與 `.jpg` 要被忽略 |
| `movie/shingeki-last-attack-7acg` | `剧场版` 標記；简繁字幕 BD |
| `movie/psycho-featurettes` | `Featurettes/` 底下 17 個特典（Trailer、Making、Menu Art…）；`Uncut` edition |
| `movie/your-name-bdmv` | **原盤**：`BDMV/` + `CERTIFICATE/`，整包標記為需人工（brief §6.2） |

## 三條容易讀反的判斷

寫 `expected` 之前先讀這三條，不然同一種情境會出現兩套答案。

**特典的季 0 編號**：發佈**明說** `S00E01` 時就照它走（brief §6.4「顯式 `SxxEyy` → 直接採用，
並用 TMDB 驗證該集存在」）；發佈只寫 `[SP][01]` 這種**自己的特典序號**時是 `unmatched`
（brief §7.6「對不到且像正片 → Unmatched，等人工指派」）。`frieren-7acg-bd-batch` 與
`overlord-s2-dbd-raws` 的差別在這裡，不是兩套標準。

**但那個編號不保證對得上 TMDB**：`frieren-7acg-bd-batch` 的 11 個特典是 `S00E01`–`S00E11`，
而凍結快照 `tests/fixtures/tmdb/tv-209867.json` 的 S0 裡，同一串「○○の魔法」佔的是
**1,2,3,4,6,7,8,9,10,11,13**（#5 是 Special Episode、#12 是另一支特典）。檔名裡沒有任何東西
能分辨這件事，而 plan / brief 也沒有一條規則做得到——所以這 11 筆的 `min_confidence` 是
**medium 而不是 high**。要做對得靠集名或片長比對，那是解析器目前沒有的能力（票 06 決定
不做，理由在下面「特典怎麼算」）。

**`subs` 是「這個發佈帶了哪幾種字幕」**，不是「影片內封了哪幾種」。外掛字幕也算：
`overlord-s2-dbd-raws`（`简繁外挂` + `.sc.ass` / `.tc.ass`）、`gto-2026-magicstar`
（`附官方日英简繁中字幕` + 四個 `.srt`）與 `squid-game-s02-y2flix`（`ESubs` + `.srt`）
的影片都帶 `subs`。字幕**怎麼放**由另一個欄位回答——brief §6.8 只有內嵌會多一個 `Hardsub`
token，內封與外掛都不加。

v0 涵蓋不到、由單元測試補的一件事：

- **`sample`**：這 20 個 torrent 一個 sample 檔都沒有——現在的發佈幾乎不再附 sample。
  規則（檔名含 `sample` 且遠小於正片）在 `tests/unit/test_parser_classify.py`。

## v1 補的三筆（2026-09-10，M1 票 06）

季集對應要修的三種形狀，各一筆真實發佈。三筆都是動漫，所以語料變成動漫 11、劇集 8、電影 4。

| id | 為什麼是它 |
| --- | --- |
| `anime/demon-slayer-hashira-uha` | **篇章名當季號**：`[鬼灭之刃 柱训练篇 / Kimetsu no Yaiba - Hashira Geiko-hen][07]` 完全沒有季號，正確答案是 S05E07。篇章名只寫在**索引站標題**上（檔名只有羅馬字的 `Hashira Geiko-hen`），而 TMDB 的 `zh-CN` 季名正好是 `柱训练篇`——這一筆同時證明了「要看發佈名不是只看檔名」與「季名要三輪語言」 |
| `anime/shingeki-s3-part2-erai` | **cour 偏移**：`Season 3 Part 2 - 01 ~ 10`，集號從 01 重數，正確答案是 S03E13–22。研究 §6.1.1 裡唯一「有季號還是三家一起錯」的那一類 |
| `anime/mizuiro-jidai-shincaps` | **單檔多集**（brief §6.6）：一個 `.ts` 檔涵蓋 01 與 02 兩集，正確答案是 `S01E01-E02`。找了很多輪——nyaa 上掛 `S01E01-E02` 標題的幾乎都是兩個獨立檔案 |

## v2 補的五筆（2026-09-16，M1 票 14c）

brief §6.4「只有集號 → 絕對編號」那一支。v1 的 23 筆一次都沒走到它（34 次全是 TMDB 只有一季），
所以那一支換算得對不對量不出來。條件是**只有集號、TMDB 上 ≥2 個正規季**，挑之前先查過快照的季數，
並在票 14c 以側錄證明每一筆真的走到那一支（那支實驗腳本隨 M1 票 14e 刪除）。語料變成動漫 14、
劇集 10、電影 4。

| id | 為什麼是它 |
| --- | --- |
| `anime/spy-x-family-s2-subsplease-batch` | SubsPlease 第二季接著第一季的 25 集往下數（`- 26v2`–`37v2`），正確答案 S02E01–12；absolute group 與各季累加一致 |
| `anime/my-hero-academia-139-subsplease` | 八季作品的 `- 139`，正確答案 S07E01（AnimeTosho 上另一組標 `S07E01 [EP: 139]`） |
| `anime/one-piece-1089-1104-erai` | **TMDB 第 22 季沿用官方集數**（S22E1089–1155）：absolute group 換對、各季累加換成 S22E01 是錯的。另有兩支特別篇，見下 |
| `tv/home-and-away-8214-bill` | 澳洲肥皂劇 `Episode.8214.2024-02-29`：累加換成 S37E32，正確答案 S37E39（TMDB 集名就叫 `Episode 8214`、播於同一天）。**非動漫上換算會錯的反例** |
| `tv/return-of-superman-e079-limo` | 韓國電視台的 `E079.150524` 無季寫法；TMDB 按年份分季，累加換成 S03E21，播出日與檔名一致，是對的 |

這五筆的正確答案都**不是從檔名推出來的**——是 TMDB 快照裡那一集的播出日與集名，對上檔名的日期、
別的發佈組標的季集或官方集數。逐筆怎麼判的在 `docs/research/profile-effect.md` §3。

- **兩筆非動漫沒有 `min_confidence`**：只有集號時該不該自動入庫，正是這一票要量的問題，寫下限等於
  先替答案選邊。
- **航海王的兩支特別篇是 `unmatched`**（`Dai Tannou Kikaku - Shi no Gekai - Trafalgar Law`、
  `Innen no Log - Mugiwara no Ichimi to Cipher Pol`）：TMDB 是 S00E28 / S00E29，但只有集名說得出來，
  與上面「自己的特典序號」同一條判準。
- **`tv-2354.json` 有 1.4 MB**（39 季、8,802 集），是其他快照加起來的好幾倍。它是唯一一筆「換算會錯」
  的非動漫反例，所以留著。
- 找過但沒收的（韓劇第二季以後、半澤直樹、Neighbours）記在研究文件 §5；《死神》相剋譚在 v3 收了。

## v3 補的兩筆（2026-09-17，M1 票 14d）

絕對編號換算的信心改看證據之後（brief §6.4 的兩條），「集號 ≤ 第一季集數」那一條兩個方向各一筆。
兩筆都從 AnimeTosho 抓 `.torrent` 解出檔案清單並核對 infohash；語料變成動漫 16、劇集 10、電影 4。

| id | 為什麼是它 |
| --- | --- |
| `anime/bleach-tybw-soukoku-tan-erai` | **每 cour 重數、篇章名只寫羅馬字**：`Bleach - Sennen Kessen Hen - Soukoku Tan - 01`–`14`，TMDB 的季名是 `Thousand-Year Blood War` / `千年血戰篇`，篇章名比對不到，掉進絕對編號換算成 S01E01–14。正確答案 **S02E27–E40**（S02E27 `A` 2024-10-05 … S02E40 `MY LAST WORDS` 2024-12-29，研究 §4）。在舊的 `anime` 規則下是 `auto_wrong` 14，規則 1 之後是 `review` 14——這一筆就是那條規則存在的理由 |
| `anime/spy-x-family-05-subsplease` | **規則 1 的代價**：2022 年第一季播出時的 `Spy x Family - 05`，正確答案 S01E05，但數字同樣讀得成後面某季的第 5 集，所以是 `review`。研究 §6.1.1 量過能不能靠「標題有認不出的多餘字」放行這種，結論是不能——它哪天變成 `auto_correct`，先回去看那一節 |

- **兩筆都沒有 `min_confidence`**：與 v2 的兩筆非動漫同一個理由，它們量的就是「該不該自動入庫」。
- **《死神》的 tags 沒有 `subs`**：`[MultiSub]` 沒說是哪幾種語言（同一家的航海王寫了 `[ENG][POR-BR]…`，那一筆才有 `EN`）。

## v4 補的兩筆（2026-09-17，M1 票 14f）

**季號剛好等於方括號集號**（`S2 [02]`）。為 `The_Final_Season[28]` 寫的那條規則曾經把這種季號丟掉。兩筆都從
Mikan 下載 `.torrent` 解出檔案清單（單檔 torrent，infohash 與 Mikan 的 episode id 相同）；語料變成動漫 18、劇集 10、電影 4。

| id | 為什麼是它 |
| --- | --- |
| `anime/rezero-s2-02-hyakuhuyu` | **TMDB 併成一季**：`S2][02]` 丟掉季號就是「只有集號、TMDB 只有一季」，直接以 medium 自動入庫成 S01E02。正確答案 **S01E27** `The Next Location`（2020-07-15）：第二輪從 S01E26 起，Mikan 發佈時間 2020-07-16，票 01 的校準也把這一組的 `[02]` 釘在第二季第 2 集。修之前是 `auto_wrong` 1。檔名裡的 `꞉` 是 U+A789，不是半形冒號 |
| `anime/mushoku-tensei-s2-02-sakurato` | **TMDB 多季**：同一個錯在這裡被「集號 ≤ 第一季集數」送審核，不會入錯但也入不了。正確答案 S02E02 `The Forest in the Dead of Night`（2023-07-17；Mikan 發佈 2023-07-19）。季號是明說的，所以 `min_confidence` 是 high |

- Re:Zero 的 `min_confidence` 是 medium：季號 2 在 TMDB 上不存在，要靠虛擬季換算（plan §4.4），至多 medium。

## v5 補的兩筆（2026-09-22，M2 票 01）

**`Season 3 - 50`：破折號後面那個數字是集號**，而它是**跨季累加**的絕對編號——季號明說是 3，數字卻從
第一季開始數。guessit 對這一種的兩種寫法各錯一種，所以兩筆都收：只寫一次時它回
`season: [3, 4, …, 50]` 一整串，第二個數字被當成集號；`Season 3 / … Season 3 - 47` 這種重複寫時
它只回 `season: 3`，`3 - 47` 因此落進 `_LOOSE_RANGE` 變成集數區間（M1 票 08 在真的索引站回應裡抓到
`S03E03–E46`，留給 M2 票 01）。兩筆都從 ACG.RIP 下載 `.torrent` 解出檔案清單（都是單檔 torrent，
檔名與索引站標題不同）；語料變成動漫 20、劇集 10、電影 4。

| id | 為什麼是它 |
| --- | --- |
| `anime/spy-x-family-s3-ani` | **只寫一次的 `Season 3 - 50`**：修之前 guessit 那一整串季號讓它以 **high 信心自動入庫成 S03E04**（`auto_wrong` 1）。正確答案 **S03E13** `A World Where We Cannot Survive`：S1 25 集 + S2 12 集 = 37，50 − 37 = 13，而 TMDB 的播出日 2025-12-27 與 ACG.RIP 的發佈時間同一天 |
| `anime/spy-x-family-s3-dynamis` | **重複寫的 `Season 3 / … Season 3 - 47`**：索引站標題是被讀成區間的那一種，而**檔名只寫一次**，所以同一筆同時蓋到兩種寫法（`merge_release` 檔名說了算，修之前一樣是 high 的 S03E04）。正確答案 **S03E10** `Austin's Troubles \| A Normal Mixer \| Moon Landing`，播出日 2025-12-07 與發佈時間同一天 |

- **兩筆都沒有 `min_confidence`**：與 v2 / v3 的四筆同一個理由——明說的季號配上跨季累加的集號該不該
  自動入庫，正是這兩筆要量的問題。修完之後它們落在 `review`（`auto_wrong` 2 → 0，`auto_correct` 不動）：
  集號 50 在只有 13 集的第三季裡不存在，而「季號明說時要不要改走絕對編號」現在沒有規則回答，
  所以交給人比猜一個好。
- 集名裡的 `|` 進不了檔名（`naming.sanitize`），所以 `target` 上是
  `Austin's Troubles A Normal Mixer Moon Landing`。

## 外掛字幕怎麼算（票 07 的決定）

字幕檔的 `target` 是**它那個影片的目標路徑**換上字幕的副檔名與語言段（plan §5）。所以：

- 一集兩個語言的側掛字幕（`.sc.ass` / `.tc.ass`）產出兩條不同的路徑（`.CHS.zh.ass` /
  `.CHT.zh.ass`），不是衝突。
- 語言由**字幕自己**的後綴、資料夾、檔名決定，不看 torrent 名：`gto-2026-magicstar` 的影片
  帶 `CHS+CHT+JP+EN` 四種，四個 `.srt` 各只有一種。
- 影片是 `unmatched` / `review` 時字幕跟著它，沒有 `target`（`overlord-s2-dbd-raws` 的
  `SP/` 底下 28 個字幕都是 `unmatched`）。

## 加一筆

1. 找一個真實發佈，把 torrent metadata 的檔案清單抄下來（路徑與位元組數原樣，去掉個資）。
2. 寫 `expected`：正確答案，不是目前的行為。`kind` 照 brief §6.2 的表，`target` 照 plan §5
   的模板。
3. 補快照：`uv run --env-file .env python scripts/record_tmdb_snapshots.py`。
4. `uv run berth bench`。數字變好就 `--update-baseline` 並在 commit message 說明；
   變差就是解析器有洞，先修再更新。

`baseline.json` 是 CI 的門檻，不是紀錄——只在**刻意**改善或刻意接受退步時才動它。

## 特典怎麼算（票 06 的決定）

票 05 留下的問題是「要不要靠集名或片長比對特典」。**不做**：檔名裡沒有集名，片長要 mediainfo
（第一階段沒有），所以加了也只是換一種猜法。規則維持兩條，兩條都不會自動入庫到錯的地方：

- 發佈**明說** `S00Exx` → 照它走，但信心**至多 medium**：字幕組的特典編號與 TMDB 的 S0 編號
  不保證一致（`frieren-7acg-bd-batch` 就是這樣）。medium 仍會自動入庫，但帶 `audit` 旗標。
- 發佈只寫 `[SP][01]` 這種自己的序號 → `unmatched`，等人工指派（brief §7.6）。
