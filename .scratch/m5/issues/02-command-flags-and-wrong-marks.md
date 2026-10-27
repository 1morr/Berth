# 02 — 命令標記：加旗標、修正標錯的、補閘門漏洞

**Status:** ready-for-agent

**Blocked by:** 01

**讀:** plan §11.6〈分段〉第 1 段；brief §14〈自主權看可不可以撤銷〉與〈對話裡的確認卡〉；`docs/research/m5-ai-direction-2026-10-27.md` A3 的 R2–R7、C1 最後一段、C4 第 4 點；`berth/services/commands.py`；`tests/unit/test_command_marks.py`；`docs/research/m5-ai-direction-2026-10-27/05-human-touchpoints.md` 觀察 4、5

## 為什麼

M5 的登錄表、確認卡與 M6 的接管開關，邊界全靠命令標記。現在的標記只有 Effect 與 inverse，表達不了「連到新位址」「送出 torrent」這類不管可不可逆都要人確認的動作，而且有幾條標錯。

## 做什麼

1. `CommandMark` 加 `flags`，`Flag` 有五個值：
   - `CONNECTS_OUT`：讓 Berth 連到新位址。
   - `SENDS_OUT`：對外發訊息。
   - `DOWNLOADS`：送出 torrent，受數量與磁碟閘。
   - `SETTINGS`：改設定。
   - `INTERNAL`：背景迴圈入口、週報產生這類，不當工具。
2. 加一支函式回答「這個命令要不要人確認」：`IRREVERSIBLE`，或帶 `CONNECTS_OUT` / `SENDS_OUT` / `SETTINGS` 任一個。規則只有這一份。
3. 在 `commands.py` 的 docstring 寫明 inverse 的三種寫法（R7）：
   - 指名的反向命令。
   - 指向自己：同一個命令換參數就能回去。
   - `None`：沒有單一反向命令，回去要重新規劃或換別的命令。
4. 修正標錯的：
   - R3：`review.confirm_audit(s)` 的 inverse 改成 `None` 並註明原因（`undo_audit` 會拆入庫，語意不同）。
   - R4：`rss.poll_due` 標 `INTERNAL`；`rss.delete_feed` 改成 `IRREVERSIBLE`（Feed Item 會被 CASCADE 刪掉）。
   - R5：會送出 torrent 的命令加 `DOWNLOADS`，包括 `rss.release_item`、`bind_series`、`poll_feed`、`downloading.add_manual_download`，以及之後找到的其他命令。
   - R6：改設定的命令加 `SETTINGS`，包括 `notify.set_bot_token`、`indexer.*`。
5. **閘門漏洞**（R2）：`test_command_marks` 只認 `iscoroutinefunction`，`@asynccontextmanager` 包過的 `download_round` 不標也不會紅。要讓它也被認出來。
6. 新規則在測試檔裡做雙向變異驗證：故意造出違規，證明會紅；改無關的命名或格式，證明不紅。

## 驗收

- [ ] 旗標與「要不要人」的判斷有單元測試
- [ ] R3–R6 的每一條都改了，`test_command_marks` 照新規則守住
- [ ] 沒標的 `@asynccontextmanager` 命令會讓閘門紅（變異驗證）
- [ ] CLAUDE.md〈架構規則〉的命令標記那一句補上旗標
- [ ] 全部檢查與 pytest 綠；progress.md 已更新

## Comments
