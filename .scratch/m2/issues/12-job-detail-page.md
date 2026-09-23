# 12 — `/jobs/:hash` Job 詳情頁

**Status:** done

**Blocked by:** 04（動作區的刪除範圍對話框）

**讀:** plan §7（`/jobs/:hash` 那一條與路由清單）、§6（jobs 群組）、§11.3 的決定 1；brief §13（頁面清單）

## 做什麼

**另建一頁**（決定 1）。M1 票 09 拍板不建，M2 建：刪除範圍是要二次確認的破壞性動作，塞在列表的
展開區說不清楚「哪一筆正在被刪」。

**這一頁有**：時間線、檔案清單與各檔決策、Plan 歷史、動作（重新解析、重新入庫、刪除範圍）。

**`/jobs` 的展開區同時瘦身**：只留狀態與時間線摘要，Plan 表格只在詳情頁。這是同一張票的兩半——
不瘦身的話兩個地方各畫一份 Plan，下一輪就會各長各的。

**刪除對話框是票 04 的那一個元件**，不是第二份實作。

**新頁面，先 `/impeccable shape`。** 票 07 的 Plan 表格已經是最密的畫面，這一頁的 Plan 歷史是
它的唯讀版——shape 時說清楚兩者的關係（能不能共用、不共用的理由）。

## 驗收

- [x] `/jobs/:hash` 有時間線、檔案清單與各檔決策、Plan 歷史、三個動作
- [x] `/jobs` 的展開區只剩狀態與時間線摘要；Plan 表格在那裡沒有第二份實作（grep 佐證）
- [x] 刪除對話框是票 04 的元件（同一個 import，不是複製）
- [x] 深連結進得來（從 `/jobs` 的一列、從 `/review` 的一列、從貼網址），不存在的 hash 有像樣的
      空狀態
- [x] `user` 登入時進得來（他看得到自己的 job），但刪除與重新入庫的入口看不到、後端也 403
- [x] `/impeccable shape` 產出留在 `.scratch/m2/`；390px 窄版可用
- [x] playwright 實跑一次：從 `/jobs` 進詳情頁、看 Plan 歷史、開刪除對話框（不真的刪），
      附截圖或文字結果
- [x] lint、type、test 綠燈

## 做完之後的樣子

**前端**：`pages/JobDetailPage.tsx`（新頁）、`jobs/JobActions.tsx`（重新規劃 / 重試 / 重新入庫 / 刪除，只住在詳情頁）、
`jobs/JobFacts.tsx`（列與身分帶共用的實測值那一行）、`jobs/JobLink.tsx`（`/review` 四類與 `/issues` 的所屬下載）、
`jobs/eventTypes.ts`（`EVENT_TYPES` 從 `JobTimeline.tsx` 搬出來，加上 `planHistory`）、`api/jobs.ts` 的 `jobQueryOptions`。
`JobTimeline` 多一個 `latest`（`/jobs` 展開區只畫最近三段、說出較早的幾筆）。`planQueryOptions` 的 `enabled` 參數拿掉
（唯一傳 `open` 的 `JobRow` 不再問計劃）。**後端**沒有改程式碼，只在 `test_jobs_api.py` 補一條 `user` 讀得到
`GET /jobs/{hash}` 的斷言。shape：`.scratch/m2/job-detail-shape.md`（使用者拍板三題）。

**grep 佐證**（第 2、3 條驗收）：`import { JobPlan }` 只有 `pages/JobDetailPage.tsx`（與它自己的測試）；
`import { JobDelete }` 只有 `jobs/JobActions.tsx` 與 `media/FilesPanel.tsx`（與它自己的測試），`export function JobDelete`
只有一處。

**實跑**（fake server `--scenario review`，playwright）：以 `skipper` 從 `/jobs` 展開 `S01E03 + OVA` 那一列——展開區只有
時間線摘要、hash 與「下載詳情」，沒有計劃也沒有按鈕——點進 `/jobs/8f403d0e…`：身分帶、重新入庫與刪除、左欄「檔案與決策」
（對不到 1、略過 1 兩組）與「計劃歷史」（計劃、略過重複兩筆）、右欄完整時間線。按「刪除」確認區就地展開在身分帶正下方，
四格全不勾、估算回「媒體庫 0 個鏈接 · 下載目錄 2 個檔案 · 不會空出空間」；**沒有按確認**。390px：單欄，
`scrollWidth` = `clientWidth`，確認區完整。`deckhand` 經 `/login?redirect=/jobs/7e3f…` 進得來：「等管理員審核」、
重新規劃在、刪除與重新入庫不在；同一個 session 直接打後端：`DELETE` 403、`POST …/reimport` 403、`GET …/deletion` 403、
`GET /jobs/{hash}` 200。不存在的 hash：「找不到這筆下載」＋回下載列表。`/review` 展開各列，所屬下載全部指到
`/jobs/<hash>`，點 26-27 那一條進得到詳情頁（種子資料沒有事件，三個空狀態各自說得出話）。
截圖：`.playwright-mcp/job-detail-1280.png`、`job-detail-delete.png`、`job-detail-390.png`、`job-detail-from-review.png`。

**實跑抓到、當場修掉的兩條**：①不存在的 hash 卡在「讀取中」七秒——正式的 QueryClient 預設重試三次（測試裡關掉了，
所以單元測試看不到）；`jobQueryOptions` 改成後端回了狀態碼就不重試（`api/jobs.test.ts`）。②`unknown_torrent` 的
「所屬下載」放的是 torrent 自己的 hash，定義上沒有 Job，連過去一定是空狀態；那一種照舊只印字（`IssuesPage.test.tsx`）。

**變異驗證**：把 `JobDelete` 放回 `JobRow`、把時間線摘要改回完整一份 → `JobsPage.test.tsx` 兩條轉紅，還原後綠。

## Comments

`/code-review` 兩軸，逐條處理：

**Standards（沒有硬性違規，五條判斷題）**

1. `planQueryOptions` 的 `enabled` 消費點只剩 `true` —— 修掉（參數與過時的註解一起拿掉）。
2. 底線連結的 className 在 `JobDetailPage` 的 `INLINE_LINK` 與 `JobLink` 各一份（repo 裡另有四處）—— **沒改**：
   抽成 `controls` 常數要動四個不屬於這張票的檔案，留給票 13（前端品質）。
3. `JobDetailPage` 的 `Fact` 重做了 `QueueRow` 的 `DetailLine` —— 修掉，改用 `DetailLine`。
4. 時間線「讀取中 / 讀不到 / 內容」三分支在詳情頁出現兩次、`JobRow` 一次 —— **沒改**：三處各自的空狀態不同，
   抽出來要多一個參數，不比現在短。
5. `planHistory` 的測試放在 `JobTimeline.test.tsx` —— 修掉，搬到 `jobs/eventTypes.test.ts`。

**Spec**

1. 刪除之後（勾 / 不勾清除紀錄）詳情頁的行為沒有測試 —— 補兩條：勾了是「找不到這筆下載」，沒勾是留在頁上、狀態「已刪除」。
2. 測試註解說後端 403 在 `test_reimport.py` —— 改指 `test_jobs_api.py` 的 `TestDelete` / `TestReimport` 與
   `test_auth_api.py`；並補一條後端斷言 `user` 讀得到 `GET /jobs/{hash}`（詳情頁靠它，原本沒有閘門）。
3. `user` 測試沒斷言重試與重新規劃還在 —— 補上。
4. shape 的「沒有 Plan 時不畫計劃歷史」與「誰送的在實測值那一行」跟實作不同 —— shape 改成實作的樣子並說明理由。
5. 重新入庫在時間線上是 `retried`（`action: reimport`），不在九種 Plan 事件裡：計劃歷史只看得到後面那一筆
   `plan_generated`。拍板時接受的範圍，**沒改**。

**與這張票無關的觀察**：後端全套跑第一次時 `test_reconcile_checks.py::TestInodeMismatch::test_twice_is_still_one`
紅了一次，log 是 guessit / rebulk 內部的 `TypeError: 'ABCMeta' object does not support the context manager protocol`
（`services/jobs.py` 背景一輪裡的 `parse_release`）。單獨重跑三次都綠、整套重跑也綠（2213 passed）。沒有穩定 repro，沒修。
