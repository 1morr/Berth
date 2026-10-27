# 有 Fribb 與沒 Fribb：AniList 條目對到 TMDB 季集的兩種算法（2026-10-28）

不是票；票 16 之後使用者要看「有 Fribb 對沒 Fribb」的差別，協調者第二輪要求補「作品靠搜尋」與冷門、撞名的作品。腳本 `scripts/experiments/fribb_vs_chaining.py`（可重跑，回應快取在 `.local/experiments/cache/fribb_vs_chaining/`），原始數據 `docs/research/fribb-vs-chaining-2026-10-28.json`。只打 AniList、TMDB 與 Fribb 的表，不經任何 AI 模型。

## 結論

**前提**：B 的 TMDB 作品是手動填的（「找對作品」不在 B 裡），所以另外有 **B2：作品靠搜尋**——照退路真的會走的路，用 AniList 第一季的標題（english、romaji、native 依序）搜 TMDB，取動畫類劇集裡首播年最接近的那一部，再照 B 串接。正解也用手填的作品；B2 找錯作品就整部算錯。

17 部（熱門 9、冷門或容易撞名 8），98 個 AniList 條目，其中 54 個 `TV` 條目拿來比；5 個無法判定，剩 **49 個判得出正解**。

| | A：Fribb | B：串接（作品已知） | B2：串接（作品靠搜尋） |
| --- | --- | --- | --- |
| 對 | **44** | **46** | **46** |
| 錯 | **4** | **3** | **3** |
| Fribb 沒有季（未覆蓋） | 1 | — | — |
| 熱門 9 部（35 個判得出） | 31 對、4 錯 | 33 對、2 錯 | 33 對、2 錯 |
| 冷門 / 撞名 8 部（14 個判得出） | 13 對、1 未覆蓋 | 13 對、1 錯 | 13 對、1 錯 |
| 作品找得對不對 | 51 個有 TMDB 劇集 id，**全對** | （給定） | 17 部**全找對** |

- **A 錯的四個，兩種原因**（全在熱門作）：
  - **TMDB 後來把季併了，Fribb 還照舊**（2 個）：咒術迴戰第 2 季、膽大黨第 2 季，Fribb 寫 `season.tmdb: 2`（與 TVDB 的分季相同），TMDB 現在只有一季，正解是 S01E25–E47、S01E13–E24。同一部的「死滅迴游」是新條目，Fribb 就對了（S01E48–E59）——舊條目沒有跟著 TMDB 的改版更新。
  - **offset 差一集**（2 個）：Re:Zero 第 2 季 `offset 26`（應是 25，brief §20.3 已記）；無職轉生第二季把第 0 集算進 AniList 的 13 集，而 TMDB 把第 0 集放進 Specials（S00E02），Fribb 給 S02E01–E13，正解 S02E01–E12。
- **Fribb 給的作品本身沒錯過**：54 個 TV 條目裡 51 個有 TMDB 劇集 id，全部指向對的作品；沒有的 3 個是兩個還沒開播、一個 Fribb 對到 TMDB 電影（輝夜姬「First Kiss wa Owaranai」，AniList 記成 4 集的 TV）。HxH 2011 有對的劇集 id、但沒有季（算未覆蓋）。
- **B 錯的三個，兩種原因**：
  - **有一集不在正篇**（2 個）：無職轉生第二季的第 0 集在 Specials，串接照 AniList 的 13 集往下數，這一季終點多一集、Part 2 整段往後推一集（腳本標「超出那一季的 24 集」）。
  - **TMDB 把一個條目拆成好幾季**（1 個，冷門 / 撞名那一組唯一的錯）：HxH 2011 在 AniList 是一個 148 集的條目，TMDB 分成 62 / 74 / 12 三季，串接全塞在第 1 季（同樣標了「超出那一季的 62 集」）。這部 TMDB 的季還沿用連續編號（S02 從 E63 起），B 的「下一季從 E01 起」在這種編法下也不成立；樣本裡只有這一部這樣編。
- **B2 與 B 完全一樣**：17 部都找到對的作品，所以錯的也是同三個。找對靠兩件事：搜尋結果裡動畫類劇集通常只有一兩部；撞名的時候首播年分得開——奇諾之旅的結果同時有 2003 與 2017 兩部、膽大黨與進擊的巨人各有一兩部別的動畫，都靠首播年挑對。**敏感度**：只用 english、只用 romaji、只用 native 搜，挑到的作品都一樣、都對；福星小子 2022 的 english 標題（「Urusei Yatsura (2022) Seasons 1 & 2」）搜不到動畫類結果，退到 romaji 才找到。樣本裡沒有「首播年也分不開」的撞名（同一年的同名作），那一種沒測到。
- **兩種一起用，樣本裡的錯都看得出來**：A 與 B 不一致的 4 列（Re:Zero 第 2 季、咒術迴戰第 2 季、膽大黨第 2 季、無職轉生第二季 Part 2）每一列都恰好一邊錯；兩邊一致卻都錯的只有無職轉生第二季，它與被標的 Part 2 在同一季；A 沒有答案的 HxH 2011，B 標了「超出」。把「有一列 A、B 不一致或 B 超出」的整季拿出來看，7 個錯都看得到；被標的列裡沒有兩邊都對的（沒有誤報）。
- **劇場版與 OVA 不比**（44 個非 TV 條目）：用播出日對 Specials 或正篇常是巧合（SPY×FAMILY CODE: White 上映那天正好播了 S02E12），所以只列 Fribb 的對法。Re:Zero 的兩部劇場版不在 AniList 的系列圖裡（Memory Snow 算在 OVA 條目 100049），與研究 08 §2.1 相同。

對產品的意思：

- **Fribb 的作品 id 可以信，季與 offset 要檢查**：這份樣本裡 Fribb 從沒指錯作品，錯的都是季（TMDB 改版之後沒跟上）與 offset。
- **退路（B2）找作品這一步在樣本裡沒出錯**，錯在串接本身（Specials 裡的一集、TMDB 把一個條目拆季）。退路的表標「未經對照表」是對的：它會錯在 Fribb 不會錯的地方，反之亦然。

**依此改了 `series-mapping` 的兩處**（協調者決定，2026-10-28）：

1. **Fribb 可用時也串接一次**：第 3 步改成 A、B 兩種都算，任一列不一致、串接超出 TMDB 那一季的總集數、或那一季沿用連續編號（第一集不是 E01，像 HxH 2011 的 S02 從 E63 起，`media_read_media` 的集號看得出），整季在表上標「兩種算法不一致，請確認」、兩種範圍並列，不自己挑一邊。原本是「範圍重疊或有縫才用集數改正」，等於讓模型自己挑；這份數據裡兩邊都會錯、而把整季拿出來看沒有漏掉也沒有誤報。
2. **退路找作品的規則寫明**：Fribb 抓不到時用 `discover_search_media` 依序試 english、romaji、native 標題，只留 `animation: true` 的結果，同名多部取 `year` 最接近 AniList 第一季開播年的那一部（B2 的做法，17 部全找對）。`discover.search_media` 給模型的結果原本只有 `year`，這一輪補上 `animation`（TMDB `genre_ids` 有 16；畫面的 API 不帶它）。

## 方法

- **系列**：從每部的一個 AniList 條目沿 `SEQUEL`、`PREQUEL`、`SIDE_STORY`、`PARENT`、`SUMMARY` 走（同 `anilist.read_franchise` 的預設，不含衍生作），一層問一次，每次間隔 2.5 秒。
- **TMDB 作品是手挑的**（不取自 Fribb，用在 B 與正解）；A 對到別的劇集算錯。
- **A**：起點 `offset.tmdb + 1`（沒有 offset 是 1）、終點起點 + AniList 集數 − 1、季是 `season.tmdb`。Fribb 有劇集 id 卻沒有季的算未覆蓋；作品對不對另記（`fribb_tmdb_ok`）。
- **B**：TV 條目照開播日排，從 S01E01 起依 AniList 集數一個接一個；一季的集數（TMDB `seasons[].episode_count`）用完，下一個條目從下一季 E01 起；超出那一季的集數照算、標出來。
- **B2**：第一個有開播日的 TV 條目的三種標題（english、romaji、native，另外問 AniList 一次取 native）依序搜 TMDB `search/multi`（Berth 的 `discover.search_media` 用的同一支），留 `media_type: tv` 而且 `genre_ids` 有 16（Animation）的，取首播年與那個條目開播年差最小的（同差取搜尋排序在前的）；第一個有結果的標題就用它。找到的作品與手挑的不同就整部算錯，相同就照它的季串接（與 B 相同）。每一種標題單獨會挑到哪一部也記下來（`b2_search.by_title`）。
- **正解**：AniList 條目的 `startDate` 對 TMDB 播出日相同的那一集，先找正篇（第 1 季起）、找不到才看 Specials；`endDate` 對正篇裡播出日相同的最後一集，**可以在後面的季**（HxH 2011 到 S03E148，這種 A、B 都給不出、一律算錯）。**容忍 ±1 天**：AniList 記的是日本首播日，深夜檔（「25:30」）在 TMDB 常記成前一天或後一天；週播兩集相隔 7 天，±1 天不會撞到隔壁那一集。同一天兩集（首播連播、串流一次放完）起點取最小、終點取最大。第一集被放進 Specials、完結日在正篇的（無職轉生第二季的第 0 集），正解取正篇那一季、開播日之後的第一集起，Specials 那一集另外註明。對不到的那一端寫「無法判定」，那一列不算對錯。
- **挑的作品**：
  - 熱門 9 部：Re:Zero（必選；TMDB 四季併成一季）、咒術迴戰、芙莉蓮、膽大黨（TMDB 併季）、進擊的巨人（分割 cour、OVA 多）、無職轉生（第 0 集、OVA）、輝夜姬（三季加劇場版）、SPY×FAMILY（分 cour、劇場版）、死神（千年血戰篇三段接在 366 集之後）。
  - 冷門 4 部：有頂天家族（兩季相隔四年）、打工吧！魔王大人（兩季相隔九年、第 2 季分兩個 cour）、玉子市場（只有劇場版接續）、來自深淵（兩季之間夾一部劇場版）。
  - 撞名 4 部（重製版，TMDB 上有同名的舊作）：水果籃子 2019、HxH 2011、福星小子 2022、奇諾之旅 2017。
  - **沒挑到「季中夾總集篇、TMDB 算進正篇」的作品**：無職轉生第一季的總集篇在 AniList 是另一個 SPECIAL 條目，不影響 TV 條目的集數。

## 走 RSS 現在的路擋不擋得住（照 plan §4.4 推論，沒有實跑解析器）

先講清楚範圍：A、B 只出現在側面板的 `series-mapping`，影響的是**挑哪些 torrent、卡片上寫哪一季**；卡片送單只帶 `source_id`、`media_id`、`route_id`，入庫的季集由規劃器照檔名重算（§4.4 的那幾條），不吃 A、B 的範圍。RSS 那條路也一樣不用 Fribb、不用 AniList，靠的是 TMDB 各集的播出日。所以下面問的是：**同樣的作品走 RSS（或手動送單之後的規劃），這幾種錯法會不會出現、出現了誰擋**。

| 錯法 | 例 | RSS 的路 | 擋不擋得住 |
| --- | --- | --- | --- |
| TMDB 併季、資料還照舊分季 | 咒術迴戰第 2 季、膽大黨第 2 季 | `2nd Season - 05`、`S2 - 05`：TMDB 沒有第 2 季 → 照 > 180 天的間隔切虛擬季（咒術迴戰 2021-03 → 2023-07、膽大黨 2024-12 → 2025-07，兩部都超過 180 天）→ 對到 S01E29、S01E17；季內連號（`- 29`）照字面就對 | **擋得住**：本來就照 TMDB 的播出日切，不會沿用舊分季；confidence 至多 medium、第一批審核 |
| offset 差一集 | Re:Zero 第 2 季 | 不用 offset：`2nd Season - 01` 照虛擬季對到 E26 | **擋得住**：這一種錯法 RSS 不會產生 |
| 同一季裡的 cour 間隔不到 180 天 | Re:Zero 第 2 季 Part 2（2020-09-30 → 2021-01-06，98 天） | `2nd Season Part 2 - 01`：Part 標記要「同一季前面幾個 cour 的長度」，而 cour 的切法也是 > 180 天，98 天切不開 → 偏移加不上去、超出時照字面讀，多半讀成 E26 | **規則擋不住，靠人**：medium、第一批審核；播出日比對的規則一擋不到（發佈晚於 E26 的播出日是正常的），規則二只對還在連載的 RSS Series 有用（發佈當時最近播出的是 Part 2 的那一集，E26 落後超過 `BEHIND_LATEST` → 送審核）。這是 A、B 都對、RSS 反而會錯的那一種 |
| 一集在 Specials（第 0 集、.5 集、總集篇） | 無職轉生第二季第 0 集 | `S2 - 00` 或 `- 00`：TMDB 第 2 季沒有第 0 集 → `episode_not_on_tmdb`、low → 審核；其餘各集照字面（`S2 - 01` → S02E01），Part 2 從 13 接下去照字面、從 01 重數時 cour 間隔 196 天切得開 → E13 起 | **擋得住**：照 TMDB 自己的集表，不數 AniList 的集數；那一集進審核 |
| TMDB 把一個條目拆成好幾季 | HxH 2011（148 集，TMDB 分成 62 / 74 / 12，而且各季沿用連續編號：S02 從 E63 起、S03 從 E137 起） | 字幕組多半寫絕對編號（`- 100`）：照播出序位數到第 100 集，就是 S02E100（TMDB 的編號本來就連續） | **擋得住**：照 TMDB 的集表換算，confidence 至多 medium。B 在這裡錯（把 148 集串在第 1 季），A 沒有季 |
| 撞名的重製版 | 水果籃子 2019、奇諾之旅 2017、福星小子 2022 | 自動綁定比的是那一季**播出的期間**（brief §15「綁定」、§4.4 最後一條）：2019 年的發佈不會綁到 2001 年的作品；手動送單是人挑的作品 | **擋得住**：與 B2 的「首播年最接近」是同一個道理 |
| TMDB 不在正篇的 TV 條目 | 輝夜姬 First Kiss wa Owaranai | 綁到輝夜姬之後 `- 01` 會對到 S01E01（照字面、剛播判準不成立）→ 錯季 | **規則擋不住**：靠 RSS Series 第一批審核；播出日比對的規則二只在作品還在連載時有用，這部早就播完 |

整體來看，RSS 的路與 A、B 的錯法大多不重疊：它照 TMDB 的播出日切，不吃 Fribb 的舊分季與 offset，也不數 AniList 的集數，所以 A 的四個錯與 B 的三個錯都不會原樣出現。它自己的盲點是「cour 間隔不到 180 天又從 01 重數」與「TMDB 放在 Specials 或別處的 TV 條目」，兩種都只能靠 medium 的審計旗標與第一批審核。

## 每部的表

A、B、B2、正解都寫成 TMDB 的 `SxxEyy–Ezz`。「—」是不比（非 TV 條目沒有 B、B2 與正解）。A / B / B2 欄寫對錯，錯的附差在哪。每部開頭寫 B2 搜到的作品與用的標題。

### Re:ZERO -Starting Life in Another World-（TMDB tv/65942）

熱門。TMDB 把四季併成一季；Fribb 的 offset 已知差一集；有 OVA 與劇場版。B2 搜到的作品：tv/65942 Re:ZERO -Starting Life in Another World-（2016-04-04，用「Re:ZERO -Starting Life in Another World-」搜），**對**。TMDB 的季：S00 90 集、S01 85 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21355 Re:Zero kara Hajimeru Isekai Seikatsu | TV | 25 | S01E01–E25 | S01E01–E25 | S01E01–E25 | S01E01–E25 | 對 | 對 | 對 |
| 100049 Re:Zero kara Hajimeru Isekai Seikatsu OVAs | OVA | 2 | S00E01–E02 | — | — | — | — | — | — |
| 108632 Re:Zero kara Hajimeru Isekai Seikatsu 2nd Season | TV | 13 | S01E27–E39 | S01E26–E38 | S01E26–E38 | S01E26–E38 | 錯：起點差 +1、終點差 +1 | 對 | 對 |
| 119661 Re:Zero kara Hajimeru Isekai Seikatsu 2nd Season Part 2 | TV | 12 | S01E39–E50 | S01E39–E50 | S01E39–E50 | S01E39–E50 | 對 | 對 | 對 |
| 163134 Re:Zero kara Hajimeru Isekai Seikatsu 3rd Season | TV | 16 | S01E51–E66 | S01E51–E66 | S01E51–E66 | S01E51–E66 | 對 | 對 | 對 |
| 189046 Re:Zero kara Hajimeru Isekai Seikatsu 4th Season | TV | 19 | S01E67–E85 | S01E67–E85 | S01E67–E85 | S01E67–E85 | 對 | 對 | 對 |

### JUJUTSU KAISEN（TMDB tv/95479）

熱門。TMDB 把三季併成一季；有劇場版 0。B2 搜到的作品：tv/95479 JUJUTSU KAISEN（2020-10-03，用「JUJUTSU KAISEN」搜），**對**。TMDB 的季：S00 10 集、S01 59 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 113415 Jujutsu Kaisen | TV | 24 | S01E01–E24 | S01E01–E24 | S01E01–E24 | S01E01–E24 | 對 | 對 | 對 |
| 131573 Jujutsu Kaisen 0 | MOVIE | 1 | TMDB 電影 movie/810693 | — | — | — | — | — | — |
| 145064 Jujutsu Kaisen 2nd Season | TV | 23 | S02E01–E23 | S01E25–E47 | S01E25–E47 | S01E25–E47 | 錯：季不同（S2 對 S1） | 對 | 對 |
| 192809 Jujutsu Kaisen: Kaigyoku・Gyokusetsu | MOVIE | 1 | TMDB 電影 movie/1338799 | — | — | — | — | — | — |
| 204066 Jujutsu Kaisen: Shibuya Jihen Tokubetsu Henshuu-ban × Shimetsu Kaiyuu Senkou Jouei | MOVIE | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 172463 Jujutsu Kaisen: Shimetsu Kaiyuu - Zenpen | TV | 12 | S01E48–E59 | S01E48–E59 | S01E48–E59 | S01E48–E59 | 對 | 對 | 對 |
| 209895 Jujutsu Kaisen: Shimetsu Kaiyuu - Kouhen | None | None | S01E60–? | — | — | — | — | — | — |

### Frieren: Beyond Journey's End（TMDB tv/209867）

熱門。TMDB 把兩季併成一季。B2 搜到的作品：tv/209867 Frieren: Beyond Journey's End（2023-09-29，用「Frieren: Beyond Journey’s End」搜），**對**。TMDB 的季：S00 26 集、S01 38 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 154587 Sousou no Frieren | TV | 28 | S01E01–E28 | S01E01–E28 | S01E01–E28 | S01E01–E28 | 對 | 對 | 對 |
| 170068 Sousou no Frieren: ●● no Mahou | ONA | 12 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 189513 Sousou no Frieren: ●● no Mahou Part 2 | ONA | 6 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 182255 Sousou no Frieren 2nd Season | TV | 10 | S01E29–E38 | S01E29–E38 | S01E29–E38 | S01E29–E38 | 對 | 對 | 對 |
| 206425 Sousou no Frieren: ●● no Mahou Part 3 | ONA | 6 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 209939 Sousou no Frieren 3rd Season | TV | None | S01E39–? | TMDB 的季用完了 | TMDB 的季用完了 | 無法判定（AniList 沒有完整的開播日） | 無法判定 | 無法判定 | 無法判定 |

### Dan Da Dan（TMDB tv/240411）

熱門。第二季被 TMDB 併進第一季（brief §20.3）。B2 搜到的作品：tv/240411 Dan Da Dan（2024-10-04，用「DAN DA DAN」搜），**對**。TMDB 的季：S01 24 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 171018 Dandadan | TV | 12 | S01E01–E12 | S01E01–E12 | S01E01–E12 | S01E01–E12 | 對 | 對 | 對 |
| 185660 Dandadan 2nd Season | TV | 12 | S02E01–E12 | S01E13–E24 | S01E13–E24 | S01E13–E24 | 錯：季不同（S2 對 S1） | 對 | 對 |
| 198966 Dandadan 3rd Season | TV | None | 未覆蓋（表上有，但沒有 TMDB 劇集） | TMDB 的季用完了 | TMDB 的季用完了 | 無法判定（AniList 沒有完整的開播日） | 無法判定 | 無法判定 | 無法判定 |

### Attack on Titan（TMDB tv/1429）

熱門。分割 cour（第 3 季 Part 2、Final Season 三段）、OVA 多。B2 搜到的作品：tv/1429 Attack on Titan（2013-04-07，用「Attack on Titan」搜），**對**。TMDB 的季：S00 37 集、S01 25 集、S02 12 集、S03 22 集、S04 28 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16498 Shingeki no Kyojin | TV | 25 | S01E01–E25 | S01E01–E25 | S01E01–E25 | S01E01–E25 | 對 | 對 | 對 |
| 18397 Shingeki no Kyojin OVA | OVA | 3 | S00E01–E03 | — | — | — | — | — | — |
| 20691 Shingeki no Kyojin Zenpen: Guren no Yumiya | MOVIE | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 20811 Shingeki no Kyojin Gaiden: Kuinaki Sentaku | OVA | 2 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 20692 Shingeki no Kyojin Kouhen: Jiyuu no Tsubasa | MOVIE | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 20958 Shingeki no Kyojin Season 2 | TV | 12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | 對 | 對 | 對 |
| 99634 Shingeki no Kyojin: LOST GIRLS | OVA | 3 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 100465 Shingeki no Kyojin Season 2: Kakusei no Houkou | MOVIE | 1 | S00E01–E01 | — | — | — | — | — | — |
| 99147 Shingeki no Kyojin Season 3 | TV | 12 | S03E01–E12 | S03E01–E12 | S03E01–E12 | S03E01–E12 | 對 | 對 | 對 |
| 104578 Shingeki no Kyojin Season 3 Part 2 | TV | 10 | S03E13–E22 | S03E13–E22 | S03E13–E22 | S03E13–E22 | 對 | 對 | 對 |
| 119113 Shingeki no Kyojin: Chronicle | MOVIE | 1 | TMDB 電影 movie/714194 | — | — | — | — | — | — |
| 110277 Shingeki no Kyojin: The Final Season | TV | 16 | S04E01–E16 | S04E01–E16 | S04E01–E16 | S04E01–E16 | 對 | 對 | 對 |
| 131681 Shingeki no Kyojin: The Final Season Part 2 | TV | 12 | S04E17–E28 | S04E17–E28 | S04E17–E28 | S04E17–E28 | 對 | 對 | 對 |
| 146984 Shingeki no Kyojin: The Final Season - Kanketsu-hen Zenpen | SPECIAL | 1 | S04E29–E29 | — | — | — | — | — | — |
| 162314 Shingeki no Kyojin: The Final Season - Kanketsu-hen Kouhen | SPECIAL | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |

### Mushoku Tensei: Jobless Reincarnation（TMDB tv/94664）

熱門。第二季有第 0 集、季中有總集篇；OVA 多。B2 搜到的作品：tv/94664 Mushoku Tensei: Jobless Reincarnation（2021-01-11，用「Mushoku Tensei: Jobless Reincarnation」搜），**對**。TMDB 的季：S00 3 集、S01 23 集、S02 24 集、S03 14 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 108465 Mushoku Tensei: Isekai Ittara Honki Dasu | TV | 11 | S01E01–E11 | S01E01–E11 | S01E01–E11 | S01E01–E11 | 對 | 對 | 對 |
| 127720 Mushoku Tensei: Isekai Ittara Honki Dasu Part 2 | TV | 12 | S01E12–E23 | S01E12–E23 | S01E12–E23 | S01E12–E23 | 對 | 對 | 對 |
| 141534 Mushoku Tensei: Isekai Ittara Honki Dasu Part 2 - Eris no Goblin Toubatsu | SPECIAL | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 146065 Mushoku Tensei II: Isekai Ittara Honki Dasu | TV | 13 | S02E01–E13 | S02E01–E13 | S02E01–E13 | S02E01–E12（第一集在 Specials（S00E02）） | 錯：終點差 +1 | 錯：終點差 +1 | 錯：終點差 +1 |
| 166873 Mushoku Tensei II: Isekai Ittara Honki Dasu Part 2 | TV | 12 | S02E13–E24 | S02E14–E25（超出那一季的 24 集） | S02E14–E25（超出那一季的 24 集） | S02E13–E24 | 對 | 錯：起點差 +1、終點差 +1 | 錯：起點差 +1、終點差 +1 |
| 178789 Mushoku Tensei III: Isekai Ittara Honki Dasu | TV | 14 | S03E01–E14 | S03E01–E14 | S03E01–E14 | S03E01–E14 | 對 | 對 | 對 |
| 217434 Mushoku Tensei III: Isekai Ittara Honki Dasu Part 2 | TV | None | 未覆蓋（表上有，但沒有 TMDB 劇集） | TMDB 的季用完了 | TMDB 的季用完了 | 無法判定（AniList 沒有完整的開播日） | 無法判定 | 無法判定 | 無法判定 |

### Kaguya-sama: Love Is War（TMDB tv/83121）

熱門。三季加一部劇場版（First Kiss）。B2 搜到的作品：tv/83121 Kaguya-sama: Love Is War（2019-01-12，用「Kaguya-sama: Love is War」搜），**對**。TMDB 的季：S00 6 集、S01 12 集、S02 12 集、S03 13 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 101921 Kaguya-sama wa Kokurasetai: Tensaitachi no Renai Zunousen | TV | 12 | S01E01–E12 | S01E01–E12 | S01E01–E12 | S01E01–E12 | 對 | 對 | 對 |
| 112641 Kaguya-sama wa Kokurasetai?: Tensaitachi no Renai Zunousen | TV | 12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | 對 | 對 | 對 |
| 125368 Kaguya-sama wa Kokurasetai: Tensaitachi no Renai Zunousen OVA | OVA | 1 | S00E01–E01 | — | — | — | — | — | — |
| 165557 Kaguya-sama wa Kokurasetai: Ultra Romantic 3rd Season Teaser PV - Ishigami Yuu wa Kataritai | ONA | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 125367 Kaguya-sama wa Kokurasetai: Ultra Romantic | TV | 13 | S03E01–E13 | S03E01–E13 | S03E01–E13 | S03E01–E13 | 對 | 對 | 對 |
| 151384 Kaguya-sama wa Kokurasetai: First Kiss wa Owaranai | TV | 4 | TMDB 電影 movie/997317 | TMDB 的季用完了 | TMDB 的季用完了 | 無法判定（TMDB 沒有哪一集在開播日 ±1 天播出） | 無法判定 | 無法判定 | 無法判定 |
| 194884 Kaguya-sama wa Kokurasetai: Otona e no Kaidan | SPECIAL | 2 | S00E05–E06 | — | — | — | — | — | — |
| 205081 Kaguya-sama wa Kokurasetai: Kanketsu-hen | MOVIE | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |

### SPY x FAMILY（TMDB tv/120089）

熱門。第 1 季分兩個 cour、第 2 季、劇場版 CODE: White。B2 搜到的作品：tv/120089 SPY x FAMILY（2022-04-09，用「SPY x FAMILY」搜），**對**。TMDB 的季：S00 3 集、S01 25 集、S02 12 集、S03 13 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 140960 SPY×FAMILY | TV | 12 | S01E01–E12 | S01E01–E12 | S01E01–E12 | S01E01–E12 | 對 | 對 | 對 |
| 142838 SPY×FAMILY Part 2 | TV | 13 | S01E13–E25 | S01E13–E25 | S01E13–E25 | S01E13–E25 | 對 | 對 | 對 |
| 158927 SPY×FAMILY Season 2 | TV | 12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | 對 | 對 | 對 |
| 158928 SPY×FAMILY CODE: White | MOVIE | 1 | TMDB 電影 movie/1062807 | — | — | — | — | — | — |
| 177937 SPY×FAMILY Season 3 | TV | 13 | S03E01–E13 | S03E01–E13 | S03E01–E13 | S03E01–E13 | 對 | 對 | 對 |

### Bleach（TMDB tv/30984）

熱門。千年血戰篇分三段，TMDB 接在 366 集的原作之後。B2 搜到的作品：tv/30984 Bleach（2004-10-05，用「Bleach」搜），**對**。TMDB 的季：S00 4 集、S01 366 集、S02 50 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 269 BLEACH | TV | 366 | S01E01–E366 | S01E01–E366 | S01E01–E366 | S01E01–E366 | 對 | 對 | 對 |
| 834 BLEACH: The Sealed Sword Frenzy | SPECIAL | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 1686 BLEACH: MEMORIES OF NOBODY | MOVIE | 1 | TMDB 電影 movie/15575 | — | — | — | — | — | — |
| 2889 BLEACH: The DiamondDust Rebellion - Mou Hitotsu no Hyourinmaru | MOVIE | 1 | TMDB 電影 movie/17101 | — | — | — | — | — | — |
| 100719 BLEACH Colorful!: Gotei Juusan Yatai Daisakusen! | OVA | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 4835 BLEACH: Fade to Black - Kimi no Na wo Yobu | MOVIE | 1 | TMDB 電影 movie/17165 | — | — | — | — | — | — |
| 8247 BLEACH: Jigoku-hen | MOVIE | 1 | TMDB 電影 movie/73245 | — | — | — | — | — | — |
| 116674 BLEACH: Sennen Kessen-hen | TV | 13 | S02E01–E13 | S02E01–E13 | S02E01–E13 | S02E01–E13 | 對 | 對 | 對 |
| 159322 BLEACH: Sennen Kessen-hen - Ketsubetsu-tan | TV | 13 | S02E14–E26 | S02E14–E26 | S02E14–E26 | S02E14–E26 | 對 | 對 | 對 |
| 169755 BLEACH: Sennen Kessen-hen - Soukoku-tan | TV | 14 | S02E27–E40 | S02E27–E40 | S02E27–E40 | S02E27–E40 | 對 | 對 | 對 |
| 185874 BLEACH: Sennen Kessen-hen - Kashin-tan | TV | 10 | S02E41–E50 | S02E41–E50 | S02E41–E50 | S02E41–E50 | 對 | 對 | 對 |

### The Eccentric Family（TMDB tv/61338）

冷門。兩季相隔四年。B2 搜到的作品：tv/61338 The Eccentric Family（2013-07-07，用「The Eccentric Family」搜），**對**。TMDB 的季：S01 13 集、S02 12 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 17909 Uchouten Kazoku | TV | 13 | S01E01–E13 | S01E01–E13 | S01E01–E13 | S01E01–E13 | 對 | 對 | 對 |
| 97642 Uchouten Kazoku 2 | TV | 12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | 對 | 對 | 對 |

### The Devil Is a Part-Timer!（TMDB tv/45997）

冷門。第 1 季與第 2 季相隔九年，第 2 季分兩個 cour。B2 搜到的作品：tv/45997 The Devil Is a Part-Timer!（2013-04-04，用「The Devil is a Part-Timer!」搜），**對**。TMDB 的季：S00 25 集、S01 13 集、S02 24 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15809 Hataraku Maou-sama! | TV | 13 | S01E01–E13 | S01E01–E13 | S01E01–E13 | S01E01–E13 | 對 | 對 | 對 |
| 130592 Hataraku Maou-sama!! | TV | 12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | 對 | 對 | 對 |
| 154539 Chiichai! Maou-sama!! | ONA | 24 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 155168 Hataraku Maou-sama!! 2nd Season | TV | 12 | S02E13–E24 | S02E13–E24 | S02E13–E24 | S02E13–E24 | 對 | 對 | 對 |

### Fruits Basket（TMDB tv/85991）

撞名。2019 重製版，TMDB 另有 2001 年的同名作。B2 搜到的作品：tv/85991 Fruits Basket（2019-04-06，用「Fruits Basket (2019)」搜），**對**。TMDB 的季：S01 25 集、S02 25 集、S03 13 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 105334 Fruits Basket: 1st Season | TV | 25 | S01E01–E25 | S01E01–E25 | S01E01–E25 | S01E01–E25 | 對 | 對 | 對 |
| 111762 Fruits Basket: 2nd Season | TV | 25 | S02E01–E25 | S02E01–E25 | S02E01–E25 | S02E01–E25 | 對 | 對 | 對 |
| 124194 Fruits Basket: The Final | TV | 13 | S03E01–E13 | S03E01–E13 | S03E01–E13 | 無法判定（TMDB 沒有哪一集在開播日 ±1 天播出） | 無法判定 | 無法判定 | 無法判定 |
| 136192 Fruits Basket: prelude | MOVIE | 1 | TMDB 電影 movie/896499 | — | — | — | — | — | — |

### Hunter x Hunter（TMDB tv/46298）

撞名。2011 重製版，TMDB 另有 1999 年的同名作。B2 搜到的作品：tv/46298 Hunter x Hunter（2011-10-02，用「Hunter x Hunter (2011)」搜），**對**。TMDB 的季：S01 62 集、S02 74 集、S03 12 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11061 HUNTER×HUNTER (2011) | TV | 148 | 未覆蓋（有 TMDB 劇集 tv/46298，沒有季） | S01E01–E148（超出那一季的 62 集） | S01E01–E148（超出那一季的 62 集） | S01E01–S03E148 | 未覆蓋 | 錯：正解跨季（S01E01–S03E148） | 錯：正解跨季（S01E01–S03E148） |
| 13271 HUNTER×HUNTER: Phantom Rouge | MOVIE | 1 | S00E01–E01 | — | — | — | — | — | — |
| 19951 HUNTER×HUNTER: THE LAST MISSION | MOVIE | 1 | S00E02–E02 | — | — | — | — | — | — |

### Urusei Yatsura（TMDB tv/154524）

撞名。2022 重製版，TMDB 另有 1981 年的同名作。B2 搜到的作品：tv/154524 Urusei Yatsura（2022-10-14，用「Urusei Yatsura (2022)」搜），**對**。TMDB 的季：S01 46 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 143277 Urusei Yatsura (2022) | TV | 23 | S01E01–E23 | S01E01–E23 | S01E01–E23 | S01E01–E23 | 對 | 對 | 對 |
| 155645 Urusei Yatsura (2022) 2nd Season | TV | 23 | S01E24–E46 | S01E24–E46 | S01E24–E46 | S01E24–E46 | 對 | 對 | 對 |

### Kino's Journey -the Beautiful World- the Animated Series（TMDB tv/74097）

撞名。2017 重製版，TMDB 另有 2003 年的奇諾之旅。B2 搜到的作品：tv/74097 Kino's Journey -the Beautiful World- the Animated Series（2017-10-06，用「Kino's Journey -the Beautiful World- the Animated Series」搜），**對**。TMDB 的季：S01 12 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 108973 Kino no Tabi -the Beautiful World- Haikyo no Kuni | SPECIAL | 27 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 98448 Kino no Tabi -the Beautiful World- the Animated Series | TV | 12 | S01E01–E12 | S01E01–E12 | S01E01–E12 | S01E01–E12 | 對 | 對 | 對 |

### Tamako Market（TMDB tv/48561）

冷門。只有劇場版接續（Tamako Love Story）。B2 搜到的作品：tv/48561 Tamako Market（2013-01-10，用「Tamako Market」搜），**對**。TMDB 的季：S00 13 集、S01 12 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16417 Tamako Market | TV | 12 | S01E01–E12 | S01E01–E12 | S01E01–E12 | S01E01–E12 | 對 | 對 | 對 |
| 17879 Tamako Market Specials | SPECIAL | 6 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 20519 Tamako Love Story | MOVIE | 1 | S00E01–E01 | — | — | — | — | — | — |
| 21014 Minami no Shima no Dera-chan | SPECIAL | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |

### Made in Abyss（TMDB tv/72636）

冷門。兩季之間夾一部劇場版接續（深き魂の黎明）。B2 搜到的作品：tv/72636 Made in Abyss（2017-07-07，用「Made in Abyss」搜），**對**。TMDB 的季：S00 5 集、S01 13 集、S02 12 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） | B2（串接，作品靠搜尋） | 正解 | A | B | B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 97986 Made in Abyss | TV | 13 | S01E01–E13 | S01E01–E13 | S01E01–E13 | S01E01–E13 | 對 | 對 | 對 |
| 101343 Made in Abyss: Tabidachi no Yoake | MOVIE | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 101344 Made in Abyss: Hourou Suru Tasogare | MOVIE | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 100643 Made in Abyss: Fukaki Tamashii no Reimei | MOVIE | 1 | TMDB 電影 movie/573730 | — | — | — | — | — | — |
| 114744 Marulk-chan no Nichijou | SPECIAL | 4 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 114745 Made in Abyss: Retsujitsu no Ougonkyou | TV | 12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | 對 | 對 | 對 |
| 153791 Made in Abyss: Retsujitsu no Ougonkyou - Papa to Issho | SPECIAL | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 160275 Made in Abyss: Mezameru Shinpi | MOVIE | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
| 218721 Made in Abyss: Mezameru Shinpi Part 2 | MOVIE | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集） | — | — | — | — | — | — |
