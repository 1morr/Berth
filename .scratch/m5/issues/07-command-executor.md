# 07 — 命令執行器

**Status:** ready-for-agent

**Blocked by:** 06

**讀:** plan §11.6〈分段〉第 2 段、§6（API 面與門禁）；brief §11（帳號與權限）、§19「M5 的方向」⑦；`docs/research/m5-ai-direction-2026-10-27.md` A3 的 R9、R12、R14；`berth/api/gate.py`；用到 `nudge()`、`hub.publish`、`current_actor()` 的 API 模組

## 為什麼

命令的語意散在 API 層：喚醒背景迴圈、推播事件、誰在做、角色判斷、把例外轉成 HTTP。AI 直接呼叫 service 會漏掉這些，M7 的 Discord 與 MCP 也一樣。執行器是三個介面共用的那一條路。

## 做什麼

1. `execute(name, args, actor)`：查登錄表、驗輸入、檢查角色、執行、做事後動作（喚醒、推播），把拒絕轉成結構化理由。
2. **actor** 有人、`system`、`rss:<id>`、`ai`。`ai` 動作要記下是替誰做的（R14：統一寫法；沒有 `job_hash` 的帳本列確認與撤銷也要記事件）。
3. **角色**：
   - 每個命令帶一個 `audience`（`admin` / `user`），預設 `admin`。
   - 一般使用者能用的是讀取類，以及處理自己送單的那幾支（brief §19「M5 的方向」⑦）；「自己的」由命令檢查 `user_id`，與 API 現在的行為一致。
   - API 的門禁與登錄表的 `audience` 要對得上，用測試守。
4. 會登錄成 AI 工具、或能被 Proposal 執行的命令，**它們的 API 路由改走執行器**，舊的呼叫路徑刪掉。其餘的路由等用到再搬。
5. 拒絕理由沿用各模組現有的 enum，經執行器變成同一個形狀。API 的 OpenAPI 形狀不變（`pnpm gen:api` 沒有差異）。

## 驗收

- [ ] 經執行器的命令會喚醒、推播、記 actor（測試）
- [ ] 一般使用者經執行器碰不到 admin 命令、碰不到別人的送單（測試）
- [ ] API 門禁與 `audience` 一致（測試）
- [ ] 搬過去的路由行為不變（既有測試綠）；`pnpm gen:api` 沒有差異
- [ ] plan §6 補執行器；全部檢查與 pytest 綠；progress.md 已更新

## Comments
