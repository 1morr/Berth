# 16 — 解析器：以發佈時間推測虛擬季

**Status:** done

**Blocked by:** 14（發佈時間已帶到規劃）

**讀:** plan §4.4、§4.6（benchmark）、§11.4（「M1 帶過來的一條」）；brief §6.4；`docs/research/profile-effect.md` §4；`docs/research/anime-episode-source.md` §6.4

## 做什麼

M1 票 06 刻意沒做的那一條：brief §6.4「以**發佈時間**推測虛擬季」（AutoBangumi v3.2 的做法）。當時解析器拿不到發佈時間，而 RSS item 一定帶著。

`mattpocock-skills:tdd`，benchmark fixture 就是紅燈：

- **自己的語料**：從票 07 的 fixture 與 Mikan 單一 feed 裡挑 split-cour、第二 cour 從 01 重數、TMDB 併成一季的作品，帶著發佈時間進 benchmark 語料。
- **規則**：發佈時間落在哪一個虛擬季（§4.4 的 180 天切法，不要調小）的播出區間，就用那個虛擬季換算。Candidate 標一個新的 `strategy`，信心至多 medium。
- 與票 14 的分工：這一條是**推測**，票 14 是**驗證**。推測錯了由驗證擋下，所以兩者要能同時存在而不互相抵銷；寫一條測試證明推測出的集數仍會被播出日比對檢查。
- 它要能分開 `profile-effect.md` §4 說的兩種讀法（第一季第 N 集 vs 後面某季從 01 重數），分不開的仍送審核。

解析器改動必跑 `berth bench`，`auto_wrong` 不得上升（專案 CLAUDE.md）。

## 驗收

- [x] 新語料進 benchmark，改動前是紅的（貼改動前的 bench 輸出）
- [x] 改動後 `berth bench` 的 `auto_wrong` 不升，新語料的自動入庫率提升（貼前後數字）
- [x] 推測結果仍經過播出日比對（整合測試）
- [x] plan §4.4 把「沒有做」那一句改成實際的規則
- [x] lint、type、test 綠燈

## Comments

**語料**（`tests/fixtures/parser/README.md` v6）：四筆新的《死神 千年血戰篇》（TMDB 把四輪併成第 2 季）——Erai-raws
訣別譚 `- 01`、禍進譚 `- 08`，shincaps 禍進譚 `- 08`（AT-X，晚 13 天），桜都字幕组禍進譚 `千年血战篇 [08]`；兩筆舊語料
補上 `published_at`（`spy-x-family-05-subsplease`、`bleach-tybw-soukoku-tan-erai`）。新欄位 `published_at` 一定帶時區，
沒帶的 `load_corpus` 拒收。「TMDB 併成一季、重數又沒有季號」的真實樣本在 Mikan / nyaa / AnimeTosho 上都沒找到
（Re:Zero、芙莉蓮重數的全帶季號），由單元測試的 Re:Zero 形狀守著。

**改動前**（HEAD 程式碼 + 新語料，另開 worktree 跑）：

```
bench: 1 file(s) auto-applied wrongly
bench: auto_wrong rose from 0 to 1
38 fixtures, 391 files
category  files  ...  auto_correct  auto_wrong  review
anime     229    ...  113           1           22
overall   391    ...  172           1           84
high: 0/84 wrong (0.0%)  medium: 1/89 wrong (1.1%)        exit=1
```

**改動後**：

```
38 fixtures, 391 files
category  files  ...  auto_correct  auto_wrong  review
anime     229    ...  118           0           18
overall   391    ...  177           0           80
high: 0/84 wrong (0.0%)  medium: 0/93 wrong (0.0%)        exit=0
```

帶發佈時間的 19 個檔案（新語料 4 + 舊語料 15）：自動入庫對 0 → 5、自動入錯 1 → 0、審核 18 → 14。留在審核的 14 個是
相剋譚的整輪合集：最後一集播出 82 天後才發，不算剛播，照規則分不開。baseline 更新成 `auto_correct 177`。

**規則與票面的偏差**（使用者未拍板，記在 progress.md「偏差與決定」）：票面是「發佈時間落在哪一個虛擬季的播出區間，
就用那個虛擬季換算」。先照這個做（那一輪第 N 集已播、那一輪離最後一集不到六週），子代理找語料時發現 shincaps 在
Re:Zero 第三輪播完兩週後錄的 `- 01`（nyaa 1957100，大小與片長像第一季重播）會被讀成 S01E51，所以改成「剛播」
競爭：各讀法換算出的那一集裡只有「某一輪的重數」那一個是發佈前六週內播的，才推測。另外把它套到**季號來自篇章名、
那一季裡有好幾輪**的情況——桜都字幕组那一筆就是這樣自動入錯的（`千年血战篇` 對到第 2 季，照字面讀是 2022 年的
S02E08）。

**「推測錯了由驗證擋下」只成立在邊角**（Spec 軸指出）：推測只收剛播的讀法，剛播正是規則一放行的條件；規則二只在
最近播出的一集落在發佈後兩天內、而且晚六週以上時擋得下。整合測試守的是「推測出的集數沒有繞過比對」（停播六週
的邊角，`TestPublishedRun`），plan §4.4 照實寫了：推測錯了主要靠 medium 的 audit 與第一批審核。手動送單不過規則二。

**code-review（對 `59fa197`，工作樹）**：
- Spec 軸：
  - 修了：`- 00` 被讀成一輪的最後一集（`rows[-1]`）。同一個洞也在既有的 `_virtual`（`Re Zero 第二季 - 00` 以
    medium 入成 S01E50）與 `_cour`，三處收成 `_counted_in`，紅 → 綠三條。
  - 修了：明說的 `S02E08` 也被推測改寫（brief「顯式 SxxEyy → 直接採用」）。季內推測只限篇章名，紅 → 綠。
  - 修了：plan §4.4 對驗證的敘述誤導（見上）。
  - 保留：搜尋結果的季集預估也吃發佈時間（票面沒提）——預估與送單之後的規劃要一致，否則結果表寫 S01E05、入庫卻是
    S01E17。
- Standards 軸：
  - 修了：`CONTEXT.md` 的 Mapping Strategy 清單補 `published_run`（硬違規）。
  - 修了：搜尋預估與 RSS 送單前去重改帶發佈時間卻沒測試（硬違規）——`test_search.py` 與
    `test_air_date_check.py::TestPublishedRun::test_a_reupload…` 各一條，拿掉發佈時間都會紅。
  - 修了：`_virtual` 改用 `_runs`、`_Mapped.target` 取代三處手拆 tuple、`_Run` 的說明對上名詞表的 Cour / Virtual season。
  - 沒修：`_published_run` 內部重算 `len(_runs(media))`（便宜，換來簡單的參數）；`media, info, span, check` 一起
    傳是這個模組既有的形狀，不在本票拆。

**UI 沒有用 playwright 實跑**：前端只多了一條理由句子（`published_in_run`，zh-Hant / en）、一個策略名稱與 audit 收起時的
主要原因，沒有新元件或版面。守它的是 `tsc`（`jobs.plan.why.*` 少一句是型別錯誤）與 `test_reason_codes.py` 的兩語佔位符
比對。要看它長什麼樣，得有一個 TMDB 併季作品的演練情境，這一票沒有做。
