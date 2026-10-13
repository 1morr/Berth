# 84 — 搜尋前：使用者點選要用哪些名字、哪幾季去問；名字的選擇記住並套用到所有作品

**Status:** done

**Blocked by:** 83（同一個搜尋面板與切換元件；先改結果，再改問法）

**讀:** `berth/services/search.py`（`search_titles`、`_title_order`、`_season_variants`、`missing_batches`、`plan_queries`、`MAX_QUERIES` 的註解）；`GET /api/search/queries`；`web/src/media/SearchPanel.tsx`；`MediaSnapshot` 的標題欄位與 TMDB `alternative_titles` 怎麼存（看別名有沒有保留語言或國家）；M4 票 77（請求預算、`take_each`）；brief §13、plan §8.4

## 為什麼（2026-10-10 使用者）

現在問哪些名字、哪幾季，都由 Berth 決定，使用者改不了：
- 名字的順序是英文、原名、顯示名（中文）、其他別名，上限 5 個。
- 兩季以上的劇只加「最新一季」的兩個查詢。

使用者想自己選：名字預設只用英文名和原名，其他的自己勾或取消；季也一樣可以手動勾。

## 做什麼

1. **名字與季都做成可點的 chip**（使用者 2026-10-10：比勾選框好看）：
   - 用票 83 篩選按鈕的同一個切換元件（`aria-pressed`），整個搜尋面板只有一種「可以開關的東西」。
   - 名字的 chip 帶語言標記（英文名、原名、中文名、別名）。
   - 預設開英文名與原名，中文名（顯示名）與其他別名預設關。
2. **名字的選擇全域記住，以語言為單位**：
   - 在任何一部作品開了中文名，之後所有作品預設都開中文名；關掉也一樣。
   - 記在 Berth 的伺服器端設定，不放瀏覽器，換裝置也一樣。
   - 要分到什麼程度（「中文」「其他別名」；別名分不分得出語言），先看快照存了什麼再定，寫在 Comments。
3. **季也是 chip，季的記號只有一套**：
   - 「不指定季」加逐季一顆。預設：開「不指定季」；兩季以上時另開最新一季（同現在）。季的選擇不記住。
   - 按搜尋與「搜缺的集」**共用同一個產生季記號的函式**：拉丁字的名字配 `S03`，有 CJK 字的名字配 `第3季`（現在按搜尋用 `Season 3`、搜缺的集用 `S03`，是兩個時期各加的兩套）。
   - **先實跑再定**：`Season 3` 當初是因為真的發佈名這樣寫（`The Bear Season 3`）。用真的索引站把 `Season N` 與 `SNN` 各搜一次比結果數（至少一部美劇、一部動畫）；`SNN` 不比較少才統一成它，比較少就兩種都留並寫下理由。數字寫進 brief §20 並附日期。
4. **按下去之前說出代價**：
   - 即時列出會問的查詢，並說「會發 N 個查詢，每個站會佔 N 格請求預算」。
   - 上限多少在 shape 時定，但不能沒有上限（索引站背後是公開站，被問太多次會封 IP）。
   - 超過上限時搜尋鍵停用並說出原因。
   - 名字有 `&` 的照舊自動多一個寫成 `and` 的，也列在查詢裡。
5. **「搜缺的集」也用使用者開的名字**：缺的形狀照舊決定是整季還是逐集，季記號走第 3 項那一個函式。
6. **預覽與實際送出的查詢只有一份實作**：照舊由後端算（`plan_queries`），前端不重算。
7. **UI 走 `/impeccable`**：先 `shape`，把稿子給使用者確認後才實作；收尾做 `critique` / `polish`。

## 驗收

- [x] shape 稿使用者確認過，路徑寫在 Comments
- [x] 預設只勾英文名與原名；在 A 作品勾了中文名，B 作品打開時中文名預設已勾；取消也一樣；pytest 與 vitest 守，做變異驗證
- [x] 開了的季會正確產生查詢，按搜尋與搜缺的集用同一個季記號函式，預覽與實際送出的查詢相同；pytest
- [x] `Season N` 與 `SNN` 的實跑比較寫進 brief §20（附日期），決定與理由寫在 Comments
- [x] 查詢數與預算格數的提示正確；超過上限時不能送出；vitest
- [x] 「搜缺的集」用勾選的名字；pytest
- [x] Playwright 實跑：一部動畫（勾中文名）與一部美劇，各搜一次；換一部作品，確認中文名預設已勾。1280 與 390 寬各截圖。用隔離環境（`berth-t84`）；**不准碰使用者的 `berth-local`**
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；`pnpm gen:api` 沒有差異；若有 migration，CHANGELOG 寫升級說明；progress.md 已更新

## Comments

**shape**：`.scratch/m4/search-choose-shape.md`。2026-10-13 使用者確認（加簡體中文名、上限 8、其餘照稿）；同日實跑後改成拉丁字名字一季問
`S03` 與 `Season 3`、上限 10（使用者拍板）。

**名字分到什麼程度（票面要求先看快照）**：快照的 `titles` 約 35 個別名與翻譯，**不帶語言**（`adapters/tmdb._titles` 收的時候丟了
`iso_639_1` / `iso_3166_1`）。所以分成五種：英文名（`title_en`）、原名、中文名（`zh-TW` 顯示名；等於英文名時不算，那是沒翻譯時的退路）、
**簡體中文名**（快照新欄位 `title_zh_cn`，取自同一個回應的 `translations` 的 `zh-CN`，不多一次請求；Mikan、dmhy 的字幕組多用它）、
其他別名。前四種全域記住（`settings.search`），別名不記、預設關、收在展開區——記住「別名」等於下一部作品三十幾個全開。
同一串字是兩種時合成一顆 chip，按它兩種都記。

**`Season N` 對 `SNN`**（2026-10-13，隔離 Prowlarr：The Pirate Bay、Mikan、dmhy；Nyaa、YTS 從容器連不上；brief §20.21）：
美劇 `S03` 比較準（TPB `The Bear Season 3` 23 筆、名字對得上 11 筆，只有 3 筆是第三季；`The Bear S03` 6 筆全是），
動畫站 `S02` 少一個數量級（Mikan `SPY x FAMILY Season 2` 189 筆、90 筆真的寫 `Season 2`；`S02` 2 筆）。照票面「`SNN` 比較少就兩種都留」：
**拉丁字名字一季問 `S03` 與 `Season 3`，CJK 名字 `第3季`**，按搜尋與搜缺的集共用 `parser.season_tokens`。上限因此從 shape 的 8 改 10。

**上限 10、超過整次不問**（不砍尾巴：名字與季是使用者開的，默默少問等於替他決定）；前端停用搜尋鍵並說原因，後端 `TOO_MANY_QUERIES` 守直接打 API
的那一條路。這推翻票 02b 的「按鈕永遠按得下去」（票面明訂）。

**變異驗證**（各自紅過，再還原）：後端——`default_choice` 不看記住的（4 紅）、別名也算記住（5 紅）、`remember_names` 不寫入（4 紅）、
拿掉上限（2 紅），無關改名不紅；前端——不呼叫記住（1 紅）、別名也記（1 紅）、不看上限（1 紅）、預覽換新中不停用（1 紅）、
快照沒讀到也說「至少開一個名字」（1 紅），無關改名不紅。

**Playwright 實跑**：隔離 compose `berth-t84`（只有 Prowlarr，port 19784、named volume、網路 10.84.0.0/16）＋這個分支的
`fake_setup_server --scenario search --port 8484`（真 TMDB、真 Prowlarr）。《葬送的芙莉蓮》開中文名搜一次（3 個查詢、符合 1046 筆）；
換《The Bear》中文名預設已開、S05 預設開，搜一次（5 個查詢）；在《The Bear》關掉中文名，回芙莉蓮也關了；開到 15 個查詢時搜尋鍵停用、
原因掛在描述上；390 寬沒有橫向捲動。截圖 `.playwright-mcp/t84/`（`frieren-1280`、`frieren-390`、`bear-1280`、`bear-390`、
`bear-over-limit-1280`、`frieren-chinese-on-1280`）。跑完 `down -v`；`berth-local` 四個容器全程 Exited、沒碰。

**code-review（兩軸 opus）處理**：Standards——兩處還指著刪掉的 `search_titles` 的註解改掉，RSS 訂閱面板的「這部作品的名字」改讀名字清單
（之前讀查詢，含季記號；現在不含別名）；開了的 chip 改當 mutation 參數傳（照緊鄰註解的規矩）；`rememberKinds` 型別用 `NameKind`。
Spec——代價那一行補上「每站每小時 N 格」（`budget`，讀這一台的 `RequestBudget.limit`）；快照沒讀到時不畫空 chip、搜尋鍵照舊按得下去；
預覽換新中停用搜尋鍵（`isPlaceholderData`），送出去的才是畫面上列的那一份；搜缺的集超過上限時只叫人關名字。
**未處理**：「別名不記」在 models（丟掉）、service（拒絕）、API（422）、前端各寫一次——models 那一條是讀舊資料的防線、service 那一條是命令本身
的規矩、API 那一條讓它是 422 不是 500，留著；`_texts` 收 8 個參數（`missing`、`season`、`from_season` 與 `choice` 一起走）是 Data Clump，
等下一次動到搜尋的參數時一起收成一個型別；實驗腳本自己寫 `urllib` 沒用 `lib.py`，一次性腳本不改。
