# 121 — Discord bot 私訊實測【實驗】

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（**需要使用者動手**：建一個 Discord application＋bot、一個測試伺服器）

**讀:** plan §11.5〈通知〉、§10（實驗腳本保留在 `scripts/experiments/`）；brief §20.23、§20.6（實驗結論的寫法）；`docs/research/discord-notifications.md`（尤其〈未查到〉與〈對 Berth 的意涵〉）；`scripts/experiments/` 現有腳本的樣子

## 為什麼

M4 的通知走 Discord bot 私訊（brief §19 2026-10-21）。查證（`docs/research/discord-notifications.md`）留下幾件文件答不了、會改變實作的事：從沒連過 gateway 的 bot 能不能私訊；收件人不在共同伺服器、關了私訊時實際回什麼；429 的實際形狀。票 123 的 adapter 與票 128 的故障處理照這裡的結論寫，契約測試的回應也從這裡錄。

## 做什麼

1. **人工步驟**（給使用者一份逐步說明，`mattpocock-skills:wizard` 可用）：Discord Developer Portal 建 application 與 bot、拿 token；建一個測試伺服器、用邀請連結把 bot 加進去；使用者打開開發者模式複製自己的 user ID。token 只經環境變數交給腳本，不寫進任何檔案。
2. `scripts/experiments/discord_dm.py`（只用 httpx，不加依賴），對真的 Discord 量：
   - 全新、從沒連過 gateway 的 bot：開 DM channel、送一則純文字、送一則帶 embed 的。
   - 超過 `content` 2000 字元、embed 合計 6000 字元時的錯誤形狀。
   - 把 bot 移出伺服器之後再送（沒有共同伺服器）：狀態碼與 `code`。
   - 使用者關掉這個伺服器的「允許伺服器成員私訊」之後再送：狀態碼與 `code`。
   - token 錯的 401 形狀。
   - 連續送到第一個 429 就停（不要刻意打爆）：body 與 `Retry-After`、`X-RateLimit-*` header；記下送了幾則才遇到。
   - 邀請連結的 OAuth2 網址形狀：只私訊時需要的 scope 與 permissions（最小權限）。
3. 結論寫進 brief §20.23（取代「待票 121 實測」那句，附日期與 Discord API 版本）；研究檔〈未查到〉逐條更新；把每種回應的 JSON 錄成 `tests/fixtures/http/discord/` 的檔，給票 123 的契約測試用（token、user id、channel id 換成假值）。

## 驗收

- [ ] brief §20.23 寫出上面七項的實測結果（日期、API 版本），研究檔〈未查到〉已更新
- [ ] `scripts/experiments/discord_dm.py` 用環境變數就能重跑，repo 裡沒有真的 token 或 id
- [ ] `tests/fixtures/http/discord/` 有成功、無共同伺服器、關私訊、401、429 五種回應
- [ ] 全部檢查綠；progress.md 有 session 紀錄
