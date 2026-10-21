# 121 — Discord bot 私訊實測【實驗】

**Status:** done

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

- [x] brief §20.23 寫出上面七項的實測結果（日期、API 版本），研究檔〈未查到〉已更新
- [x] `scripts/experiments/discord_dm.py` 用環境變數就能重跑，repo 裡沒有真的 token 或 id
- [x] `tests/fixtures/http/discord/` 有成功、無共同伺服器、關私訊、401、429 五種回應
- [x] 全部檢查綠；progress.md 有 session 紀錄

## Comments

- 2026-10-21 實測（API v10）：結論在 brief §20.23，原始回應在 `.local/experiments/results/discord_dm/`（不進版控）。
- **第一個 bot 一路回 `50278`，原因是收件人的私訊開關，不是 gateway**：測試帳號的全域「加入伺服器後允許私訊」是關的，新伺服器跟著關。排查時第一個 bot 跑了 `gateway-once`（連一次再斷開）仍是 `50278`，使用者看了隱私設定才找到原因。因為第一個 bot 已經連過 gateway，「從沒連過 gateway」那一題改用新建的第二個 bot 量（成功）；fixture 全部取自第二個 bot。
- **關私訊回的是 `50278` 不是 `50007`**：票 128 照「收件人層一種錯」寫，提示同時說兩個補法；已在票 128 第 2 點與 plan §11.5 補註。
- **腳本用 `lib.py`（標準庫）而不是票面寫的 httpx**：`scripts/experiments/README.md` 的規則是實驗腳本只用標準庫、不需要專案虛擬環境；票面的意思是不加依賴，標準庫更少。例外是 `gateway-once` 用虛擬環境既有的 `websockets`（uvicorn[standard] 帶的），排查時加的，留著給下次重量時對照。
- 使用者把兩個 bot 的 token 貼進了對話；已提醒實驗後到 Developer Portal Reset Token。repo 裡沒有 token 與真的 id（`fixtures` 寫檔前檢查、另以 grep 掃過）。
- code-review 已處理：`discriminator` 遮掉；「長度檢查先於共同伺服器」原本的原始檔被 baseline 覆蓋，補量並加 `send --length`；README 例外清單補上本腳本；執行順序收進 development.md（指令單一來源）；`Scrubber.personal` 改名 `scrub_personal`。
- code-review 未處理（判斷題，一次性腳本不值得）：`USER_AGENT` 的版本號寫死 `0.2.9`（UA 版本不影響 Discord 的行為）；`/users/@me/channels` 路徑與「寫 JSON 檔」各重複兩、三處；`cmd_ratelimit` 不走 `send()`（它要逐則記 header）；`token, user_id` 一起傳過每個 `cmd_*`。`bot_public` 預設值只印在終端、不存檔（`invite` 每次重跑都會印）。
