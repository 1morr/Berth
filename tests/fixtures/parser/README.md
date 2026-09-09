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
  "context": { "media": "tv:209867", "profile": "anime", "season_hint": null, "episode_offset": null },
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
- `expected` 逐檔一筆，順序與 `files` 相同，是**做完票 07 之後的正確答案**，不是目前的行為。
  `tags` 缺席表示這一筆不比對 tag（字幕、extras、可忽略的附屬檔）。
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
**medium 而不是 high**。要做對得靠集名或片長比對，那是解析器目前沒有的能力（記在票 05 的
Comments，票 06 / 07 決定要不要做）。

**`subs` 是「這個發佈帶了哪幾種字幕」**，不是「影片內封了哪幾種」。外掛字幕也算：
`overlord-s2-dbd-raws`（`简繁外挂` + `.sc.ass` / `.tc.ass`）、`gto-2026-magicstar`
（`附官方日英简繁中字幕` + 四個 `.srt`）與 `squid-game-s02-y2flix`（`ESubs` + `.srt`）
的影片都帶 `subs`。字幕**怎麼放**由另一個欄位回答——brief §6.8 只有內嵌會多一個 `Hardsub`
token，內封與外掛都不加。

v0 涵蓋不到、由單元測試補的兩件事：

- **`sample`**：這 20 個 torrent 一個 sample 檔都沒有——現在的發佈幾乎不再附 sample。
  規則（檔名含 `sample` 且遠小於正片）在 `tests/unit/test_parser_classify.py`。
- **多集檔**（`S01E01E02`）：沒抓到帶這種檔名的真實 torrent。票 06 補語料。

## 加一筆

1. 找一個真實發佈，把 torrent metadata 的檔案清單抄下來（路徑與位元組數原樣，去掉個資）。
2. 寫 `expected`：正確答案，不是目前的行為。`kind` 照 brief §6.2 的表。
3. 補快照：`uv run --env-file .env python scripts/record_tmdb_snapshots.py`。
4. `uv run berth bench`。數字變好就 `--update-baseline` 並在 commit message 說明；
   變差就是解析器有洞，先修再更新。

`baseline.json` 是 CI 的門檻，不是紀錄——只在**刻意**改善或刻意接受退步時才動它。
