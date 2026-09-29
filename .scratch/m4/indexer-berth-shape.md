# 頁 4 的索引站區：先測再勾、全部公開站、已加入的站試搜（M4 票 09 的 shape）

**Status:** confirmed（2026-09-30，使用者三題都照建議）

慣例來源：Prowlarr 自己的「新增索引站」對話框（選定義 → Test → Save，Test 不建立任何東西）；Sonarr / Radarr 的
Indexers 設定頁（已加入的站一列一站、各有 Test）。本 repo 的頁 3（`RouteRow`：一列一件事、結果長在那一列）。

## 查證（brief §20.7，berth-lab bundled 的 Prowlarr 2.6.5.5623 實測）

- `POST /api/v1/indexer/test` 收 schema 的定義原樣（`appProfileId` 換 1）就測得了**還沒加入**的站：通過 200 `{}`、
  不通過 400 加逐條理由，兩種都不建立任何東西（測完 `GET /indexer` 仍是 0 站）。YTS 1.9 秒、dmhy 1.1 秒。
- 搜尋只吃已加入站的 id：`GET /api/v1/search?indexerIds=99999` 回 400「all selected indexers being unavailable」。
  所以流程是「測試 → 勾通過的 → 加入 → 逐站 / 全部試搜 → 不要的移除」。
- schema 645 個定義，public 88 個；其中 NZBIndex 是 usenet、`Torrent RSS Feed` 的 `definitionName` 出現兩次
  （showRSS 是它的 preset）。公開站清單只收 `protocol == torrent`、依 `definitionName` 去重。

## 拍板（使用者）

1. **結果逐列行內**：每一站一列，狀態塊（未測 / 測試中 / 通過 / 沒通過 + 理由）、勾選、「測試」；試搜的筆數與
   前三筆也長在那一列。左欄剖面只放總數。
2. **推薦在上、其他公開站用搜尋叫出來**：九個推薦站永遠列著；下面「其他公開站（N）」一個名稱欄加一個語言下拉，
   有輸入或選了語言才列出符合的站，同樣一列一顆「測試」。
3. **「已加入」一段在上、「加站」在下**：已加入列出 Prowlarr 裡的每一站（含使用者在 Prowlarr 自己加的；那些沒有
   移除鈕），段頭一個關鍵字欄 +「搜尋全部」，每列一顆「搜尋」。加站只列還沒加的。既有 Prowlarr 只有已加入那一段、
   沒有移除；既有 Torznab 整個端點算一站。

## 版面（套件內，工作面由上而下）

- h2、lede（跟著來源：還沒選 / 套件內 / 既有，確認之前跟著草稿）、`ServiceChoice`、回頭看的說明。
- **已加入（N）**：關鍵字欄 +「搜尋全部」（次要鈕）；列：名稱、語言、「搜尋」、結果（筆數塊 + 前三筆；失敗是理由
  一句 + 原文 `<details>`）、移除（`ConfirmAction`，只有 Berth 加得回去的站：推薦清單或公開定義）。沒有站時不畫這一段。
- **加站**：「推薦的站」+「測試全部」（測這一段裡還沒測過或沒通過的）；「其他公開站（N）」名稱欄與語言下拉；
  一列：勾選（通過才勾得起來，沒勾得起來時 hint 說「先測試」）、名稱、語言、說明、狀態塊、「測試」。
- **沒通過的摘要**：加站段上方一條，`assigned` 色塊「N 站沒通過」+ 各理由的站數；整段只有這一個 `aria-live`。
  每一列的「沒通過」是中性色塊 + i18n 理由（Cloudflare 擋住 / 查無結果 / 連不上 / 其他），Prowlarr 原文收進
  `<details>`。紅色不用：沒通過的站不擋這一頁。
- 介面登入（票 07 的欄位）→ 主鈕「加入 N 站」（N = 勾著、還沒加的）；一站都沒勾而登入還沒設時是「設定介面登入」。
  「之後再說」在旁邊。
- 私有 / 半私有站：加站段尾一句「要帳號的站在 Prowlarr 自己的介面加，加完 Berth 就認得」+ 連結。連結是使用者
  主機上的位址：套件內＝瀏覽器現在的主機名 + `PROWLARR_PORT`（compose 傳給 Berth，同 Jellyfin 深連結）；既有＝
  使用者填的位址，`host.docker.internal` 換成瀏覽器的主機名，compose 主機名（`prowlarr`）給不出就拿掉。
- 剖面：接上哪一種、位址、API key、已加入幾站。

## 狀態

- 進頁與設定頁的索引站分頁：只讀（`GET /setup/indexers`），不送測試、不送寫入。
- 測試：`POST /setup/indexers/test`（`read` 命令，不寫 Prowlarr 也不寫 Berth）；結果留在前端，換頁就要重測。
  加入時 Prowlarr 自己會再連一次，所以勾著的站仍可能加不進去：那一站回到「沒通過」、理由同一套。
  **加入的結論存在後端**（上一次 apply 的逐站步驟，`checks`）：回頭看時加不進去的那幾站仍說得出為什麼
  （實作時補上；純前端的測試結果照舊換頁就沒了）。
- 試搜：`GET /setup/indexers/search?query=&indexer_id=`（不帶 id 是全部）。
- 移除：就地確認；最後一站也移除時這一頁回到未完成（照舊）。

## 換另一格的確認（`ServiceChoice`，頁 1、2、4 與設定頁共用）

- 點選（指標）照舊：第一次點「套件內」立即存下並測。**方向鍵 / 空白鍵只改草稿**，草稿是套件內時給一顆
  「使用套件內的 X」確認鈕；不送 `POST /setup/services/{kind}`。方向鍵瀏覽開的確認不搬焦點（搬走就走不回另一格），
  所以 radio 上的 `Esc` 也收得起確認（實作時補上，DESIGN.md 記為 The Focus Follows The Confirm Rule 的例外）。
- 這一頁已有結果時換另一格：`ConfirmPanel`（`role=group`、焦點移進去、`Esc` 收起並回到原本那一格）；
  套件內是確認 / 取消兩顆，既有是警告 + 表單 + 取消。
- 標題與 lede 在確認之前就跟著草稿（頁面從 `ChoiceControls.draft` 讀）。
- `switchWarning` 依原本的來源分兩種：從套件內換走說「Berth 寫進那一台的…留在那裡」；從既有換走只說這一頁要重做
  （Berth 沒寫過使用者那一台）。
