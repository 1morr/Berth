# 12 — 側面板（tracer：為什麼沒入庫）

**Status:** ready-for-agent

**Blocked by:** 11

**讀:** plan §11.6〈已定〉的串流那一條、〈分段〉第 4 段、§7（前端）；brief §13、§14；`PRODUCT.md`、`DESIGN.md`；`docs/research/m5-prototype-2026-10-27.md`〈形狀〉；`scripts/experiments/m5_agent_chat.html`（只參考行為，不參考樣式）；`web/src/AppShell.tsx`；`docs/development.md`〈UI 的 Fake 後端〉

## 為什麼

M5 第一個看得到的東西：每一頁都叫得出的對話面板，走完唯讀的「為什麼沒入庫」。後面的確認卡、外部資料、壓縮都長在它上面。

## 做什麼

1. **先 `/impeccable shape`**：
   - 側面板在桌面與手機上的樣子（手機是全螢幕的面板）。
   - 怎麼叫出來、跟目前頁面的關係。
   - 訊息、工具呼叫、錯誤、防護停下時的說明各長什麼樣。
   - 輸出 `.scratch/m5/side-panel-shape.md`。
2. **相依**：`ai`、`@ai-sdk/react`，釘當前的 stable，knip 閘門照舊。
3. **實作**：
   - `useChat` 加 `DefaultChatTransport`，只送最後一則。
   - 重新載入頁面時從 `GET /agent/conversations/{id}` 接回來。
   - 一個目前的對話加「新對話」；對話清單不在這張。
   - 工具呼叫收成一行，展開看參數與結果。
4. **安全**：
   - markdown 要消毒。
   - **不載入外部圖片**：圖片網址是常見的外洩通道（brief §14、`docs/research/m5-ai-direction-2026-10-27.md` C4 第 6 點）。
5. **沒設 provider 時**：管理員看到去設定頁的連結；一般使用者看到「管理員還沒設定」。其餘頁面與 M4 相同。
6. **Fake 後端多一個 `agent` 情境**：腳本化的假模型（參考 `scripts/experiments/m5_agent_selftest.py`），UI 驗證與前端 e2e 不需要金鑰；`docs/development.md` 的情境表補一列。
7. i18n zh-Hant 與 en。

## 驗收

- [ ] shape 文件在、實作照它
- [ ] 在 `agent` 情境問「X 為什麼沒入庫」，得到票 10 的結論分類；重新載入頁面之後對話還在（playwright 實跑，附截圖）
- [ ] 回覆裡的外部圖片不會被載入（vitest）
- [ ] 沒設 provider 時兩種角色各自看到對的說明（vitest＋實跑）
- [ ] 手機寬度沒有橫向捲動（實跑）
- [ ] 前端 e2e 加一條側面板的 tracer
- [ ] 全部檢查、pytest、vitest 綠；DESIGN.md、CHANGELOG、progress.md 已更新

## Comments
