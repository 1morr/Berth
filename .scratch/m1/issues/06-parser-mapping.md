# 06 — 解析器：季集對應與信心

**Status:** done

**Blocked by:** 05

**讀:** plan §4.1（structure_hints / map_episode / score）、§4.3、§4.4；brief §6.4、§6.5、§6.6

## 做什麼

把 ReleaseInfo 對應到 Media 的季與集，並給出三級信心。這是 M1 最難的一段，也是 benchmark 數字
第一次真的動起來的地方。

含資料夾結構提示、brief §6.4 的比對順序、三種絕對編號換算（episode group absolute、累計集數、
air_date 虛擬季 offset）各自產一個 Candidate 並附理由，以及 brief §6.5 的信心定義與批次一致性檢查。

票 01 已定案**維持 TMDB**，`ParseContext` / `MediaSnapshot` 不變。但票 01 量到的兩件事要做進來，
它們才是失敗率的主要槓桿（`docs/research/anime-episode-source.md` §7、plan §4.4）：

- **篇章名 → 季號**：九成的換算失敗是檔名只有「柱訓練篇」「最終季」「死滅迴游」這種篇章名而
  沒有季號。用 `MediaSnapshot` 的各季 `name`（TMDB 的 `season.name`）與 alternative titles 比對，
  命中就等同季號提示，另產一個 `strategy = arc_name` 的 Candidate，confidence 至多 medium。
- **「最終季 / Final Season」對到最後一季。**
- **`第二部分` / `Part.2` 當成 cour 偏移**：唯一「檔名有季號卻還是三家一起錯」的一類
  （`[星空字幕组][进击的巨人 第三季 第二部分 / Season 3 Part.2][01-10]`，正確答案是 S3E13–22）。
  看到這個標記就把同一季前面幾個 cour 的長度加上去。

plan §4.4 的虛擬季門檻維持 **180 天**（已被量測支持，調成 60 天會變差），不要順手改小。

做完這三條之後，順手看一下 benchmark 的季集失敗還剩什麼形狀：brief §10 的「什麼情況該回頭重看」
第 2 條就是拿這個當觸發條件（現在 provider 結構差異只佔 1%，主因是上面這些解析器缺口）。

## 驗收

- [x] `structure_hints` 認得 `Season 2` / `S2` / `第二季` / `2nd Season` / `Part 2` / `Specials` /
      `SPs`，以及 `Subs/` `字幕/` 與其下的語言子資料夾
- [x] `map_episode` 依 brief §6.4 的順序產 `Candidate`，三種絕對編號換算各自產一個並附 `strategy` 與理由
      （**三種不在同一個分支**，見 Comments 第 1 條）
- [x] offset 偵測（季內 `air_date` 間隔 > 180 天切虛擬季）有測試；該策略的信心至多 medium
- [x] 上下文缺 Media 時做標題比對（正規化後比 `name` / `original_name` / alternative titles /
      translations，年份加權）
- [x] 多集檔、合集、多季（brief §6.6）在語料裡各有涵蓋並解對
- [x] `score` 實作 brief §6.5 的三級定義；批次一致性檢查（同模式、連續集號、數量吻合）有測試
- [x] `berth bench`：`auto_wrong = 0`，`auto_correct` 高於票 05 的 baseline（0 → 140）
- [x] baseline 更新，改善的數字寫在 commit message 的 body
- [x] anime 與 tv / movie 的數字分開報告
- [x] lint / type / test 全綠並貼指令輸出

## Comments

**做完的樣子**：`berth bench` 23 筆語料 333 個檔案，`auto_correct` 0 → **140**（語料寫下的
128 個 import 全對，加上票 06 新增的 12 個），`auto_wrong` **0**，`missed` **0**，
`unmatched_correct` 14。剩下的 126 個 review 是字幕（37）、特典的字幕（28）與整張 BD 原盤
（61），三者都要等票 07。

**這一票的決定**（每一條都寫進了 plan / brief / 語料 README）：

1. **絕對編號的三種換算不在同一個分支**（plan §4.4 已補）。`absolute_group` 與
   `absolute_cumulative` 是「只有集號」時的兩條路；虛擬季換算要有一個季號才索引得到那一輪
   播出，所以它掛在「檔名有季號但 TMDB 沒有這一季」那條路上。brief §6.4 另外提的
   「以**發佈時間**推測」需要索引站給的發佈時間，M1 的解析器拿不到（票 08 起才有），
   沒有它就只是換一種猜法——**刻意沒做**，票 08 接上 `published_at` 之後可以回頭補。
2. **季名要三輪語言**（`en-US` / `zh-TW` / `zh-CN`）。真實發佈寫的是「柱训练篇」，而 TMDB
   的英文季名是 `Hashira Training Arc`——只留一套字的話，plan §4.4 那條「九成失敗」的規則
   對它一個都不會命中。代價是 `tv/{id}` 多打一輪（只取季名，電影不打），`SeasonSnapshot`
   多一個 `names`，18 份快照重錄。實測見 brief §20.3。
3. **特典不靠集名或片長比對**（票 05 留下的問題）。檔名裡沒有集名，片長要 mediainfo。規則
   維持兩條：明說 `S00Exx` 就照它走但信心至多 medium，只寫 `[SP][01]` 這種自己的序號則是
   `unmatched`。理由寫在 `tests/fixtures/parser/README.md`。
4. **語料補三筆**：篇章名（鬼滅之刃 柱訓練篇）、cour 偏移（進擊的巨人 Season 3 Part 2）與
   單檔多集（`- 01-02` 的 `.ts`）。三筆都是先抓 `.torrent` metadata 解出檔案清單，
   `source_url` 逐筆可查。

**票 05 留下、這一票收掉的兩件事**：`min_confidence` 與 `context.profile` 現在都有人讀了
（前者是報表的第四欄，後者決定絕對編號換算的信心上限）。語料缺的 `sample` 仍然只有單元測試。

**code-review（Standards / Spec 兩軸）之後改的**：信心的順序與封頂收進 `domain`
（原本散在四個模組，其中一份順序還是反的）、特典自編號的判斷只留一份、季號的中文寫法在
`cjk` 與 `structure` 共用同一個 pattern、`match_media` 從「只有測試在用」接上生產路徑、
brief §6.5 的「數量明顯不符 → low」補上、區間的尾巴算不出來時降到 low（原本會靜默把多集檔
變成單集檔）、`_generic` 原本認不出 `第1季`。

**留給後面的票**：`match_subtitle` 與目標路徑（票 07）；`published_at` 到位後的虛擬季換算
（票 08 之後）；`title.match_media` 的候選池目前只有 `ParseContext.candidates` 這個入口，
真正把 TMDB 搜尋結果餵進去的是 M3 的 RSS。
