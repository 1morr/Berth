# 時間表的資料源：TMDB discover 對 Bangumi 放送表（2026-11-04）

M5.5 票 08。問題：時間表（spec〈範圍〉「時間表」）以 TMDB 為主幹時，列得出幾成當季新番？九成以上照 TMDB，低於九成改以 Bangumi 為主幹。腳本 `scripts/experiments/schedule_sources.py`，指令在 `docs/development/experiments.md`；原始回應與結果 JSON 在 `.local/experiments/`（不進版控）。

## 結論

- **主幹照 TMDB**。判定用的分母是「Bangumi 放送表上的日本作品、Bangumi 說這一週有一集」（使用者定，2026-11-04）：這一週 71/76 = **93.4%**，上一週 69/76 = **90.8%**。
- 給票 09 的條件：`discover/tv`，`with_genres=16`、`with_original_language=ja|zh`、`air_date.gte` 為週一**前一天**、`air_date.lte` 為週日**後一天**。放寬一天是因為深夜檔（「25:00」）兩邊常差一天，週一凌晨的集會掉到隔壁那一週；不放寬是 92.1% / 89.5%，所以上一週是靠放寬一天才過線，結論在線邊，換季要重量。`ja|zh` 對日本作品與只用 `ja` 一樣，另外多列得出有 TMDB 條目的國產動畫（這週有集的 6 部中 5 部、上週 7 部中 5 部）。
- 漏掉的日本作品沒有一般的深夜番：都是 WEB 迷你動畫、兒童節目，以及 TMDB 沒跟上的集（清單在下面）。TMDB 上沒有的作品也點不進 `/media/:id`、訂閱不了，所以改用 Bangumi 當主幹，多出來的也只是看得到、按不下去的卡片。

## 做法

1. Bangumi `GET /calendar`（當季放送表，114 部），每部讀 `GET /v0/subjects/{id}` 的 `meta_tags` 分產地（日本 86、中國 12、其他 16）與平台（TV / WEB），讀 `GET /v0/episodes?subject_id=…&type=0` 的正篇播出日，判斷那一週有沒有一集。
2. 每個窗口（這一週 2026-11-02 – 11-08、上一週 10-26 – 11-01）跑六組 discover，全部頁數都抓，`language=zh-CN`（只為了對 Bangumi 的中文名，不是時間表要用的語言）。
3. 每部 Bangumi 作品先找 TMDB id：原名對 `original_name`、中文名對 `name`，拿掉季號（第 N 期、Season N、第 N シリーズ、伍…）壓平後相同，或較短的一邊（≥ 4 字）是另一邊的開頭；對不到再打 `search/tv`（全名、中文名、拿掉季號的原名、第一個詞）。**衍生作記號**（ミニアニメ、迷你、特別篇、劇場版、MV）一邊有、另一邊沒有，就不算同一部。第一輪把迷你動畫對到本篇，這條規則就是因此加上的。列得出的意思是「這個 id 在那一組 discover 的結果裡」。
4. 全部 114 筆對應都人工看過（輸出的「對應」段）。第一輪找不到、後來補上的：Welsh & Shedar（TMDB 中文名寫「与」）、ぷにるんず ぷに４（TMDB 只有一部）、おしりたんてい 第11シリーズ、牧神记 伍。

`air_date.gte/lte` 官方沒說篩什麼（[Discover TV](https://developer.themoviedb.org/reference/discover-tv) 的參數都沒有說明）。實測是「這段期間有一集播出」：柯南、小丸子都會列。`tv/on_the_air` 不分類型（2026-11-04 實測 1703 筆、86 頁），所以不拿來比。

## 數字

覆蓋率＝列得出的 / 分母。

| 分母 | 這一週 | 上一週 |
| --- | --- | --- |
| 日本、Bangumi 這週有集（判定用；`ja|zh` 放寬一天） | 71/76 = 93.4% | 69/76 = 90.8% |
| 同上，不放寬（`ja`、`ja|zh`、`JP`、只篩動畫都一樣） | 70/76 = 92.1% | 68/76 = 89.5% |
| 日本 TV（不看 Bangumi 有沒有集；放寬一天） | 72/77 = 93.5% | 72/77 = 93.5% |
| 日本全部（含這週沒集、沒播出日的；放寬一天） | 74/86 = 86.0% | 72/86 = 83.7% |
| 不分產地、Bangumi 這週有集（`ja|zh` 放寬一天） | 76/86 = 88.4% | 74/88 = 84.1% |
| Bangumi 放送表全部（`ja|zh` 放寬一天） | 79/114 = 69.3% | 77/114 = 67.5% |

discover 筆數（這一週）：只篩動畫 193、`ja` 92、`ja|zh` 162、`JP` 93、`ja` 放寬一天 94、`ja|zh` 放寬一天 164。`with_original_language=ja` 與 `with_origin_country=JP` 列出的日本作品相同。

## 漏掉的作品（判定用的分母）

這一週（5 部）：

- 猫猫のひとりごと 第3期（WEB 迷你動畫，bgm 707667）：TMDB 查不到。
- ミニアニメ「ホタルの嫁入り」ちょいたし（WEB 迷你動畫，bgm 713219）：TMDB 只有本篇 320909。
- ダークサモナーとデキている ミニアニメ劇場（WEB 迷你動畫，bgm 708612）：TMDB 只有本篇 335790。
- シルバニアファミリー フレアのカラフル・エブリデイ（TV 兒童，bgm 704737）：TMDB 查不到（只有 2017、2022 的前作）。
- ぷにるんず ぷに４（TV 兒童，bgm 646586）：TMDB 209198 的集停在 2025-12-27，第四期還沒建。

上一週多 2 部：歯ならび～ズ（WEB 短篇，bgm 716367，TMDB 查不到）、凶乱令嬢 ニア・リストンミニ（WEB 迷你動畫，bgm 716967，TMDB 只有本篇 312850）。

不在分母但也沒列的日本作品（這一週）：PSYREN、ふんばるず、ONE PIECE（Bangumi 這週也沒集；ONE PIECE 的 TMDB 最後一集是 2026-09-27）、わたしの幸せな結婚 特別篇（TMDB 只有本篇）、Cyberpunk: Edgerunners 2（TMDB 原文是 `en`）、プロセカ 6 周年 MV（不是劇集）。

非日本的 28 部：國產 12 部中列得出 5 部。漏掉的 7 部裡，5 部 TMDB 查不到（都市古医仙2 在 TMDB 寫成「都市古仙医」273263，兩邊的字序不同），熊出没之神奇宝物2 沒標類型，肥志百科的 TMDB 集停在 2026-04；其他 16 部是歐美卡通與特別篇（原文 `en`、`fr`、`es`），`ja|zh` 本來就不收。

## 反方向：discover 列了、放送表沒有

`ja|zh` 放寬一天，這一週 164 部裡 85 部不在 Bangumi 放送表上（`zh` 65、`ja` 20），上一週 107 部（`zh` 79、`ja` 28）。

- `zh`：國產動畫，Bangumi 放送表只收了 12 部。
- `ja`：長壽與兒童節目（ちびまる子ちゃん、ポケットモンスター、BEYBLADE X、プリキュア、リラックマ…），以及夏季開播、TMDB 這週仍有集的作品（追放された転生重騎士はゲーム知識で無双する、天は赤い河のほとり、うちの弟どもがすみません）。

所以 discover 的清單約一半不是 Bangumi 意義的「當季新番」。時間表預設列全部（spec），這些也會出現。要不要篩（例如 `first_air_date` 或 `popularity`）留給票 09 依版面決定，這裡只給數字。

## 給票 09 的事實

- discover 的每一筆只有 `id`、`name`、`original_name`、`original_language`、`origin_country`、`first_air_date`、`genre_ids`、`poster_path`、`popularity` 等，**沒有哪一集、哪一天播**。要放進週一到週日的欄、寫第幾集，得每部再讀 `tv/{id}` 的 `last_episode_to_air` / `next_episode_to_air`（或季詳情）。`ja|zh` 放寬一天是 9 頁加 164 部，在全域每秒 40 次的桶裡約 5 秒，結果進 `TtlCache`。
- Bangumi 的播出日與 TMDB 常差一天（深夜檔）。卡片放哪一天以 TMDB 的 `air_date` 為準，週界前後放寬一天才不會漏。

## 限制

- 只量了一季的兩週（2026 秋季第 5、6 週）。換季時重跑，季初的 TMDB 可能還沒建集。
- Bangumi 放送表本身不完整（國產動畫只有 12 部、跨季的作品也有缺），所以它是對照，不是正解。
- 對應是規則加人工核對，沒有第三方的 id 對照表。

## 來源

- TMDB [Discover TV](https://developer.themoviedb.org/reference/discover-tv)、[On The Air](https://developer.themoviedb.org/reference/tv-series-on-the-air-list)（2026-11-04 實測）。
- Bangumi `GET https://api.bgm.tv/calendar`、`/v0/subjects/{id}`、`/v0/episodes`（[bangumi/api](https://github.com/bangumi/api)；User-Agent 規則見 brief §20.3）。
