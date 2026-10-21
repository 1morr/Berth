# 121b — 前端 e2e `rss-subscribe`：acg.rip 第一輪預覽時而多出「重複 2」

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（排在 124 之前；跟 123 並行，123 不碰 RSS）

**讀:** 票 13b（同一條 spec 上一次的修法與 Comments）；`web/e2e/rss-subscribe.spec.ts`；plan §6 rss（預覽、重複的判定）；
progress.md 2026-09-27 票 13b 那一行

## 為什麼

`web/e2e/rss-subscribe.spec.ts:42`（1280 那份）第二次紅在同一個斷言，兩次都在跟 RSS 無關的 commit 上：

- 2026-10-13 CI run 38405255701（`d07daa3`，只改文件）
- 2026-10-21 CI run 39556789559（`718e2a7`，合併票 121：只有文件、fixture 與實驗腳本）

預期 `會送出 30 · 綁定之後送 0`，實際 `會送出 28 · 綁定之後送 0 · 排除 0 · 重複 2`。同一輪的 `rss-subscribe-390` 是綠的。
這跟 13b 的逾時不是同一種失敗：預覽有回來，只是兩筆被算成重複。前面一步剛從作品頁訂閱了 Mikan 的
LoliHouse（送出 12 集），acg.rip 搜尋 feed 裡也有 `[喵萌奶茶屋&LoliHouse]` 的條目，懷疑重複的判定取決於
前一步的送出有沒有在預覽之前落地。這只是線索，還沒有 repro。

## 做什麼

先分清楚是**產品的問題**（同樣的操作，使用者看到的「重複」數會隨時序變，代表判定本身不穩）還是 **spec 的問題**
（spec 假設的時序或測試資料不對；例如那兩筆照規則本來就該算重複，30 才是錯的期待）。前者修產品，後者修 spec
並說明為什麼原本的期待不對。不接受只拉長逾時、加 retry 或放寬斷言而說不出原因。

## 驗收條件

- [ ] 原因寫進票的 Comments：哪兩筆被算成重複、跟誰重複、為什麼有時算有時不算，附證據（log、trace 或計時）
- [ ] 有一條會紅的 repro：產品的問題就是後端整合測試（修好轉綠）；spec 的問題就是能穩定重現兩種結果的步驟
- [ ] `rss-subscribe` 與 `rss-subscribe-390` 在整套前端 e2e 裡連跑三次都綠
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 有 session 紀錄
