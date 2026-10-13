# 73 — 頁 4：Prowlarr 裡沒有推薦站時說出原因

**Status:** done

**Blocked by:** None — can start immediately（與 67 的頁 4 改動同一區，後做的那張合併）

**讀:** `docs/research/linux-trial-2026-10-09.md` §3.1（04:54 那兩列）、§6、§7 L4；brief §20.14「原生 Linux、rootless Docker 實跑」的最後一條；`berth/services/indexer.py` 的 `add_recommended_indexers` 與 `DEFAULT_INDEXERS`；頁 4 套件內的元件；`PRODUCT.md`

## 為什麼

票 42 實跑時 Prowlarr 連不上 `indexers.prowlarr.com`（`IndexerDefinitionUpdateService: Definition update failed`，SSL EOF），只剩磁碟上的 5 個站定義（Anidex、Knaben、SubsPlease、showRSS、TorrentsCSV），推薦清單上的站一個都不在。結果：

- 頁 4 的「推薦站」區只剩標題「Recommended sites」與「Do this later」，**主鍵不見、也不說為什麼**；
- 直接打 `POST /api/setup/indexers/recommended` 回 200、`checks: []`：沒測、沒加、沒有理由。

使用者只看到少了一個按鈕。那一次的根因是 VM 自己的代理，但任何擋了那個網域的網路（公司防火牆、DNS 過濾、地區封鎖）都一樣。

**失效條件**：套件內 Prowlarr 的 `GET /api/v1/indexer/schema` 裡沒有推薦清單上任何一個 `definitionName`。

## 做什麼

1. 推薦清單上的站在 Prowlarr 的定義裡一個都找不到時，頁 4 說出來：Prowlarr 還沒拿到站的清單（多半是它連不上 `indexers.prowlarr.com`），去 Prowlarr 的 System → Logs 看、網路通了之後按「重新讀取」；同時保留「之後再說」與進階的逐站挑選。
2. 只找到一部分時，照現在的做法測找得到的那幾站，回報裡列出「Prowlarr 裡沒有這幾站」。
3. API 的回應帶得出這兩種情況（不要只是空的 `checks`），前端照它顯示；zh-Hant 與 en 並列。

## 驗收

- [x] services 單元測試：schema 裡一個推薦站都沒有 → 結果標明「全部不在」；只有一部分 → 測找得到的、列出不在的（先寫紅燈）
- [x] vitest：全部不在時頁 4 顯示原因與下一步，主鍵不消失得無聲無息
- [x] playwright 實跑截圖（用演練伺服器或把套件內 Prowlarr 的定義目錄清空造情境）
- [x] 全部檢查（`pre-commit run --all-files`）、test 綠燈

## Comments

- 2026-10-14 做法：`IndexerSetup.unlisted`（推薦清單上、`indexer/schema` 與已加入的站裡都找不到的 `definitionName`），`GET /setup/indexers` 與兩顆按鈕的回應都帶。前端在「沒有站、沒有推薦候選、`unlisted` 不空」時把主鍵的位置換成 `Unlisted`：`assigned` 的 Notice（原因、`indexers.prowlarr.com`、下一步）、「重新讀取」（服務頁的重新測試，清單跟著重讀）、到 Prowlarr `/system/events` 的連結；「之後再說」與「進階」照舊。只缺幾站時主鍵照舊，結論摘要下多一行「Prowlarr 裡沒有 N 個推薦站，沒有測：…」。
- 查證（讀 Prowlarr develop 原始碼，寫進 brief §20.14）：`indexer/schema` 每次呼叫 `IndexerDefinitionUpdateService.All()`，先向 `indexers.prowlarr.com` 拿清單、失敗才讀磁碟，所以網路通了按「重新讀取」就有，不必重啟 Prowlarr。票面寫「System → Logs」：Prowlarr 的選單是 Events 與 Log Files，連到 Events。
- 實跑：新的演練情境 `unlisted`（`UnlistedProwlarr`，`POST /demo/prowlarr/online` 演網路通了）。截圖 `.playwright-mcp/t73/`：`p4-unlisted-1280.png`、`p4-unlisted-390.png`、`p4-unlisted-en-1280.png`，以及演網路通了、按「重新讀取」之後主鍵回來的 `p4-after-reread-1280.png`。Events 連結實際是 `http://127.0.0.1:9696/system/events`。
- 第一條驗收的測試放在 `tests/integration/test_indexer_one_key.py`、經 API 測（票 44 對同一個命令的測試在那裡），同時驗了 services 的結論與 API 帶得出來。紅燈先行：`KeyError: 'unlisted'`；vitest 紅燈是找不到 `data-testid="unlisted"`。
- code-review 已處理：同一作用域裡 boolean 與陣列同名 `unlisted`，前者改成 `nothingToTest`（Standards）；同檔四份一模一樣的 `client` fixture 提到模組層（Standards）；DESIGN.md 補上兩種新狀態（Standards）。
- code-review 沒處理的：
  - (1) 既有的 `${webUrl}/#/indexers`、`/#/settings/general`、qBittorrent 的 `/#/settings`（`IndexerStep.tsx`、`IndexerSites.tsx`、`QbittorrentStep.tsx`）。Prowlarr 是 BrowserRouter，`/#/settings/general` 多半會落在首頁（索引站），不是設定頁。這是從原始碼推的，沒有實跑 repro，也不在這張票裡，所以只記下、沒改（Standards）。
  - (2) `Unlisted` 與既有 Prowlarr 的 `NoSites` 形狀幾乎一樣（Standards，Duplicated Code）。沒抽共用：兩者的外層、文案、連結都不同，抽出來的元件只會剩三個參數的殼。
  - (3) 回應沒有明確的「全部不在」旗標，畫面由 `unlisted` 加上沒有推薦候選推出來（Spec）。在 `sites` 為空時兩者等價，多一個旗標就是同一件事的兩份說法。
  - (4) Prowlarr 已經有站、推薦站又全都不在時，不出說明（Spec）：沿用票 44 的「已經有站不給主鍵」，那時頁 4 已經算完成。
  - (5) 缺的站顯示 `definitionName`（`mikan`）而不是站名（Spec）：沒有定義就拿不到站名。
  - (6) Spec 軸擔心「進階」加站之後，摘要也會說「沒有測」。不管走哪一條路，不在 Prowlarr 定義裡的站都測不了也加不了，那一句照樣成立。
