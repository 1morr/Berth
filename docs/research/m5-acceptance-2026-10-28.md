# M5 驗收：真模型情境（2026-10-28）

票：[`.scratch/m5/issues/23-m5-acceptance.md`](../../.scratch/m5/issues/23-m5-acceptance.md)（真模型的那一半）。
對照：[M5 prototype](m5-prototype-2026-10-27.md)〈結果：真模型〉的第三輪。
這次打的是**產品**（`/agent/chat` 與 Proposal API），不是 prototype 的 Starlette 行程。
驅動：`scripts/experiments/m5_acceptance_scenarios.py`；演練情境：`scripts/fake_setup_server.py --scenario agent-live`。
逐字稿：[`m5-acceptance-2026-10-28/`](m5-acceptance-2026-10-28/)，檔名 `<接口>-<情境>.md`，總表 `summary.md`。

## 環境

- **模型**：使用者 `.env` 的兩組都接 DeepSeek `deepseek-flash`，和 prototype 一樣是同一個模型、兩種接口。
  - anthropic：`https://api.deepseek.com/anthropic`（Anthropic Messages 相容）。
  - openai：`https://api.deepseek.com`（Chat Completions 相容）。
- **版本**：pydantic-ai-slim 2.62.0（uv.lock；prototype 是 2.61.0），anthropic SDK 2.3.0、openai SDK 3.39.0、genai-prices 0.1.13。
- **Berth**：`agent-live`。TMDB 打真的，索引站是使用者自己的 Prowlarr（真的），AniList / Fribb / Bangumi / Tavily 都是真的，qBittorrent 是 `KeepingQbittorrent`（收下就留著，不再立刻回報被移除）。每種接口各一台全新的 Berth 和新的資料庫。
- **時間**：週三 UTC 03:50–04:00，落在 DeepSeek 尖峰時段。
- **費用**：Berth 自己的記帳（genai-prices 查價，不是腳本的價目表）。
  用 S1 anthropic 驗算：未命中 15.1K x $0.3 + 命中 102.1K x $0.006 + 輸出 5.05K x $1.2（每 MTok）= $0.0112，和 Berth 記的 0.01121 一致，所以是尖峰價，與 prototype 同價目、可直接比。
- **驅動的行為**：逐句送出，遇到確認卡一律按確認（勾全部）；**遇到模型提問不會回答**。第一輪因此有 S1、S3 停在問題上。
- **第二輪（`-answered`）**：S1、S3 在兩個接口上重跑，各加一句固定回答（driver 常數 `ANSWER` =「劇集用 Anime 路線，電影用 Movies；字幕組與來源照你推薦的挑，直接出卡給我確認。」），每個接口一台全新的 Berth。時間約 UTC 04:15–04:20。
- **S2 的三個變體**：Re:Zero（主情境）、無職轉生、HUNTER×HUNTER 2011，用來驗 `series-mapping` skill（答案見 [fribb-vs-chaining](fribb-vs-chaining-2026-10-28.md)）。
- **openai 的 S2 中途重啟**：S2 停在路線問題，回答前把同一台 Berth 從設定根目錄重啟，同一段對話接著跑（`openai-S2-continued.md`）。

## 數字

| 接口 | 情境 | 秒 | 輪 | 模型呼叫 | 工具 | input | 快取命中 | output | Tavily | 費用 USD | 卡片（命令，狀態，列數） |
|---|---|---|---|---|---|---|---|---|---|---|---|
| anthropic | S1 新番 → 訂閱 | 45 | 2 | 8 | 10 | 117,252 | 87% | 5,050 | 2 | 0.0112 | 0 |
| anthropic | S2 Re:Zero | 137 | 4 | 13 | 27 | 390,154 | 77% | 11,779 | 0 | 0.0426 | add_manual_download，executed，7 |
| anthropic | S2 無職轉生 | 37 | 1 | 6 | 5 | 44,046 | 89% | 2,547 | 0 | 0.0048 | 0 |
| anthropic | S2 HxH | 33 | 1 | 7 | 8 | 59,925 | 88% | 2,988 | 0 | 0.0060 | 0 |
| anthropic | S4 為什麼沒入庫 | 12 | 1 | 3 | 4 | 164,251 | 96% | 1,568 | 0 | 0.0048 | 0（S2 那張的延續） |
| anthropic | S3 冷門 | 43 | 1 | 7 | 10 | 58,653 | 86% | 3,084 | 0 | 0.0065 | 0 |
| anthropic | S5 貼的 RSS | 11 | 2 | 4 | 4 | 26,774 | 89% | 1,004 | 0 | 0.0022 | add_feed，executed，1 |
| anthropic | S6 AI 找網址 | 67 | 2 | 6 | 10 | 83,603 | 83% | 4,270 | 1 | 0.0099 | subscribe_mikan，executed，1 |
| openai | S1 | 38 | 2 | 6 | 7 | 68,692 | 81% | 5,030 | 0 | 0.0102 | 0 |
| openai | S2 Re:Zero | 116 | 3 | 15 | 20 | 312,355 | 79% | 8,646 | 0 | 0.0315 | 0（停在路線問題） |
| openai | S2-continued（重啟後） | 73 | 3 | 11 | 19 | 575,833 | 96% | 4,543 | 0 | 0.0145 | add_manual_download，executed，7 |
| openai | S2 無職轉生 | 51 | 1 | 8 | 9 | 62,655 | 92% | 3,086 | 0 | 0.0056 | 0 |
| openai | S2 HxH | 29 | 1 | 6 | 9 | 45,295 | 90% | 2,962 | 0 | 0.0052 | 0 |
| openai | S4 | 11 | 1 | 3 | 3 | 118,880 | 97% | 1,130 | 0 | 0.0031 | 0 |
| openai | S3 | 40 | 1 | 8 | 10 | 62,306 | 86% | 2,499 | 0 | 0.0059 | 0 |
| openai | S5 | 9 | 2 | 4 | 4 | 26,600 | 89% | 935 | 0 | 0.0021 | add_feed，executed，1 |
| openai | S6 | 76 | 2 | 5 | 9 | 50,561 | 83% | 4,075 | 1 | 0.0077 | subscribe_mikan，executed，1 |
| anthropic | S1-answered | 165 | 4 | 12 | 15 | 233,312 | 93% | 11,066 | 2 | 0.0097 | subscribe_mikan，executed，1 |
| anthropic | S3-answered | 117 | 3 | 10 | 14 | 123,453 | 90% | 6,507 | 0 | 0.0060 | add_manual_download，executed，1 |
| openai | S1-answered | 90 | 4 | 11 | 12 | 192,491 | 92% | 8,984 | 1 | 0.0083 | subscribe_mikan，executed，1 |
| openai | S3-answered | 59 | 3 | 10 | 13 | 129,485 | 89% | 5,757 | 0 | 0.0059 | add_manual_download，executed，1 |
| **anthropic 合計（10 列）** | | 667 | 21 | 76 | 107 | 1,301,423 | 87% | 49,863 | 5 | **0.1037** | |
| **openai 合計（11 列）** | | 592 | 23 | 87 | 115 | 1,645,153 | 90% | 47,647 | 2 | **0.1002** | |

- 兩個接口合計約 $0.204（第一輪 $0.174，加上 `-answered` 四列 $0.030）。`-answered` 的原始總表在 `summary-answered.md`。所有 run 的停止原因都是 `completed` 或 `awaiting_confirmation`，`errors` 全空。
- `summary.md` 原本少了 S2-continued 那一列（只在第一輪的 `summary.json`），已補在資料夾的 `summary.md` 末尾。`summary.md` 的「網搜」欄實為 Tavily 次數；DeepSeek 的伺服器端 `web_search` 這次是 0。
- `summary.md` 的「出現標記字樣」欄只是看回答裡有沒有「兩種算法不一致」，不代表標對了範圍，以〈品質〉的逐項檢查為準。

### 和 prototype 第三輪並排

可比的是第一輪的 S1–S6 六個情境（不含兩個 S2 變體、重啟後的續跑與 `-answered` 重跑）：

| | prototype 第三輪 | 這次（S1–S6） | 這次（全部列） |
|---|---|---|---|
| anthropic 模型呼叫 / 工具 | 45 / 65 | 41 / 65 | 54 / 78 |
| anthropic input / output | 501K / 23.5K | 841K / 26.8K | 945K / 32.3K |
| anthropic 快取命中 | 76% | 84% | 84% |
| anthropic 費用 | $0.066 | $0.077 | $0.088（含 `-answered`：$0.104） |
| openai 模型呼叫 / 工具 | 45 / 66 | 41 / 53 | 66 / 90 |
| openai input / output | 574K / 23.6K | 639K / 22.3K | 1,323K / 32.9K |
| openai 快取命中 | 71% | 84% | 90% |
| openai 費用 | $0.081 | $0.061 | $0.086（含 `-answered`：$0.100） |

- 模型呼叫與工具次數相近。input 變多是因為 S4 接在 S2 後面用同一段對話（歷史 119K–164K 都在快取裡，S4 單列命中 96–97%），以及 anthropic 的 S2 這次真的送了單、多一輪。
- 快取命中比 prototype 高約 10 個百分點（可能的原因之一：prototype 把確認卡放進 instructions，卡片一變快取就失效；這次沒有逐項查產品怎麼組 prompt）。
- 單列最貴仍是 S2：anthropic $0.043；openai 加上重啟後的續跑 $0.046。
- 換成 Claude 價目的推估沿用 prototype 的數量級（六個情境約 $0.5–0.6），這次沒有重算。

## 品質

### S1 新番推薦 → 訂閱

- 兩個接口都附 AniList 與 Bangumi 的評分和人數，樣本小的標出來（黑色五葉草 Bangumi 128 票；兩邊的 Cyberpunk 5.5 對 84 都特別提醒）。
- anthropic 把藥師少女排第一，openai 把黑色五葉草排第一，所以「第一部」指的是各自清單的第一名。兩者都判斷還在播，走 Mikan 訂閱，沒有去搜整季包。
- anthropic 看出 TMDB 把第三季掛在 `tv:220542` S01（60 集，第三季 = 49–60 集），字幕組的第 4 集就是 TMDB 第 52 集。openai 對上黑色五葉草 `tv:73223` 的 S02（26 集，已播 1–4），並區分字幕組用 174 的總集數編號或 S2 重新編號，推薦編號對得上的沸班亚马。
- 兩者都按 skill 在出卡前問路線（TV 或 Anime，沒有預設）。第一輪腳本不回答，所以沒有出訂閱卡。
- **`-answered` 重跑**（固定回答之後）：兩個接口都出了一張 1 列的 `rss.subscribe_mikan` 卡，內容相同：藥師少女的呢喃 第三季，`tv:220542`，bangumi 4106，字幕組 382 喵萌奶茶屋，路線 3 Anime；按確認後 `done`，feed 每 900 秒輪詢，整季回填。
  - openai 回填 8 個任務：第 49–52 集每集繁日、簡日兩種版本都抓了，模型提醒「一半是重複的」，並說沒有「單一作品排除關鍵字」的工具可用（`openai-S1-answered.md`）。
  - anthropic 回填 3 筆（49、51、52 集；簡日 2、繁日 1）；第 50 集兩條來源抓 `.torrent` 時 `source_unavailable: ConnectTimeout`（Mikan 逾時），模型查到原因並說下一輪輪詢會再試，提議用排除關鍵字只留繁日。
  - 兩邊都對上 TMDB 把三季併成 S01（60 集）、第三季 = 49–60。openai 另外指出劇場版《亡妃的秘寶》是 12/11 上映的獨立電影 `movie:1566920`，現在沒有片源。
- 小瑕疵（模型品質，非產品；指第一輪）：anthropic 的 ANN 引用連結是 JoJo 的評論頁，撐不起「藥師少女大幅領先」那句（`anthropic-S1.md:25`）；openai 有一個錯字「第 174 頁」。

### S2 Re:Zero 全系列 → 總覽卡 → 壓縮 → 追問

- 共同：
  - 兩邊都用 AniList 走圖加 Fribb 對到 `tv:65942`，講清楚 TMDB 把第 1～4 季併進 S01 共 85 集。
  - 兩部 OVA 都改成獨立的 TMDB 電影（`movie:532321`、`movie:566451`），不是 Specials。
  - 「不要短篇」排除了 Break Time 與 spin-off。
- **整季標記只做了一半**（預期：S01 整季標「兩種算法不一致」）：
  - anthropic 清單只在第 2 季那一列標，但文字說整個 S1 都標了（和表不一致）。
  - openai 標了第 2～5 列，漏了第 1 列。
- 兩邊最後都採接續法（E26–E38、E39–E50），解釋對照表會讓 E26 空著、E39 重疊；也都沒有把「整季包算不算第二季」這點留給使用者，而是自己選了。
- **anthropic**：
  - 說「清單上的都要，一次送單」之後**沒有問路線**，自己選了 Anime（路線 3），送完才說明（`anthropic-S2.md:94`）。skill 第 8 步要求兩條路線都合適又沒預設時要問。
  - 說明裡寫「這是你確認的那張卡上寫的路由」，有點把自己的決定推給使用者。
  - 一張 7 列的卡：TV 5 批（S01E01–25 / 26–38 / 39–50 / 51–66 / 67–85）加兩部電影走 Movies，7 列全 `done`。
  - `/compact`（22 → 12 則）之後問「剛剛送了什麼」，7 列和每一列的 TMDB 範圍都答對，5 批合起來鋪滿 E1–85、不重疊。
- **openai**：
  - 問了兩次「TV 還是 Anime」（符合 skill），腳本沒回答，所以沒有送任何東西。
  - `/compact`（24 → 10 則）之後問「剛剛送了什麼」，如實答「什麼都沒送出」，並重列對應關係。
  - 重啟後（`openai-S2-continued.md`）使用者回「用 Anime」，見〈新發現〉第 2 點；最後 7 列全 `done`，再問「送了什麼」答對。
  - 第 1 季選 [HorribleSubs] 01-25（15.5 GB），理由是 [SubsPlease] 那包在索引裡被標成 26–50，怕錯編號。anthropic 選了 SubsPlease 38.6 GB。

### S2 無職轉生（`tv:94664`）

- 預期：S02 整季標「兩種算法不一致」，因為第 2 季第 1 部分實際是 S02E01–E12（第 0 集在 Specials S00E02），第 2 部分接續會超出 24 集。
- **兩個接口都只標了第 2 部分那一列**（對照表 S02E13–E24 對接續推算 S02E14–E25），第 1 部分那列照單寫成 S02E01–E13，沒標。
- 兩邊都看到 S2 只有 24 集、25 會超出，但都沒提 Specials 裡的第 0 集。openai 還額外把推薦預設列成 S01/S02/S03。
- openai 的 `anilist_read_franchise` 第一次連線被拒，原樣重試就成功，沒被當成重複呼叫。

### S2 HUNTER×HUNTER 2011（`tv:46298`）

- 兩邊都選對 2011 年版（不是 1999），兩部劇場版列成獨立電影（`movie:211755`、`movie:239523`），1999 年版與 OVA 排除。
- Fribb 沒給季：S1 E1–62 / S2 E63–136 / S3 E137–148（62+74+12 = 148）。
- anthropic 三季全標，符合預期。openai 標了 S2、S3，S1 沒標，而且明說「對照表沒給季與偏移，只能靠接續推算」。

### S3 冷門（宝石の国）

- 兩邊都先用日文標題搜 Bangumi（空）、再換中文找到；對到 `tv:74091` 12 集，圖書館 0 集、沒有在途下載。
- 有重複搜但參數不同（先不帶範圍，再帶 `scope.missing`），沒有被當成迴圈。
- 都列出整季包（DHR 繁中 720p、喵萌 VCB 24.6 GB、Arid 29.7 GB 等，做種數附上），然後問來源與路線，**沒有出卡**（第一輪腳本不回答）。anthropic 還給了建議；openai 順帶提到可改用 Mikan 訂閱。
- **`-answered` 重跑**：兩個接口都送出一張 1 列的 `add_manual_download` 卡，`tv:74091`，路線 3，按確認後 `done`。
  - openai：第一個訊息仍照 skill 問了路線（TV 或 Anime，並說明 Anime 已有 8 個任務），回答後選 [Arid] 29.7 GB 雙語（75 做種），並明說它沒有中文字幕，沒把中文版放進同一張卡以免重複匯入（`openai-S3-answered.md`）。
  - anthropic：**沒問路線**，第一個訊息就自己選了 Anime 和喵萌奶茶屋 7.1 GB 簡繁外掛合集（只有 1 個做種）。送單遇到 TMDB 暫時連不上（TLS 沒回應），`media_read_media` 回空標題，`downloading_add_manual_download` 因此被 `media_missing` 拒（`anthropic-S3-answered.md`）；它說明「TMDB 目前連不上」，再讀一次 `tv:74091` 資料抓到後重送，出卡成功。
  - anthropic 收到固定回答時，先查任務，發現上一張卡已執行，**拒絕再送第二份**（會有兩份檔案搶著匯入），並提議之後若 0% 太久再換有做種的版本。
  - 一個旁枝：anthropic 的一次不帶範圍搜尋（`宝石之国 1080`）回了 The Pirate Bay 的不相關成人條目，模型忽略了它，來源列表沒用到。索引站的雜訊不是 Berth 的問題，但值得留意搜尋工具的過濾。

### S4 為什麼沒入庫

- 只讀，沒有嘗試出卡。
- **anthropic**（接在已送單的 S2 之後）：7 筆全講出 `submitted`、client 狀態 `stalledDL`、進度 0%，事件時間軸只有 `created` 與 `submitted`；明說「卡在 qBittorrent 端不在 Berth 端」，並標明「tracker／DHT 問題」是推測不是記錄。
- **openai**（它的 S2 沒送單）：查 `jobs_list_jobs` 全站 0 筆、`why_not_explain` 回 `no_source`，答「完全沒送出，卡在路線還沒選」，正確。
- 替身不再把任務立刻移除（prototype 的 `client_removed`），模型沒有再得出替身造成的錯誤結論；但 `stalledDL` 讓兩邊都猜是 tracker 沒回應，這是替身回報 0% 的副作用（見〈新發現〉第 4 點）。

### S5 使用者貼的 RSS

- 兩邊網址逐字照抄，劇集送 Anime（route 3）。
- **預覽先擋**：第一次呼叫沒給電影 Route，直接回 `{"refused": "route_required", "detail": "movie"}`（`anthropic-S5.md:9`、`openai-S5.md:9`），沒出卡；模型補上 `movie_route_id: 1` 重打，才出一張卡，按下去第一次就成功。
- 兩邊都說明「你只指定了劇集，電影我放到唯一的 Movies 路線」，事後講清楚；`ever_read` 為 false，下一輪輪詢才會抓。
- 工具結果帶 `approved_by_user: true, executed: true`，模型都照實說「已加入」。

### S6 要 AI 自己找 RSS 網址

- 兩邊都不去把搜到的網址塞進 `rss_add_feed`，說明「新增 RSS Feed 只接受你自己貼的網址」，改走 `rss_subscribe_mikan`（番組加字幕組）。所以 `address_not_from_user` 這道守衛這次沒被撞到，是模型自己繞開了。
- 出卡 1 列，按確認後回填。**兩邊都沒問使用者要哪個字幕組**：anthropic 選了 370（喵萌奶茶屋&LoliHouse），openai 選了 37（千夏字幕组）。
- anthropic 回填 10 集（7.8 GB，E29–38），並提醒第二季在 TMDB 是 S01E29–38、不會有 Season 2 資料夾，S01 的 1–28 集沒有。
- openai 回填 12 個任務：同一集抓了三種版本（繁中 AVC、簡中 AVC、HEVC 簡繁內封），第 33–38 集沒進來（整季包被排除，`not_single` x3）。模型如實說明，並指出沒有工具可取消重複任務（`openai-S6.md:41`）。

## 與 prototype 的對照

prototype 〈實跑才抓到的問題〉八點，逐項在產品裡的狀態：

1. **確認後的工具結果要明說已執行**：已修。S2、S5、S6 的恢復結果都是 `{"approved_by_user": true, "executed": true, ...}`，沒有任何一個模型說成「等你按」或「本來就存在」。
2. **待確認的呼叫不一定在最後一則**：這次沒有出現平行呼叫加卡片的情境，沒有新證據；四張卡恢復都正常。
3. **卡片預覽先跑命令驗證**：已修。S5 兩個接口都在出卡前被 `route_required` 擋下（見上）。`route_kind_mismatch` 這次沒碰到。
4. **總覽卡逐列顯示結果**：卡片逐列結果齊全（每列 `done`）。部分成功（有列被拒）這次沒發生，只有全成功的路徑被驗。
5. **連線失敗後的重試不算迴圈**：已修。openai 無職轉生的 `anilist_read_franchise` 連線被拒後原樣重試，沒有警告（`openai-S2-mushoku.md:10`、`:11`）；重啟後 `discover_search_media` 一次 TLS 失敗（`unreachable`）也順利換查詢。
6. **「讀過外部內容」的警示每張卡都亮**：這次逐字稿沒有記錄卡片上的警示，**未評估**。
7. **替身 qBittorrent 收單後立刻回報被移除**：已修。`KeepingQbittorrent` 留著，S4 看到 `submitted` / `stalledDL`，沒有 `client_removed`。例外：openai 重啟前送的任務在重啟後變 `client_removed`，是替身存在記憶體的副作用，不是產品。
8. **一輪 10 次呼叫上限太緊**：已調到 20（plan §11.6）。這次單一情境最多 15 次模型呼叫（openai S2，分 3 輪），沒有任何 run 撞到上限，停止原因全是 `completed`。

## 新發現

1. **`series-mapping` 的整季標記只被部分遵守**（兩個接口都有）。
   - 無職轉生只標了第 2 部分那一列；Re:Zero 的 anthropic 只標第 2 季、openai 漏第 1 列；HxH 的 openai 漏了 S1。
   - 模型的推理常常是對的（看出 25 超過 24、E26 空著），但沒有套到「整季都標、範圍並列」的規則。skill 文字需要更硬的措辭或例子，或把標記做成工具輸出而不是靠模型。
2. **對話被壓縮並重啟後，id 守衛會誤擋合法的 id**（`openai-S2-continued.md:11`、`:15`）。
   - 第一次送單被 `id_not_from_results` 拒：`movie:532321` 只留在壓縮摘要裡，守衛讀的是存下的工具結果。
   - 第二次被 `source_expired` 拒：source 快取在記憶體，重啟就沒了。
   - 模型重新搜尋後恢復，多花了幾次呼叫（整個續跑含最後的追問共 11 次、$0.0145）。這是守法的結果，不算 bug，但「壓縮或重啟後要先重新查 id」可以寫進 skill 或把錯誤訊息講得更直接。
3. **路線與字幕組的詢問行為**：
   - 遇到有歧義的路線（兩條可用且無預設）、字幕組或來源，模型會照 skill 先問，所以要有一句固定回答才能走完 S1、S3；driver 現在有 `ANSWER`。
   - 但 anthropic 並不穩定：S2 主情境和 S3 重跑都自己選了 Anime，事後才說明（`anthropic-S2.md:94`），skill 第 8 步沒被遵守，S2 的說法還像是使用者選的。openai 兩次都問。
4. **替身回報 `stalledDL` 0% 會誤導模型**：anthropic S4 與 openai 續跑都猜是 tracker 或 peer 問題（`anthropic-S4.md:35`、`openai-S2-continued.md:84`）。M5 驗收的 e2e 若想要乾淨的敘述，替身可改回報 `downloading` 並帶進度。
5. **Mikan 訂閱回填可能同集多版本**（待查）：openai S6 回填 12 個任務卻只有第 29–32 集，每集三種版本（`openai-S6.md:41`）。這是模型的轉述，逐字稿的任務清單被截短，沒法逐項驗證。該去看 RSS 回填對「同組同集多個版本」有沒有去重或擇優（plan 的 RSS 章節）。
6. **兩邊都沒問字幕組就訂閱**（S6）。確認卡上看得到字幕組，使用者可以勾掉，所以守住了，但模型的詢問行為偏少。
7. **腳本侷限**：第一輪驅動不回答問題，S1、S3 停在提問，S2 的 openai 要靠重啟另開一輪。已用固定回答 `ANSWER` 重跑 S1、S3 補上（`-answered`）。
8. **TMDB 暫時連不上時的行為**：anthropic S3 重跑遇到 TLS 沒回應，`media_read_media` 回的標題、年份是空的，送單預覽被 `media_missing` 拒；模型說明「TMDB 目前連不上」、重讀之後重送成功。那一筆結果照設計帶 `problem`（`agent_tools._compact_media` 不拿掉它），逐字稿截在 260 字看不到，**不是產品問題的證據**。
9. **回填同集多版本的證據變多**：除了 S6，openai S1-answered 也在同一個字幕組（喵萌奶茶屋）回填繁日、簡日各一份（8 個任務），anthropic 同樣是簡日與繁日混著（3 筆）。這很可能是設計（沒有語言擇優），見第 5 點，要不要做語言擇優需要決定。
10. **接口差異**：這次和 prototype 一樣，DeepSeek 的兩種接口行為幾乎一致；工具呼叫、串流、確認卡、恢復、壓縮都沒有接口相關的錯誤。anthropic 的 S2 比較「果斷」（直接送單），openai 比較「守規矩」（兩次問路線），這是模型取樣差異，不是接口的結構性差別。

## 結論

plan §11.6〈驗收〉的真模型那一條「情境 1、2、3 走完；Re:Zero 全系列分批送出正確」：

- **Re:Zero 全系列分批送出：達成**。兩個接口各有一次 7 列的卡，TV 5 批鋪滿 `tv:65942` S01E01–85（不重疊、不空號），兩部劇場版走獨立電影與 Movies 路線，7 列全 `done`，`/compact` 之後追問答對。
- **情境 1（新番推薦 → 訂閱）**：達成。第一輪停在路線提問；固定回答後兩個接口都出了 `rss.subscribe_mikan` 卡並 `done`（藥師少女 第三季，`tv:220542`，bangumi 4106，字幕組 382，路線 3），推薦品質達標。
- **情境 3（冷門作品）**：達成。固定回答後兩個接口都送出 `tv:74091` 的整季包（1 列、已執行）；anthropic 遇到 TMDB 暫時連不上，卡被 `media_missing` 拒一次，自行恢復。
- 所以**情境 1、2、3 在兩個接口上都走到了已執行的確認卡**。要不要補固定回答這件事只出在驅動，不是產品阻擋。
- 情境 4、5、6 都達預期：S4 只讀且說對狀態，S5 預覽擋下 `route_required`，S6 沒有塞網址、改走 Berth 自己的訂閱。
- 沒有發現需要立刻修的產品錯誤。要處理的有兩項：整季標記規則的遵守度（新發現 1），以及確認 Mikan 回填的同集多版本是不是設計（新發現 5）。
- 未測：Anthropic 與 OpenAI 官方端點、伺服器端壓縮、卡片的「讀過外部內容」警示。

## 票 23b：兩條電視 Route、作品沒有預設，卡片上選 Route

票：[`.scratch/m5/issues/23b-flag-seasons-and-ask-route.md`](../../.scratch/m5/issues/23b-flag-seasons-and-ask-route.md)。上面新發現第 3 點是起因：anthropic 在兩條電視 Route、作品沒有 `default_route_id` 時不問就選了 Anime。使用者決定多條可用就一律要人選，**由程式強制、做在確認卡上**：提出時把那一列的可選清單存進 Proposal（`preview.routes`），`decide` 只收清單裡的，沒選是 422 `route_required`；skill 第 8 步（與 `missing-episodes`、`new-season-picks` 的同一步）改成「不要在對話裡問，卡片會讓使用者選」。

- **情境 S7**：「我想看《宝石の国》（Land of the Lustrous），幫我找來源下載，字幕組照你推薦的挑，直接出卡給我確認。」句子裡**不提 Route**。`agent-live` 有 TV、Anime 兩條電視 Route，每種接口一台全新的 Berth（作品沒送過單）。驅動按卡時，要人選的列照 `ANSWER` 選 Anime（`PICKED_ROUTES`）並寫進逐字稿。
- **時間**：2026-10-28，模型與端點同上（DeepSeek `deepseek-flash`，兩種接口）。
- 逐字稿：[`anthropic-S7.md`](m5-acceptance-2026-10-28/anthropic-S7.md)、[`openai-S7.md`](m5-acceptance-2026-10-28/openai-S7.md)，總表 [`summary-23b.md`](m5-acceptance-2026-10-28/summary-23b.md)。

| 接口 | 秒 | 輪 | 模型呼叫 | 工具 | input | 快取命中 | output | 費用 USD | 卡片 | 要選 Route 的列 |
|---|---|---|---|---|---|---|---|---|---|---|
| anthropic | 31 | 2 | 8 | 12 | 62,533 | 88% | 2,811 | 0.0060 | add_manual_download，executed，1 | 1（TV、Anime，無預選） |
| openai | 48 | 2 | 6 | 12 | 48,061 | 83% | 2,597 | 0.0058 | add_manual_download，executed，1 | 1（TV、Anime，無預選） |

- **兩種接口都沒在對話裡問 Route，直接出卡**；卡片那一列要人選、沒有預選，選 Anime 之後 `done`。合計約 $0.012。
- 模型給的 `route_id` 兩邊都是 3（Anime），與腳本選的同一條，所以這一次分不出「照卡片上選的送」與「照模型給的送」；那一點由 `tests/integration/test_proposal_routes.py::TestManyRoutesFit::test_the_route_chosen_on_the_card_is_the_one_sent`（模型給 Anime、卡片選 TV、送進 TV）與前端 e2e `agent`（模型給 TV、卡片選 Anime、Job 在 Anime）守。
- openai 的回覆寫了「下載到 Anime 資料夾（你另有 TV 資料夾，卡片上可改）」：它從工具說明知道卡片會讓人選。anthropic 照卡片結果說了 Anime。
- 情境 2 的三個變體（整季標記）**這一次沒有重跑**：協調者暫停票 23b 的系列對照工具，等「只有網路搜尋 + TMDB」與「再加 AniList / Fribb / Bangumi」的比較結果決定。

## 票 23d：拿掉 Fribb 之後，Re:Zero 到出卡的每輪用量

票：[`.scratch/m5/issues/23d-drop-fribb-and-franchise-walk.md`](../../.scratch/m5/issues/23d-drop-fribb-and-franchise-walk.md)。協調者要在發版前確認兩件事：長系列找種子那一輪不撞每輪 400K input 的上限；審查後收窄的 skill 那句（「TMDB 把這一段的某集放進特別篇」）仍讓無職轉生第二季整季標記。

- **驅動**：`scripts/experiments/agent_sources_ab.py`（演練情境 `agent-live`，就是現在的產品），Re:Zero 只用 Anthropic 接口（伺服器端 `web_search`）跑到確認卡出現（不按），無職轉生兩種接口只到清單。每一輪的數字取自 `/api/agent/runs/{id}` 的每次呼叫（`per_turn`，這次加進驅動）。
- **模型**：DeepSeek `deepseek-flash`，2026-10-28 UTC 08–10 時（尖峰）。

### 修之前：兩次都超過

| 次 | 列清單那一輪 input（每次呼叫） | 網搜 | 找種子那一輪 input（每次呼叫） | 種子搜尋 / 被截斷 | 結果 |
|---|---|---|---|---|---|
| 1 | 32,241（4K、6K、22K） | 1 | **409,693**（12K → 68K，9 次） | 19 / 13 | 找種子那一輪 `token_limit`，下一輪才出卡 |
| 2 | **457,592**（4K、5K、6K、6K、**221K、216K**） | 2 | 175,541（12K → 54K，5 次） | 12 / 11 | 出卡；列清單那一輪是最後一次呼叫才沒被擋 |

逐字稿：[`t23d-before-r1-anthropic-rezero.md`](m5-acceptance-2026-10-28/t23d-before-r1-anthropic-rezero.md)、[`t23d-before-r2-anthropic-rezero.md`](m5-acceptance-2026-10-28/t23d-before-r2-anthropic-rezero.md)。

兩個根因：

1. **找種子那一輪：種子搜尋的結果在這一輪裡累積**。一次搜尋給模型的上限是 12,000 字（`Limits.result_chars`），19 次裡 13 次頂到；結果留在上下文、每次呼叫都重送，每次呼叫多約 7K。前一輪的網頁已經不送了（第 1 次這一輪從 12K 起跳），所以不是網頁。
2. **列清單那一輪：同一輪裡每次呼叫都重送整頁的伺服器端網搜**。第 2 次搜了兩次（Re:Zero 的維基集數表），兩份約 21 萬 token，之後兩次呼叫各重送一次。DeepSeek 回的是加密的整頁，Berth 截不短；Anthropic 的 `web_search` 也沒有大小參數（pydantic-ai 2.62 `WebSearchTool` 只有 `max_uses`、網域與地點）。票 23d 原本的修法只管下一輪。

### 修法

- **種子搜尋給模型只看前 10 列**，其餘只說有幾列（`rows_not_shown`；`agent_tools.MODEL_SEARCH_ROWS`）。列已照「符合」在前排好，`counts` 有各類的總數，工具說明叫模型要更準就換 `query` 再搜。測試 `tests/unit/test_agent_tools.py::TestSearchTorrentsForTheModel::test_only_the_first_rows_reach_the_model_and_it_is_told_how_many_more`。
- **伺服器端網搜只送最近一則回應裡的**（`compaction.latest_searches_only`，取代「前幾輪不送」）：搜完的下一次呼叫照送，之後不送，每份網頁最多多送一次；掛伺服器端搜尋時 instructions 多一句「搜完就把要的寫下來」。只改送出的那一份、存著的歷史不動，「出自外部來源」的比對照舊。測試 `tests/integration/test_agent_web_search.py::TestEarlierSearchesLeaveTheContext`（兩條，加 `test_each_provider_gets_its_search_tools` 的 instructions 斷言）。
  - 沒選「限制每輪的伺服器端網搜次數」：一次搜尋就可能 10 萬 token，限次數擋不住「搜一次之後每次呼叫都重送」。
  - 沒選「最近一次換成短摘要」：加密內容 Berth 讀不到，摘要只能另花一次模型呼叫。

### 修之後：兩次都在上限內

| 次 | 列清單那一輪 input（每次呼叫） | 網搜 | 找種子那一輪 input（每次呼叫） | 種子搜尋 / 被截斷 | 結果 | 費用 USD |
|---|---|---|---|---|---|---|
| 1 | 48,710（4K、6K、7K、32K） | 1 | 166,155（11K → 34K，7 次），上限的 42% | 15 / 0 | 出卡，7 列 | 0.023 |
| 2 | 143,291（4K、6K、7K、**127K**） | 2 | 102,724（12K → 27K，5 次），上限的 26% | 10 / 0 | 出卡，6 列 | 0.050 |

- 兩次的清單都對：S01E01–E25、E26–E38、E39–E50、E51–E58、E59–E66、E67–E77、E78–E85，兩部劇場版是獨立電影（研究的正解）。
- 第 2 次兩份網頁那一次呼叫是 127K，之後這一輪就結束了；它若接著再呼叫，下一次不會再帶那兩份。
- 逐字稿：[`t23d-r1-anthropic-rezero.md`](m5-acceptance-2026-10-28/t23d-r1-anthropic-rezero.md)、[`t23d-r2-anthropic-rezero.md`](m5-acceptance-2026-10-28/t23d-r2-anthropic-rezero.md)。

### 無職轉生：收窄後的那句 skill

| 次 | 接口 | 第二季前半 | 第二季整季標記 | 逐字稿 |
|---|---|---|---|---|
| skill 收窄後（修上下文之前） | anthropic | S02E01–E12 ✅ | 兩列都標「未經核對」✅ | [`t23d-narrowed-anthropic-mushoku.md`](m5-acceptance-2026-10-28/t23d-narrowed-anthropic-mushoku.md) |
| 同上 | openai（Tavily） | S02E01–E12，註明第 0 集是 S00E02 ✅ | ✅ | [`t23d-narrowed-openai-mushoku.md`](m5-acceptance-2026-10-28/t23d-narrowed-openai-mushoku.md) |
| 修上下文之後 | anthropic | S02E01–E12 ✅ | ✅ | [`t23d-anthropic-mushoku.md`](m5-acceptance-2026-10-28/t23d-anthropic-mushoku.md) |
| 同上 | openai（Tavily） | S02E01–E12 ✅ | ✅ | [`t23d-openai-mushoku.md`](m5-acceptance-2026-10-28/t23d-openai-mushoku.md) |

第一、三季都沒有誤標。

### 補缺集：一季十幾集、每集各自一個發佈

「只給前 10 列」之後，補缺集（`missing-episodes`，一季只搜一次 `scope: {missing, season}`）一季缺十幾集、每集各自一個發佈時，前 10 列可能被幾集的好幾個版本佔滿，模型看不到的那幾集就不會上卡。

- **紅燈**：`tests/integration/test_agent_anime_scenarios.py::TestMissingEpisodes`，一季 14 集都沒有，只有單集發佈（Fast 做了前 7 集、做種更多排在前面，Slow 每一集一個）。修之前模型拿到的「符合」只蓋到第 1–7 集。
- **修法**：給模型的那一份除了前 10 列，之後「符合」而帶來新集數的列也給（`agent_tools._rows_to_show`；整季包算蓋到整季），重複的、不符合的才不給。不靠模型再搜，也不必讓 `scope` 支援指定集數。單元測試 `test_later_rows_come_in_only_for_episodes_not_yet_shown`。
- **真模型**：演練情境 `agent-live-missing`（替身 TMDB 的 SPY×FAMILY 第一季 12 集都沒有，替身索引站只有單集發佈：Fast 前 6 集、Slow 全 12 集），`agent_sources_ab.py --set missing --groups missing`，兩種接口各 1 次到出卡。

| 接口 | 卡片列數 | 卡片涵蓋的集 | 種子搜尋 | 費用 USD | 逐字稿 |
|---|---|---|---|---|---|
| anthropic | 12 | 第 1–12 集全有（Fast 1–6、Slow 7–12） | 5（第 1 次是 `missing` + `season`，其餘是模型自己找整季包） | 0.014 | [`t23d-missing-anthropic.md`](m5-acceptance-2026-10-28/t23d-missing-anthropic.md) |
| openai | 12 | 第 1–12 集全有 | 3 | 0.010 | [`t23d-missing-openai.md`](m5-acceptance-2026-10-28/t23d-missing-openai.md) |

### 新番推薦：產品現在的樣子（AniList 季表 + Bangumi 放送表 + 網搜）

票 23d 只拿掉整部系列用的 AniList 搜尋、系列走圖與 Fribb，新番推薦的兩個來源照留；這裡確認它沒有跟著變差。`agent_sources_ab.py --only picks`（演練情境 `agent-live`），Anthropic 接口 2 次、OpenAI 接口（Tavily）1 次，跑到確認卡出現。題目同 A/B 研究：「推薦這一季（2026 年秋季）評價好的新番動畫 5 部，附評分與評分人數」→「第一部幫我安排」。

| 次 | 工具 | 5 部都有 AniList 分數與人數 | Bangumi 分數與票數 | 都是 2026 秋季 | 跨站分歧 | 卡片 | 費用 USD |
|---|---|---|---|---|---|---|---|
| r1 anthropic | 季表、放送表、`web_search` ×2 | 5/5 | 4/5（JoJo SBR 是 ONA，放送表沒有，有說） | ✅ | Edgerunners 2（AniList 84 / 20,839 人對 Bangumi 5.5 / 4,591 票）標「嚴重分歧」 | `rss.subscribe_mikan` 黑色五葉草 第二季 | 0.015 |
| r2 anthropic | 季表、放送表、`web_search` ×1 | 5/5 | 4/5（同上） | ✅ | 同上，附 CBR 等評論網址 | `rss.subscribe_mikan` 藥屋少女 第三季 | 0.012 |
| r1 openai | 季表、放送表、Tavily ×1 | 5/5 | 4/5（同上） | ✅ | 同上，附 Reddit 討論串 | `rss.subscribe_mikan` 藥屋少女 第三季 | 0.009 |

- 三次的五部相同（藥屋少女 第三季、黑色五葉草 第二季、JoJo 飆馬野郎 2nd & 3rd STAGE、冰之城牆 第二季、Edgerunners 2），只有排序不同；Bangumi 128 票的那一部三次都標「樣本偏小」。
- **對照 A/B 研究的完整組**（`agent-sources-ab-2026-10-28.md`〈評分〉的 Picks：AniList 5/5、Bangumi 4/5、四次榜單幾乎一樣、跨站分歧只有完整組穩定抓得到）：**沒有變差**，三次都和完整組同一個水準。沒有改程式或 skill。
- 卡片是榜單第一部的 Mikan 訂閱（還在播），三次都出卡、沒有被防護停下。
- 逐字稿：[`t23d-picks-r1-anthropic.md`](m5-acceptance-2026-10-28/t23d-picks-r1-anthropic.md)、[`t23d-picks-r2-anthropic.md`](m5-acceptance-2026-10-28/t23d-picks-r2-anthropic.md)、[`t23d-picks-r1-openai.md`](m5-acceptance-2026-10-28/t23d-picks-r1-openai.md)。

### 花費

修之前 $0.131，收窄後的無職轉生 $0.019，修之後 Re:Zero $0.073、無職轉生 $0.024，合計 **$0.247**（使用者把上限放寬到 $1）。補缺集另 $0.024（上限 $0.5），新番推薦另 $0.036（上限 $0.3）。

## 票 27：訂閱的 skill 與多語言搜尋（2026-10-29）

演練情境 `agent-live`（真 TMDB、真索引站、真 Mikan / Nyaa / acg.rip、真模型；qBittorrent 收下就留著），`scripts/experiments/agent_sources_ab.py --set subscribe`，每一次一台全新的 Berth，只跑到確認卡出現（不按）。三題：

- `sub-zh`：「幫我訂閱鐵旅！meet with 鐵道少女」→「就照你推薦的字幕組，出卡給我確認。」
- `sub-en`：「Subscribe me to TETSURYO! Meet with Tetsudou Musume, I want each new episode as it comes out.」→「Go with the subgroup you recommend and give me the card to confirm.」（TMDB 的英文名；問的人不會寫中文）
- `frieren-zh`：「下載葬送的芙莉蓮第一季」→ 固定回答（Route 與來源照推薦、直接出卡）

看的是：有沒有用原名、英文名與對話語言的名字搜；訂閱有沒有列字幕組比較表、等人選（第一句之後就出卡算沒等）、卡上字幕組必選；下載有沒有在對話裡列出中文字幕的發佈。

**「搜了哪些名字」怎麼讀**：不帶 `query` 的那一次問的是搜尋設定開著的名字，全新 Berth 是出廠值英文名與原名（`SearchSettings`）；逐字稿截掉了工具結果，`attempts` 看不到，這一格是照設定推的。表裡其餘的字是模型自己用 `query`（種子搜尋）或 `term`（Mikan 搜番組）打的，照逐字稿抄。

### 最終版（第 4、5 輪）

訂閱（第 4 輪，最終版 `subscribe`，兩種接口各 1 次）：

| 接口 | 題 | 搜了哪些名字 | 比較表 | 等人選 | 卡片 | 費用 USD | 逐字稿 |
|---|---|---|---|---|---|---|---|
| anthropic | sub-zh | 預設（英文、原名）；`鐵旅`、`铁旅！meet with 铁道少女`；Mikan `鐵旅！meet with 鐵道少女` | 5 組，推薦繁中的 ANi | ✅ 結尾「你想訂哪一組？」 | Mikan，ANi 預選，2 選 1 必選 | 0.004 | [`t27-r4-anthropic-sub-zh.md`](m5-acceptance-2026-10-28/t27-r4-anthropic-sub-zh.md) |
| anthropic | sub-en | 預設；`铁旅！邂逅铁道少女`、`鐵旅！meet with 鐵道少女`；Mikan 同上 | 5 組（英文字幕 4 組），推薦 SubsPlease | ✅ | nyaa 關鍵字，SubsPlease 預選，8 選 1 必選 | 0.004 | [`t27-r4-anthropic-sub-en.md`](m5-acceptance-2026-10-28/t27-r4-anthropic-sub-en.md) |
| openai | sub-zh | 預設；`铁旅`；Mikan `鐵旅` | 5 組，推薦 ANi | ✅ | Mikan，ANi，2 選 1 必選 | 0.003 | [`t27-r4-openai-sub-zh.md`](m5-acceptance-2026-10-28/t27-r4-openai-sub-zh.md) |
| openai | sub-en | 預設；`铁旅`；Mikan `鐵旅！meet with 鐵道少女` | 6 組（英文字幕 4 組），推薦 SubsPlease | ✅ | nyaa 關鍵字，SubsPlease，8 選 1 必選 | 0.004 | [`t27-r4-openai-sub-en.md`](m5-acceptance-2026-10-28/t27-r4-openai-sub-en.md) |

四次都沒在列表那一則說「卡片已備好」。英文對話推薦的英文字幕組不在 Mikan，所以走 nyaa 關鍵字訂閱；中文對話選的 ANi 在 Mikan，走 Mikan。

下載（第 5 輪，最終版 `missing-episodes`，兩種接口各 2 次）：

| 次 | 接口 | 搜了哪些名字 | 列表 | 等人選 | 卡片 | 費用 USD | 逐字稿 |
|---|---|---|---|---|---|---|---|
| 1 | anthropic | `scope: missing`（英文、原名）；`葬送的芙莉蓮`、`葬送的芙莉莲`、`葬送のフリーレン 第1季`、`葬送的芙莉莲 01-28`、`Frieren 繁日双语 BDRip` | ✅ 中文字幕 / 英文多語兩組 | ✅ 問字幕要哪種、要不要 29–38 | ❀拨雪寻春❀ 01–28 簡繁日內封 | 0.005 | [`t27-r5-r1-anthropic-frieren-zh.md`](m5-acceptance-2026-10-28/t27-r5-r1-anthropic-frieren-zh.md) |
| 1 | openai | `scope: missing`；`葬送的芙莉蓮`、`葬送的芙莉莲`、`送葬者芙莉莲` 等 8 次 | ✅ | ✅ | 喵萌奶茶屋&LoliHouse 01–28 修正合集 | 0.006 | [`t27-r5-r1-openai-frieren-zh.md`](m5-acceptance-2026-10-28/t27-r5-r1-openai-frieren-zh.md) |
| 2 | anthropic | `scope: missing`；`葬送のフリーレン`、`葬送的芙莉蓮`、`葬送的芙莉莲` 等 7 次 | ✅ | ✅ | 喵萌奶茶屋&LoliHouse 01–28 | 0.006 | [`t27-r5-r2-anthropic-frieren-zh.md`](m5-acceptance-2026-10-28/t27-r5-r2-anthropic-frieren-zh.md) |
| 2 | openai | `Frieren Beyond Journey's End`、`葬送のフリーレン`、`scope: missing`、`葬送的芙莉莲` 等 8 次 | ✅ | ✅ 另問要不要 29–38 | 喵萌奶茶屋&LoliHouse 01–28 | 0.006 | [`t27-r5-r2-openai-frieren-zh.md`](m5-acceptance-2026-10-28/t27-r5-r2-openai-frieren-zh.md) |

四次都載入 `missing-episodes`、說明 TMDB 第 1 季收了 38 集（29–38 是 2026 年播的第二季）而「第一季」取 01–28，卡上都是中文字幕的合集。

### 怎麼改到最終版（第 1–3 輪）

| 輪 | skill 的樣子 | 看到的問題 | 改了什麼 |
|---|---|---|---|
| 1 | 初版 | 訂閱：中文兩次都在列表那一則說「訂閱卡已準備好 / 已預選 ANi」（其實還沒出卡）；openai 英文沒列表、第一句就出 Mikan 卡、預選繁中的 ANi。下載：兩種接口都**沒載入任何 skill**（`missing-episodes` 的描述只寫補缺集），沒列候選；openai 挑了英文字幕的 EMBER | `subscribe`：列表那一則不叫訂閱工具、不說卡已備好；`missing-episodes`：描述涵蓋「下載一季」，出卡前列候選 |
| 2 | 上面兩處 | 訂閱四次都對。下載兩次都載入了 skill、挑了中文字幕，但出卡那一步只叫工具、不寫字，表沒出現 | 「表寫在叫 `downloading_add_manual_download` 之前」 |
| 3 | 同上（只跑下載） | 兩次都列了表 | — |
| 4 | 描述收窄成「一季」（不搶 `series-mapping` 的整部系列）、`subscribe` 第 6 步改字（卡上只有一個選項時不必選，照票 26） | 訂閱四次都對；下載 openai 又沒寫表（1/2） | 沒說字幕偏好、候選又有不同字幕語言時，列表、推薦、**問完再出卡** |
| 5 | 最終版 | 四次都對 | — |

逐字稿：第 1 輪 `t27-r1-*`、第 2 輪 `t27-r2-*`、第 3 輪 `t27-r3-*`、第 4 輪的下載題 `t27-r4-*-frieren-zh.md`。

### 其他看到的

- **字幕組名讀錯一個**：nyaa 關鍵字卡的選項裡有 `VARYG (Tetsuryou! meet with Tetsudou Musume`（`rss.search_subgroups` 把組名後面的括號一起讀進來），其餘 7 個正常。屬票 26 的組名解析，記在票 27 Comments。
- **Mikan 卡的 `name`**：第 2 輪 anthropic sub-zh 把 Feed 名寫成字幕組名 `ANi`，其餘是作品名。只影響 RSS 頁上 Feed 的名字。
- **繁中全名沒拿去搜種子**：多數次只用短名（`鐵旅`、`铁旅`）或 Mikan 的簡中番組名搜索引站，繁中全名只拿去搜 Mikan。這部在索引站上只有英文名的發佈，中文名怎麼搜都沒有可用的，比較表不受影響；skill 說「每個不在 `attempts` 裡的名字都用 `query` 再搜」，這一點只做到一部分。
- **種子搜尋次數**：第 2 輪 anthropic 的下載題搜了 20 次（$0.009，每輪最多 85K input），沒有撞上限；最終版 6–9 次。
- **`new-season-picks` 改成載入 `subscribe`**，沒有另外用真模型跑推薦新番。

### 花費

第 1 輪 $0.022、第 2 輪 $0.027、第 3 輪 $0.012、第 4 輪 $0.024、第 5 輪 $0.023，合計 **$0.107**（上限 $1）。
