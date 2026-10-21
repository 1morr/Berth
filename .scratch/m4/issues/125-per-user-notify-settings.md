# 125 — 每人的通知設定；「可以看了」照媒體庫權限送、同作品合併

**Status:** done

**Blocked by:** 123

**讀:** plan §11.5〈通知〉的「種類與收件人」；brief §11（帳號與權限）、§12；M1.5 票 01（受限使用者的權限實測）；`berth/services/jellyfin_access.py`（`UserViews` 的允許清單）；`berth/adapters/jellyfin/client.py` 的 `user_views`；票 123 的通知設定頁與 shape

## 為什麼

票 123 只送管理員。通知是每個人的：一般使用者也要收「可以看了」，而且只收得到自己在 Jellyfin 看得到的媒體庫——M1.5 做了受限使用者，通知不能從旁邊把作品名漏給他。一次入庫一整季時，同一部作品也不該一集一則。

## 做什麼

1. 通知設定頁對每位登入的使用者（含 `user` 角色）開放「我的通知」：自己的 Discord ID、要收哪些種類（`user`：可以看了、正在下載；管理員另有等你處理、週報）、測試按鈕。bot token 那一半照舊只有管理員看得到。
2. 收件人規則：訂閱了這個種類、有 Discord ID、而且 Jellyfin `UserViews` 看得到那筆 Job 的媒體庫。`UserViews` 讀不到時（Jellyfin 掛了）這一則延後，不猜。
3. **合併**：寫入時設「最早送出時間」為 5 分鐘後；同一個收件人、同一部作品、還沒送出的那一則存在時，把新的併進去（季集範圍合起來）而不是新增一列。送出迴圈只送時間已到的。
4. 新增的種類先只有「可以看了」接上；「正在下載」的勾選在票 126 才有作用（這張先存設定）。

## 驗收

- [x] `user` 角色看不到那個媒體庫時不收；看得到時收（pytest，Fake Jellyfin 的 `UserViews`）
- [x] 同一部作品 5 分鐘內兩筆 Job → 一則，季集範圍合起來；超過 5 分鐘是兩則（pytest）
- [x] 沒勾「可以看了」、沒填 Discord ID 的人不收（pytest）
- [x] `UserViews` 讀不到時延後而不是送出或丟掉（pytest）
- [x] 一般使用者看得到自己的通知設定、看不到 bot token 那一半（vitest；playwright 以 `user` 登入實跑附截圖）
- [x] 全部檢查、pytest、vitest 綠；CHANGELOG、progress.md 已更新

## Comments

- 2026-10-22 實作（session 紀錄見 progress.md）。截圖在本票目錄（演練後端 `healthy`，以 `deckhand`（`user`）登入，1280 / 390 各兩張：`crew-1-empty-*`、`crew-2-delivered-*`）。
- **可見性在送出時問、合併在寫入時做**：`queue_ready` 在 resolver 的寫交易裡，不能打網路，所以只看訂閱與 Discord ID；`send_due` 對每位收件人問 `Users/{id}` 與 `UserViews`（`jellyfin_access.visible_libraries`，從 `_grant` 抽出的 `_views`，不動 session）。看不到、帳號停用或刪掉的那一則放棄（`error` 以 `withheld:` 開頭）；Jellyfin 問不到的留著，一輪遇到問不到就停，滿 24 小時照 `GIVE_UP_AFTER` 放棄。
- **API 拆兩半**：「我的」那一半從 `/settings/notifications/me`、`/test` 搬到 `/me/notifications`（`GET|PUT`、`POST /test`，登入就行）；`/settings/notifications` 只剩 bot 與 Berth 的網址，門禁表照舊 ADMIN。`set_bot_token`、`set_berth_url` 不再收 `user_id`（票 123 Comments 那一條）。前端一般使用者的「設定」入口通到通知頁（沒有分頁列）；慣例照 Overseerr：每個人的通知在自己的設定裡，管道設定在管理員那邊。
- code-review 已改：
  - resolver 的 `moment` 在問 Jellyfin 之前取，拿它判斷合併會併進送出迴圈剛撿走的那一則（新的季集跟著舊內容被標成已送）。`_announce` 改收 `ready_at`（`now or utcnow()`，在問完之後取），合併再留 `_MERGE_GUARD` 30 秒：離送出不到 30 秒的不併、另起一則（測試 `test_a_message_about_to_be_sent_is_not_merged_into`，拿掉 guard 會紅，已實測）。
  - i18n key 與頁面裡的 `crew*` 改 `user*`（CONTEXT.md 沒有 crew）；測試裡的 `CREW` 是既有慣例（`test_inventory_api` 等），沒改。
  - `_cleared`（回 bool 卻改狀態）改名 `_withheld`。
- code-review 未處理（決定或歸屬）：
  - **管理員另有的「等你處理」「週報」沒有勾選**：那兩種種類本身是票 127、131 加的，現在勾了也沒有東西送；它們加種類時順手加勾選，只給管理員。
  - **只併還在合併時間裡的那一則**：已到時間、因 Discord 退避或 Jellyfin 問不到而延後的那一則不再併，長時間故障時同一部作品每 5 分鐘一則。要併得先讓送出迴圈「撿走」的那一則與「還在等」的分得開（多一個狀態），留給里程碑收尾看要不要。
  - **訂閱只在寫入時看**：5 分鐘內取消訂閱，那一則照送；清掉 Discord ID 的那一則停在 pending 到 24 小時放棄。
  - **升級之前排著的「可以看了」沒有 `library`**，送出時當成看不到而放棄。待送表從票 123 才有，還沒進任何 release，所以不做資料 migration。
  - `_libraries_of` 回的 `(dict, str)` 用「不在 dict 裡」表示沒問到，可以換成小型別；`read_bot` / `read_mine` 各算一次 bot 有沒有設定；頁面把 `admin` 往下傳四層挑補法。都小，沒改。
