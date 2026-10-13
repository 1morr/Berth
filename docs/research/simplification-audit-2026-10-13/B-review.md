# B 複核

複核方法：每條都自己重新 grep `berth/`、`tests/`、`scripts/`、`web/src`（必要時加 `docs/`），打開兩邊的程式碼讀過，並在 `docs/progress.md`（「偏差與決定」從第 224 行起）、`docs/plan.md`、`docs/design-brief.md` 與程式註解裡找保留理由。只讀，沒有改任何 repo 檔案。

| 編號 | 判定 | 理由（自己查到的證據） | 修正後的建議 / 大小 / 風險（若有改） |
|---|---|---|---|
| B1 | 通過但修正 | `grep -rn route_collection_type` 的結果：定義在 `berth/domain/parser.py:647`；寫入有 `berth/services/plan.py:492`、`berth/services/search.py:634`、`tests/unit/test_parser_first_batch.py:254`，另外還有 worker 漏掉的 `scripts/experiments/first_batch_rule.py:55,94` 與 `scripts/fake_setup_server.py:2616`。`berth/parser/`、`berth/naming/` 對 `collection_type`/`CollectionType` 的 grep 是 0，`ParseContext` 在 parser 內也沒有被 `model_dump` 或 `getattr` 動態讀取（`release.py:165` 的 `model_dump` 處理的是 `ReleaseInfo`）。`adapters/ai.py` 的 `AiPlanner.propose(context, …)` 會收到 `ParseContext`，但它沒有呼叫端，`NullAiPlanner` 也不讀 context。progress.md 沒有寫保留理由。 | 除了 worker 列的地方，scripts 的三處 kwarg 也要一起刪。`search.py` 的 `collection_type_for` import（`search.py:48`）只在第 634 行用到，要一併拿掉，那一行沒有其他副作用。plan §4.3（`docs/plan.md:285`）要同步改。大小：小。風險：純內部，不經 API 也不持久化。值得度維持高。 |
| B2 | 通過但修正 | `_take_subtitle_kind`（`berth/parser/cjk.py:232-240`）一次回兩個值：`True/False/None` 與 `HARDSUB/EXTERNAL/SOFTSUB/UNKNOWN`，前者可由後者推出。`CjkHints` 的消費端是 `release.py:149`，只取 `hints.subtitle_kind`。`.hardsub` 的其他讀取都屬於 `Tags.hardsub`（`release.py:191`、`api/search.py:46`、`bench.py:339`、`naming:455,476`）。`CjkHints.hardsub` 只有 `tests/unit/test_parser_cjk.py:61,67,73,80` 在讀。`CjkHints` 沒有被序列化，沒有出現在 API 或 DB。 | 刪欄位，`_take_subtitle_kind` 改成只回 `SubtitleKind`，測試改斷言 `subtitle_kind`。另外要同步改 `docs/plan.md:271` 的 `CjkHints` 欄位清單（它列了 `hardsub: bool | None`）。大小：小。風險：純內部。 |
| B3 | 通過但修正 | `ReleaseInfo.video_codec/bit_depth/audio`（`berth/domain/parser.py:539-541`）只在 `release.py:145-147` 寫入。`grep -rnE "video_codec|bit_depth|\baudio\b"` 在 berth/tests/scripts/web 的其他命中分別屬於 `MediaInfoSummary`、`FileKind.AUDIO`、i18n 的 `audio` key，沒有一處讀 `ReleaseInfo` 的這三格。`ReleaseInfo` 也沒有離開 parser：services 只取 `.group/.episode/.title_candidates`，或透過 `tags_of`；progress.md:821 記著 `job_files.release_info_json` 沒有填。`merge_release` 雖然泛用地 `model_dump`，但只是複製欄位，不算消費。 | worker 漏了一個文件依據：`docs/design-brief.md:207`（§6.3「發佈名解析 → ReleaseInfo」）把 `video_codec`、`bit_depth`、`audio` 列為 ReleaseInfo 的規格欄位。brief 是決定衝突時的準據，所以刪除時要同一個 commit 改 brief §6.3，並在 progress.md 記一行偏差。大小：小。風險：純內部，不經 API 也不持久化。 |
| B4 | 改判刻意保留 | 讀取者確實只有 `duration_s`（`services/plan.py:252,562`）。`width`、`height`、`video_codec`、`bit_depth`、`audio_langs`、`subtitle_tracks` 全部沒有讀取者；worker 少列了 `SubtitleTrack.lang/title/default`，它們同樣沒人讀。不過保留有成文理由：progress.md:919（票 15 Comments 逐條，標「不排里程碑、維持現狀（等證據或等消費者）」）列了「Tags 的解析度改讀 mediainfo（票 11，等發佈名說謊的真實案例）」，這要靠 `width/height`。brief 也把它們定為規劃訊號：`docs/design-brief.md:150`、`:181` 寫「時長、影音軌、內封字幕語言」，`:271` 寫解析度「mediainfo 優先」。plan §8.7（`docs/plan.md:561`）把整組定為 `probe()` 的回傳。這些資料已經持久化在 `job_files.mediainfo_json`，要等之後的消費者用。 | 移到「刻意保留」，出處：progress.md:919、brief:150/181/271、plan.md:561。若使用者仍想縮減，風險要照 worker 寫的：既有 JSON 只當 dict 讀（`plan.py:252`），刪欄位不需要 migration。 |
| B5 | 通過但修正 | 逐欄 grep（含 `web/src/api/schema.d.ts`，0 命中）：`jobs.last_seen_in_client_at` 只在 `claims.py:234`、`downloads.py:458` 寫入；註解 `models/job.py:70` 說要在「torrent 從客戶端消失時」用它，但這個消費者不存在。`plans.decided_by/decided_at` 寫入在 `plan_review.py:161-162,190-191`、`rematch.py:603-604`，讀取只有測試（另有 `tests/integration/test_database.py:206` 的原生 SQL INSERT）。`ledger.source_inode` 只寫不讀：`inode_mismatch` 與刪除檢查讀的是 `(source_dev, target_inode)`（`services/deletion.py:368`）。`ledger.link_mode` 永遠是 `HARDLINK`。`users.last_login_at` 只寫不讀。`job_files.updated_at` 只寫不讀。API 回應的 Out 模型沒有任何一個帶這些欄位，`from_attributes` 也不會帶到。 | 需要修正四點。(1) `job_files.updated_at` 還有一個寫入點 `services/reimport.py:129`，worker 漏了。(2) `settings.updated_at`（`models/setting.py:37`，ORM 的 `onupdate` 自動寫，讀取者為 0）worker 在工具表判成「誤報」，判錯了，應該併入本條。(3) `ledger.source_inode` 是 NOT NULL 且沒有 default，刪它要改 4 處產品寫入（`claims.py:359`、`importer.py:373`、`issues.py:379,475`），以及 11 處建列的 tests/scripts（`tests/integration/test_inventory.py:254`、`test_plan.py:246,391`、`test_routes.py:731`、`test_rss_api.py:512`、`test_rss_backfill.py:120`、`test_rss_series_view.py:213`、`scripts/experiments/large_library_berth.py:434`、`scripts/fake_setup_server.py:2228,2539,2631,3161`），大小算中偏大。`link_mode` 一刪，`models/ledger.py:37` 的 `HARDLINK` 常數與 `models/__init__.py:11,59` 的 re-export 也跟著失去用途。(4) migration 的地雷要寫清楚：`7c3e5a9b2d41_m1_ledger_series_id.py` 的 docstring 記載 ledger 用 batch 重建時，兩個外鍵的順序是反射出來的、不固定，會讓「降回去再升上來是同一份 schema」那條測試失敗，所以該檔升版改用原生 `ADD COLUMN`。刪 ledger 欄位應該用 SQLite 原生 `DROP COLUMN`（這幾欄沒有索引也沒有外鍵），不要用 batch。大小：中（一支 migration 加上述寫入點）。風險：動到持久化資料與 migration，plan §2（`docs/plan.md:105,127,131,134`）要同步改。值得度維持低；worker 提的「只改文件、承認是稽核欄位」是合理的替代方案。 |
| B6 | 通過 | 讀了三份：`domain/parser.py:379-401`（`ReasonParams`/`ItemReason`/`why`）、`domain/binding.py:91-105`（`BindReason`/`because`）、`domain/screening.py:56-66`（`SkipReason`/`skipped`）。模型形狀相同，檢查本體 `frozenset(params) != X_PARAMS[code]` 逐字相同，`grep "frozenset(params)"` 正好 3 處。「不能有 `count` 鍵」這條規則也在三處註解各寫一次，由三支測試分別守。兩支 docstring 只寫「形狀照 X」（`binding.py:3`、`screening.py:3`），說明是有意照抄，但沒寫為什麼不共用；progress.md「偏差與決定」也找不到理由，所以不算刻意保留。 | 同 worker：抽一個泛型基底或小工廠，code enum、參數表、i18n 命名空間仍各自保留。JSON 形狀（`code` + `params`）不能變，因為 `plan_items.reasons_json` 已經持久化，`api/plans.py:114`、`api/rss.py:185,267` 也是對外形狀。大小：中。風險：只動 Python 就不動 API 或持久化。值得度低。 |
| B7 | 駁回 | 兩邊不是同一件事。`naming.episode_target`（`naming/__init__.py:97-99`）組的是 Jellyfin 檔名規格（brief §20.1，帳本與 Jellyfin 之間的合約）；`domain.episode_label`（`domain/parser.py:403-406`）的 docstring 寫明它是「理由的參數與畫面」用的機器字串，消費者是 `why(...)` 的參數，以及 `services/first_batch.py:140`、`services/plan.py:792` 的畫面文字。`naming` 的模組 docstring（`naming/__init__.py:3-5`）寫「模板…凍結…要改模板只改這裡，不影響其他模組」。照 worker 的建議讓檔名改走 `episode_label`，以後調整畫面或理由的格式就會靜靜地改掉媒體庫檔名，反而違反這條。airing/runtime 的 `end if end != start else None`（`parser/airing.py:67`、`parser/runtime.py:67`）是呼叫端多做一次已被被呼叫端涵蓋的判斷，屬於寫法層級，不會讓兩套規則長出不同答案。 | 不列。順手清掉 airing/runtime 那個多餘的三元式也可以，但它不在本票範圍內。 |
| B8 | 通過 | `services/claims.py:83` 的 `_TMDB_ID = re.compile(r"\[tmdbid-(\d+)\]$")` 是 `naming.FOLDER_TEMPLATE`（`naming/__init__.py:19-21`）的反解，寫在 naming 之外。產品碼裡只有這一份（`grep tmdbid` 結果）；`scripts/fake_setup_server.py:957` 的 `TMDB_TAG` 是開發腳本裡的第三份。作品資料夾的「寫」與「讀」分屬 naming 與 services 兩個模組。 | 補一點修正：後果比 worker 寫的輕。`claims.py:338` 用 regex 取得候選後，`read_target`（`claims.py:347` → `naming/__init__.py:331` 的 `parts[0] != folder_name(media)`）會用模板重算一次核對，所以模板漂移的結果是「認不出」，不會「認錯」。建議照舊：在 naming 加 `tmdb_id_of(folder)`。大小：小。風險：無對外介面。值得度低。 |
| B9 | 通過 | `parser/classify.py:124` 的 `kind_by_extension` 與 `:172` 的 inline `_BY_EXTENSION.get(extension(...))` 查的是同一張表。現在答案相同（`None` 與 `OTHER` 在 `is not VIDEO` 下等價）。只要 `kind_by_extension` 日後加了特例，`_biggest_video_per_directory` 不會跟著改，就會長出不同答案。 | 同 worker（改一行）。大小：小。風險：無。值得度最低，可以併進下一張動 classify 的票。 |
| B10 | 改判刻意保留 | 引用數確認是 0：`PlanEngine.AI` 在 berth/tests 都沒有引用，寫入只有 `RULES`（`services/plan.py:889`）與 `USER`（`plan_review.py:131`、`rematch.py:596`）。但 worker 對 progress.md:15 的解讀不完整。`docs/plan.md:322`（2026-09-24 改寫後的現行版本）寫明 M5 AI 任務的核心是 `AiPlanner.propose` 產出一份 Plan，「驗證通過後依任務模式（影子 / 自動）記錄或套用」；自動模式套用的 Plan 就需要一個 engine 值。`docs/design-brief.md:159` 的 `plan_generated(engine=rules|ai, …)` 與 `docs/plan.md:131` 的 `engine`（`rules` / `ai` / `user`）都把它列為規格。而且它在對外 API 型別裡（`web/src/api/schema.d.ts` 的 `"rules" \| "ai" \| "user"`，來源 `api/plans.py:170`），刪掉等於改對外介面。 | 移到「刻意保留」，出處：plan.md:322、brief:159、plan.md:131。另外有一處小落差可以順手記下：`domain/enums.py:1011` 的註解還寫「M4」，2026-09-24 已改到 M5（progress.md:15）。 |
| B11 | 通過但修正 | 用 AST 重掃三個 `__init__.__all__` 以外的檔案，零使用的名稱與 worker 列的完全一致：parser 是 `SAMPLE_RATIO, VIRTUAL_SEASON_GAP, VOUCHED, MediaMatch, Misfit, SubtitleMatch, langs_in`；domain 是 `CONFIDENCE_ORDER, LANG_ORDER, ReasonParams`；models 是 `DEFAULT_INTERVAL_SEC, SetupTmdb`。這些名稱在各自模組內都還在用，不是死碼，只是 re-export 多餘。沒有任何程式動態讀 `berth.parser/domain/models.__all__`（`tests/integration/test_loop_shutdown.py:78` 讀的是 `pipeline.__all__`）。 | worker 的掃法只看名稱有沒有在包外出現，沒看是不是經過包路徑 import，所以漏了一批「名稱有人用、但沒人經包路徑拿」的 re-export。我另以 AST 比對 `from berth.<pkg> import …` 與 `<pkg>.X`，補出：parser 的 `StructureHints`（`mapping.py:41`、`planner.py:42`、`services/search.py:59` 都從 `berth.parser.structure` 拿）、`matches`、`SHORT_FEATURE`、`match_subtitle`（測試從 `berth.parser.subtitles` 拿，`tests/unit/test_parser_subtitles.py:10`）；models 的 `HARDLINK`（`claims.py:65` 從 `berth.models.ledger` 拿）、`SetupIndexer`、`SetupJellyfin`。大小：小。風險：無對外介面。值得度低。 |
| B12 | 通過但修正 | 讀了兩邊。`web/src/rss/searchTerm.ts:9-15` 與 `berth/parser/binding.py:89-119` 的 `skeleton()`（搭配 `search_terms` 拿掉季名）是同一個概念：從發佈名讀出作品名。而且兩邊已經長出不同答案。progress.md:1220 原文：「代價是綁定框預填不拆季名（`web/src/rss/searchTerm.ts` 是 `skeleton` 的前端手抄），Re:Zero 要人自己刪『第四季』」。這是一筆記下的代價，不是保留理由，所以不改判刻意保留。另一個實例：`[千夏字幕組][中文名_Romaji][第12話]`，前端的 `/^\s*(?:\[[^\]]*\]\s*)+/` 會吃掉全部三格括號，最後退回整串原文；後端 `skeleton` 會讀出 `中文名`、`Romaji`（docstring 自己舉的例子）。worker 漏了第二個消費者：除了 `web/src/rss/SeriesBinder.tsx:47`，還有 `web/src/rss/OneshotSection.tsx:232`。現在的 `SeriesOut`（`berth/api/rss.py:200`）與 `OneshotItemOut`（`:323`）都沒有現成的「搜尋預填」欄位。 | 由後端在 `SeriesOut` 與 oneshot 的回應各加一格預填字串（用 `search_terms` / `skeleton`，取哪一個由開票時決定），刪掉 `searchTerm.ts` 與 `searchTerm.test.ts`，重生 `schema.d.ts`。大小：中。風險：API 回應多一個欄位，屬相容的新增；不動持久化。值得度從低上調到中：已經有使用者看得到的分歧（Re:Zero 案例），而且概念的擁有者明確是 parser。 |

## 刻意保留抽查

逐條打開出處核對：

- `berth/parser/seasons.py:1-6`：有寫理由（「寫法各寫一份的話，三邊遲早分岔，所以字串在這裡」）。成立。
- `berth/parser/publishing.py:1-6`、`:27-29`：有寫理由（門檻各用一套的話，推測與驗證會互相打架；`just_aired` 的 docstring 說明 mapping 與 first_batch 共用）。成立。
- `berth/naming/__init__.py:278-284`（`extension`）：docstring 寫「分類與目標檔名要的是同一個答案，各切一次遲早會分岔」。成立。
- `berth/naming/__init__.py` 的 `Reading` docstring（實際在約 :300-307，worker 寫的 :309-316 行號略偏）：寫明「不是另一套規則…用上面同一組模板重算一次」。成立。
- `berth/domain/mediainfo.py:1-8`：寫明住在 domain 的架構理由（plan §1.3）。成立。
- `berth/models/setting.py:202`（`RETIRED_FAILURES`，註解 M4 票 32）與 `:225-230`（`_retired_failure` 的 docstring）：有寫理由，消費者是舊資料。成立。
- `_RESOLUTION` 兩份：行號錯了，在 `berth/parser/release.py:49`，不是 :57；另一份在 `berth/naming/__init__.py:430`。兩處都沒有註解寫保留理由，但兩者確實不同：前者從發佈名擷取，後者驗證單一 token 的形狀，還多收 `\dK`。比較精確的歸類是「不是重複（不列）」，不是「刻意保留（有出處）」。
- `CjkHints.subtitle_kind` 與 `Tags.hardsub`：判定正確，兩者分屬不同層（`release.py:191` 由前者推出後者）。這條同樣是「不是重複」，沒有成文出處。
- `DEFAULT_INTERVAL_SEC`、`CN_DIGITS` 等「模組內有用的常數」：本來就不是發現，放在刻意保留區不影響結論。
- 補一條同類情況給清單參考：`tests/e2e/payload.py:47-48` 另外定義了 `SHORT_FEATURE = 300`，與 `parser/classify.py:80` 重複。理由寫在 `:15`（容器只有標準庫、沒有 Berth）和 `:47` 的註解裡，屬於刻意保留。

## 工具判定抽查

抽了 14 條「誤報」：

| 位置 | 項目 | 複核 |
|---|---|---|
| berth/domain/binding.py:94 | model_config | 正確，`ConfigDict(frozen=True)` 由 pydantic 讀 |
| berth/models/setting.py:44 | model_config | 正確，`extra="ignore"` |
| berth/models/media.py:48 | model_config | 正確 |
| berth/models/route.py:25 | model_config | 正確 |
| berth/parser/structure.py:46 | model_config | 正確 |
| berth/domain/mediainfo.py:42 | model_config | 正確 |
| berth/models/types.py:22 | impl | 正確，`TypeDecorator.impl` |
| berth/models/types.py:23 | cache_ok | 正確 |
| berth/models/types.py:25 | process_bind_param | 正確，SQLAlchemy 回呼 |
| berth/models/types.py:32 | process_result_value | 正確 |
| berth/models/types.py:25/44 | dialect | 正確，回呼簽章參數 |
| berth/models/types.py:42 | cache_ok | 正確 |
| berth/db/engine.py:62 | daemon | 正確，對 aiosqlite 執行緒的屬性賦值，用途就是副作用（`engine.py:57-61` 有註解） |
| berth/models/setting.py:37 | updated_at | **判錯**：ORM 自動寫入不等於有人用。讀取者是 0（berth 全域與 `schema.d.ts` 都沒有讀它；`tests/integration/test_database.py:247,304,346` 只是原生 SQL INSERT），性質和 `job_files.updated_at` 一樣，應該歸入 B5（已在上表 B5 修正）。 |

結論：14 條裡有 13 條判誤報是對的，1 條判錯。pydantic `model_config` 與 SQLAlchemy `TypeDecorator` 這兩類誤報佔了 vulture 結果的大宗，適合寫進 whitelist（閘門評估可以引用這個比例）。

## 複核者另外發現

- **re-export 的漏網**：已併入 B11 的修正（`StructureHints`、`matches`、`SHORT_FEATURE`、`match_subtitle`、`HARDLINK`、`SetupIndexer`、`SetupJellyfin`）。
- **`job_files.updated_at` 的寫入點不一致**：`services/reimport.py:129` 只在 size 改變時才寫，`services/plan.py:561` 在量完 mediainfo 時寫，其他更新 `job_files` 的路徑都不寫。B5 若採「只改文件、保留欄位」的做法，這個欄位的語意會說不清楚；這是支持「刪掉」而不是「保留」的一個理由，附給使用者做判斷。
- 以下屬於 adapters 區，不在 B 的範圍，只做交叉提醒：`berth/adapters/ai.py` 的 `AiPlanner` / `NullAiPlanner` 沒有產品呼叫端，只有 `tests/unit/test_ai.py`。這是刻意保留，出處是 `docs/plan.md:322`（「至今沒有呼叫端」，留給 M5）。C 區的報告若列了它，應該歸到刻意保留。
