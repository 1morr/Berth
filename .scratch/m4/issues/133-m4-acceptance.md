# 133 — M4 驗收

**Status:** ready-for-agent

**Blocked by:** 121、122、123、124、125、126、127、128、129、130、131、132

**讀:** plan §11.5 的驗收段、§10；`docs/development.md`〈e2e〉；`tests/e2e/`（`conftest.py`、`test_4_m3_rss.py`、`stack.py`）；票 123 的 Discord base URL 環境變數；M3 票 21（上一個里程碑的驗收怎麼做）

## 為什麼

plan §11.5 的驗收要在真的 qBittorrent 與 Jellyfin 上走一遍；Discord 這一端用假伺服器記下收到的訊息，讓 CI 每天都能跑。

## 做什麼

1. e2e 加一個假的 Discord API（錄下每一則私訊；可以切成回 5xx 或整個關掉），Berth 用票 123 的環境變數指過去。
2. 新的 e2e 模組照 plan §11.5 的驗收：
   - RSS 命中 → 下載 → 入庫 → Jellyfin 可見：收件人收到「正在下載」與「可以看了」兩則，內容說得出作品、季集與 Route。
   - 一件進審核的事推出「等你處理」，連結開得到那一件。
   - 週報（觸發一次產生）說得出這週入庫、修了什麼、還有什麼等人。
   - 假 Discord 關掉時管線照樣走完、健康頁通知卡說得出來；打開之後補送。
3. 過一遍 121–132 的 Comments，未處理的照 M3 票 21 的做法分類歸屬，寫進 plan。
4. 使用者在試跑環境用真的 Discord 實走一次（手動，記在 Comments）。

## 驗收

- [ ] 新 e2e 模組在本機 `tests.e2e.stack` 與 CI 的 e2e workflow 都綠
- [ ] 上面四個情境各有斷言
- [ ] 121–132 的 Comments 都有歸屬，寫進 plan §11.5
- [ ] 使用者真機實走一次，記在 Comments
- [ ] 全部檢查、pytest、vitest 綠；progress.md 的 M4 列標「驗收完成」；CHANGELOG 已更新
