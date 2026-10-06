# 39 — 頁 4 既有表單改用頁 1、2 的元件與端點；錯誤版面與右欄狀態

**Status:** done

**Blocked by:** 37（拿掉 Torznab 之後，共用元件不必背「接法」單選）、34（要更新真服務 e2e）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S3「Prowlarr API key 錯」那列、§A3「兩條寫 `choices` 的路徑」、§C3 第 3 條、「Berth 精靈哪裡不統一」第 2 條、簡化方案 E-2、改進清單 P1-2、P1-4）；票 21；brief §16.3；plan §9.3

## 為什麼（2026-10-06 審計）

- 頁 4 既有表單有自己的元件與端點（`POST /setup/indexers/connect`），錯誤版面和頁 1、2 不一樣，少了「測試結果」那一列。
- key 錯的時候，右欄仍寫「API key 已取得」。截圖 s3-14。
- 寫 `choices` 有兩條路徑：頁 1、2 走 `POST /setup/services/{kind}`，會經過 `_start_over` 的清理；頁 4 那條不經過。

## 做什麼

1. 頁 4 既有表單換成頁 1、2 的 `ExistingForm`。連線改走 `POST /setup/services/{kind}`，`choices` 只剩一條寫入路徑，都經過同一份清理。
2. 刪掉 `POST /setup/indexers/connect`。它是 OpenAPI 公開的端點，屬對外 API 刪除（D5 / E-2 已拍板），要記進 CHANGELOG。
3. 右欄的憑證狀態跟著最近一次連線測試走：失敗時不寫「已取得」。
4. plan §6 的 API 表與 §9.3 同一個 commit 改。

## 驗收

- [x] 整合測試：Prowlarr 經 `POST /setup/services/prowlarr` 連線、換台時走 `_start_over` 的清理（雙向：換台會清、同一台不清）
- [x] vitest：頁 4 既有表單與頁 1、2 是同一個元件；key 錯時錯誤區有「測試結果」那一列，右欄不寫「已取得」
- [x] 舊端點刪掉，OpenAPI 型別重新產生
- [x] 真服務 e2e 與前端 e2e 更新並綠燈；playwright 實跑 key 錯與 key 對，附截圖
- [x] 全部檢查（`pre-commit run --all-files`）、test 綠燈

## Comments

**2026-10-07 實作紀錄**

- 後端：刪 `indexer.connect_indexer` 與 `POST /setup/indexers/connect`，頁 4 既有改送 `POST /setup/services/prowlarr`
  （`setup.choose_service` 本來就收既有 Prowlarr，換台走 `_start_over`）。消費點跟著歸零的兩樣一起刪：
  `GET /setup/indexers` 的 `reason`（只給舊表單選補法）、`IndexerProbe` 的 `reason` / `sites`（`probe_indexer`
  只剩健康檢查呼叫，改成直接回那一條 `SetupStep`）。CHANGELOG 記破壞性。
- 前端：`IndexerStep` 不再傳 `existingForm`，用 `ServiceChoice` 內建的 `ExistingForm` 與 `TestLine`；`existingForm`
  這個 prop 沒有別人用，刪了。`Fix` 補兩句：既有 Prowlarr 的 `auth_required` 說去哪裡複製 key（原本頁 4 那一句），
  key 留空的 `api_key_missing` 說要貼 key（code-review 抓到原本會掉到「連不到這個位址」）。右欄 API key 那一格看
  `status.services` 的最近一次測試（`keyState`）。
- 設定 → Prowlarr：位址與 key 改用連線區 `ServiceConnection`（與另兩頁同一份，票面沒列，但舊端點刪了它沒有別的路），
  `IndexerActions` 只剩站的那一區。換來源要先確認（`switchWarning`，code-review）；使用者按的重新測試之後也重測
  健康、重讀站（code-review：原本轉綠之後站那一區停在「先在上面接上」）。
- 整合測試（`test_setup_api.py`）：換台會清用「既有 → 套件內」看——換到既有時連線測試本來就蓋掉纜繩，既有那一台
  也沒有介面登入紀錄，所以「既有 A → 既有 B」看不出有沒有清。雙向變異驗過：讓 Prowlarr 不清，換台那條紅；
  一律清，同一台那條紅。
- e2e：真服務 e2e 的精靈多一段 `_prowlarr_as_existing`（錯 key 是 `auth_required`、從 berth 唯讀掛載讀對的 key 連上、
  「之後再說」換回套件內不跟過來）；前端 e2e `existing` 先貼錯 key 再貼對，演練伺服器 `mixed` 的既有 Prowlarr 只收
  一把 key（`Scenario.connect_api_key`）。

**實跑（前端 e2e `existing` / `existing-390`，演練伺服器 `mixed`）**

截圖在 session scratchpad 的 `t39/`，不進版控。

| 情境 | 結果 |
| --- | --- |
| key 錯（1280、390） | 表單下是頁 1、2 那一條：「沒通過」、「測試結果：API key 不被接受」、手動步驟說去「設定 → 一般」複製、「重新測試」；右欄 API key 寫「不被接受」（`t39-wrong-key-*`） |
| key 對 | 「連上了」、索引站 2、「改位址或憑證」；右欄「已取得」、已加入 2，下面是已加入與加站（`t39-right-key-*`） |

**code-review 沒處理的**

- `indexer.probe_indexer`（健康檢查）與 `setup._test_connection`（精靈）各自問 `system/status` 與判版本，原本
  docstring 說「兩份實作會讓一份先過期」的那個風險還在；票 39 只是拿掉了第三個呼叫點。
- `IndexerActions` 現在只有設定頁用，仍住在 `setup/IndexerStep.tsx`；`IndexerCutaway` 的 `bundled` 可從來源推出。
- `jellyfin.cutaway.server` / `apiKey` / `libraries` 看起來沒有引用處（票 39 只刪了自己弄成孤兒的 `held` / `absent`）。
