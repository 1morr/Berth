# 13 — 通知寫作品名與集數

**Status:** done

**Blocked by:** 10

**讀:** spec〈範圍〉「通知」；brief §14（通知）；ADR-0015；`services/notify.py`（`_part`）；`describe_spans`

## 為什麼

遲到走現有的「等你處理」與「放太久」，不加通知種類，收件人也一樣（訂閱了它、有 Discord ID 的管理員），週報沿用。但現在的訊息只寫種類與數量，只知道「1 個 Issue（遲到）」還得點進去看。

## 做什麼

1. 這一波有 `episodes_overdue` 時，內文列出作品名與晚的集（`describe_spans`），最多五部，其餘寫「等 N 部」。
2. 送出時照 `detail_json` 組字，zh-Hant 與 en 並列。`reason = next_run`（11）的件寫成「可能是下一輪」，不寫成晚了。
3. 其他 Issue 種類的訊息不變。

## 驗收

- [x] Discord 訊息寫出作品名與晚的集（zh-Hant、en；測試）
- [x] 超過五部時其餘寫「等 N 部」（測試）
- [x] 沒有 `episodes_overdue` 的一波，訊息與現在相同（測試）
- [x] 全部檢查、pytest 綠；progress.md 已更新

## Comments

- 做法：送出一輪多讀一次這一波遲到 Issue 的 `detail_json`（`notify._overdue_details`），「等你處理」與「放太久」的內文在原來那一行下面一部一行（`_overdue_lines`）。只列這一波新增、送出時還開著的，早就開著的遲到不重列。
- 巡檢的 `detail_json` 多一格 `title_en`（`sweep._overdue_detail`），英文私訊用英文片名；票 13 以前開的件沒有，退回 `title`。plan〈`notify_sender`〉與〈`sweeper`〉同步。
- 測試：`tests/integration/test_notify_overdue.py` 7 條，一條從真的巡檢走到送出守 `detail_json` 形狀；五個變異（五部改六部、拿掉換輪、「放太久」不列、改列全部開著的、英文不用 `title_en`）各自讓對應的測試變紅。
- code-review 已處理：`_overdue_lines` 裡的 `late`、`found` 改名。未處理（判斷題）：
  - 換輪的件，種類標籤仍寫「1 個 Issue（遲到）」，下面那一行才說「可能是下一輪」：標籤與前端 Issue 清單同一組詞（`issues.typeLabel`），不照 `reason` 換。
  - `detail_json` 的形狀靠字串鍵在 `sweep` 寫、`notify` 讀，測試的 `detail()` 抄第三份；有真巡檢那條守著，沒抽 TypedDict。
  - 標題照語言選在 `_render` 與 `_overdue_lines` 各一份（後者多退回 `title`）；`current` 與 `overdue` 一起穿過 `_deliver` → `_render_waiting` → `_render_lingering`，沒打包。
  - `detail_json` 少鍵時整則組不成句子、當場放棄（同其他種類）；巡檢一定寫齊，沒放寬。
