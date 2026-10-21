# 123 — Tracer：「可以看了」送到管理員的 Discord

**Status:** ready-for-agent

**Blocked by:** 121

**讀:** plan §11.5〈通知〉、§1（依賴方向）、§3.2（背景迴圈慣例）、§3.3（交易紀律）、§8 一個 adapter 的寫法（qBittorrent）；brief §5.2（`jellyfin_item_resolved`）、§14、§20.23；`docs/research/discord-notifications.md`；`berth/services/resolver.py`（寫 `JELLYFIN_ITEM_RESOLVED` 那段，約 :621）；`berth/main.py` 的 lifespan（迴圈怎麼掛）；`berth/adapters/qbittorrent/`（client＋fake 的樣子）；`berth/models/setting.py`；CLAUDE.md〈架構規則〉的 `@command`；CONTEXT.md

## 為什麼

M4 本體的第一條端到端：一筆 Job 在 Jellyfin 認出來，管理員的手機收到「可以看了」。之後的種類、每人設定、故障處理都疊在這條路上。

## 做什麼

1. **開頭先 `/impeccable shape` 通知設定頁**（`.scratch/m4/notify-settings-shape.md`）：設定頁新的一個分頁「通知」，這張只放管理員那一半（bot token、邀請連結、我的 Discord ID、測試按鈕），票 124、125 會往上加。
2. **資料**：`notifications` 待送表（plan §11.5 列的欄位）與 migration；每位使用者的 Discord user ID 存在使用者身上（這張就定成 per-user，票 125 再開放給每個人）；bot token 存在設定裡新的通知分組，API 回應只回「已設定」不回原文。
3. **adapter**：`adapters/notify/` 的 channel 介面（送一則給一位收件人，回成功或分類過的失敗）＋ Discord 實作（照票 121 的結論）＋ Fake；契約測試用票 121 錄的回應。Discord API 的 base URL 可由環境變數覆寫（給票 133 的 e2e 指到假伺服器），寫進 `docs/development.md`。
4. **services**：寫入一則（與觸發它的狀態變更同一筆交易）、送出一輪；新模組的公開 `async def` 標 `@command`。
5. **pipeline**：新的送出迴圈，照現有迴圈的慣例掛進 lifespan。這張只做「失敗留著下一輪再送」，退避、放棄與健康頁是票 128。
6. **「可以看了」**：`jellyfin_item_resolved` 寫下時，給每位有 Discord ID 的管理員排一則；內容說得出作品、季集與 Route（電影只說作品）。
7. **測試按鈕**：送一則測試訊息給按的人，失敗時當場說出原因。
8. CONTEXT.md 加「通知」與「待送表」的詞；CHANGELOG〈Added〉。

## 驗收

- [ ] 一筆 Job 寫下 `jellyfin_item_resolved` → 每位有 Discord ID 的管理員各一則，內容含作品、季集、Route（pytest，Fake channel）
- [ ] 觸發的交易 rollback 時沒有通知列（pytest）
- [ ] 送出迴圈對 Fake 送出後狀態是已送；Discord 回 5xx 時留著、下一輪再送（pytest）
- [ ] 契約測試對票 121 錄的成功與失敗回應綠
- [ ] bot token 不出現在任何 API 回應與 log（pytest 捕 log 斷言；變異：在 log 印一次 token 會紅）
- [ ] 通知設定頁：設 token、填 ID、按測試（vitest；playwright 實跑附截圖）
- [ ] 使用者用真的 bot 收到一則「可以看了」與一則測試訊息（手動，記在 Comments）
- [ ] 全部檢查、pytest、vitest 綠；import-linter 依賴方向沒破；CHANGELOG、CONTEXT.md、development.md、progress.md 已更新
