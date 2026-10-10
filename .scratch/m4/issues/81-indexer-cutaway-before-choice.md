# 81 — 精靈頁 4：還沒選之前，剖面不說「你自己的 Prowlarr」

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** M4 票 80 的 Comments 最後一條；`web/src/setup/IndexerStep.tsx` 的剖面（`Cutaway`，「接法」那一列看 `bundled`）；頁 1、頁 2 的剖面在還沒選、測試中時怎麼說（`JellyfinStep`、`QbittorrentStep`）

## 為什麼

票 80 實跑時看到：頁 4 還沒選「套件內」或「既有」時，剖面的「接法」就寫「你自己的 Prowlarr」；選了套件內、還在連線測試時也一樣。原因是剖面只看 `bundled` 是不是 true，把「還沒選」當成「選了既有」。第一次安裝的人一定會經過這頁。

## 做什麼

- 「接法」只在真的選了之後才說套件內或你自己的；還沒選時說「還沒選」或照頁 1、頁 2 的做法（先看它們怎麼處理，三頁說法一致）。
- 選了套件內、還在測試中時說套件內。
- 同一個剖面裡其他列若也把「還沒選」當成既有，一併改。
- zh-Hant 與 en 並列。

## 驗收

- [ ] 頁 4 還沒選、選了套件內測試中、選了套件內完成、選了既有，四種狀態的「接法」各自正確；vitest 守，做變異驗證
- [ ] 頁 1、頁 2、頁 4 還沒選時的剖面說法一致（若頁 1、頁 2 也有同樣的問題，一起修）
- [ ] Playwright 實跑：頁 4 的四種狀態各一張截圖。用隔離環境（專案名 `berth-t81`、另一組 port）；**不准碰使用者的 `berth-local`**
- [ ] 全部檢查、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新

## Comments
