# 動漫季集來源定案（M1 票 01 / brief §10、§20.6）

2026-09-09。腳本是 [`scripts/experiments/anime_episode_source.py`](../../scripts/experiments/README.md)，
可重跑；原始 JSON 落在 `.local/experiments/results/`（不進版控）。結論回寫 brief §10（【研究】→
【決定】）與 §20.6。

## 0. 結論

**維持 TMDB 當 anime profile 的季集來源。不引入 TVDB。**

在 7,833 筆真實字幕組釋出上量到的換算失敗率：

| 來源 | 失敗率 | 錯置 | 退回 review |
| --- | --- | --- | --- |
| **TMDB 季集**（現況） | **8.0%** | 627 | 0 |
| TVDB default(aired) season | 7.6% | 597 | 0 |
| TVDB absolute | 7.6% | 597 | 0 |

差距是 **0.4 個百分點**，而且方向兩邊都有：TVDB 在《航海王》贏 4.4 個百分點，在
《SPY×FAMILY》輸 3.9 個百分點。換來的代價是第二個 provider 的 ID 對應與設定步驟、
Jellyfin 那一端必須改用 TVDB 插件刮才對得上，以及走 absolute 的話每部劇都要多寫一次
`Series.DisplayOrder`（§5）。**不值得。**

（授權**不是**理由：TVDB 的 v4 key 免費自助申請，使用者自備 key 完全可行；
不可行的只有「Berth 內建一把發給所有人」，而那條路 TMDB 這邊也不打算走 —— 見 §5 第 1 點。）

更重要的是：**失敗的主因不是編號來源。** 三個來源同時失敗的有 **573 筆**，佔 TMDB 全部失敗的
91%、TVDB 的 96%（另外只有 TMDB 錯 54 筆、只有 TVDB 錯 24 筆、沒有其他組合）。主要成因是
**檔名裡沒有季號**，例如
`[Up to 21°C] 鬼灭之刃 柱训练篇 - 08`、`[NaN-Raws]进击的巨人_The_Final_Season[28]`。
換 provider 對這一類一集都救不到。真正該投資的是解析器把**篇章名**（柱訓練篇、最終季、
死滅迴游）對到季號，見 §7。

## 1. 樣本

10 部作品，涵蓋票要求的四種形態。挑選理由與 Mikan 的番組 id 固定在
[`scripts/experiments/anime_sample.json`](../../scripts/experiments/anime_sample.json)。

| 作品 | 形態 | 為什麼選它 |
| --- | --- | --- |
| ダンダダン Dandadan | split-cour | TVDB 切成 S1/S2 各 12 集（另有一集未播的 S3 佔位），TMDB 併成一季 24 集 —— brief §20.3 點名的合併政策本體 |
| 無職転生 Mushoku Tensei | split-cour ×2 | S1 與 S2 都分割兩 cour（各隔半年以上），兩個 provider 都把兩 cour 併成一季 |
| SPY×FAMILY | split-cour + 劇場版 | 行銷上的「第二季」其實是第三輪播出；劇場版 CODE: White 夾在中間 |
| 鬼滅の刃 Demon Slayer | 劇場版接續正篇 | 無限列車先劇場版再剪成 TV 篇；之後每個 arc 各自成季 |
| 呪術廻戦 Jujutsu Kaisen | 連續兩季 | TVDB 三季正篇（另有一集未播的 S4 佔位），TMDB 全部併成一季 59 集 |
| 進撃の巨人 Attack on Titan | split-cour ×4 | 最終季拆成四段跨三年播；兩個 provider 對「最終季幾集」還不一致（28 vs 30） |
| Re:ゼロ Re:Zero | split-cour ×3 | S2 與 S4 都分割兩 cour；TVDB 四季，TMDB 併成一季 85 集 |
| ONE PIECE | 長篇累計編號 | 字幕組一律用官方編號（1100+）；兩邊都切了 23 季但切點完全不同 |
| 名探偵コナン Detective Conan | 長篇累計編號 | TMDB 是一季 1213 集（等於絕對編號），TVDB 切成 34 個年度季 |
| 葬送のフリーレン Frieren | 連續兩季 | S1 是一次播完的雙 cour（28 集），S2 另起；TMDB 併成一季 38 集 |

## 2. 三種來源的季集對照

| 作品 | TMDB 季集 | TVDB default(aired) | TVDB absolute | 播出輪次 |
| --- | --- | --- | --- | --- |
| dandadan | 1 季 24 集 `[24]` | 3 季 25 集 `[12, 12, 1]` | 1–24 | 2 |
| mushoku-tensei | 3 季 61 集 `[23, 24, 14]` | 3 季 61 集 `[23, 24, 14]` | 1–63 | 5 |
| spy-family | 3 季 50 集 `[25, 12, 13]` | 3 季 50 集 `[25, 12, 13]` | 1–51 | 4 |
| demon-slayer | 5 季 63 集 `[26, 7, 11, 11, 8]` | 5 季 63 集 `[26, 7, 11, 11, 8]` | 1–63 | 5 |
| jujutsu-kaisen | **1 季 59 集** `[59]` | 4 季 60 集 `[24, 23, 12, 1]` | 1–59 | 3 |
| attack-on-titan | 4 季 87 集 `[25, 12, 22, 28]` | 4 季 **89** 集 `[25, 12, 22, 30]` | 1–89 | 7 |
| re-zero | **1 季 85 集** `[85]` | 4 季 85 集 `[25, 25, 16, 19]` | 1–85 | 6 |
| one-piece | 23 季 1181 集，S1 = 61（East Blue 弧） | 23 季 1177 集，S1 = **8**（切點與 TMDB 完全不同） | 1–1178 | 2 |
| detective-conan | **1 季 1213 集**（等於絕對編號） | 34 季 1213 集，每季一個播出年度（28, 26, 28, 24, 28, …, 27） | 1–1212 | 1 |
| frieren | **1 季 38 集** `[38]` | 2 季 38 集 `[28, 10]` | 1–38 | 2 |

四件事值得單獨記下來：

- **TMDB 正在把整部作品併成一季**：咒術（3 季 → 59 集）、Re:Zero（4 季 → 85 集）、
  芙莉蓮（2 季 → 38 集）、Dandadan（2 季 → 24 集）、柯南（34 季 → 1213 集）。brief §20.3
  說的合併政策比原記載更激進：不只 split-cour，**連續的獨立季也在併**。
- **TVDB 的 absolute 會把 OVA 與劇場版也編進去**：SPY×FAMILY 的劇場版 CODE: White 佔掉
  absolute 38，正篇第 38 集的 absolute 是 39；無職轉生的兩支 OVA 佔掉 17 與 25；
  航海王的跨作品特別篇佔掉 590。**absolute ≠ 正篇第幾集。**
- **兩邊對「有幾集」都可能不一致**：進擊的巨人最終季 TMDB 28 集、TVDB 30 集。
- 上表 TVDB 欄的**最後一個 1 集是尚未播出的佔位**（Dandadan 的 S3、咒術的 S4），不是正篇，
  量測時不計入。
- **鬼滅之刃兩邊完全一致**（26/7/11/11/8）。無限列車先上劇場版、再剪成 7 集的 TV 篇，
  兩個 provider 都把它當成 S02 —— **這個形態沒有分歧，換 provider 也沒有好處。**

## 3. 資料來源與可重跑方式

| 東西 | 來源 | 備註 |
| --- | --- | --- |
| TMDB 季集 | TMDB API `tv/{id}`、`tv/{id}/season/{n}` | 憑證讀環境變數 `TMDB_API_KEY`（使用者自備，票 02b；2026-09-09 之前是讀 adapter 裡的內建憑證） |
| TVDB aired + absolute | Sonarr 的 Skyhook `https://skyhook.sonarr.tv/v1/tvdb/shows/en/{tvdbId}` | 免 key。**只用於本實驗**，理由見 §5 |
| 字幕組實際釋出 | Mikan Project `RSS/Bangumi?bangumiId=`（標題 + 發佈時間）與逐季番組清單 | Mikan 的「番組」就是一輪播出（cour），這是輪次邊界的來源 |

指令在根目錄 README 的〈實驗腳本〉。抓過的東西會快取在
`.local/experiments/cache/anime_episode_source/`，重跑分析不必再等一次網路。

### Skyhook 當 TVDB 替身，先驗過

Skyhook 是 Sonarr 自營的 TVDB 代理，**不是給第三方用的公開 API**（§5），但它的資料就是
TVDB 的。為了確認拿它當替身不會歪掉，把 10 部作品的 aired season 集數逐一對
`thetvdb.com/series/{slug}/allseasons/official` 的網頁：**10/10 完全一致，零分歧**。

## 4. 量測方法

### 4.1 判斷對錯的錨點：發佈時間，不是編號

最容易搞錯的一步是「字幕組寫的 12 到底是哪一集」。不去猜他們**應該**怎麼編號，改成用
Mikan 的發佈時間把檔名的數字釘到實際播出上：一筆釋出的發佈日期若落在某一集播出後
−1～+3 天內、而且那個窗口裡只有一集，就當作它指的是那一集。一週一集的節奏下這個窗口
最多只會對到一集。

再對每個（播出輪次, 字幕組）取這些錨點的**眾數偏移量**，就得到這一組在這一輪的編號習慣。
校準有三道閘：至少 4 個錨點、至少 3 個不同集號、眾數要佔七成以上，而且**這一組在這一輪
的全部釋出**（不只錨定到的那些）套上偏移量後都必須落在這一輪之內。最後一條在擋一個很難
察覺的錯：固定晚十天發佈的字幕組，每一筆都會被釘到下一集去，整組偏移量差一集 —— 但它
最後一集的號碼會因此掉到這一輪之外，就是這樣抓出來的（動漫國字幕組的 SPY×FAMILY、
悠哈璃羽的芙莉蓮、諸神字幕組的進擊的巨人都是這樣被擋下來的）。

校準出來的偏移量若不是四種成立的習慣之一（§4.2），就是校準失敗，整組丟掉並計數 ——
這種筆數在三個來源都是 100% 錯，留著只會替三欄同時灌水。全樣本只有 63 筆（0.8%）。

### 4.2 字幕組實際用的四種編號習慣

偏移量是量出來的，習慣是照偏移量翻譯的，不是預設的分類：

| 習慣 | 意思 | 樣本 |
| --- | --- | --- |
| `restart` | 每 cour 從 01 重新起算 | 5,364（68%） |
| `absolute_official` | 接著往下算，用官方編號（特輯 / 劇場版也佔號） | 1,233（16%） |
| `absolute` | 接著往下算，用正篇序位 | 981（13%） |
| `season_relative` | 季內連號：分割兩 cour 的第二 cour 從 13 接下去 | 255（3%） |

`season_relative` 是原本沒想到的一種：無職轉生 S2 的第二 cour、Re:Zero S2/S4 的第二 cour、
進擊的巨人 S3 的第二 cour，字幕組都用「第二季 13」而不是「第二季 01」。

順帶量到的是**同一個作品同時存在多種習慣**：Dandadan 第二季，桜都字幕組發 `S01 | 01-24`、
LoliHouse 發 `[13-24]`、Prejudice-Studio 發 `S2 - 10`、Skymoon-Raws 發 `S2 - 20`
（季號 + 絕對編號）。任何「假設字幕組編號一致」的設計都會踩到。

### 4.3 三個來源共用同一套換算器

比較要公平，換算規則就必須同一套，差別只在餵給它的結構。規則（`map_episode`）：

有季號提示時，依序試三條 —— 季內編號 → 虛擬季內編號（plan §4.4 的 air_date 斷點）→
帶著季號的絕對編號。沒有季號時：先當第一季的集號，溢位就當絕對編號。「當絕對編號」這一步
**來源自己帶 absolute 欄位就查表，沒有就只能數播出序位**，TVDB 有、TMDB 沒有，這正是兩者
真正的差別所在。TVDB absolute 這一欄借同一份 TVDB 紀錄的 aired season 解季號再輸出絕對
編號（Sonarr 就是這樣做的），不給它這個能力等於故意打敗它。

換算器本身有 `--self-test`：三個手算過的形態（Dandadan 的 TMDB 併季、SPY×FAMILY 的行銷季號 ≠
播出輪次、劇場版佔掉一個 absolute），外加把 180 天與 60 天兩個門檻的**不同答案**都釘住 ——
同一份資料在 180 天下「第二季 01」對、在 60 天下錯，這正是 §6.4 那個結論的最小可執行版本。

### 4.4 樣本與捨棄

Mikan 抓到 16,688 個標題，解析出集號 13,998 筆，其中發佈時間唯一對到某一集 11,122 筆。
最後進入統計的是 **7,833 筆釋出集數**（合集會展開成它涵蓋的每一集，因為那真的是那麼多個檔案）。
捨棄的主要是校準證據不足的字幕組（9,392 集）—— BD 合集、補檔、只發過一兩集的小組。

TMDB 那一欄的「正確答案」要靠播出日期把 TVDB 的第 N 集對到 TMDB 的哪一集：**96.7% 是播出
日期唯一命中**，3.3% 對不上而退回播出序位，這幾筆的正確答案本身存疑，已在原始 JSON 標記。

## 5. 實作可行性（查證於 2026-09-08，一手來源）

即使數字打平，實作面還有幾件事把 TVDB 推得更遠。第 1 點原本被我算成「代價」，2026-09-09
重看後**不成立**，保留在這裡是為了不讓同一個錯誤再被寫一次：

1. **授權：只擋「內建」，不擋 TVDB 本身 —— 所以它不是選 TMDB 的理由。**
   ~~原本這裡寫成一道硬牆，是錯的~~（2026-09-09 修正）。事實是：申請 v4 key **免費且自助**，
   選 End-User Subscriptions 會自動核准，`/login` 的 `pin` 選填、不帶 PIN 實測讀得到資料
   （brief §20.3，2026-09-07 已查證）。ToS 第 2 節的 "non-transferable"、"solely for the
   product or project for which you have been provided access"
   （[tos](https://www.thetvdb.com/tos)）擋的是**Berth 內建一把 key 發給所有使用者**，不是
   「使用者自己申請一把、填進 Berth」。而後者正是本專案對 TMDB 也要走的路（brief §16.3），
   **兩邊對稱，這一項在兩個 provider 之間不構成差異**。
   仍然成立的是：走使用者自備 key 就多一道設定步驟，而 TVDB 那一把是為了 TMDB 之外**再多**
   一把 —— 成本算在下面第 4 點的「第二個 provider」，不算在授權。
2. **Jellyfin 根本沒有「絕對編號」這個概念**。`Emby.Naming` 解析得出 `Show - 128.mkv` 的數字，
   但 `EpisodeInfo` 只有 `EpisodeNumber` / `SeasonNumber`，沒有 absolute 欄位；沒有季資料夾時
   `EpisodeResolver` 直接把季號設成 1。要讓 TVDB 插件走 absolute，得把**整部劇**的
   `Series.DisplayOrder` 設成 `absolute`（走 `tvshow.nfo` 的 `<displayorder>`，或
   `POST /Items/{id}` 但會觸發整劇 FullRefresh + ReplaceAllMetadata）。也就是說採用 TVDB
   absolute 不只是換編號，是多一個「每部劇都要寫一次、而且混排序無解」的寫入動作。
   插件本身沒有任何排序設定（`PluginConfiguration.cs` 全部 12 個欄位裡沒有）。
3. **要多一把使用者自備的 key，而它是為了 TMDB 之外再多一個 provider。** Media 主鍵仍是
   `tv:<tmdb id>`，所以每個 Media 要多存一組 `tvdb_id` 並處理對不上的情況；快照要抓兩次、
   快取兩份、失敗模式兩種；精靈與設定頁要多一步。這些成本換的是 §0 的 0.4 個百分點。
4. **Skyhook 不能寫進正式實作**。它無認證、現在打得通，適合當實驗替身；但後端封閉源
   （Team Sonarr 在官方論壇明說 "It is not open source and we don't have plans to open source
   it."）、無文檔、無 SLA，servarr 官方對同類 metadata proxy 的政策是
   "We do not support directly hitting any metadata service that isn't our own"。
   真要接 TVDB 就得自己打 v4 API：絕對編號只在 `EpisodeBaseRecord`，
   `/series/{id}/extended` 只回 default order，要 absolute 得另外打
   `/series/{id}/episodes/absolute`（`page` 必填、每頁 100 筆），而「一次拿多種排序」的
   issue #98 已 open 五年未做。

順帶查證：**TMDB 的 Absolute episode group 不能當備援** —— 10 部裡只有 6 部有，而且有的部有
多個互相衝突（進擊的巨人有四個 Absolute group，集數 89/97/97/97），柯南的那個叫
"China Online Version"。要絕對編號只有 TVDB 給得穩定。

## 6. 失敗案例逐條

全樣本只有 **13 種**不同的失敗簽章（作品 × 輪次 × 編號習慣 × 季號提示），全部列在下面：

| # | 作品 | 輪次 | 編號習慣 | 檔名的季號 | 誰錯了 |
| --- | --- | --- | --- | --- | --- |
| 1 | demon-slayer | #2 無限列車篇 | 每 cour 從 01 | 無 | 三家 |
| 2 | demon-slayer | #3 遊郭篇 | 每 cour 從 01 | 無 | 三家 |
| 3 | demon-slayer | #4 刀匠村篇 | 每 cour 從 01 | 無 | 三家 |
| 4 | demon-slayer | #5 柱訓練篇 | 每 cour 從 01 | 無 | 三家 |
| 5 | attack-on-titan | #1 第二季 | 每 cour 從 01 | 無 | 三家 |
| 6 | attack-on-titan | #2 第三季前半 | 每 cour 從 01 | 無 | 三家 |
| 7 | attack-on-titan | #3 第三季後半 | 每 cour 從 01 | **有（3）** | 三家 |
| 8 | jujutsu-kaisen | #3 死滅迴游 | 每 cour 從 01 | 無 | 三家 |
| 9 | mushoku-tensei | #3 第二季前半 | 每 cour 從 01 | 無 | 三家 |
| 10 | mushoku-tensei | #4 第二季後半 | 季內連號 | 有（3，寫錯） | 三家 |
| 11 | mushoku-tensei | #5 第三季 | 每 cour 從 01 | 無 | 三家 |
| 12 | one-piece | #1 | 官方編號 | 無 | 只有 TMDB |
| 13 | spy-family | #4 第三季 | 正篇序位 | 有（3） | 只有 TVDB |

第 7 條與其餘「三家」不同，值得單獨看（§6.1.1）。

### 6.1 三個來源一起錯（573 筆，佔 TMDB 失敗的 91%）—— 檔名沒有季號

全部是樣本裡真實出現的標題：

| 作品 | 輪次（正篇第幾集） | 檔名 | 換算器算成 | 真正是 |
| --- | --- | --- | --- | --- |
| demon-slayer | #2 無限列車篇（27–33） | `[jibaketa合成][代理商粤语]鬼灭之刃 无限列车篇 … - 01` | 第 1 集 | 第 27 集 |
| demon-slayer | #3 遊郭篇（34–44） | `[jibaketa合成][代理商粤语]鬼灭之刃 游郭篇 … - 02` | 第 2 集 | 第 35 集 |
| demon-slayer | #4 刀匠村篇（45–55） | `[jibaketa合成][代理商粤语]鬼灭之刃 刀匠村篇 … - 03` | 第 3 集 | 第 47 集 |
| demon-slayer | #5 柱訓練篇（56–63） | `[Up to 21°C] 鬼灭之刃 柱训练篇 … - 08` | 第 8 集 | 第 63 集 |
| attack-on-titan | #4 最終季（60–75） | `[NaN-Raws]进击的巨人_The_Final_Season[28]` | 第 28 集 | 第 87 集 |
| jujutsu-kaisen | #3 死滅迴游（48–59） | `[沸班亚马制作组] 咒术回战 死灭回游 前篇 - 03` | 第 3 集 | 第 50 集 |
| mushoku-tensei | #3（24–35） | `[爱恋字幕社&漫猫字幕社]…[无职转生Ⅱ …][03]` | 第 3 集 | 第 26 集 |
| mushoku-tensei | #5（48–61） | `[黒ネズミたち] 无职转生 Ⅲ … - 03` | 第 3 集 | 第 50 集 |

這一類（上表第 1–6、8、9、11 條）的成因是**篇章名帶了語意但沒有數字**：「柱訓練篇」「最終季」「死滅迴游」「無限列車篇」在三個
來源裡都不是一個季號，換算器只能當成第一季。鬼滅（358 筆）與進擊的巨人（166 筆）兩部就
佔了這 573 筆的九成。

無職轉生那兩筆是另一個成因，同樣與來源無關：**季號寫成全形羅馬數字**（`无职转生Ⅱ`、
`无职转生 Ⅲ`，U+2161 / U+2162）。本實驗的解析器只認半形 `II` / `III`，而且要求前後是空白，
所以 `Mushoku Tensei II]` 這種寫法也漏掉。

**兩個成因都是解析器的缺口，不是來源的缺口。** 對策見 §7。

#### 6.1.1 有季號也會錯：「第三季 第二部分 / Season 3 Part.2」

上表第 7 條是唯一一個**檔名寫了季號卻還是三家一起錯**的：

```
[星空字幕组][进击的巨人 第三季 第二部分 / Shingeki no Kyojin Season 3 Part.2][01-10 Fin][合集]
```

季號有（3），集號從 01 起算，但這是**第三季的後半 cour** —— 正確答案是 S3E13–22，換算器全部
給成 S3E01–10。缺的不是季號，是 **`第二部分` / `Part.2` 這個標記**：看到它就要把前半 cour 的
長度加上去。這個寫法在 split-cour 的作品裡很常見（進擊的巨人第三季、無職轉生第二季都有），
而且它與 §4.2 的 `season_relative` 是同一件事的兩種寫法 —— 有的組直接從 13 接下去，有的組
寫「第二部分」再從 01 起算。

### 6.2 只有 TMDB 錯（54 筆）—— 沒有絕對編號欄位

`one-piece` 輪次 #1，字幕組用官方編號（`[Skymoon-Raws][One Piece 海贼王][1177]`）。TVDB 直接
查 absolute 表就命中；TMDB 沒有這個欄位，只能數播出序位，而 TMDB 收錄 1181 集、TVDB 正篇
1177 集，序位從第 66 集起就開始錯位。例：字幕組寫 932，實際是正篇第 931 集。

失敗率 4.4%（54/1233）而不是 100%，是因為 TMDB 的《航海王》各季 `episode_number` 本身就
接近官方編號，只在少數幾段錯開。

### 6.3 只有 TVDB 錯（24 筆）—— 劇場版佔掉一個絕對編號

`spy-family` 輪次 #4（第三季），ANi 用正篇序位接著往下算（`SPY×FAMILY Season 3 - 50`）。
劇場版 CODE: White 佔掉 absolute 38，所以正篇第 50 集的 TVDB absolute 是 51 —— 字幕組數的是
正篇，TVDB 數的是含劇場版。TMDB 沒有這個問題，因為它根本不編絕對編號。

**這一條正是票要求的「劇場版接續正篇」形態的量化結果**：劇場版不會改變季集結構（鬼滅的
無限列車兩邊都是 S02），但會在 TVDB 的絕對編號線上插一個號，讓「接著往下算」的字幕組編號
與 TVDB absolute 差一。

### 6.4 不算失敗但值得記：虛擬季門檻不能調小

分割兩 cour 的第二 cour 用「季內連號」時（無職轉生 S2 的 13–24、Re:Zero S2 的 14–25），
plan §4.4 的虛擬季門檻設 180 天，三個來源都是 0.4% 失敗。門檻若調成 60 天，TMDB 會惡化到
22.0%（TVDB 仍是 0.4%）—— 因為 60 天會把一季切成兩個虛擬季，季號提示就對不上了。

**結論：plan §4.4 的 180 天是對的，不要調小。** 這也是為什麼全樣本在 180 天門檻下
（TMDB 8.0%）比 60 天（TMDB 9.7%）好。

## 7. 這份研究改變了什麼

1. **brief §10 的【研究】結案為【決定】：維持 TMDB。** 理由是 §0 的 0.4 個百分點與 §5 的三道
   實作牆。`media` 表不加 `tvdb_id` / `episode_source`，不做 TVDB adapter，票 03 / 05 / 06 不動。
2. **brief §10 原本寫的弱點對策要改。** 原文是「靠絕對編號換算 + review」。實測顯示絕對編號
   換算只影響 16% 的釋出、且 TMDB 在那一段只錯 4.4%；真正的弱點是**篇章名沒有季號**。
3. **plan §4.4 的 180 天門檻已被量測支持**，寫進 plan 當作有數字的決定，不再是借來的常數。
4. **plan §4 補一條解析器需求：篇章名 → 季號**。用 `MediaSnapshot` 已有的各季 `name`
   （TMDB 的 `season.name` 就是「Hashira Training Arc」「Entertainment District Arc」）與
   alternative titles 比對檔名裡的篇章名。這是唯一能動到 §6.1 那九成失敗的槓桿，落在票 06。
5. **「最終季」這種序數詞要對到最後一季**，同樣落在票 06。
6. **季號的全形羅馬數字要認**（Ⅱ Ⅲ Ⅳ，U+2160 起），半形 `II` / `III` 的邊界也不能只認空白
   （`Mushoku Tensei II]` 要認得出來）。落在票 05 的 token 化階段。
7. **`第二部分` / `Part.2` 要當成 cour 偏移**（§6.1.1）：有季號還錯的唯一一類就是它。看到這個
   標記就把同季前面幾個 cour 的長度加上去；它與 `season_relative` 是同一件事的兩種寫法。
   落在票 06。

## 8. 已知限制

- Mikan 的番組最早只到 2013 年前後，進擊的巨人 S1（2013）與航海王 / 柯南 2013 年以前的
  cour 沒有字幕組樣本，那幾段沒有量到。
- 只量華語字幕組（Mikan）。英語圈的 SubsPlease / Erai-raws 沒有納入 —— nyaa.si 在本機
  被 DNS 攔截（解析到 `198.18.1.151`，憑證主機名不符），改用 Mikan。英語組多數用「每 cour
  從 01 起算」，與樣本裡最大的那一類同形態，不預期會翻轉結論，但**未證實**。
- 樣本裡 9,392 集因為字幕組的校準證據不足而捨棄，主要是 BD 合集與補檔。這些檔案在真實使用
  中一樣要入庫，它們的失敗率沒有量到。
- TMDB 那一欄有 3.3% 的「正確答案」是靠播出序位對出來的，本身存疑。

## 從 brief 搬來（§20.3）

從 design-brief §20.3 搬來（原文，未改字；brief 已壓縮成結論加連結）。


### 20.3 TMDB

**TMDB**

- 季/集 schema：`season_number: 0` 為 Specials；每集有 `episode_number`、`name`、`air_date`、`episode_type`、`runtime`。（[tv-season-details](https://developer.themoviedb.org/reference/tv-season-details)）
- Episode Groups 類型：Original air date / **Absolute** / DVD / Digital / Story arc / Production / TV。Absolute 只在有人替該劇建立 group 時存在，不是每部都有。（[episode-group-details](https://developer.themoviedb.org/reference/tv-episode-group-details)）
- 標題：`name` 依 `language`（預設 `en-US`）回傳，翻譯缺時可能是空字串，**要自己 fallback 到 `original_name`**；`alternative_titles` 是各國別名，與 translations 無關，兩者都應納入標題比對。（[translations](https://developer.themoviedb.org/reference/tv-series-translations)、[alternative-titles](https://developer.themoviedb.org/reference/tv-series-alternative-titles)）
- `find/{external_id}` 支援 `imdb_id`、`tvdb_id` 等反查。（[find-by-id](https://developer.themoviedb.org/reference/find-by-id)）
- 速率：官方文件未列；TMDB 員工在論壇稱約 50 req/s、20 併發/IP。條款：非商業免費、需顯示 TMDB logo 與聲明「This product uses the TMDB API but is not endorsed or certified by TMDB.」（[faq](https://developer.themoviedb.org/docs/faq)）
- **探索三支端點的形狀**（2026-09-09 對真 API 錄，fixture 在 `tests/fixtures/http/tmdb/`）：`trending/{tv,movie}/week` 與 `search/multi` 的每一筆帶 `media_type`，`{tv,movie}/popular` **不帶**（型別由端點決定）。劇集用 `name` / `original_name` / `first_air_date`，電影用 `title` / `original_title` / `release_date`。`search/multi` 也回人物——`?query=miyazaki` 那一輪 20 筆裡 16 筆是 `person`。
- **`language` 換掉的不只是文字，還有清單的成員與順序**（2026-09-09 實測）：`trending/tv/week` 的 `en-US` 與 `zh-TW` 兩輪各 20 筆，只有 17 筆相同。所以清單要以 `en-US` 那一輪為準，`zh-TW` 只當「這一部叫什麼」的查表（plan §8.3）。`{tv,movie}/popular` 與 `search/multi` 在同一輪實測裡成員一致。
- **回應裡的 `popularity` 不是清單的排序依據**（2026-09-09 實測）：`trending` 與 `popular` 兩支的 `results[]` 都不是照 `popularity` 降冪排的（`tv/popular` 首五筆是 583 / 440 / 692 / 417 / 398）。要照 TMDB 的排名就直接用陣列順序，拿 `popularity` 重排會得到第三種順序。
- **未翻譯時 `name` 回英文而不是空字串**（2026-09-09 實測 `zh-TW`）：`tv/popular` 那一輪的 `Watch What Happens Live with Andy Cohen`、`El conquistador` 都原樣回來。所以「翻譯缺」與「同名」在回應上分不出來，兩種都當成「顯示英文」即可。
- **詳情四支端點的形狀**（2026-09-09 對真 API 錄，fixture 在 `tests/fixtures/http/tmdb/`，票 04）：`tv/{id}` 的 `seasons[]` 每筆有 `season_number` / `name` / `episode_count` / `air_date`，`season_number: 0` 就是 Specials；`tv/{id}/season/{n}` 的 `episodes[]` 每筆有 `episode_number` / `name` / `air_date` / `runtime`（未播的集數 `runtime` 是 `null`）；`movie/{id}` 有 `runtime` 而完全沒有 `seasons`。不存在的 id 回 **404 加 `status_code: 34`**，與「TMDB 壞了」是兩件事。
- **劇集的 `status`**（2026-09-27 查證，M4 票 13）：六種字串 `Returning Series`、`Planned`、`In Production`、`Ended`、`Canceled`、`Pilot`——官方文件沒有列，TMDB 維護者在論壇確認過這份清單（[TMDB Talk: Status for TV and Movies](https://www.themoviedb.org/talk/6685c10585e1cbe90c4a5fe0)）；錄下的 `tv-detail.spy-x-family.*.json` 是 `"Ended"`。Berth 把 `Ended` 與 `Canceled` 讀成「不會再播了」（`MediaSnapshot.ended`，RSS Series 的完結看它，§15「呈現」）。
- **Absolute episode group 的絕對編號要自己從 0-based 的 `order` 推**（2026-09-09 實測 SPY×FAMILY 的 `689a2aec017d0bc9ecc6fac8`）：group 裡的 `episode_number` **保留播出序的原值**，所以第一季二十五集之後，S02E01 在 group 裡仍然是 `episode_number: 1`，而它的絕對編號是 26（`order: 25`）。照 `episode_number` 讀會把整個第二季算成第 1–12 集。同一部作品有五個 episode group（Cours / 兩個 type 1 / Absolute / Blu-ray / Story Arcs），只有 `type: 2` 是絕對編號——這與「有的部有多個互相衝突的 Absolute group」是同一件事的兩面。
- **動漫 split-cour 正被 TMDB 與 TVDB 同步合併成單季連續編號**（例如 Dandadan S2 併入 S1），字幕組編號則多數按 cour 重新從 01 起算。（[TMDB talk](https://www.themoviedb.org/talk/697d0680d564e13094e4e270)、[TVDB KB](https://support.thetvdb.com/kb/faq.php?id=61)）**2026-09-09 實測修正兩點**：（一）TMDB 的合併比這段原記載更激進，**連獨立的連續季也在併** —— 咒術迴戰 3 季併成 1 季 59 集、Re:Zero 4 季併成 1 季 85 集、芙莉蓮 2 季併成 1 季 38 集、柯南 34 季併成 1 季 1213 集；TVDB 這幾部都維持分季。（二）**這不是主要錯誤來源** —— 量化後合併只造成 0.4 個百分點的差距，真正的主要來源是檔名沒有季號（§10、`docs/research/anime-episode-source.md`）。
- **季名逐語言翻譯，而且三套字都有人用**（2026-09-10 實測 `tv/85937`、`tv/1429`，票 06）：同一季的 `name` 在 `en-US` / `zh-TW` / `zh-CN` 分別是 `Hashira Training Arc` / `柱訓練篇` / `柱训练篇`，進擊的巨人第四季則是 `The Final Season` / `第4季` / `最终季`。**篇章名比對必須三套都留**：真實發佈裡最常見的寫法是簡體（`[Up to 21°C] 鬼灭之刃 柱训练篇 - 08`），只留英文季名的話 plan §4.4 那條規則對它一個都不會命中。代價是 `tv/{id}` 多打一輪 `zh-CN`（只取季名，電影不打，plan §4.3、§8.3）。
- **`alternative_titles` 帶篇章名但不帶季號**（2026-09-10 實測 `tv/85937`）：CN 只有 `鬼灭之刃 锻刀村篇` / `鬼灭之刃 游郭篇` 兩筆，TW 五個篇章齊全，JP 是羅馬字（`Kimetsu no Yaiba: Hashira Geiko-hen`）。它們對不出「這是第幾季」——那個對應只有 `seasons[].name` 給得出來，所以比對的主力是季名，別名只是補充。
- **split-cour 的兩個 cour 之間可以超過半年**（2026-09-10 實測 `tv/1429/season/3`）：進擊的巨人第三季 E12 播於 2018-10-15、E13 播於 2019-04-29，相隔 196 天。所以 plan §4.4 的 180 天門檻同時切得出「虛擬季」與「同一季裡的 cour」——它們本來就是同一件事。
- **字幕組的編號習慣有四種，同一部作品會並存**（2026-09-09 實測 7,833 筆）：每 cour 從 01 重新起算（68%）、官方編號（16%）、正篇序位（13%）、季內連號（分割兩 cour 的第二 cour 從 13 接下去，3%）。Dandadan 第二季同時存在 `S01 | 01-24`、`[13-24]`、`S2 - 10`、`S2 - 20`（季號 + 絕對編號）四種寫法。解析器不能假設編號一致。

### 20.3 TheTVDB v4

**TheTVDB v4**

- 存取模型（2026-09-07 重查，**原記載過度，已更正**）：申請 v4 key **免費**，dashboard → API Keys → Create a v4 API Key；選 End-User Subscriptions 者「your key will be automatically approved and ready for use」（[KB#81](https://support.thetvdb.com/kb/faq.php?id=81)）。`/login` 的 `pin` 是**選填**，官方文檔原話「provide your API key as "apikey". If you have a user-supported key, **also** provide your subscriber PIN as "pin". Otherwise…」（[v4-api swagger](https://thetvdb.github.io/v4-api/)）；不帶 PIN 可取得 token 並讀資料（本機實測）。
- 但**授權模型未變**：所有 key 必須「either a commercial license, or have subscriptions enabled for end users」（[KB#62](https://support.thetvdb.com/kb/faq.php?id=62)）；README 明說 user-supported 模式「requires that each of your users has a $12/year TheTVDB subscription」（[v4-api](https://github.com/thetvdb/v4-api)）；KB#81 另警告開發者自用 PIN「prohibited from sharing a PIN for multiple users… Your access may be shut off at any time, and/or legal action may be pursued」。→ **個人自用沒問題；Berth 內建一把 key 給所有使用者是靠執行寬鬆，隨時可能被關。** 若採用，走「使用者自己申請免費 key」而非內建。
- Jellyfin 官方 TVDB 插件是同一個形狀：`PluginConfiguration.cs` 有唯讀的「tvdb api key **for project**」（插件內建）與選填的「tvdb api key for user, this is the **subscriber's pin**」（[jellyfin-plugin-tvdb](https://github.com/jellyfin/jellyfin-plugin-tvdb/blob/master/Jellyfin.Plugin.Tvdb/Configuration/PluginConfiguration.cs)）。→ 使用者把 Jellyfin 媒體庫切成 TVDB 刮削**不需付費**，§10 的「Jellyfin 同源」理由因此被削弱。
- 季類型：default(aired) / absolute / dvd / alternate / regional，**每部劇都有**；對比 TMDB 的 Absolute episode group 只在有人替該劇手動建立時才存在。這是 TVDB 對動漫絕對編號換算的實質優勢。Sonarr 只用 TVDB（經 Skyhook 代理），並靠 TheXEM 做 scene 編號對應（[xem-guide](https://wiki.servarr.com/sonarr/xem-guide)）。
- **`absolute` 會把 OVA 與劇場版也編進去**（2026-09-09 實測 10 部）：SPY×FAMILY 的劇場版 CODE: White 佔掉 absolute 38，正篇第 38 集的 absolute 是 39；無職轉生兩支 OVA 佔掉 17 與 25；航海王的跨作品特別篇佔掉 590。**absolute ≠ 正篇第幾集**，而字幕組「接著往下算」時數的是正篇。
- 取資料要打兩次：`/series/{id}/extended` 只回 default order，絕對編號要另外打 `/series/{id}/episodes/absolute`（`page` 必填、每頁 100 筆），且 `absoluteNumber` 只在 `EpisodeBaseRecord`、`EpisodeExtendedRecord` 沒有。「一次拿多種排序」的 [issue #98](https://github.com/thetvdb/v4-api/issues/98) 開了五年未做。（2026-09-08 查 [v4-api swagger](https://thetvdb.github.io/v4-api/) 4.7.10）
- **授權是硬牆**：ToS 第 2 節寫 key 為 "non-transferable"、"solely for the product or project for which you have been provided access"，並禁止 "transfer, assign"（[tos](https://www.thetvdb.com/tos)）。官方對「終端使用者直連」只給談約或 subscriber-supported key（每位使用者 $11.99/年）兩條路；「每人自己申請一把免費 key」官方從未表態，**未證實**。

### 20.3 Jellyfin 絕對編號、Skyhook 與 Sonarr

**Jellyfin 對絕對編號的支援（2026-09-08 讀原始碼）**

- **Jellyfin 沒有「絕對編號」這個概念。** `Emby.Naming` 解析得出 `Show - 128.mkv` 的數字，但 `EpisodeInfo` 只有 `EpisodeNumber` / `SeasonNumber`；沒有季資料夾時 `EpisodeResolver` 直接把季號設成 1。
- 要走 absolute 得把**整部劇**的 `Series.DisplayOrder` 設成 `absolute`（`tvshow.nfo` 的 `<displayorder>`，或 `POST /Items/{id}` 但會觸發整劇 FullRefresh + ReplaceAllMetadata）。jellyfin-plugin-tvdb 的 `PluginConfiguration.cs` 12 個欄位裡**沒有任何排序設定**，排序只來自 `Series.DisplayOrder`。
- absolute + specials 目前是壞的：插件把 absolute 的特輯打回 `official` season 0 查詢，[issue #91](https://github.com/jellyfin/jellyfin-plugin-tvdb/issues/91) 從 2023 open 至今。

**TMDB 的 Absolute episode group 不能當備援**（2026-09-08 實測 10 部）：只有 6 部有；有的部有多個互相衝突（進擊的巨人四個 Absolute group，集數 89/97/97/97），柯南的那個叫 "China Online Version"。而且 group 內的 `episode_number` 保持 aired order 原值，絕對編號要自己從 0-based 的 `order` 推。

**Sonarr Skyhook 不能寫進產品**：`https://skyhook.sonarr.tv/v1/tvdb/shows/en/{tvdbId}` 免認證、有 `absoluteEpisodeNumber`，適合當量測替身（本專案的實驗就是這樣用的，10/10 與 thetvdb.com 網頁一致）；但它封閉源（Team Sonarr 官方論壇："It is not open source and we don't have plans to open source it."）、無文檔、無 SLA，servarr 對同類 metadata proxy 的政策是 "We do not support directly hitting any metadata service that isn't our own"。

**Sonarr 作為先例**

- Series Type：Standard / Daily / Anime（絕對編號）。預設動漫命名：`{Series TitleYear} - S{season:00}E{episode:00} - {absolute:000} - {Episode CleanTitle} [{Custom Formats}{Quality Full}]…{-Release Group}`。（[settings](https://wiki.servarr.com/sonarr/settings)）
- v4 以 Custom Formats 取代 Preferred Words；Release Profiles 保留 must / must-not contain。
- EpisodeFile（帳本先例）欄位：`relativePath`、`path`、`size`、`dateAdded`、`sceneName`、`releaseGroup`、`language`、`quality`、`mediaInfo`、`qualityVersion`（1 一般、2 proper、3+ 可用於動漫 v3）。（[starr sonarr](https://pkg.go.dev/golift.io/starr/sonarr)）§8 的 `ledger` 至少要涵蓋這些。

### 20.3 動漫 ID 對應

**動漫 ID 對應**

- **Fribb/anime-lists** `anime-list-full.json`（由 anime-offline-database + Anime-Lists 自動產生）：每筆含 `anidb_id`、`anilist_id`、`mal_id`、`kitsu_id`、`imdb_id`、`themoviedb_id`、`tvdb_id`，並有 `season {tvdb, tmdb}` 與 `episode_offset {tvdb, tmdb}`。**這就是「AniList/MAL 條目 → TMDB 季 + 集 offset」的直接資料**。（[Fribb/anime-lists](https://github.com/Fribb/anime-lists)）更新頻率未證實。**M5 票 23d 拿掉**：實測會錯在季與 offset，研究見 `docs/research/fribb-vs-chaining-2026-10-28.md`、`docs/research/agent-sources-ab-2026-10-28.md`。
- Anime-Lists 的 `anime-list.xml` 只有 AniDB→TVDB（`defaulttvdbseason`、`episodeoffset`、`mapping-list`），無 TMDB。新專案 [anibridge-mappings](https://github.com/anibridge/anibridge-mappings) 目標是 AniDB/AniList/MAL/TMDB/TVDB 集級對應，可觀察。
- AutoBangumi v3.2 加入「Episode Offset Auto-Detection」：用 TMDB 各集 `air_date` 偵測「虛擬季」並建議 offset。（[autobangumi bangumi](https://www.autobangumi.org/en/feature/bangumi.html)）本系統 §6.4 的絕對編號換算應同時用「累計集數」與「air_date 區間」兩種訊號。
- Shoko + Shokofin 以 AniDB ED2K hash 辨識檔案，是動漫 metadata 的「黃金標準」但整套獨立生態，與 TMDB 路線不相容，不納入。

### 20.3 動漫資料來源 AniList Bangumi Fribb

**動漫資料來源：AniList、Bangumi、Fribb（2026-10-28 查證＋實測，M5 票 16）**

**M5 票 23d 拿掉 Fribb 與 AniList 的標題搜尋、系列走圖**（`docs/research/agent-sources-ab-2026-10-28.md`）：Berth 只用 AniList 的季表與 Bangumi 放送表。下面 Fribb 與 `relations` 的事實留作紀錄；fixture 只剩 `anilist/`、`bgm/`。

側面板的推薦新番與整部系列要的三個來源（研究 `docs/research/m5-ai-direction-2026-10-27/08-scenario-data-sources.md` §2、`docs/research/m5-anime-sources-2026-10-28.md`；fixture 當時在 `tests/fixtures/http/{anilist,bgm,fribb}/`，`scripts/experiments/anime_sources.py` 錄的）。

- **AniList**（`POST https://graphql.anilist.co`，免 key、不要求 User-Agent）：文件寫 90 次 / 分，頁首警告**目前降級成 30 次 / 分**、不收提高上限的申請，另有沒公布數字的突發限制（[Rate Limiting](https://docs.anilist.co/guide/rate-limiting)）；實測回應帶 `X-RateLimit-Limit: 30`、`X-RateLimit-Remaining`。超過就**封一分鐘**，封鎖期間每個請求都回 429 帶 `Retry-After`（秒）與 `X-RateLimit-Reset`，body `{"data": null, "errors": [{"message": "Too Many Requests.", "status": 429}]}`——所以重試要全程序一起停，各自重試只會延長封鎖。錯誤寫在 `errors`（實測錯的參數回 400 加 `Unknown argument …`），`Page.media(id_in: […])` 問不存在的 id 回 200 加空清單。條款（[Terms of Use](https://docs.anilist.co/guide/terms-of-use)）：月營收 < $150 免費；禁止當備份 / 儲存服務、禁止 hoarding（大量收集），所以 Berth 只按需問、程序內快取 6 小時、不落地。`relations` 用 `relationType(version: 2)`（2026-10-28 對 schema 內省：`SOURCE`、`COMPILATION`、`CONTAINS` 的說明是「Version 2 only」，另有 version 3 多一個 `SAME_UNIVERSE`）；`Page` 一頁最多 50 筆（實測要 60 筆回 50、`pageInfo.perPage: 50`）；同一層的條目用 `id_in` 一次問完，Re:Zero 不含衍生作的六個條目五次問完（原型一個節點一次要十二次）。季表的打分人數是 `stats.scoreDistribution[].amount` 的加總（實測 Fall 2026 第一名 Cyberpunk: Edgerunners 2 人氣 107,511、打分 19,544 人）。
- **Bangumi**（`GET https://api.bgm.tv/calendar`，免 key）：**非瀏覽器要帶 User-Agent，含開發者 ID 與應用名，分發的應用帶版本、開源的帶主頁**，預設的可能被擋（[user agent.md](https://github.com/bangumi/api/blob/master/docs-raw/user%20agent.md)）；Berth 送 `1morr/berth/<版本> (https://github.com/1morr/Berth)`。`/calendar` 記在官方 OpenAPI 的 `open-api/api.yml`（不在 `v0.yaml`），所有欄位都不是必填：實測 112 部裡只有 57 部有 `rank`、93 部有 `rating.score`。回 `cache-control: max-age=3600`，Berth 照它記一小時；沒有公布的速率上限。
- **Fribb/anime-lists**（`https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json`，7.5 MB、39,579 筆）：**倉庫沒有授權檔**（GitHub 的 license 是 `null`），資料出自 anime-offline-database（**ODbL 1.0** + DbCL 1.0）與 Anime-Lists（也沒有授權檔）。判讀（不是法律意見）：**沒有明文授權，嚴格說等於保留所有權利**；Berth 要的那幾格（TMDB 的季與 offset）多半出自同樣沒有授權檔的 Anime-Lists，或 Fribb 自己用 TMDB API 補的，不全來自 ODbL 的那一份。站得住的理由是用法：倉庫公開、README 說明它就是給人對照 id 用的、社群工具普遍這樣抓，而沒有任何條款禁止；ODbL 那一部分明文允許使用與重製（§3.1），署名與 share-alike 只在**公開傳遞**資料庫或公開使用產出時才適用。**結論：照票面用 Fribb**——使用者的 Berth 在執行時下載到自己的 `CONFIG_ROOT`、只自己查詢，不打包進 repo 或 image（那才是再散布）；fixture 只留測試要的 17 筆原文（少量摘錄，當契約測試的證據）。不加 ODbL 署名：自託管、只給自己人看，沒有公開使用（§4.3）；Berth 若哪天公開展示查到的結果再加。要內建一份快照的話，先請作者補授權（在別人的倉庫開 issue，要當次同意）。上游每週二約 16:04 UTC 自動更新一次（最近十次都是 `automated list update`），Berth 每週重抓一次。**下載會斷**：實測一次 `curl` 只拿到 6.6 MB 就結束，所以先解得開才換掉舊檔。只有約兩成條目有 TMDB id；`episode_offset.tmdb` 是「這一輪在那一季的起點前一集」，但會差一集（Re:Zero 第 2 季寫 26，照 offset + 1 讀是 E27–E39：與第 1 季的 25 集之間空一集、又與下一輪（offset 38，E39 起）重疊一集；TMDB 實際是 E26–E38——換算要用 AniList 的集數串起來對 TMDB 的總集數，`series-mapping`）。17 部的實測（`docs/research/fribb-vs-chaining-2026-10-28.md`）：Fribb 的作品 id 沒錯過，錯在季與 offset（TMDB 併季之後 Fribb 照舊分季、offset 差一集）；只靠集數串接則錯在 Specials 裡的一集與 TMDB 把一個條目拆成好幾季——所以 `series-mapping` 兩種都算、不一致就整季交給人。Re:Zero 的 OVA（Memory Snow / Frozen Bond 所在的 100049）對到 TMDB 的 Specials（第 0 季），兩部劇場版在 TMDB 是獨立電影、Fribb 沒有，要用標題搜尋。

### 20.3 Seerr

**Seerr（前 Jellyseerr / Overseerr）**

- 2026 年 3 月起 Jellyseerr 與 Overseerr 合併為 **Seerr**（[seerr-release](https://docs.seerr.dev/blog/seerr-release)）；本文件所有「Seerr」指它。
- 登入：以 Jellyfin / Emby / Plex 帳號登入，可選本地帳號；第一個以媒體伺服器**管理員**身分登入者成為 owner；權限為細粒度旗標（Manage Users、Manage Requests、Auto-Request…）。（[users](https://docs.seerr.dev/using-seerr/settings/users)）
- 可用性判定（來源碼 `server/lib/scanners/jellyfin/index.ts`）：讀 Jellyfin item 的 `ProviderIds.Tmdb`，缺則 `Imdb` → TMDB find，再缺則 `AniDB` → 內建 anime-list 對應。本系統 §9 認領 unmanaged 檔案時可沿用這條鏈。
- 深連結（來源碼 `server/entity/Media.ts`）：`{externalUrl}/web/index.html#!/details?id={itemId}&context=home&serverId={serverId}`。§12 採用此格式。
