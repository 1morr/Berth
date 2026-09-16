# 14d — 絕對編號換算改由證據決定信心，不再看 Route profile

**Status:** ready-for-agent

**Blocked by:** 14c（2026-09-16 插入，排在 14c 之後、14e 與 15 之前：14e 要拿掉的欄位，解析器先不讀）

**讀:** `docs/research/profile-effect.md` §0、§3、§4、§6.1；brief §6.4、§6.5、§19（Route profile 那一列）、§20.4（「只有集號、TMDB 上多季的真實發佈」）；plan §4.4（「絕對編號換算」那一條）；`tests/fixtures/parser/README.md`（v2 那一節）；`docs/research/anime-episode-source.md` §1、§3、§4（第 1 步的資料與正解怎麼來的）；`scripts/experiments/README.md` 的 `anime_episode_source.py` 那幾條

## 做什麼

票 14c 量到：Route profile 唯一的作用是「只有集號、TMDB 上不只一季」時，`mapping._from_number` 的絕對編號換算
自動入庫（`anime`，medium）還是送審核（`standard`，low），而「是不是動漫」預測不了換算對錯——
《Home and Away》（非動漫）換錯、《超人回來了》（非動漫）換對、《死神》相剋譚（動漫）換錯。

使用者拍板（brief §19）：**移除 profile，改由兩條證據決定。** 這一票做解析器那一半；欄位本身在 14e 拿掉。

每個換算出來的候選預設 medium，遇到任一條就降到 low 並附理由：

1. **集號 ≤ 第一個正規季的集數**（`_length(regular[0])`）。這個數字同時讀得成「第一季第 N 集」與「後面某季
   從 01 重數的第 N 集」。
2. **檔名帶播出日，而候選那一集在 TMDB 上不是那一天播的。** `ReleaseInfo` 要多一個播出日欄位；`guessit`
   要加 `date_year_first`，否則韓國電視台的 `150524` 會讀成 2024-05-15（14c 實測）。

原型（14c 在 scratchpad monkeypatch，研究 §6.1）在 28 筆語料上量到 **auto_correct 170、auto_wrong 0**
（現況 169 / 0；多出來的是《超人回來了》），《死神》相剋譚 14 檔送審核。

**已知代價**（使用者接受）：多季作品第一季、檔名沒有季號的發佈會送審核，例如 2022 年的
`[SubsPlease] Spy x Family - 05`。第一季的發佈幾乎不寫季號，所以這個代價可能不小，**而它沒量過**。

**規則 1 動工前先量一次**（2026-09-16 使用者要求加的第 1 步）：用票 01 那 7,833 筆以發佈時間判定過正解的真實發佈，
回答「規則 1 擋下的，是對的多還是錯的多」，以及「發佈標題比作品標題多出字」能不能把兩者分開——《死神》多了
`Sennen Kessen Hen - Soukoku Tan`，`Spy x Family - 05` 沒有。分得開的話，規則 1 收窄成「集號 ≤ 第一季集數**而且**
標題有認不出的多餘字」，第一季的補檔可以照樣自動入庫。

## 怎麼做

1. **量規則 1 的代價，決定它的形狀。** 新腳本 `scripts/experiments/absolute_rule_cost.py`（import `berth`，沿用
   `anime_episode_source.py` 的函式與 `.local/experiments/cache/` 的快取；要 `TMDB_API_KEY`，快取被清掉的話重抓約十分鐘）：
   - **樣本**：票 01 的 10 部裡 TMDB 上有 ≥ 2 個正規季的 5 部——SPY×FAMILY（3 季）、無職轉生（3）、鬼滅之刃（5）、
     進擊的巨人（4）、航海王（23），以 repo 裡的快照為準（`tv-120089`、`tv-94664`、`tv-85937`、`tv-1429`、`tv-37854`）。
     另外 5 部 TMDB 只有一季，走 `single_season`，規則 1 碰不到。
   - **正解**：照票 01 研究 §4.1 的校準（發佈時間錨點 → 每個（輪次, 字幕組）的偏移量）得到每筆發佈實際是 TMDB 的第幾季第幾集。
     **`Trial` 與 `Release` 沒存 Mikan 的原始標題**，要讓 `collect()` 把標題帶出來（改 `anime_episode_source.py` 可以，
     `--self-test` 要照樣過）。票 01 的 TMDB 資料是 2026-09-09 抓的，先比對它與 repo 快照的各季集數一致再算，不一致就記下來。
   - **Berth 怎麼讀**：每筆發佈當成一個以標題為檔名的單檔 torrent 丟進 `plan`（Mikan 只給標題，沒有檔案清單——這是近似，
     記進研究文件），側錄 `_from_number` 的方法同 `profile_effect.py`。只看走到絕對編號分支的那些。
   - **要回答的數字**（檔案數，合集逐集展開）：
     - 集號 ≤ 第一季集數：正解是第一季的（A，規則 1 把對的擋進審核）與正解是後面某季的（B，規則 1 擋下的錯）。
     - 集號 > 第一季集數：現行換算對與錯的數量——規則 1 沒碰到的這一側，自動入庫的前提是它大多是對的。
     - 候選收窄規則 R「集號 ≤ 第一季集數而且標題有認不出的多餘字」：A 裡放行幾筆、**B 裡漏掉幾筆**。「認不出的多餘字」
       怎麼定義在腳本裡寫清楚（例如標題候選正規化後不等於快照 `titles` 裡任何一個）。
   - **判準**：R 在 B 裡**一筆都沒漏**、而且 A 裡放行的不是零 → 採用 R；R 漏掉 B 的任何一筆 → 維持原本的規則 1（漏掉的那筆
     在產品裡就是自動入錯）。R 只漏極少數卻放行大量 A 這種取捨，帶數字用 AskUserQuestion 問使用者。「> 第一季集數」那一側
     錯的比例明顯不低時也先問，那表示規則 1 之外還少一條。
   - 數字、判準的結果、近似的限制寫進 `docs/research/profile-effect.md` §6.1（新的小節），摘進 brief §20.4；
     `scripts/experiments/README.md` 與根 README 的〈實驗腳本〉補這支。腳本不要 import `Profile`，14e 才不必連它一起刪。
2. **補兩筆語料當紅燈**（照 plan §4.6 與語料 README：真實檔案清單、逐筆 `source_url`、逐檔 `expected`）：
   - `anime/bleach-tybw-soukoku-tan-erai`：[nyaa 1950688](https://nyaa.si/view/1950688)，索引站標題
     `[Erai-raws] Bleach: Sennen Kessen Hen - Soukoku Tan - 01 ~ 14 [1080p DSNP WEB-DL AVC AAC][MultiSub] [BATCH]`，
     torrent 在 AnimeTosho（infohash `3592ff8c8e4873cfcce58f1391d11694d2120c43`）。**TMDB 快照 `tv-30984` 還沒錄**，
     加進語料之後跑 `scripts/record_tmdb_snapshots.py`。正解 **S02E27–E40**（研究 §4：S02E27 `A` 2024-10-05 …
     S02E40 `MY LAST WORDS` 2024-12-29）。現行規則下它是 `auto_wrong` 14——**先貼這個紅燈的 `berth bench` 輸出**。
     14c 從 torrent metadata 解出的檔案清單（多檔 torrent，路徑不含根資料夾；抄進語料前可再對一次 torrent）：

     | 路徑 | 位元組 |
     | --- | --- |
     | [Erai-raws] Bleach - Sennen Kessen Hen - Soukoku Tan - 01 [1080p DSNP WEB-DL AVC AAC][MultiSub][46878389].mkv | 1005682790 |
     | [Erai-raws] Bleach - Sennen Kessen Hen - Soukoku Tan - 02 [1080p DSNP WEB-DL AVC AAC][MultiSub][B84D074C].mkv | 1027267731 |
     | [Erai-raws] Bleach - Sennen Kessen Hen - Soukoku Tan - 03 [1080p DSNP WEB-DL AVC AAC][MultiSub][5FFBA8A1].mkv | 845597434 |
     | [Erai-raws] Bleach - Sennen Kessen Hen - Soukoku Tan - 04 [1080p DSNP WEB-DL AVC AAC][MultiSub][0897C7A1].mkv | 1138436893 |
     | [Erai-raws] Bleach - Sennen Kessen Hen - Soukoku Tan - 05 [1080p DSNP WEB-DL AVC AAC][MultiSub][EFF80224].mkv | 927448504 |
     | [Erai-raws] Bleach - Sennen Kessen Hen - Soukoku Tan - 06 [1080p DSNP WEB-DL AVC AAC][MultiSub][A1734715].mkv | 887387375 |
     | [Erai-raws] Bleach - Sennen Kessen Hen - Soukoku Tan - 07 [1080p DSNP WEB-DL AVC AAC][MultiSub][A695DE37].mkv | 1074281784 |
     | [Erai-raws] Bleach - Sennen Kessen Hen - Soukoku Tan - 08 [1080p DSNP WEB-DL AVC AAC][MultiSub][4FD5F4B3].mkv | 1070955540 |
     | [Erai-raws] Bleach - Sennen Kessen Hen - Soukoku Tan - 09 [1080p DSNP WEB-DL AVC AAC][MultiSub][D83A43C6].mkv | 899504051 |
     | [Erai-raws] Bleach - Sennen Kessen Hen - Soukoku Tan - 10 [1080p DSNP WEB-DL AVC AAC][MultiSub][2D7AD539].mkv | 904352363 |
     | [Erai-raws] Bleach - Sennen Kessen Hen - Soukoku Tan - 11 [1080p DSNP WEB-DL AVC AAC][MultiSub][5DC5FB94].mkv | 960025102 |
     | [Erai-raws] Bleach - Sennen Kessen Hen - Soukoku Tan - 12 [1080p DSNP WEB-DL AVC AAC][MultiSub][06EF2F73].mkv | 960377830 |
     | [Erai-raws] Bleach - Sennen Kessen Hen - Soukoku Tan - 13 [1080p DSNP WEB-DL AVC AAC][MultiSub][080FB8D7].mkv | 907725338 |
     | [Erai-raws] Bleach - Sennen Kessen Hen - Soukoku Tan - 14 [1080p DSNP WEB-DL AVC AAC][MultiSub][B1131AEC].mkv | 935238338 |

   - `anime/spy-x-family-05-subsplease`：[nyaa 1525282](https://nyaa.si/view/1525282)，
     `[SubsPlease] Spy x Family - 05 (1080p) [547FDE9F].mkv`（單檔 torrent，1,476,197,510 bytes；快照 `tv-120089`
     14c 已錄）。正解 S01E05。它記下規則 1 的代價：照原本的規則 1 改完之後它在 `review`；採用 R 的話它會是
     `auto_correct`，那就是 R 救回來的樣子。
   - 兩筆的語料 README 條目；`context.profile` 暫時照動漫寫 `anime`（14e 整批拿掉）。
3. `mattpocock-skills:tdd` 改 `_from_number`：不讀 `context.profile`；兩條規則（規則 1 照第 1 步定的形狀）各有單元測試，
   **雙向**——觸發時是 low 並帶理由、差一集 / 差一天（採用 R 時：標題沒有多餘字）不觸發。`150524` 讀成 2015-05-24 有測試。
4. `berth bench`：`auto_wrong` 0，《死神》14 檔是 `review`；`--update-baseline` 並在 commit 說明。
5. `uv run python scripts/experiments/profile_effect.py` 此時四種組合應該完全相同——貼輸出，當作「profile
   已經沒有讀者」的證據（腳本在 14e 刪）。
6. 文件：brief §6.4（只有集號那一條）、§6.5（medium 的定義）、plan §4.4（絕對編號換算）改成兩條證據；
   研究 §6.1 的原型數字換成實作量到的。

## 驗收

- [ ] `uv run python scripts/experiments/absolute_rule_cost.py` 可重跑；A、B、R 放行與漏掉的數量、「> 第一季集數」那一側的對錯、
      近似的限制寫進研究 §6.1 並摘進 brief §20.4；規則 1 的形狀照判準定案（需要時使用者已拍板），決定記進 `docs/progress.md`。
- [ ] 兩筆新語料進 `tests/fixtures/parser/`，README 已記；紅燈的 `berth bench` 輸出已貼（《死神》`auto_wrong` 14）。
- [ ] `mapping._from_number` 不讀 `context.profile`；規則 1、2 各有雙向單元測試；`ReleaseInfo` 帶播出日，`150524` 有測試。
- [ ] `uv run berth bench` 輸出已貼：`auto_wrong` 0、《死神》`review` 14、`Spy x Family - 05` 照第 1 步的結論（原規則 `review`、
      採用 R 則 `auto_correct`）；baseline 已更新。
- [ ] `profile_effect.py` 四種組合相同的輸出已貼。
- [ ] brief §6.4、§6.5、§19（Route profile 那一列的代價說明），plan §4.4，研究 §6.1 已改；兩支新腳本的 README 條目已補。
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest` 全綠，貼指令輸出。

**不做：**

- 拿掉 `routes.profile` 與其他任何讀寫 profile 的地方：14e。
- 讓《死神》相剋譚對到 S02E27–40（羅馬字篇章名 `Sennen Kessen Hen` 對 TMDB 季名）：送審核就是這一票的目標。
- 用索引站的發佈時間推測季（brief §6.4 提過）：解析器拿不到，研究 §4 也說明它分不出這兩種情形。

## Comments
