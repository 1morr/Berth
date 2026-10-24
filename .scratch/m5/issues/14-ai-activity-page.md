# 14 — AI 活動頁

**Status:** done

**Blocked by:** 11、12

**讀:** plan §11.6〈AI 活動頁〉；brief §6.10「外部文字是資料」⑤、§14；CONTEXT.md 的 AI Activity；票 05 定下的 actor 格式

## 為什麼

AI 做過的每一個寫入都要有地方看、能撤銷，這是可逆動作直接執行的前提。M6 的背景接管也寫到同一頁。

## 做什麼

1. 先 `/impeccable shape`，輸出 `.scratch/m5/ai-activity-shape.md`。
2. 列出 AI 執行過的每一個寫入命令與確認過的 Proposal：何時、代誰、哪個工具、輸入摘要、AI 給的理由、這一輪的 tokens、出自哪則對話（連得回去）。資料從票 05 的 actor 撈，不另寫一份日誌；撈不出來就回頭補 actor，而不是新開表。
3. 逐筆撤銷：有反向命令的按得到，已經撤銷過的或沒有反向命令的說明為什麼不行。
4. 管理員看全部，`user` 只看自己對話裡的。

## 驗收

- [x] 票 11、12 的寫入都出現在這頁，撤銷後狀態正確（整合測試）
- [x] `user` 看不到別人的（pytest）
- [x] 實跑截圖（playwright）
- [x] 全部檢查、pytest、vitest 綠；DESIGN.md、progress.md 已更新

## Comments

2026-10-24 實作（`/implement`）。shape 在 `.scratch/m5/ai-activity-shape.md`，使用者答的四題記在 brief §19。

- **資料從對話撈，不從 actor 撈**：`events.actor` 的 `ai:<user id>` 只掛在 Job 的事件上，訂閱、加索引站沒有，也說不出工具、理由與對話；
  對話存下的工具結果、`proposals` 與 `UndonePart` 本來就是 AI 做過什麼的紀錄。照票「不另寫一份日誌、不新開表」的意思，補在既有的記錄上：
  寫入工具的輸入一律帶 `reason`（`WriteInput`，原 `ProposalInput`）、`ai_calls.message_id`（migration `5e1a7c3d9b20`）。
- **migration 不用 batch**：第一版用 `batch_alter_table` 加外鍵欄，整套 pytest 一起跑時 `test_downgrading_then_upgrading_lands_on_the_same_schema`
  紅（只在跟其他測試同一個程序時）。重建表時兩條既有外鍵的順序取自 set，降回 base 再升上來的 DDL 字面對不上。改用 SQLite 原生
  `ADD COLUMN … REFERENCES` 與 `DROP COLUMN`，同 `a6c3e9f2b815` 的做法。
- **截圖**（`web/e2e/ai-activity.spec.ts`，`assistant` 情境）：本目錄 `activity-*`（兩列：確認過的加索引站 dmhy、AI 直接做的送單，理由、
  tokens、展開的輸入）、`undo-confirm-*`、`undone-*`、`conversation-*`（從活動頁打開那則對話，送單卡說已撤銷），1280 與 390 各一組。
- 實作中自己定的小事：面板抬頭的「活動」在 `lg` 以下先收起面板（那時面板取代頁面）；對話標題用「」不用書名號；不說「反向命令」，
  說「這一件做了就撤不回」；加索引站那一列的對象是站名；確認過的可逆卡在活動頁撤銷後，面板上的卡多一句「這一筆後來撤銷了。」；
  一次回覆裡有一次呼叫沒回報用量，那一格就是不知道（「—」），不印部分加總（Spec review 提出）。

code-review（兩軸，基準 `97e31e50`）處理了：`WriteInput` 說明裡的 "log"（CONTEXT.md 的 AI Activity 避用）、確認卡「做成了沒」
的判斷兩份不一致（收成 `proposals.card_id_of` / `done_of`，`undo` 與活動頁共用）、`_Walk` / `said_id` 改名、後端 `truncated`
沒有測試、`subscribe_search_feed` 沒在活動頁的整合測試裡、部分加總的 tokens。未處理，記在這裡：

- 展開的輸入欄名照原樣印（`source_id`）：DESIGN.md 的 The Machine String Rule，機器字串在展開區照原樣。
- `ActivityEntryOut.result_type` 是 `str` 不是封閉的 `ToolResultType`：頁上 `targetOf` / `undoCopy` 的 switch 在新增結果型別時
  `tsc` 不會紅（認不得的不印對象、撤銷用通用文案）。存下的舊型別也會出現在這裡，與 `ToolResultPart.result_type` 同理。票 15 收尾時可再看。
- `targetOf` / `undoCopy` 與結果卡各自對 `result_type` 分派（Repeated Switches）；撤銷的三個值（對話、那一則、call id）是 Data Clump。
- 確認卡執行到一半出錯（`Refusal(internal_error)`，可能做了一半）不列；登錄表裡已經拿掉的工具做過的寫入不列（分不出讀寫）。
- `read_activity` 讀看得到的全部對話訊息再截 200 筆：家用的量可以，M6 背景任務寫進來時再看要不要在 SQL 截。
