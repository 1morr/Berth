# 125 — 每人的通知設定；「可以看了」照媒體庫權限送、同作品合併

**Status:** ready-for-agent

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

- [ ] `user` 角色看不到那個媒體庫時不收；看得到時收（pytest，Fake Jellyfin 的 `UserViews`）
- [ ] 同一部作品 5 分鐘內兩筆 Job → 一則，季集範圍合起來；超過 5 分鐘是兩則（pytest）
- [ ] 沒勾「可以看了」、沒填 Discord ID 的人不收（pytest）
- [ ] `UserViews` 讀不到時延後而不是送出或丟掉（pytest）
- [ ] 一般使用者看得到自己的通知設定、看不到 bot token 那一半（vitest；playwright 以 `user` 登入實跑附截圖）
- [ ] 全部檢查、pytest、vitest 綠；CHANGELOG、progress.md 已更新
