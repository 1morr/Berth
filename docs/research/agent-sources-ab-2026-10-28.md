# 側面板的資料來源 A/B：完整組對精簡組（2026-10-28）

實驗，不是票。驅動 `scripts/experiments/agent_sources_ab.py`，逐字稿在 [`agent-sources-ab-2026-10-28/`](agent-sources-ab-2026-10-28/)，逐次的數字與評分在 [`agent-sources-ab-2026-10-28.json`](agent-sources-ab-2026-10-28.json)。

## 結論

**系列對應（整部系列），精簡組夠用，而且這三部比完整組準；新番推薦，精簡組不夠。**

- **系列對應**：三部 × 兩種接口 × 兩次，共 12 次。
  - 精簡組：錯的範圍是 **0**。
  - 完整組：無職轉生第二季前半 4/4 列成 S02E01–E13（正解 E01–E12，第 0 集在 Specials），其中 2 次沒有任何提醒。
  - 錯的根源是 AniList 的 13 集把第 0 集算進去，Fribb 的 offset 也跟著錯。兩種算法同源，所以「一致地錯」，整季標記這道防線就失效了。
  - Re:Zero：完整組每次都把 Fribb 錯的 E27–E39 端到使用者面前請他確認。精簡組照網頁的集數表串接，加總等於 85，4/4 全對、沒有多餘的確認。
  - HxH 2011 與劇場版：兩組一樣好。電影 16/16 都找到正確的獨立 TMDB 條目。
- **新番推薦**：
  - 完整組 4/4 每一部都有 AniList 分數與人數，Bangumi 4/5，四次的榜單幾乎一樣，網搜斷線那一次也一樣。
  - 精簡組四次有人數的分別是 5/5、2/5、2/5、0/5。最差那次只拿到 MAL 會員數，五部裡三部可能不是這一季的。
  - 跨站分歧（AniList 84 對 Bangumi 5.5）只有完整組穩定抓得到。
- **代價**：精簡組多花約 45% 的錢（$0.358 對 $0.247）、多 46% 的 input token，因為網頁內容進了上下文。另外有 4 次被停下：
  - Anthropic 接口的 Re:Zero 兩次撞到每輪 40 萬 input 的上限，其中一次沒出卡。
  - 2 次是 DeepSeek 思考時用完了單次 `max_tokens` 4096、什麼都沒回。
  - 完整組 16 次都沒有被停下。
- **建議**（使用者要求程式盡量簡單、沒用就拿掉）：
  - **Fribb：拿掉候選。** 這三部裡它不是錯（Re:Zero、無職第二季），就是沒資料（HxH 的 TV 沒有季、劇場版指到 Specials）。精簡組沒有它反而更準。
  - **AniList：留 `anilist_read_season`**，那是新番推薦的主幹，提供當季名單與評分人數。`anilist_search_anime` 與 `anilist_read_franchise` 可以從 `series-mapping` 拿掉，改用精簡版的流程（網搜集數表加 TMDB 的季集表）。無職轉生的錯正出在 AniList 的集數。
  - **Bangumi 放送表：留**，給新番推薦的中文名、票數與跨站分歧。
- **拿掉 Fribb 之前先補兩件事**：
  - 這三部是 `fribb-vs-chaining` 研究裡挑出來的難題，樣本偏向 Fribb 錯的情況；那份研究的另外 14 部 Fribb 多半是對的。動手前用同一支驅動，對那 14 部跑一次精簡組的系列對應，確認不會退步（估約 $0.2）。
  - brief §15 的「offset 建議」候選設計是靠 Fribb 的；拿掉 Fribb，那個候選要重新設計。
- **採用精簡流程要一起處理的**：
  - 網頁讓上下文變大，Re:Zero 這種長系列會撞每輪 token 上限：要嘛限制網搜摘錄的長度，要嘛讓找種子那一輪先壓縮。
  - 精簡版 skill 的「有第 0 集要整季標記」被漏過一次，規則要寫得更硬。
  - 拿不到網頁時精簡組會退回憑記憶，這 32 次沒碰到，沒測到。

## 設計

- **同模型**：DeepSeek `deepseek-flash`，兩種接口（Anthropic 相容、OpenAI 相容），使用者 `.env` 的 key。
- **兩組只差資料來源**（演練情境 `agent-live` 對 `agent-live-lean`，`scripts/fake_setup_server.py`），其餘完全相同：同提示詞、同 instructions，TMDB、索引站與 Berth 原本的工具都一樣。
  - **完整組**：現在的產品，多 `anilist_*`、`fribb_lookup_anime`、`bgm_read_calendar`。
  - **精簡組**：這五支不給；`series-mapping` 與 `new-season-picks` 換成 [`scripts/experiments/agent_sources_lean_skills/`](../../scripts/experiments/agent_sources_lean_skills/) 那一版。
    - 系列對應用網搜查各季與 cour 的集數表，用 `media_read_media` 的季集表串接；集數加不起來、超出、沿用連續編號、有第 0 集或總集篇時整季標「未經核對，請確認」。
    - 新番推薦用網搜查當季清單與分數，人數查不到就說不知道。
    - 步驟、取捨與其他規則照抄原版，沒有故意寫弱。
- **網路搜尋兩組一樣**：Anthropic 接口只給伺服器端 `web_search`（不給 Tavily key），OpenAI 接口用 Tavily。
- **題目**：
  - 情境 1 新番推薦：「推薦這一季評價好的新番 5 部，附評分與人數」→「第一部幫我安排」。
  - 情境 2 整部系列：Re:Zero、無職轉生、HUNTER×HUNTER 2011。「先列清單」→「都要，一次送單」。
  - 模型問 Route 或來源時給一次固定回答。**只跑到確認卡出現**，不按、不送單。
- **次數**：兩組 × 兩種接口 × 四題 × 兩次 = 32 次。每一次（組 × 接口 × 重複）一台全新的 Berth；兩組交錯跑，尖峰與離峰的價差兩組各半。
- **花費**：$0.605（上限 $1.5）。第一次跑到一半，DeepSeek 在設定 AI 時的測試連線逾時，驅動補了重試與接續，已完成的 4 題沒有重跑。
- **評分**：每次的季集範圍對照 `docs/research/fribb-vs-chaining-2026-10-28.json` 的正解，由另一個代理讀逐字稿評，抽查過無職轉生與新番推薦的關鍵幾條。逐字稿的工具結果截在 260 字，模型實際讀到的網頁看不全（Anthropic 接口的 `web_search` 結果本來就是加密的）。

## 數字

| 組 | 次數 | 費用 USD | input | output | 模型呼叫 | 工具呼叫 | 網搜 | 秒 | 防護停下 |
|---|---|---|---|---|---|---|---|---|---|
| full | 16 | 0.2470 | 2,807,000 | 125,475 | 163 | 228 | 4 | 1503 | 0 |
| lean | 16 | 0.3584 | 4,094,477 | 154,078 | 163 | 271 | 33 | 1574 | 4 |

| 題目 | 接口 | 組 | 出卡 | 費用 USD（平均） | input | output | 模型呼叫 | 工具呼叫 | 網搜 | 秒 | 防護停下 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| picks | anthropic | full | 2/2 | 0.0099 | 146,380 | 6,468 | 7.0 | 8.5 | 1.0 | 46 | — |
| picks | anthropic | lean | 2/2 | 0.0174 | 230,161 | 7,706 | 8.5 | 9.5 | 3.0 | 72 | — |
| picks | openai | full | 2/2 | 0.0129 | 128,440 | 6,505 | 8.5 | 10.5 | 1.0 | 67 | — |
| picks | openai | lean | 2/2 | 0.0148 | 148,676 | 8,121 | 9.5 | 12.5 | 3.0 | 70 | — |
| rezero | anthropic | full | 2/2 | 0.0154 | 235,773 | 8,637 | 12.5 | 17.5 | 0.0 | 120 | — |
| rezero | anthropic | lean | 1/2 | 0.0417 | 618,470 | 16,326 | 14.5 | 27.5 | 1.0 | 148 | token_limit, error, token_limit |
| rezero | openai | full | 2/2 | 0.0277 | 327,662 | 10,681 | 13.5 | 23.0 | 0.0 | 145 | — |
| rezero | openai | lean | 2/2 | 0.0274 | 337,662 | 10,300 | 13.0 | 27.0 | 2.5 | 118 | — |
| mushoku | anthropic | full | 2/2 | 0.0097 | 128,442 | 5,957 | 9.5 | 13.0 | 0.0 | 84 | — |
| mushoku | anthropic | lean | 2/2 | 0.0267 | 232,810 | 12,810 | 10.0 | 17.5 | 1.5 | 104 | error |
| mushoku | openai | full | 2/2 | 0.0172 | 169,792 | 8,489 | 11.5 | 12.5 | 0.0 | 95 | — |
| mushoku | openai | lean | 2/2 | 0.0205 | 170,318 | 9,935 | 9.5 | 15.0 | 3.5 | 100 | — |
| hxh2011 | anthropic | full | 2/2 | 0.0146 | 146,732 | 8,652 | 10.5 | 15.0 | 0.0 | 98 | — |
| hxh2011 | anthropic | lean | 2/2 | 0.0179 | 211,878 | 6,277 | 9.0 | 12.5 | 1.0 | 104 | — |
| hxh2011 | openai | full | 2/2 | 0.0161 | 120,280 | 7,348 | 8.5 | 14.0 | 0.0 | 97 | — |
| hxh2011 | openai | lean | 2/2 | 0.0128 | 97,266 | 5,564 | 7.5 | 14.0 | 1.0 | 72 | — |

## Re:Zero（tv:65942，S01 85 集）

| 跑 | S1 | S2 | S2P2 | S3 | S4 | 錯且沒標記 | S01 整季標記 | 電影 | 卡 |
|---|---|---|---|---|---|---|---|---|---|
| r1-anthropic-full | ✅🏳 | ◐🏳 | ✅🏳 | ✅🏳 | ✅🏳 | 0 | 是 | 2/2 獨立電影 | 7 列 ✓ |
| r2-anthropic-full | ✅ | ◐🏳 | ✅ | ✅ | ✅ | 0 | 否（只標 S2 那一列） | 2/2 | 7 列 ✓ |
| r1-openai-full | ✅ | ◐🏳 | ✅ | ✅ | ✅ | 0 | 否 | 2/2 | 7 列 ✓ |
| r2-openai-full | ✅ | ◐🏳 | ✅ | ✅ | ✅ | 0 | 否 | 2/2 | 7 列 ✓ |
| r1-anthropic-lean | ✅ | ✅ | ✅ | ✅（分 cour） | ✅（分 cour） | 0 | 否（規則不觸發） | 2/2 | **沒出卡**（token_limit → AI 服務錯誤） |
| r2-anthropic-lean | ✅ | ✅ | ✅ | ✅（分 cour） | ✅（分 cour） | 0 | 否 | 2/2 | 7 列 ✓（中途撞 token_limit） |
| r1-openai-lean | ✅ | ✅（S2 兩部分合併成一列） | ✅ | ✅ | ✅ | 0 | 否 | 2/2 | 7 列 ✓ |
| r2-openai-lean | ✅ | ✅（合併） | ✅ | ✅ | ✅ | 0 | 否 | 2/2 | 6 列 ✓ |

### 無職轉生（tv:94664）

真值：S01E01–11、S01E12–23、**S02E01–12**（第 0 集在 S00E02）、S02E13–24、S03E01–14；III Part 2 還沒上 TMDB（8 跑都正確排除）。

| 跑 | S1a | S1b | II | II P2 | III | 錯且沒標記 | S02 整季標記 | 第 0 集 / OVA | 卡 |
|---|---|---|---|---|---|---|---|---|---|
| r1-anthropic-full | ✅ | ✅ | ❌ E01–13 | ◐🏳 | ✅ | **1** | 否 | OVA → S0；第 0 集沒提 | 3 列 ✓ |
| r2-anthropic-full | ✅ | ✅ | ❌ E01–13 | ✅（E13 重疊） | ✅ | **1** | 否（還宣稱「兩種算法一致」） | OVA → S0 | 3 列 ✓ |
| r1-openai-full | ✅ | ✅ | ❌🏳 | ◐🏳 | ✅ | 0 | 是 | OVA → S0 | 3 列 ✓ |
| r2-openai-full | ✅ | ✅ | ❌🏳 | ◐🏳 | ✅ | 0 | 是 | OVA → S0 | 3 列 ✓ |
| r1-anthropic-lean | ✅ | ✅ | ✅ | ✅ | ✅ | 0 | 否（違反 lean 的「第 0 集要標」） | 有說特別篇在 S0 | 3 列 ✓ |
| r2-anthropic-lean | ✅ | ✅ | —🏳 | —🏳 | ✅ | 0 | 是 | 第 0 集另列 → S0 ✓ | 4 列 ✓（中途 AI 錯誤） |
| r1-openai-lean | ✅ | ✅ | —🏳 | —🏳 | ✅ | 0 | 是 | OVA → S0 請確認 | 3 列 ✓（沒問就選路線） |
| r2-openai-lean | ✅ | ✅ | ✅🏳 | ✅🏳 | ✅ | 0 | 是 | 第 0 集 = S00E02，從種子標題證實 | 3 列 ✓ |

### HUNTER×HUNTER 2011（tv:46298，62 / 74 / 12，S02 從 E63 起）

| 跑 | S01 | S02 | S03 | 錯且沒標記 | 整季標記（應標 S1–S3） | 電影 211755 / 239523 | 卡 |
|---|---|---|---|---|---|---|---|
| r1-anthropic-full | ✅（總括註記） | ✅🏳 | ✅🏳 | 0 | 部分（S1 只有一句總括） | 2/2 | 5 列（BlackRabbit 分季包） |
| r2-anthropic-full | ✅🏳 | ✅🏳 | ✅🏳 | 0 | 是 | 2/2 | 3 列（AnimeRG 純本篇） |
| r1-openai-full | ✅ | ✅🏳 | ✅🏳 | 0 | 部分 | 2/2 | 5 列（iAHD 分季包，286 GB） |
| r2-openai-full | ✅🏳 | ✅🏳 | ✅🏳 | 0 | 是 | 2/2 | 3 列（Judas + Movies ⚠） |
| r1-anthropic-lean | ✅ | ✅🏳 | ✅🏳 | 0 | 部分 | 2/2 | 3 列（Judas + Movies ⚠） |
| r2-anthropic-lean | ✅ | ✅🏳 | ✅🏳 | 0 | 部分 | 2/2 | 3 列（Judas + Movies ⚠） |
| r1-openai-lean | ✅ | ✅🏳 | ✅🏳 | 0 | 部分 | 2/2 | 3 列（Judas + Movies ⚠） |
| r2-openai-lean | ✅ | ✅🏳 | ✅🏳 | 0 | 部分 | 2/2 | 3 列（Judas + Movies ⚠） |

⚠：「Complete Series + Movies」整包放在 tv:46298 底下，又另外加兩列電影 → 劇場版檔案在 Anime 路線會變成未匹配的雜檔，而且下載兩份。集數不會匯入錯位置。

### Picks（2026 秋季 5 部 + 安排第一部）

| 跑 | 部數 | 每部都有分數+評分人數 | 小樣本警告 | 引用來源 | 確實是 2026 秋季 | 第一部 → TMDB / 卡 |
|---|---|---|---|---|---|---|
| r1-anthropic-full | 5 | 是（AniList 5/5、Bangumi 4/5） | 是 | 是（URL） | 是 | 藥屋 S3 → tv:220542，訂閱 ✓ |
| r2-anthropic-full | 5 | 是（5/5、4/5） | 是 | 部分（只寫站名） | 是 | 黑色五葉草 S2 → tv:73223 S2，訂閱 ✓ |
| r1-openai-full | 5 | 是（5/5、4/5） | 是 | 部分（tavily 連不上） | 是 | 藥屋 S3 → 220542，訂閱 ✓ |
| r2-openai-full | 5 | 是（5/5、4/5） | 是 | 是 | 是 | 黑色五葉草 S2 → 73223，訂閱 ✓ |
| r1-anthropic-lean | 5 | 部分（2/5，另 1 部來源可疑） | 部分（總括） | 是 | 是 | 藥屋 S3 → 220542，訂閱 ✓ |
| r2-anthropic-lean | 5 | **是（5/5，三個站）** | 是 | 是 | 是 | 黑色五葉草 S2 → 73223，訂閱 ✓ |
| r1-openai-lean | 5 | 部分（2/5，其中「MAL 6.9 萬人」很可能讀錯） | 是 | 是 | 是 | 冰之城牆 S2 → tv:283428，訂閱 ✓ + 一張沒人要的 S1 下載卡 |
| r2-openai-lean | 5 | **否（0/5，只有 MAL 會員數）** | 部分 | 是（只有單一站） | **可疑**（3 部沒有其他跑佐證） | 藥屋 S3 → 220542，訂閱 ✓ |

### 評審的發現

### lean 一樣好、甚至更好的地方

- **Re:Zero：lean 4/4 範圍全對、沒有雜訊；full 4/4 都把 Fribb 錯的 E27–E39 端到使用者面前。** lean 用 wikipedia 的集數串接，加總 = 85，正確地沒有標記（`r1-openai-lean-rezero.md:35`、`r2-openai-lean-rezero.md:36`）。full 每一跑都把第 2 季列成「E26–E38 / E27–E39，請確認」（`r1-anthropic-full-rezero.md:29`、`r2-openai-full-rezero.md:23`），等於把一個 Fribb 自己造出來的錯推給使用者。有兩跑還自己編理由說明為什麼差一集：「第 26 集似乎是特別篇」（`r2-openai-full-rezero.md:34`）、「TMDB 把某一集收進了特別篇」（`r1-anthropic-full-rezero.md:41`），兩個都是幻覺。整季標記的規則 full 也只有 1/4 做到（`r1-anthropic-full-rezero.md:36`），其他三跑只標那一列。
- **無職轉生：lean 沒有任何錯的範圍；full 4/4 把 II 列成 S02E01–E13（錯），其中 2 跑沒有標記。** AniList 的 13 集把第 0 集算進去了，Fribb 的 offset 也跟著錯，所以 full 的 A、B 兩種算法在 II 這一列「一致地錯」（研究文件已預言）。r2-anthropic-full 更宣稱「兩種算法結果相同，13 + 12 = 24」（`r2-anthropic-full-mushoku.md:27`），是整個實驗唯一一個完全沒有警告、而且算術錯的清單。lean 從 wikipedia 拿到「正片 12 集 + 第 0 集」：2 跑直接給出正確範圍（`r1-anthropic-lean-mushoku.md:29-30`、`r2-openai-lean-mushoku.md:24-25`），另外 2 跑拒絕猜範圍、整季標記（`r2-anthropic-lean-mushoku.md:26-27,34`、`r1-openai-lean-mushoku.md:24-25,32`）。r2-openai-lean 還從種子標題證實第 0 集 = S00E02（`:65`）。
- **HxH：兩組都 8/8 正確、S2/S3 都標記。** 連續編號（S02 從 E63 起）直接寫在 `media_read_media` 的集號裡，lean 不靠 Fribb 也看得到（`r1-anthropic-lean-hxh2011.md:26`、`r2-openai-lean-hxh2011.md:30`）。Fribb 對這部 TV 沒有季資料，對兩部劇場版給的是 S0，8 跑都自己改用獨立的電影條目。
- **電影 / OVA：兩組 16/16 都找到正確的獨立電影 id**（Re:Zero 532321 / 566451、HxH 211755 / 239523）；無職的 OVA 8/8 放在 S0、預設不勾。
- **Picks 的最佳單跑是 lean**：r2-anthropic-lean 透過 anigems 拿到 MAL + Bangumi + Filmarks，5/5 都有人數，Bangumi 98 票標「樣本太小，不列入排序」（`r2-anthropic-lean-picks.md:17-50`）。它的 Bangumi 數字和 full 的工具結果接近，可信。

### lean 比較差的地方

- **Picks 的評分人數覆蓋率是 lean 最大的弱點，而且變異很大。** full 4/4 都是 AniList 5/5 + Bangumi 4/5，四跑榜單幾乎一樣（`r1-anthropic-full-picks.md:17-23`、`r2-openai-full-picks.md:15-21`），連 tavily 斷線的那一跑也一樣（`r1-openai-full-picks.md:12-13`）。lean 的四跑分別是 5/5、2/5、2/5、0/5：
  - r2-openai-lean 只有 MAL 會員數；五部裡三部其他跑都沒出現，分數 6.97–7.40，模型自己也承認不算「評價好」（`r2-openai-lean-picks.md:19-23,33`）。評審所知《偵探已經死了》第二季是 2025 年 7 月播出，所以疑似抓到過期或混入的頁面；工具結果被截斷，無法證實。
  - r1-openai-lean 把 AniList 的 81% 誤解成「好評比例」（`r1-openai-lean-picks.md:15`），引用的「MAL 8.35（約 69,000 人）」轉引自 IMDb 片單（`:19`），但同一部在 r2-anthropic-lean 是 7,015 人。
  - r1-anthropic-lean 有一半是「人數未知」，還有一筆來源可疑（`r1-anthropic-lean-picks.md:26,32,50`）。
  - 跨站分歧（Cyberpunk 2：AniList 84 / 19,544 人 vs Bangumi 5.5 / 4,571 票）是 full 靠 `bgm_read_calendar` 才抓得到的訊號（`r1-anthropic-full-picks.md:46`）；lean 只有一跑做得到。
- **Re:Zero 上的穩定性**：lean 的 anthropic 介面兩跑都撞到 token_limit，其中一跑沒出卡（`r1-anthropic-lean-rezero.md:75,81`、`r2-anthropic-lean-rezero.md:72`）。lean 按 cour 拆成 7 列，搜尋次數變多；full 沒有這個問題。這和來源有關，但比較間接。
- **lean 沒有遵守自己 skill 的標記規則**：r1-anthropic-lean 的無職有第 0 集卻沒標（`r1-anthropic-lean-mushoku.md:35`）。這次範圍剛好對，但規則失效的時候沒有安全網。HxH 的 S1 lean 0/4 標記（full 3/4 有註記）；S1 範圍是對的，所以沒有實害。
- **lean 依賴網頁**：anthropic 介面的 `web_search` 結果是加密的，看不到模型實際讀到什麼。拿不到網頁的時候，lean 的 skill 會退回「憑記憶」；這 32 跑沒有出現這種情況，所以沒有測到。
- HxH 的卡片 lean 4/4 都用 Judas「Complete Series + Movies」包，full 只有 1/4；兩跑 full 明確說明為什麼避開（`r1-openai-full-hxh2011.md:58`、`r2-anthropic-full-hxh2011.md:63`）。這比較像抽樣差異，不像來源造成的。

### full 比較差的地方

- 錯誤全部出在 full：**無職 II 的錯範圍 4 次（2 次沒標記），Re:Zero 的錯候選範圍 4 次（有標記）**。lean 在三部作品裡錯的範圍是 0。
- full 的雙算法設計在 Re:Zero 製造了不必要的確認（正解用串接就能算出來），在無職 II 又因為兩種算法同源（都繼承了 AniList 的 13 集）而「一致地錯」。規則要求整季標記，但模型常常只標有分歧的那一列（Re:Zero 3/4、無職 1/4），錯的 II 列就這樣漏掉了。

### 其他（兩組都有）

- 13/32 跑在使用者說「一次送單」後，還沒回答路線就自己選 route 3 出卡（例如 `r1-openai-lean-mushoku.md:57`）。兩組都有，與來源無關。
- 卡片的 media id 32 跑都和表格一致。沒有任何一列會匯入到錯的集或錯的作品；唯一的雜檔風險是上面的 HxH Judas 包。

## 限制

- 每組每題只有 2 次，模型只有 DeepSeek 一個；Claude 或 GPT 的結果可能不同。
- 三部系列是為了難才挑的（TMDB 併季、第 0 集、撞名與連續編號）。Fribb 對的作品不在這次的樣本裡，所以上面才建議拿掉之前先補跑另外 14 部。
- 只跑到確認卡出現：送單、入庫與 RSS 的結果都沒有量。
