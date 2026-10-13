# B parser / naming / domain / models / db

方法：先逐條判 vulture 結果，再用自寫腳本掃三件事：(1) 模組級名稱在產品程式碼的外部引用數；(2) enum 成員 `Class.MEMBER` 引用數；(3) ORM 欄位與 pydantic 欄位的「讀取」（`.col` 且不是賦值左側）引用數；(4) 各 `__init__.__all__` 的名稱有無包外的產品消費者（vulture 會把 `__all__` 當作使用，所以這類漏網只能這樣找）。重複則靠 grep 季集號 / 標題正規化 / 副檔名 / 目標檔名模板相關的 regex 與格式字串。

parser 內部的季名寫法（`seasons.py`）、標題正規化（`title.normalize_title` 被 binding / mapping 共用）、副檔名（`naming.extension` 被 classify 共用）、發佈時間窗口（`publishing.py`）都已是單一來源，不列。

## 發現

### B1 `ParseContext.route_collection_type` 只有人寫、解析器沒人讀
- 類別：沒人用
- 是什麼：欄位定義在 `berth/domain/parser.py:647`（註解稱「劇集不能進 movies」），產品程式碼兩處在組 `ParseContext` 時填它：`berth/services/plan.py:492`、`berth/services/search.py:634`。`berth/parser/` 內沒有任何 `context.route_collection_type` 讀取。
- 證據：`grep -rn route_collection_type berth` 只有 1 處定義 + 2 處寫入；`grep -rE "(context|ctx)\.route_collection_type" berth` 為 0。測試 `tests/unit/test_parser_first_batch.py:254` 只是傳入它。`docs/plan.md:285` 的欄位清單列了它。
- 建議：刪欄位、刪兩處呼叫端的賦值與測試的那一個 kwarg，plan §4.3 的欄位清單同步改。「劇集不能進 movies」的實際守衛在 `domain.collection_type_for`（services 端），不靠這個欄位。
- 大小：小
- 風險：純內部（`ParseContext` 不經 API / 持久化）；`search.py:634` 的 `collection_type_for(...)` 呼叫若只為這個欄位也可一併刪（需確認該行沒有其他副作用）。
- 值得度：高。介面上看起來是「解析器依 Route 種類判斷」，實際不是，會誤導讀的人。

### B2 `CjkHints.hardsub` 與 `CjkHints.subtitle_kind` 是同一件事的兩個表示
- 類別：重複 / 沒人用（只有測試讀）
- 是什麼：`_take_subtitle_kind`（`berth/parser/cjk.py:232-240`）同時回 `(hardsub, subtitle_kind)`，`hardsub` 恰好等於「`subtitle_kind is HARDSUB`；`UNKNOWN` 時為 `None`」。欄位在 `berth/domain/parser.py:450`。產品程式碼只讀 `subtitle_kind`（`berth/parser/release.py:191` 的 `info.subtitle_kind is SubtitleKind.HARDSUB`）。
- 證據：`grep -rn "\.hardsub" berth/parser` 無對 `CjkHints.hardsub` 的讀取（`Tags.hardsub` 是另一個欄位，不算）；只有 `tests/unit/test_parser_cjk.py:61,67,73,80` 斷言它。
- 建議：刪 `CjkHints.hardsub` 與 `_take_subtitle_kind` 的第一個回傳值，測試改斷言 `subtitle_kind`。
- 大小：小
- 風險：純內部 pydantic 模型，未序列化出去。
- 值得度：中。同一事實兩份、將來易分歧；改動很小。

### B3 `ReleaseInfo.video_codec` / `bit_depth` / `audio` 解析了但沒人讀
- 類別：沒人用
- 是什麼：欄位在 `berth/domain/parser.py:539-541`，`berth/parser/release.py:145-147` 從 guessit 填入。`ReleaseInfo` 只在 parser 內流動（`tags_of` 只取 source / resolution / subtitle / group / version / edition）。
- 證據：`grep -rnE "\.(video_codec|bit_depth|audio)\b" berth` 在 parser / services / api / naming 全無讀取；tests 也沒有（`tests` 裡的 `video_codec` 都是 `MediaInfoSummary` 的）。vulture 對這三個只報 `video_codec`/`bit_depth`（在 test-only 清單，被 mediainfo 同名欄位掩蓋）與 `audio`（在 unused 清單）。
- 建議：刪三個欄位與 `release.py` 的三行。若將來要「依編碼挑重複版本」再加（目前 `Tags` 也沒有這幾格，brief §6.8 命名詞彙也不含）。
- 大小：小
- 風險：純內部，`ReleaseInfo` 未持久化、未進 API。
- 值得度：中。解析了卻無人用，且容易被誤認為「已支援」。

### B4 `MediaInfoSummary` 與 `SubtitleTrack` 多數欄位寫入 `mediainfo_json` 後無人讀
- 類別：沒人用（待複核：是 plan 明列的規格）
- 是什麼：`berth/domain/mediainfo.py:30-31,49-53` 的 `SubtitleTrack.codec/forced`、`video_codec`、`bit_depth`、`audio_langs`、`subtitle_tracks`，由 `berth/adapters/mediainfo.py:71-76` 產生，`berth/services/plan.py:560` 整個 `model_dump` 進 `job_files.mediainfo_json`。唯一讀取者是 `plan.py:252`（`duration_s`）與 `plan.py:562`（`summary.duration_s`）；`width/height` 同樣沒人讀。
- 證據：`grep -rnE "audio_langs|subtitle_tracks|\.forced|\.bit_depth" berth` 只有 adapter 與模型本身；測試只驗 adapter 解析（`tests/unit/test_mediainfo.py`）與 `tests/integration/test_plan.py:859` 的存入。`docs/plan.md:561` 把整組規格列為 `probe()` 的回傳。
- 建議：兩種做法讓使用者挑：(a) 縮到 `duration_s`（連 adapter 與 `_subtitle/_langs` 輔助一起縮）；(b) 保留，因為 plan §8.7 寫明供「重複版本取捨」將來使用。不知道是否有票要用它，故列待複核。
- 大小：中（adapter + domain + 兩支測試）
- 風險：`job_files.mediainfo_json` 是持久化 JSON，既有資料裡有舊欄位；刪欄位後 `MediaInfoSummary` 若不 `extra="ignore"` 讀舊資料會失敗，但目前只當 dict 讀（`(row.mediainfo_json or {}).get("duration_s")`），風險小。無 migration。
- 值得度：低。是預留給未來功能的資料，不是邏輯分歧；除非使用者想嚴格執行「沒人用就刪」。

### B5 寫入但從不讀取的 DB 欄位
- 類別：沒人用
- 是什麼（逐欄，各欄皆只有寫入、沒有任何 API / UI / services 讀取）：
  - `berth/models/job.py:71` `jobs.last_seen_in_client_at`：寫入 `services/claims.py:234`、`services/downloads.py:458`。
  - `berth/models/plan.py:55-56` `plans.decided_by` / `decided_at`：寫入 `services/plan_review.py:161-162,190-191`、`services/rematch.py:603-604`。`decided_by` 只有測試讀（`tests/integration/test_plan_review.py:259`、`test_rematch.py:149`）。
  - `berth/models/ledger.py:54` `ledger.source_inode`：寫入 `services/claims.py:359`、`importer.py:373`、`issues.py:379,475`（注意：`target_inode` 另有人讀，`inode_mismatch` 靠的是它）。只有測試讀（`tests/integration/test_importer.py:229`）。
  - `berth/models/ledger.py:81` `ledger.link_mode`：寫入 `services/claims.py:370`（永遠是 `hardlink`），只有 `tests/integration/test_importer.py:233` 讀。
  - `berth/models/auth.py:26` `users.last_login_at`：寫入 `services/auth.py:196`，只有 `tests/integration/test_auth_service.py:139` 讀。
  - `berth/models/job.py:96` `job_files.updated_at`：寫入 `services/plan.py:561`，無讀取。
- 證據：腳本以「`.col` 且不是賦值左側」計讀取，產品程式碼與 `web/src/api/schema.d.ts` 皆為 0（上列 tests 讀取另計）。`docs/plan.md:105,127,131,134` 這些欄位當資料模型列出，應是稽核用途設想。
- 建議：先問使用者要不要「稽核欄位」這類保留；要刪的話刪欄位 + 兩三處寫入 + 對應測試斷言。`link_mode` 與 `source_inode` 可保留作為將來 `inode_mismatch` 檢查的依據則列為保留。
- 大小：中（每欄要一支 alembic migration + 所有寫入點 + 測試；可合併成一支 migration）
- 風險：**動到持久化資料與 migration**：SQLite `ALTER TABLE DROP COLUMN` 在 batch 模式下要重建表；`ledger` 與 `plans` 資料量大且是帳本，風險比 `jobs` 高；刪 `plans.decided_*` 需確認 `docs/plan.md:131` 已承諾的欄位是否要同步改文件。
- 值得度：低。欄位本身無害，只是死資料；刪的成本（migration + 風險）大於收益，建議除非使用者堅持，否則列為「只更新 plan 文件，承認這幾欄是稽核用」。

### B6 三套「code + params 的理由」模型與建構函式逐字相同
- 類別：重複
- 是什麼：`berth/domain/parser.py:379-408`（`ItemReason` / `why` / `REASON_PARAMS`）、`berth/domain/binding.py:84-105`（`BindReason` / `because` / `BIND_PARAMS`）、`berth/domain/screening.py:41-66`（`SkipReason` / `skipped` / `SKIP_PARAMS`）。三個 pydantic 模型形狀相同（`code` + `params: dict[str, str|int]`），三個建構函式本體相同（比對 `frozenset(params)` 與參數表、不符就 `ValueError`）。`ReasonParams` 型別別名只在 `parser.py` 用，另兩套各寫一次 `dict[str, str | int]`。三份前端對照測試也各一支（`tests/unit/test_reason_codes.py`、`test_bind_reasons.py`、`test_skip_reasons.py`）。
- 證據：三個檔案的 docstring 都寫「形狀照 X」（`binding.py:3`、`screening.py:3`），表示是有意複製形狀，但沒有寫為什麼不共用同一個泛型。
- 建議：若要統一：抽一個以 code enum 與參數表為參數的小工廠 / 泛型基底，三個 code enum 與參數表仍各自留（它們對應不同的前端 i18n 命名空間 `plans.reason.*` / `rss.grounds.*` / `rss.skip.*`）。若不想動，就列成刻意保留。
- 大小：中
- 風險：`ItemReason` 進 `plan_items.reasons_json`（持久化）與 API 回應；`BindReason` / `SkipReason` 也進 API。只動 Python 實作、不動 JSON 形狀則無風險；若改欄位名會動到持久化資料。
- 值得度：低。三份各 ~10 行、規則穩定，且 code 集合與 i18n 命名空間本來就分開；重複的是樣板不是判斷。

### B7 劇集目標檔名的「S01E02[-E03]」格式在 naming 與 domain 各組一次
- 類別：重複
- 是什麼：`berth/naming/__init__.py:98-100` 手工組 `S{season:02d}E{episode:02d}` 加 `-E{end:02d}`（並自己判斷 `end != episode`）；`berth/domain/parser.py:403-406` 的 `episode_label()` 做一模一樣的事。反解端 `naming._EPISODE_HEAD`（`naming/__init__.py:424`）又是第三份寫法（regex）。另外 `berth/parser/airing.py:67` 與 `berth/parser/runtime.py:67` 呼叫 `episode_label(season, start, end if end != start else None)`，那個 `end if end != start else None` 已被 `episode_label` 內建的 `episode_end == episode` 判斷涵蓋，是多餘的重複判斷。
- 證據：`grep -rnE "S\{[a-z_]+:02d\}E" berth` 命中 domain/parser.py:405、naming:98、title.py:163（後者是搜尋 token，不同用途）。
- 建議：`episode_target` 用 `episode_label(season, episode, episode_end)` 取代手組（`naming` 已經 import `berth.domain`）；airing / runtime 直接傳 `end`。`_EPISODE_HEAD` 保留（是反解）。
- 大小：小
- 風險：目標檔名輸出必須逐字不變（`tests/unit` 的命名測試與 `rebuild-ledger` 的反解測試守著），不動對外介面與持久化資料。
- 值得度：中。檔名是帳本與 Jellyfin 的合約，兩處各自組格式是潛在分歧點。

### B8 `claims._TMDB_ID` 是 `naming.FOLDER_TEMPLATE` 的另一份手寫反解（跨區：services）
- 類別：重複
- 是什麼：`berth/services/claims.py:83` `re.compile(r"\[tmdbid-(\d+)\]$")` 解析作品資料夾名；寫入端是 `berth/naming/__init__.py:19-21` 的 `FOLDER_TEMPLATE`。`naming` 已有反解函式 `read_target`（`naming/__init__.py:317`），但目前資料夾的 tmdb id 是 claims 自己讀。
- 證據：`grep -rn "tmdbid" berth --include=*.py` 只有 naming 的模板、claims.py:83 與 `claims.py:460` 的使用；claims 的註解寫著 `（naming.FOLDER_TEMPLATE）`，承認是對應模板。
- 建議：把「從資料夾名讀 TMDB id」放進 `naming`（例如 `tmdb_id_of(folder)`），claims 呼叫它。
- 大小：小
- 風險：無對外介面。
- 值得度：低。只有一處、註解已指明來源；模板改動時會連動出錯，但出錯時測試會抓到。

### B9 `classify` 內兩種判斷「是不是影片副檔名」
- 類別：重複
- 是什麼：`berth/parser/classify.py:124` 有 `kind_by_extension()`（公開、`_kind_of` 與 `rebuild-ledger` 都用它）；同檔 `classify.py:172` `_biggest_video_per_directory` 卻直接寫 `_BY_EXTENSION.get(extension(entry.name)) is not FileKind.VIDEO`。
- 證據：同一檔案兩個位置，同一個 `_BY_EXTENSION` 查表。
- 建議：第 172 行改成 `kind_by_extension(entry.name) is not FileKind.VIDEO`。
- 大小：小（一行）
- 風險：無。
- 值得度：低。純 DRY，不會長出不同答案（兩邊都查同一個表）。

### B10 `PlanEngine.AI` 成員沒有任何引用
- 類別：沒人用
- 是什麼：`berth/domain/enums.py:1012` `AI = "ai"`，註解稱「M1 的實作永遠沒有意見」。`berth/` 與 `tests/` 沒有任何 `PlanEngine.AI`，寫入 `plans.engine` 的只有 `RULES`（`services/plan.py:889`）與 `USER`（`plan_review.py:131`、`rematch.py:596`）。
- 證據：腳本掃所有 enum 成員，只有 `PlanEngine.AI`（及僅測試用的 `IssueSubject.LEDGER_ID`，後者是 `SUBJECT_OF` 對照表在用，不算）無產品引用。progress.md:15 把 M5 AI 重新定義為「AI 替人按審核頁的按鈕」，不再產生一份 `engine=ai` 的 Plan。
- 建議：刪成員，並更新 `docs/plan.md:131`、`docs/design-brief.md:159`（`plan_generated(engine=rules|ai…)`）。若 M5 仍要用 `engine=ai` 標記則保留。
- 大小：小
- 風險：**動到對外介面與持久化**：`PlanEngine` 出現在 API schema（`web/src/api/schema.d.ts:4189` `"rules" | "ai" | "user"`）、alembic migration `ebe69db7a48b` 的 Enum 寫了 `"ai"`（`native_enum=False` 且沒有 CHECK 約束，所以不需要 migration，但舊 migration 不可改）。
- 值得度：低。待 M5 設計定案再決定；現在刪可能要再加回來。

### B11 `__init__.__all__` 裡包外沒人 import 的名稱
- 類別：沒人用
- 是什麼：以下名稱在 `__all__` 重新匯出，但包外（含測試）零使用：`berth/parser/__init__.py` 的 `SAMPLE_RATIO`、`VIRTUAL_SEASON_GAP`、`VOUCHED`、`MediaMatch`、`Misfit`、`SubtitleMatch`、`langs_in`；`berth/models/__init__.py` 的 `DEFAULT_INTERVAL_SEC`、`SetupTmdb`；`berth/domain/__init__.py` 的 `CONFIDENCE_ORDER`、`LANG_ORDER`、`ReasonParams`。另外包外只有測試用的：`QUIET_AFTER`、`SETTLED_AFTER`、`SHORT_FEATURE`、`match_media`、`match_subtitle`、`merge_release`、`structure_hints`（parser）、`SETTINGS_GROUPS`（models）、`BIND_PARAMS`、`REASON_PARAMS`、`SKIP_PARAMS`（domain，皆為對照表測試用，屬刻意）。
- 證據：腳本 (4)；vulture 因為 `__all__` 而不報這些。
- 建議：從三個 `__init__` 的 import 與 `__all__` 拿掉「零使用」那些，名稱留在各自模組內（模組內仍使用）。
- 大小：小
- 風險：無對外介面。
- 值得度：低。縮小公開面而已，不影響行為。

### B12 前端 `searchTerm.ts` 與後端 `binding.skeleton` 各自從發佈名挑作品名（跨區：web，待複核）
- 類別：重複（待複核疑點）
- 是什麼：`web/src/rss/searchTerm.ts:9-15` 用 regex 去掉 `[組名]`、取 ` - 數字` 前的名字、以 ` / ` 切後取最後一段，作為綁定搜尋框預填；後端 `berth/parser/binding.py:89-119` `skeleton()` 做相同事但更完整（用 `parser.cjk` 認組名、處理方括號標題、`_NAMES` 切分），`search_terms`（`binding.py:139`）也是取最後一段往前。`skeleton` 的 docstring 明說知道前端那份（「`web/src/rss/searchTerm.ts` 挑的是最後一段，這裡每一段都要」）。
- 證據：兩邊各有測試（`web/src/rss/searchTerm.test.ts`、`tests/unit/test_binding*.py`）；前端預填的是 UI 輸入框的初始值，後端是自動綁定的候選。
- 建議：待複核——若前端可改用後端回傳的 `search_terms`（RSS Series 的 API 回應多一格）就能刪掉 TS 那份；否則列為刻意保留（前端要在使用者尚未送出任何請求時即時預填）。我不確定現有 API 是否已有這個欄位，需要 web 區塊的 worker / 使用者確認。
- 大小：中
- 風險：動 API 回應形狀。
- 值得度：低。兩邊目的不同（預填 vs 自動綁定），且前端那份只有 5 行。

## 刻意保留

- 季名寫法三個讀者共用一份字串、各自加錨點：`berth/parser/seasons.py:1-9`（模組註解寫明「三邊遲早分岔，所以字串在這裡」）。
- 發佈時間窗口兩邊共用：`berth/parser/publishing.py:1-8`；`mapping._just_aired`（`mapping.py:617`）與 `first_batch._just_aired`（`first_batch.py:112`）是薄包裝，註解 `publishing.py:27` 已說明。
- `naming.extension` 對 classify 與 rebuild-ledger 共用：`berth/naming/__init__.py:278-284` docstring（「分類與目標檔名要的是同一個答案，各切一次遲早會分岔」）。
- `naming` 的反解（`read_target` / `_SLOTS` / `_EPISODE_HEAD`）刻意是「用同一組模板重算一次、一字不差才算」，不是第二套規則：`berth/naming/__init__.py:309-316` 的 `Reading` docstring。
- `mediainfo` 領域模型放在 `domain/`：`berth/domain/mediainfo.py:1-9`（adapter 與 parser 都只能 import domain 的架構理由）。
- `DEFAULT_INTERVAL_SEC`、`CN_DIGITS`、`THRESHOLD`、`FACTORY_NAMES`、`RETIRED_FAILURES`、`NAMING_CONVENTION`、`PRAGMAS` 等：模組內被使用的常數，只是沒有跨模組引用，不算死碼。
- `RETIRED_FAILURES` 是為舊值保留的相容分支，但註解 `berth/models/setting.py:202` 與 `:230` 說明是「M4 票 32 退役的值仍可能存在於舊的設定檔」，有消費者（舊資料），不列。
- `CjkHints.subtitle_kind` 與 `Tags.hardsub`：不同層（解析結果 vs 檔名 token），不算重複。
- `_RESOLUTION` 兩份（`berth/parser/release.py:57` 與 `berth/naming/__init__.py` 的 `_RESOLUTION`）：一個是從發佈名擷取，一個是驗證檔名 token 的形狀（反解），用途不同。

## 工具結果判定

### B_vulture_unused_anywhere.txt

| 位置 | 項目 | 判定 | 理由 |
|---|---|---|---|
| berth/domain/binding.py:94 | model_config | 誤報 | pydantic `ConfigDict` 由框架讀取 |
| berth/domain/enums.py:1012 | AI | 真的沒人用 | 見 B10 |
| berth/domain/media.py:23 | model_config | 誤報 | 同上 |
| berth/domain/media.py:44 | model_config | 誤報 | 同上 |
| berth/domain/media.py:63 | model_config | 誤報 | 同上 |
| berth/domain/mediainfo.py:23 | model_config | 誤報 | 同上 |
| berth/domain/mediainfo.py:42 | model_config | 誤報 | 同上 |
| berth/domain/parser.py:385 | model_config | 誤報 | 同上 |
| berth/domain/parser.py:416 | model_config | 誤報 | 同上 |
| berth/domain/parser.py:446 | model_config | 誤報 | 同上 |
| berth/domain/parser.py:481 | model_config | 誤報 | 同上 |
| berth/domain/parser.py:519 | model_config | 誤報 | 同上 |
| berth/domain/parser.py:541 | audio | 真的沒人用 | 見 B3 |
| berth/domain/parser.py:566 | model_config | 誤報 | 同上 |
| berth/domain/parser.py:618 | model_config | 誤報 | 同上 |
| berth/domain/parser.py:635 | model_config | 誤報 | 同上 |
| berth/domain/parser.py:647 | route_collection_type | 真的沒人用 | 見 B1（寫入者 2 處，讀取者 0） |
| berth/domain/parser.py:661 | model_config | 誤報 | 同上 |
| berth/domain/screening.py:56 | model_config | 誤報 | 同上 |
| berth/models/job.py:71 | last_seen_in_client_at | 真的沒人用（只寫） | 見 B5 |
| berth/models/job.py:96 | updated_at | 真的沒人用（只寫） | 見 B5（`job_files.updated_at`） |
| berth/models/media.py:48 | model_config | 誤報 | pydantic |
| berth/models/plan.py:56 | decided_at | 真的沒人用（只寫） | 見 B5 |
| berth/models/route.py:25 | model_config | 誤報 | pydantic |
| berth/models/setting.py:37 | updated_at | 誤報 | ORM `default`/`onupdate` 自動維護；`tests/integration/test_database.py:247,304,346` 以原生 SQL 寫入，且屬於設定表的審計慣例，無讀取但不是服務碼寫入的死欄位（待使用者是否要一併歸入 B5） |
| berth/models/setting.py:44 | model_config | 誤報 | pydantic |
| berth/models/setting.py:154 | model_config | 誤報 | pydantic |
| berth/models/setting.py:169 | model_config | 誤報 | pydantic |
| berth/models/setting.py:188 | model_config | 誤報 | pydantic |
| berth/models/setting.py:212 | model_config | 誤報 | pydantic |
| berth/models/setting.py:240 | model_config | 誤報 | pydantic |
| berth/models/setting.py:259 | model_config | 誤報 | pydantic |
| berth/models/setting.py:276 | model_config | 誤報 | pydantic |
| berth/models/setting.py:294 | model_config | 誤報 | pydantic |
| berth/models/setting.py:312 | model_config | 誤報 | pydantic |
| berth/models/setting.py:330 | model_config | 誤報 | pydantic |
| berth/models/setting.py:357 | model_config | 誤報 | pydantic |
| berth/models/setting.py:381 | model_config | 誤報 | pydantic |
| berth/models/setting.py:394 | model_config | 誤報 | pydantic |
| berth/models/setting.py:464 | model_config | 誤報 | pydantic |
| berth/models/types.py:23 | cache_ok | 誤報 | SQLAlchemy `TypeDecorator.cache_ok` 由框架讀取 |
| berth/models/types.py:42 | cache_ok | 誤報 | 同上 |
| berth/parser/structure.py:46 | model_config | 誤報 | pydantic |

### B_vulture_used_only_in_tests.txt

| 位置 | 項目 | 判定 | 理由 |
|---|---|---|---|
| berth/db/engine.py:62 | daemon | 誤報 | `connection._thread.daemon = True` 是對 aiosqlite 執行緒的屬性賦值（註解 `engine.py:60` 說明與 SQLAlchemy 方言一致），副作用就是用途 |
| berth/domain/mediainfo.py:30 | codec | 沒人讀（只寫入 JSON） | 見 B4 |
| berth/domain/mediainfo.py:31 | forced | 沒人讀 | 見 B4 |
| berth/domain/mediainfo.py:49 | video_codec | 沒人讀 | 見 B4 |
| berth/domain/mediainfo.py:50 | bit_depth | 沒人讀 | 見 B4 |
| berth/domain/mediainfo.py:52 | audio_langs | 沒人讀 | 見 B4 |
| berth/domain/mediainfo.py:53 | subtitle_tracks | 沒人讀 | 見 B4 |
| berth/domain/parser.py:539 | video_codec | 真的沒人用 | 見 B3（`ReleaseInfo`，與 mediainfo 同名但不同類別，test 引用的是 mediainfo 那個） |
| berth/domain/parser.py:540 | bit_depth | 真的沒人用 | 見 B3 |
| berth/models/auth.py:26 | last_login_at | 只寫，僅測試讀 | 見 B5 |
| berth/models/ledger.py:54 | source_inode | 只寫，僅測試讀 | 見 B5 |
| berth/models/ledger.py:81 | link_mode | 只寫，僅測試讀 | 見 B5 |
| berth/models/plan.py:55 | decided_by | 只寫，僅測試讀 | 見 B5 |
| berth/models/types.py:22 | impl | 誤報 | `TypeDecorator.impl` 由 SQLAlchemy 讀 |
| berth/models/types.py:25 | process_bind_param | 誤報 | SQLAlchemy 回呼 |
| berth/models/types.py:25 | dialect | 誤報 | 回呼簽章參數（必須存在） |
| berth/models/types.py:32 | process_result_value | 誤報 | SQLAlchemy 回呼 |
| berth/models/types.py:32 | dialect | 誤報 | 回呼簽章參數 |
| berth/models/types.py:41 | impl | 誤報 | 同上 |
| berth/models/types.py:44 | process_bind_param | 誤報 | 同上 |
| berth/models/types.py:44 | dialect | 誤報 | 同上 |
| berth/models/types.py:49 | process_result_value | 誤報 | 同上 |
| berth/models/types.py:49 | dialect | 誤報 | 同上 |

（`berth/models/setting.py:37` `settings.updated_at` 與 `berth/models/job.py:96` `job_files.updated_at` 的區別：前者是 ORM `onupdate` 自動欄位，從不在服務碼賦值；後者是 `services/plan.py:561` 手動寫入。兩者都沒有讀取者，是否納入 B5 由使用者決定。）
