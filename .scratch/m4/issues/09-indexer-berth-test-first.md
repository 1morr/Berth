# 09 — Prowlarr 頁的索引站：預設不勾、先測再勾、全部公開站可搜尋

**Status:** ready-for-agent

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

- [ ] 查證結論與來源寫進 brief §20.7
- [ ] 沒測過或測試失敗的站勾不起來（vitest，雙向）
- [ ] 全部公開站的清單來自 Prowlarr 的 schema、可搜尋；加一個不在推薦清單上的站成功（`berth-lab/reset.sh bundled` 實測）
- [ ] 既有 Prowlarr 的頁面沒有勾選與加入，試搜得到它已有的站（vitest + `berth-lab` existing 實測）
- [ ] 進入精靈這一頁與設定頁的索引站分頁都不送檢查請求（vitest + playwright network 紀錄）
- [ ] 1280 與 390 截圖：結果出來後「前往下一個泊位」不必捲動
- [ ] 單站失敗：原文不直接顯示、一條摘要一個 live 區、沒有容器主機名的連結、主鈕只數沒加的（vitest，照 fake 的四站失敗）
- [ ] 換另一格：Esc 收起確認、焦點進確認區、方向鍵瀏覽不送 `POST /setup/services/{kind}`、從既有換走的警告不說「寫過偏好」（vitest）
- [ ] plan §9.3 頁 4、brief §16.3 同步
- [ ] lint、type、test、前端 e2e 綠燈

## Comments
