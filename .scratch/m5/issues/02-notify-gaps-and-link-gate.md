# 02 — 通知的兩個缺口與連結閘門

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** plan §11.5〈M5 開工前的審查補記〉「排進 M5 開頭」、§7；M4 票 124、126 的 Comments；`services/downloading` 的 docstring（`download_round`、`presser`）；後端 `deeplink.MEDIA_PAGE` 與前端的路由表

## 為什麼

M4 收尾審查留下三條沒人接手的：

- 放行、全部下載、改 Route 時傳下去的 `presser`（「誰按的」，那個人不收自己按的「正在下載」）沒有測試：API 那一層拿掉 `user_id=` 也不會紅（票 126）。
- 關機時被取消的那一輪，已經送出的 Job 沒有「正在下載」那一則（票 126）。
- 通知連結的作品頁路徑（後端 `/media/{media_id}`）與前端路由 `/media/$mediaId` 只靠註解綁著，前端改路由時連結靜靜變成 404（票 124）。M5 的結果卡與 M7 的 Discord embed 會連回更多頁面，先補這道門。

## 做什麼

1. **`presser`**：放行、全部下載、改 Route 三條路各一條測試，按的人收不到、其他訂閱者收得到；拿掉 API 那一層的 `user_id=` 會紅。
2. **被取消的那一輪**：先寫出 repro（一輪送出兩筆之後被 `CancelledError` 打斷，看不到「正在下載」），再讓已送出的照樣排進待送表。取消時的寫入不能拖住關機——照 `test_loop_shutdown` 的取向，排不進去只記 log。
3. **連結閘門**：讓前後端讀同一份事實，或讓一邊的測試讀另一邊的定義（例如前端測試從後端匯出的路徑模板對照路由表）。挑最不需要新機制的做法，理由寫進票。後端其他組前端網址的地方（Job、Issue、清單頁的錨點）一起納入。

## 驗收

- [ ] 三條路的 `presser` 各有測試，拿掉傳遞會紅（pytest）
- [ ] 被取消的一輪：改之前 repro 紅、改之後已送出的有「正在下載」（pytest）
- [ ] 前端路由與後端連結模板不一致時紅、改無關路由不紅（雙向變異）
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新
