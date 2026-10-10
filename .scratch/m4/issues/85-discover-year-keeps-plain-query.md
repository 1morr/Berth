# 85 — 探索搜尋：拿掉年份拆分，打的字整串原樣問 TMDB

**Status:** done

**Blocked by:** None — can start immediately

**讀:** M4 票 69 的 Comments〈決定〉的「探索的年份」、〈已知限制〉；`berth/services/discover.py`（年份拆分、`search_year`）；`tests/integration/test_discover.py` 的 `TestSearchWithAYear`；brief §20.19

## 為什麼

票 69 讓「Nosferatu 1922」找得到東西：結尾是年份時，拆成片名加年份去問 TMDB，那一年**完全沒有結果**才退回原字串。

但片名本身以數字結尾的作品會被拆錯：「Space 1999」被拆成片名 `Space`、1999 年，那一年有別的片，就不會退回，真正的《Space: 1999》找不到。「the 1975」也一樣。

**使用者拍板（2026-10-10）**：整個拿掉年份拆分。使用者搜尋時不會加年份，同名不同年的作品看卡片上的年份就認得出來；「Nosferatu 1922」回到 0 筆是可接受的代價。

## 做什麼

- `services/discover.py`：刪掉年份拆分（`split_year`、`_with_year`），不論有沒有年份，都把打的字（正規化後）原樣問 `search/multi`。
- adapter 的 `search_year`（介面、HTTP client、假 client）、它的契約測試與錄製的 fixture 沒有別的呼叫端，一起刪，不留相容層。
- 測試改成守「帶年份的字串原樣送出、不拆」，含「Space 1999」原樣送出、結果裡有《Space: 1999》。
- brief §20.19（事實留著，標明 Berth 不用）、plan、CHANGELOG、progress.md 偏差與決定（推翻票 69 的探索年份）同步。

## 驗收

- [x] 「Space 1999」「Nosferatu 1922」「nosferatu (1922)」「Blade Runner 2049」都原樣送 `search/multi`、不另外問帶年份的端點；「Space 1999」的結果有《Space: 1999》（假 TMDB 回應）；pytest 守，做變異驗證
- [x] `search_year` 與它的契約測試、fixture 已刪，沒有殘留的呼叫端
- [x] 實跑：真的 TMDB 搜「Space 1999」結果有《Space: 1999》、搜「Nosferatu」列得出各年份的那幾部，附結果（不得在任何輸出印出 TMDB key）；用隔離環境，**不准碰使用者的 `berth-local`**
- [x] 全部檢查、pytest、vitest 綠；brief、plan、CHANGELOG、progress.md 已更新

## Comments

### 決定

- **使用者中途改了決定（2026-10-10）**：票面原本是「拆開問的同時也照原字串問、合併，拆開的排前面」。那一版做完（紅綠、變異驗證、真 TMDB 實跑）後被推翻，程式碼整份丟掉，票面改寫成現在這樣。那一版的實測留作紀錄：「Space 1999」32 筆，前 24 筆是帶 1999 年那兩支回的別部 Space 片，《Space: 1999》（tv:134）排第 25 筆，這是 brief §20.19 引的數字。
- 檔名 `85-discover-year-keeps-plain-query.md` 沒改：progress.md 與其他地方用票號指它。

### 驗證

- 變異（`tests/integration/test_discover.py::TestSearchWithANumberAtTheEnd`）：在 `search_media` 裡把結尾年份拆掉再問 → 5 條全紅（請求是 `search/space`、結果沒有 tv:134）；另外多問一次拆開的片名 → 參數化 4 條紅；只改一行註解 → 5 條綠。
- 真 TMDB 實跑：暫存 SQLite（`%TEMP%/berth-t85-*`，跑完刪掉）、`HttpServiceClientFactory` 直接呼叫 `search_media`，不經 docker、沒碰 `berth-local`。key 從主 checkout 的 `.env` 只抽 `TMDB_API_KEY` 進環境變數，輸出沒有印出來。
  - `Space 1999`：8 筆，第一筆 `tv:134 Space: 1999 (1975)`，第二筆 `movie:542499 Space: 1999 (1975)`
  - `Nosferatu`：19 筆，含 `movie:426063 (2024)`、`movie:653 (1922)`、`movie:1528448 (2025)`、`movie:6404 Nosferatu the Vampyre (1979)`、`movie:1428364 (1991)`
  - `Nosferatu 1922`：0 筆（接受的代價）
- `uv run pre-commit run --all-files` 全過（eslint 第一次以 0xC0000005 崩潰，重跑通過，不是 lint 錯誤）；`uv run pytest`：3793 passed、24 deselected；`pnpm -C web test`：90 個檔案、1444 條通過。

### code-review（兩軸 opus）

- Standards：沒有硬違規。已採納：請求斷言原本先用 `startswith("search/")` 過濾，改成比對整份 `client.requests`。未處理：`test_space_1999_finds_the_series` 與參數化那一格部分重疊，驗收要求「結果有《Space: 1999》」，所以留著。
- Spec：沒有缺漏、多做或做錯。未處理的小建議：本票「讀:」行指的 `search_year`、`TestSearchWithAYear` 已經刪了（那是開工時的閱讀指引）；CHANGELOG 放在 Changed 而不是 Removed，條目裡有寫「取代 0.2.3 的…」。
