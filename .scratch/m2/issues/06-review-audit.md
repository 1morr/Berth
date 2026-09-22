# 06 — Review Queue ⅓：佇列骨架 + audit 確認 / 撤銷

**Status:** ready-for-agent

**Blocked by:** 04（撤銷走 `delete_job` 的 `unlink` 旗標、admin 門禁）、05（`issue` 那一類的列要有 `issues` 表才畫得出來）

**讀:** plan §6（review 群組、plans 群組）、§7（路由與元件那兩條）、§11.3 的決定 6 與 7；brief §6.5（信心與門檻）、§11、§13

## 做什麼

M2 驗收第三條（「medium 自動入庫的檔案可在佇列中一鍵撤銷」）本身就是一條 tracer bullet：
它端到端穿過 `GET /review`、`/review` 頁、confirm / undo 與票 04 的刪除原語，而且不需要
Plan 的逐列編輯。所以佇列的骨架跟著它一起立。

**`GET /review` 是一支端點、一份清單、一列一件事**（決定 6）。每一列帶 `kind`
（`plan` / `audit` / `unmatched` / `duplicate` / `issue`）、指向它的物件（plan id / ledger id /
issue id）、**一句封閉集合的理由**與這一列能按的動作。排序是「需要人動手的排前面」
（`plan` 與 `unmatched` 先、`audit` 與 `duplicate` 次、`issue` 最後），同類之內舊的在前。
**不分頁**——超過 200 列時回前 200 並帶 `total`，那時候該修的是上游而不是分頁。

這一票的清單裡**只會出現 `audit` 與 `issue` 兩類**（其餘三類在票 07、08），但端點與元件一開始
就照五類的形狀做，後面兩票只是把列填進去。`issue` 那一類的動作**就地按**（打 `POST
/issues/{id}/resolve`），不跳頁。

**動作**：`POST /review/audit/{ledger_id}/confirm`（清掉 `ledger.audit` 與對應 `plan_items.audit`，
寫 event `audit_confirmed`）、`POST /review/audit/{ledger_id}/undo`（走 `delete_job` 的 `unlink`
旗標刪掉硬鏈接、帳本那一列刪掉、Job 回 `review` 並帶 `review_reason = audit_undone`，寫 event）。

**`/review` 是新頁面，先 `/impeccable shape`**。這個 shape 要一次涵蓋：五類列的共同骨架、
「需要人動手的排前面」怎麼看得出來、動作按鈕的位置與破壞性動作的確認。票 14 的媒體庫
「待審 / 對不到」清單用的是同一個元件，shape 時一併定（那一頁只放 `plan` 與 `unmatched` 兩類的
子集）。

**門禁**：`review/*` 整組 admin（決定 7）。`user` 送單之後碰到低信心 Plan 只能等，
**畫面上要說得出「等管理員審核」**——那句話在 `user` 看得到的地方（Media 詳情、`/jobs`），
不在 `/review`。

## 驗收

- [ ] `/impeccable shape` 的產出留在 `.scratch/m2/review-shape.md`，涵蓋五類列與媒體庫那一份子集
- [ ] `GET /review` 一支端點回兩類的列，排序照「需要人動手的排前面、同類舊的在前」；超過 200
      列時回前 200 並帶 `total`（測試造 201 列）
- [ ] 每一列的理由是封閉集合的 code + 參數，不是後端拼好的句子（前端翻譯，zh-Hant 與 en 並列）
- [ ] medium 自動入庫的一筆：佇列上看得到 → 按確認之後從佇列消失、`ledger.audit` 清掉、
      時間線有 `audit_confirmed`
- [ ] 同一筆改按撤銷：硬鏈接沒了、帳本那一列沒了、Job 回 `review` 且 `review_reason = audit_undone`、
      時間線寫得出來（整合測試走完整條）
- [ ] `issue` 那一類就地按得動作，按完那一列從佇列消失，不跳頁
- [ ] `user` 登入時 `/review/*` 全是 403，前端看不到入口；`user` 的 Media 詳情與 `/jobs` 上
      低信心的那一筆說得出「等管理員審核」
- [ ] playwright 實跑確認與撤銷各一次，附截圖或文字結果
- [ ] lint、type、test 綠燈

## Comments
