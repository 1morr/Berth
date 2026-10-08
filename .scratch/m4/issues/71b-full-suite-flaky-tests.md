# 71b — 全套 pytest 才會紅、單跑就過的測試：找出根因

**Status:** ready-for-agent

**Blocked by:** 71（使用者決定排在 0.2.1 發版之後，2026-10-09）

**讀:** `docs/development.md`〈全部檢查〉與測試段；`tests/conftest.py` 與 integration 的 fixture；下面三次出現的紀錄（票 59、55、70 的 Comments 與 progress.md 2026-10-08～09）

## 為什麼

同一類紅燈在三張票各出現一次，都只有跑全套才紅，單跑、整檔重跑、再跑一次全套都會過。三張票都沒改到那些測試或它們測的程式：

| 票 | 測試 | 現象 |
| --- | --- | --- |
| 59（rebase 後） | `tests/integration/test_setup_api.py::TestQbittorrent::test_applying_writes_only_the_login` | setup 階段 error，沒留 traceback |
| 55（收尾） | `test_rss_api` 的 `preview_then_follow_from_now` | failed，單跑 3/3 過 |
| 70（rebase 後） | `tests/integration/test_setup_api.py::TestGate::test_after_the_owner_the_same_writes_need_a_session[POST-/api/setup/qbittorrent/apply-None]` | failed，單跑 TestGate 3×38 過，再跑全套過 |

這類偶發會讓每張票的驗收多跑一輪全套（約 12 分鐘），也讓真的紅燈被當成「又是偶發」放過。

## 做什麼

1. 用 `mattpocock-skills:diagnosing-bugs`。**先分清是產品的問題還是測試的問題**（共用狀態、順序依賴、時間或時鐘、port、背景工作沒收乾淨、資料庫或檔案沒隔離），不要先猜。
2. **先做出會紅的 repro**：
   - 例如固定 `-p randomly` 的 seed、只跑造成干擾的那幾個檔案的組合、或 `--count` 重複；
   - 寫成一條指令或一支腳本，失敗率要量出來（N 次裡紅幾次）。
3. 修根因，修完用同一個 repro 證明失敗率歸零（同樣的 N 次）。
4. **只拉長逾時、加 retry、加 sleep，而說不出原因的修法不收。**
5. 原因如果在產品程式（不是測試），照 tdd 補一條會紅的測試。

## 驗收

- [ ] 寫明根因（是產品還是測試、哪個共用狀態或順序），附 repro 指令與修前失敗率
- [ ] 修後同一個 repro 失敗率 0（次數與修前相同），附輸出
- [ ] 三條測試都在根因的解釋範圍內；有不在範圍內的，另開票並寫明
- [ ] 全部檢查、pytest 全套綠；progress.md 記一行
