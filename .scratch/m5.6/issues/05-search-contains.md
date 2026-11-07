# 05 — 種子搜尋的 `contains`

**Status:** done

**Blocked by:** 01

**讀:** spec〈範圍〉C1；研究文檔 §1 第 3 點、§4 C1；plan §6〈search〉、§8.4〈結果的分類與取用〉；`agent_tools._rows_to_show` 的 docstring

## 為什麼

給模型的搜尋結果只有前 `MODEL_SEARCH_ROWS` 列，加上之後「符合」而帶來新集數的列。`query` 搜出來的單集多半不算「符合」，會被截掉，所以「非人少女」那次模型只好一集搜一次（9 次）。

## 做什麼

1. `search.search_torrents` 加 `contains: list[str]`（選填）：每個詞都要出現在發佈名裡，比對前做 NFKC 與 casefold，和 `parser.title` 用同一個正規化函式。**先篩再截斷**。
2. 字幕組、語言版本、解析度都用這同一個參數，不另外開專用欄位。
3. 有 `contains` 時給模型的列數上限放寬：數字用實際 token 量來定（同一組結果量有放寬與沒放寬兩種），寫在 Comments 與常數旁的註解。
4. 工具說明寫一句什麼時候用（列出一個字幕組的整季，不要逐集搜）。人用的搜尋端點沒帶 `contains` 時行為不變。

## 驗收

- [x] `query: 非人少女, contains: [喵萌奶茶屋, 繁日]` 的 fixture 一次回出 13 集，沒有被截斷（測試）
- [x] 全形、半形、大小寫不同也比得到；任一個詞沒出現就不列（測試）
- [x] 沒帶 `contains` 時結果與截斷規則不變（既有測試綠）
- [x] 放寬的上限有 token 量的依據（Comments）
- [x] 全部檢查、pytest 綠；progress.md 已更新

## Comments

- **放寬的上限 20（`agent_tools.MODEL_SEARCH_ROWS_NARROWED`）怎麼定的**：用 `_compact_search` 實際輸出的那一份量（fixture `tests/fixtures/search/hitodenashi-2025.json`、`json.dumps(ensure_ascii=False)`、tiktoken `cl100k_base`）：
  - 同一組 13 列、沒帶 `contains`（上限 10）：10 列，2,523 tokens（4,882 字元）。
  - 同一組 13 列、帶 `contains`（上限 20）：13 列全給，3,249 tokens（6,257 字元）；每列約 240。
  - 一個字幕組一天發兩種解析度（26 列）時，上限 20：4,955 tokens。
  - 對照：一次逐集搜尋光是重送上下文就約 7K（`_compact_search` 的註解，Re:Zero 實測）。放寬一次多 0.7K（13 集）到 2.4K（20 列），換掉九到十三次搜尋；20 是預設的兩倍，13 集整季進得來，還留得下幾列別的版本。
- **fixture 的來源**：`tests/fixtures/search/hitodenashi-2025.json` 照票 01 的 S7 逐字稿（`.local/experiments/results/m5_acceptance/`）重造：13 集的 info hash／大小／發佈時間照確認卡逐列抄，片名 01／02／03／13 照 `baseline-s7s8/anthropic-S7.md`、12 照 `baseline-retry-s7/openai-S7.md`，其餘同一格式換集數；7³ACG／Judas／SubsPlease 照抄（info hash 在逐字稿被截斷，是假值），兩列 TPB 是照原對話的熱門清單補的（S7 的查詢沒有 TPB）。寫在 `HITODENASHI_RESULTS` 旁的註解。
- **`繁日` 也會命中 `简繁日内封`**：真正的喵萌奶茶屋&LoliHouse 那幾列（`[简繁日内封字幕]`）字串裡有「繁日」。這是子字串比對的既定行為（票選了通用的一格，不開專用欄位）；要只拿繁日雙語就用 `繁日双语`。fixture 只放繁日雙語那 13 集，那幾列沒進來。
- **`contains` 與 `filtered_out` 兩個公開欄位**：`contains` 是給 `_compact_search` 判斷要不要放寬用的（也讓模型看得到自己篩了什麼）；`filtered_out` 是 `contains` 篩掉的筆數，讓 `returned = merged + filtered_out + Σ counts.total` 仍然成立（plan §8.4 已改；人用的 `GET /search` 不送 `contains`，對外永遠是 0）。不叫 `narrowed`：CONTEXT.md 的 **Narrowing** 是媒體庫牆上依類型、年份縮小。
- **正規化之後什麼都不剩的詞是參數錯**（如 `!!!`）：`ValueError` 交給模型當工具失敗（`agent._guard` 的通用那條），不默默當成沒篩——工具說明承諾「keep only releases whose name has every one of these words」。
- **驗證**：`tests/integration/test_search.py` 63 passed（新增 7 支：13 集一次回並經真正的 `MODEL_VIEWS` 確認模型看到 13 列、寬度與大小寫雙向、缺一個詞不列、沒帶 `contains` 不變、筆數加得起來、先篩再截斷、空詞拒絕）；`tests/unit/test_agent_tools.py` 24 passed（放寬與 `rows_not_shown` 兩支）。全份 `tests/unit` + `tests/integration` 5733 passed、1 skipped；`pre-commit run --all-files` 全綠（ruff、mypy、import-linter、prettier、eslint、knip）。
- **code-review 未處理的發現**：(1) 不為 token 量測新留 `scripts/experiments/` 腳本——量的是檢入的 fixture 與 tokenizer，重跑的方式就是上面那幾行，不值得為 transitive dependency（`tiktoken` 由 pydantic-ai 帶進來）多一支腳本。(2) 整合測試裡三行 arrange 的重複照這個檔的既有寫法（每支自己 arrange），沒有再抽 fixture。
