# 14c — Profile 去留：補踩得到絕對編號分支的語料，量過再決定

**Status:** ready-for-agent

**Blocked by:** 無硬相依（2026-09-15 插入，排在 14b 之後、15 之前：結論若是移除或改名，精靈與 Route 設定頁的 UI 會變，
票 15 的 UI 收尾要審的是定案之後的樣子）

**讀:** plan §4.4（「絕對編號換算」那一條）、§4.6、§8.4（動漫 profile 的季號變體）；brief §6.4、§6.5、§20.3（TMDB 合併季、
Sonarr 的 Series Type）、§20.4（樣本清單、韓劇 `E01` 無季）；`tests/fixtures/parser/README.md`；
`docs/research/anime-episode-source.md`；CONTEXT.md 的 **Profile** 與 **Library Route**

## 做什麼

Route 的 profile（`standard` / `anime`）在介面上叫「命名 profile」。2026-09-15 查證（票 14a 之後的對話）發現：

- **它不影響命名。** brief §7.1 的劇集與動漫是同一套模板，`berth/naming/` 沒有任何一處讀它。
- 真正讀它的只有三處：
  1. `berth/parser/mapping.py` 的 `_from_number`：發佈只有集號、TMDB 上又不只一季時，把集號當絕對編號換算
     （`absolute_group`、`absolute_cumulative`）。`anime` 給 medium；Route 預設 `medium_auto_import`，所以會自動入庫。
     `standard` 給 low 並附理由 `absolute numbering is an anime convention; this route is not anime`，也就是送審核。
  2. `berth/services/search.py` 的 `search_titles`：`anime` 多問最新一季的 `<英文標題> Season N` / `<標題> 第N季`，
     佔掉排最後的別名。
  3. `berth/services/routes.py` 的 `_check_profile`：電影媒體庫的 Route 不收 `anime`（`profile_unsupported`）。

**用現有語料量過，profile 對解析結果零影響。** 語料 23 筆、333 個檔案，其中 13 筆是 `anime`。以四種組合重算：原樣、
每筆翻轉、全部 `standard`、全部 `anime`。逐檔的桶完全相同：

| auto_correct | auto_wrong | review | missed | unmatched_correct | extra_correct | subtitle_correct | skipped |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 140 | 0 | 61 | 0 | 42 | 41 | 37 | 12 |

原因是第 1 點那一段在語料上**一次都沒走到**。以 monkeypatch 側錄，`_from_number` 被呼叫 34 次，每一次都在前面
「TMDB 只有一季」（`single_season`）的分支就回傳了。這與 brief §20.3 對得上：

- TMDB 近年連獨立的連續季也在併，例如咒術迴戰 3 季併成 1 季 59 集。
- 票 06 的篇章名、cour 偏移、虛擬季已經接住多數沒有季號的動漫發佈，那幾條都不看 profile。

所以 profile 現在是一個「使用者每建一條 Route 都要回答、卻量不出作用」的設定。這張票補上踩得到那一段的語料再量一次，
讓去留有證據。

## 怎麼做

1. **補語料。** 照 plan §4.6 的規矩：
   - 真實 torrent 的檔案清單、逐筆 `source_url`、`expected` 逐檔寫。
   - TMDB 快照用 `scripts/record_tmdb_snapshots.py` 錄一次凍結。
   - 出處與涵蓋範圍記進 `tests/fixtures/parser/README.md`。

   至少要有兩類：
   - **動漫、只有集號、TMDB 上多季。** 檔名沒有季號也沒有篇章名、集號超過第一季集數的真實發佈，長壽作品的絕對編號最典型。
     TMDB 合併季很激進，**候選作品先查快照，確認真的有 ≥ 2 個正規季**，不要憑印象挑。
   - **非動漫、只有集號、TMDB 上多季。** 這是反例，驗證 `standard` 擋的東西是不是真的會錯。先看韓劇
     `Show.E15.YYMMDD…-NEXT` 這種無季寫法：brief §6.4 規定它視為 Season 1，所以要找「其實是第二季以後」的那種。
     找不到就記下找過哪些。

   每一筆都要**證明真的走到絕對編號分支**：沿用下面實驗的側錄法，把命中的策略寫進研究文件。沒走到的那筆不算數，換一筆。
2. **把實驗做成可重跑的腳本** `scripts/experiments/profile_effect.py`，位置與慣例同 `anime_episode_source.py`：
   - 讀 `bench.load_corpus`，以 `dataclasses.replace(fixture, profile=…)` 產出四種組合（原樣 / 翻轉 / 全 `standard` / 全 `anime`）。
   - 用 `bench.score`、`bench._add`、`bench.render` 算報表，逐檔比對 `bench.bucket` 的差異。
   - 另外側錄 `mapping._from_number` 走到哪一個分支。
   - 不改 repo 裡的任何語料或程式碼。
3. **寫 `docs/research/profile-effect.md`。** 內容是四種組合的桶、逐檔差異、每筆新語料命中的分支。結論摘進 brief §6.4 或
   §20.4 並附連結。
4. **帶著數字請使用者拍板**：用 AskUserQuestion，推薦項放第一個，判準寫在問題裡。
   - **保留**：新語料上 `standard` 與 `anime` 在 `auto_wrong` 或 `auto_correct` 真的有差。例如非動漫反例在 `anime` 下自動入庫錯了、
     在 `standard` 下送審核。保留的話：
     - 介面上的「命名 profile」改成說得出實際作用的名字，zh-Hant / en 並列。
     - CONTEXT.md 的定義從「命名與解析偏好」改成實話。
     - brief、plan 同步。
   - **移除**：兩種 profile 在新語料上也沒有差。這張票**不做移除**，只開出後續票並列檔案清單，至少包含：
     - `routes.profile` 欄位與 migration。
     - API 形狀裡的欄位：`RouteIn`、`RouteEditIn`、`RouteSelectionIn`、`RouteOut`、`LibraryChoiceOut`。
     - 精靈與設定頁的 `ProfilePicker`。
     - `_check_profile` 與 `profile_unsupported`。
     - `ParseContext.profile` 與語料裡的 `context.profile`。
     - 搜尋的季號變體：改成對所有劇集都做，還是拿掉。
     - CONTEXT.md、brief、plan、PRODUCT.md。
   - **改成作品層級**：數字顯示有用，但「一條 Route 一個設定」的粒度不對，例如同一個媒體庫混著動漫與非動漫。這要另一輪查證
     （怎麼從作品本身判斷），同樣只開後續票，不在這張票做。
5. **更新 baseline。** 語料變了，`tests/fixtures/parser/baseline.json` 照 plan §4.6 更新，並在 commit 說明。`auto_wrong`
   不得上升；上升代表找到了解析器缺陷，另開票，不在這裡改解析器。

## 驗收

- [ ] 至少兩筆新語料：動漫絕對編號 ≥ 1、非動漫只有集號 ≥ 1（後者找不到時記下找過的作品與理由）。逐筆 `source_url`、
      TMDB 快照已錄、README 已記。
- [ ] 每筆新語料走到 `_from_number` 絕對編號分支的側錄證據寫在研究文件。
- [ ] `uv run python scripts/experiments/profile_effect.py` 可重跑，四種組合的報表與逐檔差異寫進
      `docs/research/profile-effect.md`，結論摘進 brief。
- [ ] `uv run berth bench` 輸出已貼上；baseline 已更新；`auto_wrong` 沒有上升。
- [ ] 使用者已拍板（保留 / 移除 / 改成作品層級），決定記進 `docs/progress.md`「偏差與決定」。
- [ ] 保留：介面文案、CONTEXT.md、brief、plan 已改，前端測試綠。移除或改粒度：後續票已開、檔案清單已列、
      `docs/progress.md` 里程碑列的票數已更新。
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest` 全綠，
      貼指令輸出。動到前端時再加 `pnpm -C web format:check && pnpm -C web typecheck && pnpm -C web lint && pnpm -C web test`。

**不做：**

- 移除 profile 或改成作品層級的實作：拍板之後另開票。
- 量搜尋季號變體的效果：要打真的索引站，替身量不出來；移除時怎麼處理由後續票決定。
- TVDB / anime-lists 當季集來源：brief §10 已結案。
- 為了讓 profile 有作用而改解析器規則。

## Comments
