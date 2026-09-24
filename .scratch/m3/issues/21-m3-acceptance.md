# 21 — M3 驗收

**Status:** ready-for-agent

**Blocked by:** 01–20 全部

**讀:** plan §11.4（範圍與驗收）、§10；brief §15、§17

## 做什麼

里程碑收尾。plan §11.4 的驗收是八條：

> 一個 Mikan 聚合 feed 加一個 Nyaa 或 acg.rip 搜尋 feed 全自動追完；中途訂閱的一部補齊舊集，之後的新集自動入庫；同一集兩個字幕組、同組 v1 與 v2 都並存；合集被排除；一部 split-cour 在審核裡改正一次之後其餘集數跟著對；一筆發佈時間與換算出的那一集播出日對不上的不自動入庫；Jellyfin 認到的季集與帳本不同時開出 Issue；已確認的 RSS Series 的新集數不出現在 audit 清單。

**e2e**：真服務那一套（`tests/e2e/`）加一個 M3 模組。公開 RSS 站不能進 CI，所以 feed 由一個本地替身 HTTP 伺服器用票 07 的 fixture 提供，下載與入庫走真的 qBittorrent 與 Jellyfin。前端 e2e（`pnpm -C web e2e`）加一條 RSS 流程：加 feed → 綁定 → 看到 Job。

**另外對真站跑一次**：用使用者自己的 Mikan `MyBangumi` 與一個 acg.rip 搜尋 feed，在本機 compose 上跑一輪，貼結果（這一輪不進 CI）。

**收尾動作**（專案 CLAUDE.md）：

- `/impeccable critique`、`audit`、`polish` 各一輪，P0 / P1 當場修，其餘記進票的 Comments
- 票 01–20 的 Comments 逐條分成「修掉」「延後（寫進 plan §11.5 M4 或更後）」「不做」
- `/impeccable document` 把 DESIGN.md 與 `.impeccable/design.json` 追上
- `docs/progress.md` 的 session 紀錄與偏差；CHANGELOG

## 驗收

- [ ] e2e 覆蓋八條驗收，全程自動化（貼 CI run 連結與輸出）
- [ ] 真站一輪的結果（feed、長出的 RSS Series、自動綁定幾部、入庫幾集）
- [ ] critique / audit / polish 結果與分數；P0 / P1 已修
- [ ] 票 01–20 的 Comments 已逐條歸屬
- [ ] lint、type、test、`berth bench` 綠燈；CI 全綠
