# 有 Fribb 與沒 Fribb：AniList 條目對到 TMDB 季集的兩種算法（2026-10-28）

不是票；票 16 之後使用者要看「有 Fribb 對沒 Fribb」的差別。腳本 `scripts/experiments/fribb_vs_chaining.py`（可重跑，回應快取在 `.local/experiments/cache/fribb_vs_chaining/`），原始數據 `docs/research/fribb-vs-chaining-2026-10-28.json`。只打 AniList、TMDB 與 Fribb 的表，不經任何 AI 模型。

## 結論

11 部、74 個 AniList 條目，其中 44 個 `TV` 條目拿來比；4 個無法判定，剩 **40 個判得出正解**。

| | 對 | 錯 | 無法判定 |
| --- | --- | --- | --- |
| **A：Fribb**（`season.tmdb` + `episode_offset.tmdb`） | **36** | **4** | 4 |
| **B：串接**（AniList 集數照開播日串，`series-mapping` 的退路） | **38** | **2** | 4 |

- **A 錯的四個，兩種原因**：
  - **TMDB 後來把季併了，Fribb 還照舊**（2 個）：咒術迴戰第 2 季、膽大黨第 2 季，Fribb 寫 `season.tmdb: 2`（與 TVDB 的分季相同），TMDB 現在只有一季（59 集、24 集），正解是 S01E25–E47、S01E13–E24。同一部的咒術迴戰「死滅迴游」是新條目，Fribb 就對了（S01E48–E59）——舊條目沒有跟著 TMDB 的改版更新。
  - **offset 差一集**（2 個）：Re:Zero 第 2 季 `offset 26`（應是 25，起點與終點都 +1，brief §20.3 已記）；無職轉生第二季把第 0 集算進 AniList 的 13 集，而 TMDB 把第 0 集放進 Specials（S00E02），Fribb 給 S02E01–E13，正解 S02E01–E12（終點 +1，與 Part 2 的 E13 重疊）。
- **B 錯的兩個，一種原因**：**有一集不在正篇**。無職轉生第二季的第 0 集在 Specials，串接照 AniList 的 13 集往下數，這一季終點多一集、Part 2 整段往後推一集（S02E14–E25，超出那一季的 24 集——腳本會標「超出」）。總集篇、.5 集被 TMDB 放進 Specials 的都會這樣錯；這次的樣本裡只有這一種。
- **Fribb 沒覆蓋的 TV 條目 3 個**，全在無法判定那四個裡：兩個還沒開播（膽大黨第 3 季、無職轉生第三季 Part 2），一個 TMDB 不在正篇（輝夜姬「First Kiss wa Owaranai」，AniList 記成 4 集的 TV）。第四個無法判定的芙莉蓮第 3 季 Fribb 有、但還沒開播。
- **兩種一起用，樣本裡的錯都看得出來**：A 與 B 不一致的 4 列（Re:Zero 第 2 季、咒術迴戰第 2 季、膽大黨第 2 季、無職轉生第二季 Part 2）每一列都恰好一邊錯，Part 2 那一列 B 還標了「超出那一季的 24 集」。兩邊一致卻都錯的只有無職轉生第二季，而它與 Part 2 在同一季——把「有一列被標」的整季拿出來看，6 個錯都看得到。被標的列裡沒有兩邊都對的（沒有誤報）。
- **劇場版與 OVA 不比**（30 個非 TV 條目）：用播出日對 Specials 或正篇常是巧合（SPY×FAMILY CODE: White 上映那天正好播了 S02E12），所以只列 Fribb 的對法。13 部劇場版裡 Fribb 對到 TMDB 電影的 8 部；OVA、特別篇多半對到 Specials 或沒有。Re:Zero 的兩部劇場版不在 AniList 的系列圖裡（Memory Snow 算在 OVA 條目 100049），與研究 08 §2.1 相同。

對產品的意思：

- **skill 照現在寫的就對**：Fribb 做主、用集數串起來檢查。這份數據支持把「檢查」寫得更具體——**Fribb 與串接不一致、或串接超出 TMDB 那一季的集數時，那一整季標出來請人確認**；整季都一致、也沒超出的，樣本裡全對。目前 `series-mapping` 第 3 步只說「範圍重疊或有縫時用集數串起來」，沒說「Fribb 指到的季在 TMDB 上的位置跟串接不一樣」也要停下來；要不要改由使用者決定，這份檔案只給數據。
- **Fribb 抓不到時的退路（B）比 Fribb 還準一點**，但它會錯在 Fribb 不會錯的地方（一集在 Specials），反之亦然，所以退路的表要標「未經對照表」是對的。

## 方法

- **系列**：從每部的一個 AniList 條目沿 `SEQUEL`、`PREQUEL`、`SIDE_STORY`、`PARENT`、`SUMMARY` 走（同 `anilist.read_franchise` 的預設，不含衍生作），一層問一次，每次間隔 2.5 秒。
- **TMDB 劇集是手挑的**（不取自 Fribb），A 對到別的劇集算錯。
- **A**：起點 `offset.tmdb + 1`（沒有 offset 是 1）、終點起點 + AniList 集數 − 1、季是 `season.tmdb`。
- **B**：TV 條目照開播日排，從 S01E01 起依 AniList 集數一個接一個；一季的集數（TMDB `seasons[].episode_count`）用完，下一個條目從下一季 E01 起。
- **正解**：AniList 條目的 `startDate` 對 TMDB 播出日相同的那一集，先找正篇（第 1 季起）、找不到才看 Specials；`endDate` 對同一季裡播出日相同的最後一集。**容忍 ±1 天**：AniList 記的是日本首播日，深夜檔（「25:30」）在 TMDB 常記成前一天或後一天；週播兩集相隔 7 天，±1 天不會撞到隔壁那一集。同一天兩集（首播連播、串流一次放完）起點取最小、終點取最大。第一集被放進 Specials、完結日在正篇的（無職轉生第二季的第 0 集），正解取正篇那一季、開播日之後的第一集起，Specials 那一集另外註明。對不到的那一端寫「無法判定」，那一列不算對錯；只知道開播日、還沒完結的只比季與起點（這次沒有這種）。
- **挑的作品**：Re:Zero（必選；TMDB 四季併成一季）、咒術迴戰與芙莉蓮與膽大黨（TMDB 併季）、進擊的巨人（分割 cour、OVA 多）、無職轉生（第 0 集、OVA）、輝夜姬（三季加劇場版）、SPY×FAMILY（分 cour、劇場版）、死神（千年血戰篇三段接在 366 集之後）、有頂天家族與打工吧！魔王大人（冷門；後者第 2 季分兩個 cour、與第 1 季相隔九年）。**沒挑到「季中夾總集篇、TMDB 算進正篇」的作品**：無職轉生第一季的總集篇在 AniList 是另一個 SPECIAL 條目，不影響 TV 條目的集數。

## 走 RSS 現在的路擋不擋得住（照 plan §4.4 推論，沒有實跑解析器）

先講清楚範圍：A、B 只出現在側面板的 `series-mapping`，影響的是**挑哪些 torrent、卡片上寫哪一季**；卡片送單只帶 `source_id`、`media_id`、`route_id`，入庫的季集由規劃器照檔名重算（§4.4 的那幾條），不吃 A、B 的範圍。RSS 那條路也一樣不用 Fribb、不用 AniList，靠的是 TMDB 各集的播出日。所以下面問的是：**同樣的作品走 RSS（或手動送單之後的規劃），這幾種錯法會不會出現、出現了誰擋**。

| 錯法 | 例 | RSS 的路 | 擋不擋得住 |
| --- | --- | --- | --- |
| TMDB 併季、資料還照舊分季 | 咒術迴戰第 2 季、膽大黨第 2 季 | `2nd Season - 05`、`S2 - 05`：TMDB 沒有第 2 季 → 照 > 180 天的間隔切虛擬季（咒術迴戰 2021-03 → 2023-07、膽大黨 2024-12 → 2025-07，兩部都超過 180 天）→ 對到 S01E29、S01E17；季內連號（`- 29`）照字面就對 | **擋得住**：本來就照 TMDB 的播出日切，不會沿用舊分季；confidence 至多 medium、第一批審核 |
| offset 差一集 | Re:Zero 第 2 季 | 不用 offset：`2nd Season - 01` 照虛擬季對到 E26 | **擋得住**：這一種錯法 RSS 不會產生 |
| 同一季裡的 cour 間隔不到 180 天 | Re:Zero 第 2 季 Part 2（2020-09-30 → 2021-01-06，98 天） | `2nd Season Part 2 - 01`：Part 標記要「同一季前面幾個 cour 的長度」，而 cour 的切法也是 > 180 天，98 天切不開 → 偏移加不上去、超出時照字面讀，多半讀成 E26 | **規則擋不住，靠人**：medium、第一批審核；播出日比對的規則一擋不到（發佈晚於 E26 的播出日是正常的），規則二只對還在連載的 RSS Series 有用（發佈當時最近播出的是 Part 2 的那一集，E26 落後超過 `BEHIND_LATEST` → 送審核）。這是 A、B 都對、RSS 反而會錯的那一種 |
| 一集在 Specials（第 0 集、.5 集、總集篇） | 無職轉生第二季第 0 集 | `S2 - 00` 或 `- 00`：TMDB 第 2 季沒有第 0 集 → `episode_not_on_tmdb`、low → 審核；其餘各集照字面（`S2 - 01` → S02E01），Part 2 從 13 接下去照字面、從 01 重數時 cour 間隔 196 天切得開 → E13 起 | **擋得住**：照 TMDB 自己的集表，不數 AniList 的集數；那一集進審核 |
| TMDB 不在正篇的 TV 條目 | 輝夜姬 First Kiss wa Owaranai | 綁到輝夜姬之後 `- 01` 會對到 S01E01（照字面、剛播判準不成立）→ 錯季 | **規則擋不住**：靠 RSS Series 第一批審核；播出日比對的規則二只在作品還在連載時有用，這部早就播完 |

整體來看，RSS 的路與 A、B 的錯法大多不重疊：它照 TMDB 的播出日切，不吃 Fribb 的舊分季與 offset，也不數 AniList 的集數，所以 A 的四個錯與 B 的兩個錯都不會原樣出現。它自己的盲點是「cour 間隔不到 180 天又從 01 重數」與「TMDB 放在 Specials 或別處的 TV 條目」，兩種都只能靠 medium 的審計旗標與第一批審核。

## 每部的表

A、B、正解都寫成 TMDB 的 `SxxEyy–Ezz`。「—」是不比（非 TV 條目沒有 B 與正解）。A / B 欄寫對錯，錯的附差在哪。

### Re:ZERO -Starting Life in Another World-（TMDB tv/65942）

TMDB 把四季併成一季；Fribb 的 offset 已知差一集；有 OVA 與劇場版。TMDB 的季：S00 90 集、S01 85 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接） | 正解 | A | B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 21355 Re:Zero kara Hajimeru Isekai Seikatsu | TV | 25 | S01E01–E25 | S01E01–E25 | S01E01–E25 | 對 | 對 |
| 100049 Re:Zero kara Hajimeru Isekai Seikatsu OVAs | OVA | 2 | S00E01–E02 | — | — | — | — |
| 108632 Re:Zero kara Hajimeru Isekai Seikatsu 2nd Season | TV | 13 | S01E27–E39 | S01E26–E38 | S01E26–E38 | 錯：起點差 +1、終點差 +1 | 對 |
| 119661 Re:Zero kara Hajimeru Isekai Seikatsu 2nd Season Part 2 | TV | 12 | S01E39–E50 | S01E39–E50 | S01E39–E50 | 對 | 對 |
| 163134 Re:Zero kara Hajimeru Isekai Seikatsu 3rd Season | TV | 16 | S01E51–E66 | S01E51–E66 | S01E51–E66 | 對 | 對 |
| 189046 Re:Zero kara Hajimeru Isekai Seikatsu 4th Season | TV | 19 | S01E67–E85 | S01E67–E85 | S01E67–E85 | 對 | 對 |

### JUJUTSU KAISEN（TMDB tv/95479）

TMDB 把三季併成一季；有劇場版 0。TMDB 的季：S00 10 集、S01 59 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接） | 正解 | A | B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 113415 Jujutsu Kaisen | TV | 24 | S01E01–E24 | S01E01–E24 | S01E01–E24 | 對 | 對 |
| 131573 Jujutsu Kaisen 0 | MOVIE | 1 | TMDB 電影 movie/810693 | — | — | — | — |
| 145064 Jujutsu Kaisen 2nd Season | TV | 23 | S02E01–E23 | S01E25–E47 | S01E25–E47 | 錯：季不同（S2 對 S1） | 對 |
| 192809 Jujutsu Kaisen: Kaigyoku・Gyokusetsu | MOVIE | 1 | TMDB 電影 movie/1338799 | — | — | — | — |
| 204066 Jujutsu Kaisen: Shibuya Jihen Tokubetsu Henshuu-ban × Shimetsu Kaiyuu Senkou Jouei | MOVIE | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |
| 172463 Jujutsu Kaisen: Shimetsu Kaiyuu - Zenpen | TV | 12 | S01E48–E59 | S01E48–E59 | S01E48–E59 | 對 | 對 |
| 209895 Jujutsu Kaisen: Shimetsu Kaiyuu - Kouhen | None | None | S01E60–? | — | — | — | — |

### Frieren: Beyond Journey's End（TMDB tv/209867）

TMDB 把兩季併成一季。TMDB 的季：S00 26 集、S01 38 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接） | 正解 | A | B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 154587 Sousou no Frieren | TV | 28 | S01E01–E28 | S01E01–E28 | S01E01–E28 | 對 | 對 |
| 170068 Sousou no Frieren: ●● no Mahou | ONA | 12 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |
| 189513 Sousou no Frieren: ●● no Mahou Part 2 | ONA | 6 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |
| 182255 Sousou no Frieren 2nd Season | TV | 10 | S01E29–E38 | S01E29–E38 | S01E29–E38 | 對 | 對 |
| 206425 Sousou no Frieren: ●● no Mahou Part 3 | ONA | 6 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |
| 209939 Sousou no Frieren 3rd Season | TV | None | S01E39–? | TMDB 的季用完了 | 無法判定（AniList 沒有完整的開播日） | 無法判定 | 無法判定 |

### Dan Da Dan（TMDB tv/240411）

第二季被 TMDB 併進第一季（brief §20.3）。TMDB 的季：S01 24 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接） | 正解 | A | B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 171018 Dandadan | TV | 12 | S01E01–E12 | S01E01–E12 | S01E01–E12 | 對 | 對 |
| 185660 Dandadan 2nd Season | TV | 12 | S02E01–E12 | S01E13–E24 | S01E13–E24 | 錯：季不同（S2 對 S1） | 對 |
| 198966 Dandadan 3rd Season | TV | None | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | TMDB 的季用完了 | 無法判定（AniList 沒有完整的開播日） | 無法判定 | 無法判定 |

### Attack on Titan（TMDB tv/1429）

分割 cour（第 3 季 Part 2、Final Season 三段）、OVA 多。TMDB 的季：S00 37 集、S01 25 集、S02 12 集、S03 22 集、S04 28 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接） | 正解 | A | B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 16498 Shingeki no Kyojin | TV | 25 | S01E01–E25 | S01E01–E25 | S01E01–E25 | 對 | 對 |
| 18397 Shingeki no Kyojin OVA | OVA | 3 | S00E01–E03 | — | — | — | — |
| 20691 Shingeki no Kyojin Zenpen: Guren no Yumiya | MOVIE | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |
| 20811 Shingeki no Kyojin Gaiden: Kuinaki Sentaku | OVA | 2 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |
| 20692 Shingeki no Kyojin Kouhen: Jiyuu no Tsubasa | MOVIE | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |
| 20958 Shingeki no Kyojin Season 2 | TV | 12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | 對 | 對 |
| 99634 Shingeki no Kyojin: LOST GIRLS | OVA | 3 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |
| 100465 Shingeki no Kyojin Season 2: Kakusei no Houkou | MOVIE | 1 | S00E01–E01 | — | — | — | — |
| 99147 Shingeki no Kyojin Season 3 | TV | 12 | S03E01–E12 | S03E01–E12 | S03E01–E12 | 對 | 對 |
| 104578 Shingeki no Kyojin Season 3 Part 2 | TV | 10 | S03E13–E22 | S03E13–E22 | S03E13–E22 | 對 | 對 |
| 119113 Shingeki no Kyojin: Chronicle | MOVIE | 1 | TMDB 電影 movie/714194 | — | — | — | — |
| 110277 Shingeki no Kyojin: The Final Season | TV | 16 | S04E01–E16 | S04E01–E16 | S04E01–E16 | 對 | 對 |
| 131681 Shingeki no Kyojin: The Final Season Part 2 | TV | 12 | S04E17–E28 | S04E17–E28 | S04E17–E28 | 對 | 對 |
| 146984 Shingeki no Kyojin: The Final Season - Kanketsu-hen Zenpen | SPECIAL | 1 | S04E29–E29 | — | — | — | — |
| 162314 Shingeki no Kyojin: The Final Season - Kanketsu-hen Kouhen | SPECIAL | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |

### Mushoku Tensei: Jobless Reincarnation（TMDB tv/94664）

第二季有第 0 集、季中有總集篇；OVA 多。TMDB 的季：S00 3 集、S01 23 集、S02 24 集、S03 14 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接） | 正解 | A | B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 108465 Mushoku Tensei: Isekai Ittara Honki Dasu | TV | 11 | S01E01–E11 | S01E01–E11 | S01E01–E11 | 對 | 對 |
| 127720 Mushoku Tensei: Isekai Ittara Honki Dasu Part 2 | TV | 12 | S01E12–E23 | S01E12–E23 | S01E12–E23 | 對 | 對 |
| 141534 Mushoku Tensei: Isekai Ittara Honki Dasu Part 2 - Eris no Goblin Toubatsu | SPECIAL | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |
| 146065 Mushoku Tensei II: Isekai Ittara Honki Dasu | TV | 13 | S02E01–E13 | S02E01–E13 | S02E01–E12（第一集在 Specials（S00E02）） | 錯：終點差 +1 | 錯：終點差 +1 |
| 166873 Mushoku Tensei II: Isekai Ittara Honki Dasu Part 2 | TV | 12 | S02E13–E24 | S02E14–E25（超出那一季的 24 集） | S02E13–E24 | 對 | 錯：起點差 +1、終點差 +1 |
| 178789 Mushoku Tensei III: Isekai Ittara Honki Dasu | TV | 14 | S03E01–E14 | S03E01–E14 | S03E01–E14 | 對 | 對 |
| 217434 Mushoku Tensei III: Isekai Ittara Honki Dasu Part 2 | TV | None | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | TMDB 的季用完了 | 無法判定（AniList 沒有完整的開播日） | 無法判定 | 無法判定 |

### Kaguya-sama: Love Is War（TMDB tv/83121）

三季加一部劇場版（First Kiss）。TMDB 的季：S00 6 集、S01 12 集、S02 12 集、S03 13 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接） | 正解 | A | B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 101921 Kaguya-sama wa Kokurasetai: Tensaitachi no Renai Zunousen | TV | 12 | S01E01–E12 | S01E01–E12 | S01E01–E12 | 對 | 對 |
| 112641 Kaguya-sama wa Kokurasetai?: Tensaitachi no Renai Zunousen | TV | 12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | 對 | 對 |
| 125368 Kaguya-sama wa Kokurasetai: Tensaitachi no Renai Zunousen OVA | OVA | 1 | S00E01–E01 | — | — | — | — |
| 165557 Kaguya-sama wa Kokurasetai: Ultra Romantic 3rd Season Teaser PV - Ishigami Yuu wa Kataritai | ONA | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |
| 125367 Kaguya-sama wa Kokurasetai: Ultra Romantic | TV | 13 | S03E01–E13 | S03E01–E13 | S03E01–E13 | 對 | 對 |
| 151384 Kaguya-sama wa Kokurasetai: First Kiss wa Owaranai | TV | 4 | TMDB 電影 movie/997317 | TMDB 的季用完了 | 無法判定（TMDB 沒有哪一集在開播日 ±1 天播出） | 無法判定 | 無法判定 |
| 194884 Kaguya-sama wa Kokurasetai: Otona e no Kaidan | SPECIAL | 2 | S00E05–E06 | — | — | — | — |
| 205081 Kaguya-sama wa Kokurasetai: Kanketsu-hen | MOVIE | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |

### SPY x FAMILY（TMDB tv/120089）

第 1 季分兩個 cour、第 2 季、劇場版 CODE: White。TMDB 的季：S00 3 集、S01 25 集、S02 12 集、S03 13 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接） | 正解 | A | B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 140960 SPY×FAMILY | TV | 12 | S01E01–E12 | S01E01–E12 | S01E01–E12 | 對 | 對 |
| 142838 SPY×FAMILY Part 2 | TV | 13 | S01E13–E25 | S01E13–E25 | S01E13–E25 | 對 | 對 |
| 158927 SPY×FAMILY Season 2 | TV | 12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | 對 | 對 |
| 158928 SPY×FAMILY CODE: White | MOVIE | 1 | TMDB 電影 movie/1062807 | — | — | — | — |
| 177937 SPY×FAMILY Season 3 | TV | 13 | S03E01–E13 | S03E01–E13 | S03E01–E13 | 對 | 對 |

### Bleach（TMDB tv/30984）

千年血戰篇分三段，TMDB 接在 366 集的原作之後。TMDB 的季：S00 4 集、S01 366 集、S02 50 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接） | 正解 | A | B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 269 BLEACH | TV | 366 | S01E01–E366 | S01E01–E366 | S01E01–E366 | 對 | 對 |
| 834 BLEACH: The Sealed Sword Frenzy | SPECIAL | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |
| 1686 BLEACH: MEMORIES OF NOBODY | MOVIE | 1 | TMDB 電影 movie/15575 | — | — | — | — |
| 2889 BLEACH: The DiamondDust Rebellion - Mou Hitotsu no Hyourinmaru | MOVIE | 1 | TMDB 電影 movie/17101 | — | — | — | — |
| 100719 BLEACH Colorful!: Gotei Juusan Yatai Daisakusen! | OVA | 1 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |
| 4835 BLEACH: Fade to Black - Kimi no Na wo Yobu | MOVIE | 1 | TMDB 電影 movie/17165 | — | — | — | — |
| 8247 BLEACH: Jigoku-hen | MOVIE | 1 | TMDB 電影 movie/73245 | — | — | — | — |
| 116674 BLEACH: Sennen Kessen-hen | TV | 13 | S02E01–E13 | S02E01–E13 | S02E01–E13 | 對 | 對 |
| 159322 BLEACH: Sennen Kessen-hen - Ketsubetsu-tan | TV | 13 | S02E14–E26 | S02E14–E26 | S02E14–E26 | 對 | 對 |
| 169755 BLEACH: Sennen Kessen-hen - Soukoku-tan | TV | 14 | S02E27–E40 | S02E27–E40 | S02E27–E40 | 對 | 對 |
| 185874 BLEACH: Sennen Kessen-hen - Kashin-tan | TV | 10 | S02E41–E50 | S02E41–E50 | S02E41–E50 | 對 | 對 |

### The Eccentric Family（TMDB tv/61338）

冷門：兩季相隔四年。TMDB 的季：S01 13 集、S02 12 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接） | 正解 | A | B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 17909 Uchouten Kazoku | TV | 13 | S01E01–E13 | S01E01–E13 | S01E01–E13 | 對 | 對 |
| 97642 Uchouten Kazoku 2 | TV | 12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | 對 | 對 |

### The Devil Is a Part-Timer!（TMDB tv/45997）

冷門：第 1 季與第 2 季相隔九年，第 2 季分兩個 cour。TMDB 的季：S00 25 集、S01 13 集、S02 24 集。

| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接） | 正解 | A | B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 15809 Hataraku Maou-sama! | TV | 13 | S01E01–E13 | S01E01–E13 | S01E01–E13 | 對 | 對 |
| 130592 Hataraku Maou-sama!! | TV | 12 | S02E01–E12 | S02E01–E12 | S02E01–E12 | 對 | 對 |
| 154539 Chiichai! Maou-sama!! | ONA | 24 | 未覆蓋（表上有，但沒有 TMDB 劇集或季） | — | — | — | — |
| 155168 Hataraku Maou-sama!! 2nd Season | TV | 12 | S02E13–E24 | S02E13–E24 | S02E13–E24 | 對 | 對 |
