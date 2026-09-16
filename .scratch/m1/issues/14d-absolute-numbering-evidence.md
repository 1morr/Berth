# 14d — 絕對編號換算改由證據決定信心，不再看 Route profile

**Status:** ready-for-agent

**Blocked by:** 14c（2026-09-16 插入，排在 14c 之後、14e 與 15 之前：14e 要拿掉的欄位，解析器先不讀）

**讀:** `docs/research/profile-effect.md` §0、§3、§4、§6.1；brief §6.4、§6.5、§19（Route profile 那一列）、§20.4（「只有集號、TMDB 上多季的真實發佈」）；plan §4.4（「絕對編號換算」那一條）；`tests/fixtures/parser/README.md`（v2 那一節）

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
`[SubsPlease] Spy x Family - 05`。沒有訊號分得出它與《死神》那種重數。

## 怎麼做

1. **先補兩筆語料當紅燈**（照 plan §4.6 與語料 README：真實檔案清單、逐筆 `source_url`、逐檔 `expected`）：
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
     14c 已錄）。正解 S01E05。它記下已知代價：改完之後它在 `review`，數字看得見。
   - 兩筆的語料 README 條目；`context.profile` 暫時照動漫寫 `anime`（14e 整批拿掉）。
2. `mattpocock-skills:tdd` 改 `_from_number`：不讀 `context.profile`；兩條規則各有單元測試，**雙向**——
   觸發時是 low 並帶理由、差一集 / 差一天不觸發。`150524` 讀成 2015-05-24 有測試。
3. `berth bench`：`auto_wrong` 0，《死神》14 檔是 `review`；`--update-baseline` 並在 commit 說明。
4. `uv run python scripts/experiments/profile_effect.py` 此時四種組合應該完全相同——貼輸出，當作「profile
   已經沒有讀者」的證據（腳本在 14e 刪）。
5. 文件：brief §6.4（只有集號那一條）、§6.5（medium 的定義）、plan §4.4（絕對編號換算）改成兩條證據；
   研究 §6.1 的原型數字換成實作量到的。

## 驗收

- [ ] 兩筆新語料進 `tests/fixtures/parser/`，README 已記；紅燈的 `berth bench` 輸出已貼（《死神》`auto_wrong` 14）。
- [ ] `mapping._from_number` 不讀 `context.profile`；規則 1、2 各有雙向單元測試；`ReleaseInfo` 帶播出日，`150524` 有測試。
- [ ] `uv run berth bench` 輸出已貼：`auto_wrong` 0、《死神》`review` 14、`Spy x Family - 05` `review` 1；baseline 已更新。
- [ ] `profile_effect.py` 四種組合相同的輸出已貼。
- [ ] brief §6.4、§6.5，plan §4.4，研究 §6.1 已改。
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest` 全綠，貼指令輸出。

**不做：**

- 拿掉 `routes.profile` 與其他任何讀寫 profile 的地方：14e。
- 讓《死神》相剋譚對到 S02E27–40（羅馬字篇章名 `Sennen Kessen Hen` 對 TMDB 季名）：送審核就是這一票的目標。
- 用索引站的發佈時間推測季（brief §6.4 提過）：解析器拿不到，研究 §4 也說明它分不出這兩種情形。

## Comments
