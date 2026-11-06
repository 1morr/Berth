# 05 — 種子搜尋的 `contains`

**Status:** ready-for-agent

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

- [ ] `query: 非人少女, contains: [喵萌奶茶屋, 繁日]` 的 fixture 一次回出 13 集，沒有被截斷（測試）
- [ ] 全形、半形、大小寫不同也比得到；任一個詞沒出現就不列（測試）
- [ ] 沒帶 `contains` 時結果與截斷規則不變（既有測試綠）
- [ ] 放寬的上限有 token 量的依據（Comments）
- [ ] 全部檢查、pytest 綠；progress.md 已更新

## Comments
