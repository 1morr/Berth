# 14f — 季號剛好等於方括號集號時，不要把季號丟掉

**Status:** ready-for-agent

**Blocked by:** 14e（2026-09-17 插入，排在 14e 之後、15 之前：新語料照 14e 之後沒有 `context.profile` 的格式寫）

**讀:** `berth/parser/release.py` 的 `_numbers`；`tests/unit/test_parser_release.py` 的 `test_a_bracket_glued_to_the_word_season_is_an_episode`；plan §4.1（`parse_release` 那一列）、§4.4（虛擬季）、§4.6；brief §6.4；`tests/fixtures/parser/README.md`（「加一筆」）；`docs/research/anime-episode-source.md` §6.1（`The_Final_Season[28]` 從哪裡來）；`docs/progress.md` 偏差與決定裡 2026-09-17 票 14d 的「發現（沒修）」那一條

## 做什麼

`release._numbers` 有一條規則是為 `[NaN-Raws]进击的巨人_The_Final_Season[28]` 寫的：方括號黏著 `Season` 時，guessit
把集號讀成季號、而且不再回集號，所以「季號等於方括號集號」時丟掉季號。**它也丟掉了真的季號**：
`[桜都字幕组] 无职转生～到了异世界就拿出真本事～ S2 / Mushoku Tensei S2 [02]` 的 `S2` 是季號、`[02]` 是集號，
兩個數字剛好相等，於是讀成沒有季號的第 2 集。同一組的 `[03]` 就讀得對。

票 14d 量規則 1 時發現（使用者 2026-09-17 要求開票）。後果看 TMDB 怎麼分季（2026-09-17 以 repo 快照、真實檔名跑 `plan`）：

| 發佈 | TMDB | 現在 | 正解 |
| --- | --- | --- | --- |
| Re:Zero `S2][02]`（hyakuhuyu、KissSub） | 一季 85 集 | **import medium S01E02——自動入錯** | S01E27 `The Next Location`（第二輪從 S01E26 起，虛擬季換算） |
| 無職轉生 `S2 [02]`（Sakurato） | 三季 | review low（規則 1 擋下） | S02E02 `The Forest in the Dead of Night` |
| 進擊的巨人 `[Attack on Titan S2][02]`（诸神字幕组） | 四季 | review low（規則 1 擋下） | S02E02 |
| 鬼滅之刃 `柱训练篇 Kimetsu no Yaiba S05 [05]`（织梦字幕组） | 五季 | import medium S05E05（篇章名救回來） | S05E05，但明說的季號應該是 high |

**範圍量過**（2026-09-17，票 01 快取裡 10 部作品的全部 16,688 個 Mikan 標題；照 `_numbers` 的條件重算，session 暫存區的一次性腳本）：
這條規則丟掉季號的標題 115 個——

- **94 個丟對了**，全部是方括號緊接在 `Season` 後面：`[NaN-Raws]进击的巨人_The_Final_Season[17]`、`[ANi]进击的巨人 The Final Season[28]`。
- **21 個丟錯了**，季號是獨立的 `S2` / `S05` 記號，方括號集號另外一格：無職轉生 9（桜都字幕组 5、喵萌奶茶屋 `[无职转生 2期 / Mushoku Tensei S2][02]` 4）、
  Re:Zero 6（百冬练习组 2、爱恋&漫猫字幕组 4）、鬼滅之刃 4（织梦字幕组）、進擊的巨人 2（诸神字幕组）。

分類用的是 `re.search(r"season[\s_.]*[\[【]\s*0*N\s*[\]】]", cleaned, re.I)`（N 是那個數字、`cleaned` 是 `normalize_cjk` 之後的字串）：
命中的 94 個全是對的、沒命中的 21 個全是錯的。**這是候選判準，不是定案**——實作時照 TDD 定，但 94 個要照樣丟、21 個要讀回季號。

## 怎麼做

1. **語料紅燈**（照 plan §4.6 與語料 README）。檔案清單是 2026-09-17 從 Mikan 下載 `.torrent` 解出來的（單檔 torrent，infohash 與 Mikan 的
   episode id 相同），抄進語料前可再對一次。注意 Re:Zero 檔名裡的 `꞉` 是 U+A789（modifier letter colon），不是半形冒號：
   - `anime/rezero-s2-02-hyakuhuyu`：[Mikan 2af35f8c…](https://mikanani.me/Home/Episode/2af35f8c1ee3089096f06e1584133253081ad271)，
     `torrent_name` `【百冬练习组】【Re: 从零开始的异世界的生活 S2_Re꞉ Zero kara Hajimeru Isekai Seikatsu S2】[02][1080p AVC AAC][简体]`，
     檔案 `[hyakuhuyu][Re꞉ Zero kara Hajimeru Isekai Seikatsu s2][02][1080p AVC AAC][CHS].mp4`（313,460,539 bytes），快照 `tv-65942`（已錄）。
     正解 **S01E27**：TMDB 把 Re:Zero 併成一季，S01E26 `Each One's Promise` 2020-07-08 是第二輪的第一集，S01E27 播於 2020-07-15；
     Mikan 的發佈時間 2020-07-16，票 01 的校準也把這一組的 `[02]` 釘在第二季第 2 集。現在是 **`auto_wrong` 1**——先貼這個紅燈的 `berth bench` 輸出。
   - `anime/mushoku-tensei-s2-02-sakurato`：[Mikan a88e3987…](https://mikanani.me/Home/Episode/a88e398734a8fbdcd8a6aa810a19f967c6f24842)，
     `torrent_name` `[桜都字幕组] 无职转生～到了异世界就拿出真本事～ S2 / Mushoku Tensei S2 [02][1080p][简繁内封]`，
     檔案 `[Sakurato] Mushoku Tensei S2 [02][HEVC-10bit 1080P AAC][CHS&CHT].mkv`（442,054,657 bytes），快照 `tv-94664`（已錄）。
     正解 **S02E02**（2023-07-17；Mikan 發佈 2023-07-19）。現在是 review（規則 1 擋下），修好之後應該是明說的季號、high。
   - 兩筆的語料 README 條目。
2. `mattpocock-skills:tdd` 改 `_numbers`。雙向單元測試用上面量到的**真實標題**：
   - 讀回季號：`Mushoku Tensei S2 [02]`、`[Attack on Titan S2][02]`、`Kimetsu no Yaiba S05 [05]`、`Re:Zero kara Hajimeru Isekai Seikatsu S2][02]` 這幾種 → (季, 集)。
   - 照舊當集號：既有的 `_The_Final_Season[28]`，加上中間有空白的 `The Final Season[28]` → (None, 集)。
3. **重掃一次票 01 的標題**（方法同上，腳本不必留），確認 94 個照樣丟、21 個讀回季號，數字記進 progress.md。
4. `uv run berth bench`：`auto_wrong` 0，兩筆新語料都是 `auto_correct`；`--update-baseline` 並在 commit 說明。
5. 文件：語料 README；CHANGELOG（Fixed）；plan §4.1 `parse_release` 那一列若提到這條規則就一起改。

## 驗收

- [ ] 兩筆新語料進 `tests/fixtures/parser/`，README 已記；紅燈的 `berth bench` 輸出已貼（Re:Zero `auto_wrong` 1）。
- [ ] `_numbers` 不再丟掉獨立的季號記號；判準寫在註解裡；雙向單元測試（四種獨立季號讀回、兩種黏著 `Season` 的方括號仍是集號）。
- [ ] 票 01 標題重掃的前後數字記進 progress.md：原本丟對的 94 個仍丟、丟錯的 21 個讀回季號。
- [ ] `uv run berth bench` 輸出已貼：`auto_wrong` 0、兩筆新語料 `auto_correct`；baseline 已更新。
- [ ] CHANGELOG 已記。
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest` 全綠，貼指令輸出。

**不做：**

- 其他讀不出季號的寫法：`[银光字幕组][进击的巨人2Shingeki no Kyojin 2][02]`（數字黏在標題上、沒有 `S` 記號）、`2期` 單獨出現。它們走的是規則 1，
  送審核不會入錯；要修另開票。
- 規則 1 的形狀（票 14d 已定案）。

## Comments
