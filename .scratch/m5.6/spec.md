# M5.6 AI 對話精簡

由 [`docs/research/agent-slimming-2026-11-06.md`](../../docs/research/agent-slimming-2026-11-06.md) 細化（2026-11-06 開工 session）。這個里程碑在 plan §11 原本沒有小節，開工時補了 §11.6c，只放連到這裡的一行；程式碼裡的 §11.6c 引用指這份。

## 目標

試用機上一段真實對話（conversation `b0e4f028`，「幫我找想吃掉你的那個什麼動漫」）花了 5 分鐘、30 次工具呼叫，其中種子搜尋 18 次；確認卡 13 列同一部作品，Route 要點 13 次。使用者要的方向是 **skills 與工具簡潔、通用**，確認卡不要逐列問同一件事（2026-11-06 使用者勾選 A1、A2、A4、B1–B4、C1–C4，放棄 A3）。

排在 M6 前：M6 的背景任務也走同一組命令與工具，先把工具和說明收乾淨。

分層原則（研究文檔 §3）：政策（Route 怎麼定、去重複、哪些要人選）放伺服器；怎麼解讀結果放工具說明與輸出；跨任務的共同規則寫一次在系統指示；skill 只寫這類任務的決策順序。

## 範圍

- **基準**（票 01）：改動前用真模型跑 `scripts/experiments/m5_acceptance_scenarios.py` 的 S1–S6 與 S2 的三個變體（兩種接口），另加兩個情境：S7「非人少女」那段對話（直接要下載），S8 照原對話的模糊開頭（只說「找」、沒說要下載）。工具呼叫數、input token、費用、種子搜尋次數、卡片上要選 Route 的次數都記下來。
- **C2 季記號 bug**（票 02）：只有一季的作品第 1 季整季缺時，`missing_batches` 只送「名字 第1季」，動畫站零筆。修法（第 1 季另送不帶記號的名字，或只有一季時不加記號）先實測索引站再定，結果寫進 brief §20。作品頁「搜缺的集」也走同一段，修好兩邊都受益。
- **A1、A2 確認卡的 Route**（票 03）：卡片依 `media_id` 分組，每組選一次 Route，套到那組勾著的列；兩部以上作品、可選 Route 有交集時，頂部多一個「全部套用」。`decide` 的 `routes` 照舊逐列送，API 不變。參考 Sonarr / Radarr 的 Manual Import（勾選的列整批設定），開工時再對一次現行版本。
- **A4 模型不給 `route_id`**（票 04）：會送進 Route 的命令（`sends_into_a_route`：送單、Mikan 訂閱、關鍵字訂閱）在給模型的輸入裡不帶 `route_id`。伺服器在提出時決定：可選的只有一條就用它；不只一條出 `RouteAsk`（預選照舊）；一條都沒有就拒絕。給模型的工具拿掉 `media.route_choices`，`media.read_media` 給模型的那一份拿掉 `routes`、`default_route_id`，skill 的 Route 段落刪掉。`rss.add_feed` 的 `tv_route_id` / `movie_route_id` 是 Feed 層的設定，不動。
- **C1 `contains`**（票 05）：`search.search_torrents` 加 `contains: list[str]`，每個詞都要出現在發佈名裡（正規化同 `parser.title`），先篩再截斷；有 `contains` 時給模型的列數上限放寬。
- **C4 `find_in_library` 給集數**（票 06）：劇集的命中多 `episodes`，用 Jellyfin 的季集號以範圍表示，註明不是 TMDB 編號。
- **B1–B4 系統指示與 skills**（票 07）：共同規則（搜尋語言、只在要下載或問有什麼時才搜種子、已有的不重抓、確認卡的說法）寫進系統指示。5 個 skill 併成 `download`、`subscribe`、`recommend`，不點名特定作品。`why-not-imported` 改寫成 `why_not.explain` 的工具說明；「從媒體庫重建帳本」的指引只留在 `media.read_media` 輸出的 `hint`。
- **C3 `rss.subscribe`**（票 08、09）：模型只給 `media_id` 與字幕組，伺服器用作品的各種名字找 Mikan 番組、用開播日挑；找到而且有那個字幕組就走 Mikan，否則走 nyaa / acg.rip 關鍵字。卡片列出找到的字幕組與來源，由人選一個。給模型的工具拿掉 `bangumi.search_bangumi`、`bangumi.read_bangumi`、`rss.subscribe_mikan`、`rss.subscribe_search`（命令本身留著，RSS 頁還在用），工具從 22 支減到 18 支。
- **UI 收尾**（票 10）、**側面板可拖拉調整寬度**（票 10b，2026-11-07 使用者追加）與**驗收**（票 11）。

不做：
- A3（預選 AI 給的 Route，或按類型預選）：A1、A2 做完之後一張卡最多選一次；預選 AI 給的會回到 M5 票 23 實測的問題。之後要做時參考 Jellyseerr 的「Anime Root Folder」（未查證）。
- TPB / YTS 對查不到的查詢回一整頁無關結果：另一個問題，這個里程碑不修。

## 共同規則

- **給模型的文字一律英文**：系統指示、skill、工具說明、工具輸出的 `hint`。給人看的確認卡文案走 i18n key，zh-Hant 與 en 並列。
- **同輪要改的文件**：brief §14（確認卡、skills）、§20（這個里程碑實測到的外部事實，附來源）；plan §6〈agent〉〈proposals〉、§7〈確認卡〉；`CONTEXT.md`（有新名詞或改名時）；`scripts/experiments/README.md`（實驗腳本有增改時）。
- `services` 新增或改動的公開命令都標 `@command`；非 `internal` 的進命令登錄表。`test_command_marks.py`、`test_command_registry.py`、`test_agent_tools.py`、`test_skills.py` 的斷言跟著改，不加豁免。
- 動 `parser/` 的票必跑 `berth bench`，`auto_wrong` 不得上升，貼數字。
- **舊 Proposal 照樣按得下去**：升級前存下、參數裡帶 `route_id` 的卡，核准與執行的行為不變；新欄位容得下舊列，不回填。
- 關掉 AI 時與 M5.5 相同：確認卡、Route 選擇、搜缺的集都不需要 AI。
- UI 改動用 playwright 實跑，附截圖或文字結果，桌機與 390px 都看。
- 真模型的量測：結果放在 `.local/experiments/results/`，摘要（數字表與結論）寫進研究文檔新的一節並 commit；要用 `.env` 的 key，缺 key 時問使用者。

## 驗收

- S7（要下載「非人少女」、選喵萌奶茶屋繁中單集）的種子搜尋 ≤ 6 次，和票 01 量到的基準比（原對話 18 次裡有一次是還沒說要下載就搜的，S7 量不到，不拿來比）；13 列同一部作品的送單卡，Route 只要選 1 次。
- S8（模糊開頭，只說「找」、沒說要下載）沒有種子搜尋。
- skills 3 個、總行數 ≤ 80，沒有點名特定作品；給模型的工具 18 支。數字由測試守。
- S1–S6 與 S2 三個變體按 M5 驗收逐項檢查，品質不比基準差，S2 變體的範圍標記不變差；工具呼叫數、input token、費用和票 01 的基準並列比較。
- 只有一季、第 1 季整季缺的 CJK 名字作品，「搜缺的集」問得到動畫站（單元測試加上一次實測紀錄）。
- 模型給的工具輸入裡沒有 `route_id`。作品可選兩條 Route 時卡片問一次並預選上次用的；只有一條時不用選；零條時提出就被拒絕，理由交給模型。
- 升級前存下、帶 `route_id` 的 Proposal 照樣核准與執行（整合測試）。
- 一次 `query` 加上 `contains: [字幕組, 語言]` 就拿到那個字幕組的整季單集，不用逐集搜。
- `find_in_library` 命中劇集時帶 Jellyfin 季集範圍；Jellyfin 沒刮到 TMDB id 時，模型照樣說得出使用者有哪幾集。
- `rss.subscribe`：Mikan 找得到番組與字幕組時走 Mikan，找不到時走關鍵字來源；卡片說出來源與找到的字幕組。RSS 頁的 Mikan 訂閱與關鍵字訂閱行為不變。
- 確認卡的分組與「全部套用」在桌機與 390px 都可用（playwright），鍵盤操作得到。
- 助理側面板可拖拉調整寬度、寬度會記住，390px 不畫把手（playwright）。

## 票序

票在 `.scratch/m5.6/issues/`，編號即建議的開工順序；依賴寫在各票的 `Blocked by`，編號在前不代表擋住後面。

| 票 | 標題 | Blocked by |
| --- | --- | --- |
| 01 | 基準：S1–S8 真模型跑一次 | — |
| 02 | 只有一季的作品，整季缺時問得到動畫站 | 01 |
| 03 | 確認卡同一部作品只選一次 Route，加「全部套用」 | — |
| 04 | 模型不給 `route_id`，Route 由伺服器在提出時定 | 01、03 |
| 05 | 種子搜尋的 `contains` | 01 |
| 06 | `find_in_library` 給集數 | 01 |
| 07 | 共同規則進系統指示，skills 5 → 3 | 04、05、06 |
| 08 | `rss.subscribe` 走 Mikan | 04 |
| 09 | `rss.subscribe` 退回關鍵字來源，拿掉舊的四支工具 | 07、08 |
| 10 | M5.6 UI 收尾 | 03、04、09 |
| 10b | 助理側面板可拖拉調整寬度 | 10 |
| 11b | 修「可以看了」真服務 e2e 的穩定紅 | — |
| 11 | M5.6 驗收 | 01–10b、11b |
