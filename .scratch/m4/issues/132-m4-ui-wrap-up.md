# 132 — M4 UI 收尾

**Status:** ready-for-agent

**Blocked by:** 125、127、131

**讀:** plan §11.5〈修補段結案時票 Comments 的遺留〉的「M4 UI 收尾一張票」（每條都附了出處票）；CLAUDE.md〈UI〉；DESIGN.md、PRODUCT.md

## 為什麼

CLAUDE.md 要求每個里程碑的 UI 收尾前跑 `critique`、`audit`、`polish`。修補段結案時，還有幾條使用者看得到的遺留被指名留到這一輪。

## 做什麼

1. plan §11.5 列的七條逐條處理，每條先照出處票的描述重現（截圖或測試），再修；重現不了的寫進 Comments 不修：
   - 390 寬精靈 sticky 主鍵遮住下方欄位（M4 票 06）
   - 搜尋區塊 critique 未處理的五條（M4 票 84b）
   - 英文 `Settings → Library paths` 三處（M2 票 03）
   - 作品頁季表不隨背景入庫更新（M4 票 12、M3 票 06）
   - 票 31 留給「M4 收尾 polish」的五項
   - `docs/development.md` 的 `mixed` 情境 qBittorrent 帳密說法（M4 票 103）
   - `.impeccable/design.json` 落後 DESIGN.md（最後跑 `/impeccable document`）
2. 通知設定頁、週報頁跑 `/impeccable critique`、`audit`、`polish`，P0 / P1 修掉，P2 以下寫進 Comments。

## 驗收

- [ ] 七條每條有重現紀錄與處理結果（修了附測試或截圖，不修附理由）
- [ ] 通知設定頁、週報頁 critique 與 audit 的 P0 / P1 為零
- [ ] `.impeccable/design.json` 與 DESIGN.md 同步
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新
