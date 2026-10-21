# 127 — 「有 N 件等你處理」（含 Issue 新增）

**Status:** done

**Blocked by:** 122、123、124

**讀:** plan §11.5〈通知〉（「Issue 新增」已併進這一則）；brief §19 2026-10-21 兩條；`berth/services/review.py` 的 `review_total`；`berth/services/issues.py` 的 `count_open`；`berth/services/rss.py` 待綁定的計數（`_awaiting_*` 一帶）；前端審核、Issue、RSS 頁各自的網址（一件時要連到那一件）

## 為什麼

Berth 平常不必打開的前提是「有事需要人的時候它會說」（plan §11.5）。待審核、Issue、待綁定的 RSS Series 是三個要人動手的地方。

## 做什麼

1. 有新的一件出現（進審核、Issue 開或重開、RSS Series 變待綁定）時，給有 Discord ID、訂閱了的管理員排一則，最早送出時間 10 分鐘後；期間再有新的併進同一則。
2. 送出時重算：說出這一波新增了什麼（種類與數量，例如「新增 3 件：1 個 Issue（找不到檔案）、2 件待審核」）與現在的總數；送出前都已處理掉、總數是 0 就不送。
3. 連結（票 124）：這一波只有一件時連到那一件，多件連到對應的清單；沒設網址時不附。
4. 「Issue 新增」不另外送。被忽略、條件仍在的 Issue 不算新增（票 122）。

## 驗收

- [x] 10 分鐘內三件（各一種）→ 一則，列出種類與數量與總數（pytest）
- [x] 只有一件時，三種各自連到那一件的網址（pytest）
- [x] 送出前已處理掉、總數 0 → 不送（pytest）
- [x] 被忽略的 Issue 隔天對帳不觸發（pytest，依票 122）
- [x] `user` 角色不收（pytest）
- [x] 全部檢查、pytest 綠；CHANGELOG、progress.md 已更新

## Comments

- 2026-10-22 實作（session 紀錄見 progress.md）。截圖在本票目錄（演練後端 `issues` 情境：`issues-hash.png` 是 `/issues#issue-3` 載入後焦點落在那一列，`notify-admin.png` 是管理員看得到「有 N 件等你處理」的勾選）。
- **看清單，不掛寫入點**：送出迴圈每一輪先跑 `notify.watch_waiting`，`services/waiting.waiting_now` 照三份清單取「現在有誰」，與上一輪（`settings.notify_waiting`）比；新出現的寫進那位管理員還在 10 分鐘合併時間裡的那一則。送出時（`send_due`）再取一次重算。理由與其餘決定見 progress.md「偏差與決定」同日五條（其中兩條由使用者在 code-review 後拍板）。
- **連結**：單件時連到清單頁那一列的錨點（`/review#audit-12`、`/issues#issue-5`、`/rss#series-7`），前端 `useHashTarget` 在資料載入後捲過去、焦點放上去，目標在收著的 `<details>`（一組 audit）裡時先攤開；多件時每一種一條清單連結。`Message.link` 改 `links`（Discord 寫在內文最後一行、以 ` · ` 隔開，仍不放 embed `url`）。
- code-review 已改：
  - 被忽略之後條件解除過（`cleared_at`）、再發生的 Issue 原本也被當成「條件仍在」壓掉不推（Spec 軸）。改由 `issues.still_ignored` 判斷，並且只拿這一輪剛出現的去問（Standards 軸：原本每 10 秒對全部 Issue 歷史跑一次 correlated subquery）。測試 `test_an_ignored_issue_whose_condition_cleared_and_came_back_is_new`。
  - 看守原本自己 commit 兩次，關機時 cancel 落在中間會漏一條連線（`test_loop_shutdown` 的 `NotifySender-2` 紅）。改成不 commit、與 `send_due` 開頭那一次一起落地。
  - `"new"` 魔術字串改 `_NEW`；照清單拼的文案 key 補完整性測試（`test_every_list_has_its_sentences`）。
- code-review 未處理（決定或歸屬）：
  - **審核佇列超過 `QUEUE_LIMIT`（200）列時**，排在後面那一件的錨點在頁面上找不到，連過去只停在清單頂端。佇列塞到 200 列時該修的是上游（`review.py` 檔頭的立場），沒改。
  - **一般使用者之後升成管理員**不會自動補上「等你處理」：預設照第一次登入時的角色給，升級之後勾選出現、要自己勾。沒有失效報告，先不做。
  - 錨點形狀（`audit-12`、`issue-5`、`series-7`）在後端 `waiting.py` 與前端四個元件各寫一次，沒有跨前後端的閘門；前端 `ADMIN_ONLY_KINDS` 也是寫死的一份（後端照樣剝掉，前端漏了只是多顯示一格）。`_ISSUE_LABEL` 與前端 `issues.typeLabel` 是同一組詞，測試只守齊全、不比對一致。
  - 後端單件連結只對 `audit` 有 pytest；`plan`、`unmatched`、`duplicate` 的錨點是同一個 `f"{kind}-{id}"`，`duplicate` 由前端 vitest 守。
  - Plan 一個 Job 一份、重新規劃沿用 `plan_id`：同一波裡處理掉又回到審核的那一件，送出時仍算「還在」。邊角，沒改。
