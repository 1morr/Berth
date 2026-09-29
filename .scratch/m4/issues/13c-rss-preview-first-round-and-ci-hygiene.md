# 13c — main CI 紅：`rss-preview` 第一輪「新 0 筆」、pre-commit hygiene

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（M4 01–17 推上 main 後的第一個 CI 就紅，先修綠）

**讀:** 票 12、13、13b 的 `## Comments`（`rss-preview` / `rss-subscribe` 那幾條）；plan §3.2（背景迴圈）、§6 rss；
progress.md 2026-09-27 票 11 那一條「同一個 Feed 一次只輪一輪」（`1513db5`）

## 為什麼

main `6a90fc8` 的 CI（run 36614179332）兩個 job 紅：

1. **web-e2e**：33 條中 `rss-preview`（1280）紅，`rss-preview-390` 同一輪是綠的：

   ```
   Locator: getByRole('region', { name: /^Feed/ }).getByRole('article', { name: 'acg.rip' }).getByRole('status')
   Expected substring: "新 30 筆"
   Received string:    "這一輪：新 0 筆、長出 0 個 RSS Series（自動綁定 0 個）、送出 0 筆。"
   ```

   票 12 收尾時 `rss-preview-390` 已經紅過一次（單獨重跑綠），這是第二次。第一輪看到 0 筆新 Item，像是背景
   poller 與「立即輪詢」搶同一個 Feed：背景那一輪先把 30 筆記成已見，畫面上那一輪就是 0（票 11 的 `1513db5`
   讓同一個 Feed 一次只輪一輪，但沒有說畫面上顯示的是哪一輪）。**還沒 repro，第一步就是做出來。**

2. **hygiene**：`pre-commit run --all-files` 的 `trailing-whitespace` 與 `end-of-file-fixer` 改了檔：
   `.impeccable/critique/2026-09-28T13-52-10Z__web-src-setup-ownerstep-tsx.md`、
   `.impeccable/critique/2026-09-29T06-57-20Z__web-src-pages-setuppage-tsx.md`、
   `.scratch/m4/issues/06-wizard-jellyfin-first.md`、`09-indexer-berth-test-first.md`、`13-rss-series-by-work.md`。

要先分清楚 1 是**產品的問題**（使用者按「立即輪詢」或新加 Feed 時，畫面說「新 0 筆」但其實 30 筆被背景那一輪收走，
等於說錯話）還是**spec 的問題**（等待條件或測試資料的時序）。前者修產品，後者修 spec；只拉長逾時而說不出原因的不收。

## 驗收條件

- [ ] 找出 1 的原因並寫進票的 Comments，附證據（log、trace 或計時）
- [ ] 產品的問題：一條會紅的後端或前端測試，修好轉綠；spec 的問題：說明原本的等待條件為什麼不對，改 spec
- [ ] `rss-preview` 與 `rss-preview-390` 在整套前端 e2e 裡連跑三次都綠
- [ ] `pre-commit run --all-files` 乾淨；想一下為什麼本機的 pre-commit 沒擋下這些檔（`.impeccable/` 與 `.scratch/`
      是不是被排除、或 session 繞過了 hook），有需要就補上，並在 Comments 說明
- [ ] lint、type、test、前端 e2e 綠燈；push 後 main 的 CI 全綠（附 run 連結）
