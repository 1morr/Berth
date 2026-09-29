# 09 — Prowlarr 頁的索引站：預設不勾、先測再勾、全部公開站可搜尋

**Status:** done

**Blocked by:** 15（15 把 Prowlarr 與索引站併成一頁；這張改那一頁的索引站那一半）

**讀:** plan §9.3 頁 4「Prowlarr 與索引站」、§8.4；brief §16.3、§20.7（Prowlarr API）、§20.14、§19 2026-09-26「精靈與探索的試跑回饋」與 2026-09-29「精靈改為每個服務手動選擇」兩列；開工先 `/impeccable shape` 這一頁的索引站區

## 為什麼（2026-09-26 使用者試跑）

- 預設全勾，按一次就把九個站全加進 Prowlarr；連不上的站（試跑時 Nyaa.si 的 SSL 失敗）也照樣試。
- 結果列在清單下面，「前往下一個泊位」被擠到最底；左欄還有大片空間。
- 只有 Berth 挑的九個站；使用者想要 Prowlarr 裡的其他站得自己去 Prowlarr 加。
- 設定頁的索引站一進去就開始檢查，同樣改成手動。

2026-09-29 起（brief §19）索引站在 Prowlarr 那一頁的下半，只對**套件內** Prowlarr 挑站；既有 Prowlarr 用使用者已有的
索引站，Berth 不替它加站（票 05 已擋 422）。

## 先查證

用 context7 / Prowlarr OpenAPI 確認兩件事，結論與來源補進 brief §20.7：
- `POST /api/v1/indexer/test` 能不能測**還沒加入**的定義（Prowlarr 自己的「新增索引站」對話框有 Test 按鈕）。
- 搜尋是否只能對已加入的站（`GET /api/v1/search?indexerIds=`）——若是，「加入之前先搜」做不到，流程就是
  「測試 → 勾通過的 → 加入 → 逐站 / 全部試搜 → 不要的移除」。

## 做什麼

1. 套件內：推薦清單預設**不勾**；每一站一顆「測試」，只有測試通過的勾得起來；一顆「測試全部」。
2. 加入之後每一站一顆「搜尋」與一顆「搜尋全部」，輸入關鍵字、看各站筆數與前幾筆標題（現在的 `indexer.search_indexers` 已有逐站形狀）。
3. 測試與搜尋的結果放左欄（或逐列行內，shape 時定），不把「前往下一個泊位」擠下去；與上半的介面登入同一頁，排版一起看。
4. 推薦清單之外加「全部公開站」：`indexer/schema` 裡 privacy = public 的定義，可依名稱、語言搜尋，同樣先測再加。
   私有 / 半私有站要依定義動態產生帳密欄位——這一張不做，連到 Prowlarr 自己的介面去加，Berth 認得 Prowlarr 裡已有的站。
5. 既有：列出 Prowlarr 裡已有的站與站數，可試搜，沒有勾選與加入。
6. 設定頁的索引站分頁：進入不自動檢查，同一套元件。
7. **單站失敗的呈現**（票 15 critique 的 P1，使用者 2026-09-29 排在最前）：現在加站失敗是 Prowlarr 的英文原文、
   `role=alert` 一次好幾塊；「Query successful, but no results」被說成連不上；補法連結是容器主機名
   `http://prowlarr:9696/#/indexers`（瀏覽器解析不到）；失敗之後主鈕數的是已經加好的站；紅色在這裡不代表這一步被擋。
   改成：常見失敗（Cloudflare、查無結果、連不上）對應成 i18n 理由，原文收進可展開的區塊；失敗收成一條 `assigned`
   摘要、只一個 live 區；連結給使用者主機上的位址，給不出就拿掉；主鈕只數還沒加的。和第 1 條的「先測再勾」一起 shape。
8. **換另一格的確認**（票 15 critique / audit 的 P2，`web/src/setup/ServiceChoice.tsx`，頁 1、2、4 與設定頁共用）：改用
   `ConfirmPanel`（焦點移進去、Esc 收起）；確認之前標題與 lede 跟著草稿的來源；`switchWarning` 依原本的來源分兩種說法
   （從既有換走時 Berth 沒寫過那一台的偏好）；方向鍵在兩格間移動只改草稿、不觸發套件內的選擇與測試。

## 驗收

- [x] 查證結論與來源寫進 brief §20.7
- [x] 沒測過或測試失敗的站勾不起來（vitest，雙向）
- [x] 全部公開站的清單來自 Prowlarr 的 schema、可搜尋；加一個不在推薦清單上的站成功（`berth-lab/reset.sh bundled` 實測）
- [x] 既有 Prowlarr 的頁面沒有勾選與加入，試搜得到它已有的站（vitest + `berth-lab` existing 實測）
- [x] 進入精靈這一頁與設定頁的索引站分頁都不送檢查請求（vitest + playwright network 紀錄）
- [x] 1280 與 390 截圖：結果出來後「前往下一個泊位」不必捲動
- [x] 單站失敗：原文不直接顯示、一條摘要一個 live 區、沒有容器主機名的連結、主鈕只數沒加的（vitest，照 fake 的四站失敗）
- [x] 換另一格：Esc 收起確認、焦點進確認區、方向鍵瀏覽不送 `POST /setup/services/{kind}`、從既有換走的警告不說「寫過偏好」（vitest）
- [x] plan §9.3 頁 4、brief §16.3 同步
- [x] lint、type、test、前端 e2e 綠燈

## Comments

- 2026-09-30 實作（shape：`.scratch/m4/indexer-berth-shape.md`，使用者三題都照建議：結果逐列行內；推薦在上、其他公開站用
  名稱 / 語言叫出來；「已加入」一段在上、「加站」在下）。
- 查證（berth-lab bundled 的 Prowlarr 2.6.5.5623，brief §20.7）：`indexer/test` 收還沒加入的定義，通過 200 `{}`、不通過
  400 加理由，都不建立任何東西；`indexerIds` 只認已加入的站（不存在的 id 回 400）。schema 645 個定義、public 88 個，其中
  NZBIndex 是 usenet、`Torrent RSS Feed` 的 `definitionName` 出現兩次——公開站清單只收 torrent、依 `definitionName` 去重。
  錄下 `tests/fixtures/http/prowlarr/indexer-test.rejected.*.json`。
- berth-lab 實跑（image `berth:m4-09`）：
  - bundled（`reset.sh bundled` 之後走精靈）：進頁 4 只發 `GET /api/setup/indexers`；「測試全部」約 5 秒，Nyaa.si（SSL）、
    Anime Tosho 連不上，1337x、EZTV 被 Cloudflare 擋，其餘 5 站通過；其他公開站 78 個，Knaben 在這台連不上、TorrentsCSV
    通過並加入；私站連結是 `http://localhost:29696/#/indexers`，開得起來。
  - **實測抓到的 bug**：TorrentsCSV 的 schema 預設 `enable: false`，原樣送回去加成的是停用的站，「搜尋全部」跳過它、
    畫面說「還沒搜」。修：`add_indexer` 一律送 `enable: true`（契約測試修前紅）；前端停用的站說「在 Prowlarr 停用了」、
    不給搜尋。重建 image 之後移除再加一次，啟用、搜尋全部有問到它。
  - existing（home-prowlarr 以使用者身分用它自己的 API 加了 dmhy、YTS）：頁 4「已加入 2 站」，沒有勾選、加入與移除，
    搜尋全部 dmhy 80 筆、YTS 103 筆。泊位板原本仍說上一次測試的「尚未加入索引站」，改成清單讀得到就用清單（vitest）。
  - 1280 × 720 與 390 × 844 在結果出來之後回到頁頂，「前往下一個泊位」在畫面內（lab 與 e2e 的
    `4-indexers-viewport.png` 各兩張）。
- code-review（Standards、Spec 兩軸）修掉的：radio 觸發的確認另寫了一份 Esc 處理（改用 `useInPlaceConfirm` 的
  `escapeOnly`）、方向鍵瀏覽時 radio 上按 Esc 收不起確認（補上，DESIGN.md 記為例外）；測試請求沒送到時多一個紅色
  `role=alert`（併進摘要那一個 live 區）；既有 Prowlarr 沒有 shape 寫的連結（`prowlarrWeb` 補既有：`host.docker.internal`
  換成瀏覽器主機名、compose 主機名不給）；plan 的 API 表沒同步；`verify_sites` 測已加入站的分支沒有呼叫端（刪）；
  `hostOf` 兩份；沒通過的列照 The Heavier Line Rule 換 `rule-strong`；e2e「進頁不送寫入」的取樣點有競態；`keeps` / `web`
  改名。
- **沒處理的**：
  - Smell（判斷題）：站的描述欄位（`privacy`、`language`、`description`、`protocol`）在 `ProwlarrIndexer`、
    `IndexerDefinition`、`IndexerSite`、`IndexerCandidate` 與兩個 `*Out` 各一份；`useChoiceDraft` 之後的
    `switching` 推導在四個服務頁各寫一次；`IndexerStep` 與 `IndexerActions` 各組一次「已加入 + 加站」；前端的
    `'prowlarr_login'` 靠註解對齊後端（票 07 起就是這樣）；幾處巢狀三元組狀態字。
  - 既有 Prowlarr 測試那一條的「索引站 0」是上一次測試時的數字，重新測試才會變；回頭看的說明（`RevisitNote`）不分來源，
    既有那一頁也說「測試並加更多公開站」。
