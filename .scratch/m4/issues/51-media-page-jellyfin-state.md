# 51 — 作品頁的 Jellyfin 狀態與媒體庫頁一致

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S6 Jellyfin 那列、§3.2 Jellyfin 回驗那列、改進清單 P2-9）；M4 票 02；brief §20.1、§20.8；plan §3.2、§8.2

## 為什麼（2026-10-06 審計，實測）

- 入庫後約 2 分鐘，Jellyfin 已經有這部片：媒體庫頁出現在牆上，作品頁也有「在 Jellyfin 看」。
  同一時間，作品頁的「檔案與版本」卻寫「Jellyfin 還在掃描，下一次查詢 9 分鐘後」，原因是 resolver 的退避。截圖 s6-13、s6-14。

## 做什麼

1. 先定位兩邊讀的是什麼：媒體庫頁直接問 Jellyfin，作品頁讀 resolver 的排程狀態。決定修哪一邊、為什麼，寫在 Comments。
2. 可選的方向：作品頁打開時順便查一次，查到就提前回驗；或在退避中改說「Berth 下一次確認在 N 分鐘後」，不要說 Jellyfin 還在掃。
   回驗的權威來源仍然是 resolver（票 02）。

## 驗收

- [ ] 整合測試：Jellyfin 已有該項目、resolver 還在退避時，作品頁不寫「還在掃描」（雙向：Jellyfin 真的還沒有時照舊）
- [ ] vitest：作品頁文案（zh-Hant 與 en）
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
