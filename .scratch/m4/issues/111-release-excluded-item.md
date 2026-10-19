# 111 — 被排除的 Feed Item 可以「仍然下載」

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** brief §15「全部接受，只排除」「處理」、§14（命令標記）；plan §3.2（`rss_poller`）、§6 rss；`berth/services/rss.py` 的 `_screen`、`_rescreen`、`_submit`、`_submit_waiting`；`web/src/rss/ItemLine.tsx`、`web/src/rss/skip.ts`

## 為什麼

使用者 2026-10-19：從作品頁訂閱一個 Mikan 番組 × 字幕組，那條單一 feed 只有一筆 `[01-12 合集]`，被全域的「不自動下載合集」擋成 `excluded`。取消勾選再輪詢也回不來——排除條件只往前看（放寬不放回），輪詢又以 `(feed_id, guid)` 去重。現在只能放寬全域開關、再到一次性連結手動送，例外沒有一個地方可以放。

參考 Sonarr：互動搜尋列出被 profile 擋下的 release 與理由，仍可逐筆「照樣下載」。逐筆、人按的放行不違反 brief §15「拿掉一條規則不該讓幾個月前被它擋下的一次全部下載」——那一條防的是批次放回。

## 做什麼

1. **後端命令**（`mattpocock-skills:tdd`）：`services/rss` 加一支放行一筆 `excluded` Item 的命令，**當場送出**，走與 `_submit_waiting` 同一支 `_submit`（`trigger = rss`、帶 RSS Series id），所以第一批審核、送單時的去重（同一個 torrent、帳本已有 → `duplicate`）照常。
   - 只放行「RSS Series 已綁定、Feed 已選過第一輪（`primed_at` 不是空的）」的 Item；其他回拒絕（各自一種 `RssRefusal`：不是 `excluded`、還沒綁定、還在預覽）。
   - **送不出就留在 `excluded`**（Route 紅燈、磁碟門檻這些），回送單那一頭的理由。不放回 `matched` 等下一輪：下次改規則時 `_rescreen` 會把它重新排除，也不另加「人放行過」的欄位。
   - 命令標記照 brief §14：它會開 Job，比照 `subscribe_mikan` 的標法；沒有單一反向命令的理由寫在 docstring。
2. **API**：`POST /rss/items/{item_id}/release`（名字可依現有端點慣例調整），回這一筆的新狀態；拒絕走 `RssRefusalOut`。
3. **前端**：`ItemLine` 對 `excluded` 的列加「仍然下載」——「最近的 Feed Item」與 RSS Series 展開的清單兩處都有。不能放行時按鈕停用並說為什麼（還沒綁定、還在預覽）；送出後那一列換成送出去的 Job（或 `duplicate` 的理由）；被拒時就地說原因。i18n zh-Hant、en 並列。
4. **文件**：brief §15 補一句「逐筆放行」與它和「只往前看」的關係；plan §6 rss 加端點；CHANGELOG；progress.md session 紀錄。

## 不做

- 整批放行、依規則放行。
- 放行 `duplicate`。
- 還沒綁定或還在預覽的 Item 先放行、之後再送（要多一個欄位，2026-10-19 使用者確認不做）。

## 驗收

- [ ] 已綁定、已選過第一輪的 `excluded` Item 放行後送出成 Job（`trigger = rss`、帶 Series id），Item 變 `downloaded`（pytest）
- [ ] 同一個 torrent 已送過時放行得到 `duplicate`，不重送（pytest）
- [ ] 還沒綁定、還在預覽、不是 `excluded` 各回各的拒絕，Item 不變（pytest，各做變異驗證）
- [ ] 送單被拒時 Item 留在 `excluded`、回送單的理由（pytest）
- [ ] 兩處清單都看得到按鈕；停用時說原因；送出後列換成 Job（vitest，zh-Hant 與 en）
- [ ] playwright 實跑放行一筆合集，附截圖（1280 與 390）
- [ ] 全部檢查、pytest、vitest 綠；brief、plan、CHANGELOG、progress.md 已更新

## Comments
