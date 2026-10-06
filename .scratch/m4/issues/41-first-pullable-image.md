# 41 — 發第一個可拉的 image

**Status:** ready-for-agent

**Blocked by:** 32、33、34、35、36、37、38、39、40（D8：P0、P1 修完才發；42 在這張之後，用發出去的 image 實跑，使用者 2026-10-06 同意）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（環境限制 1、§3.2「可拉的 image」、§3.3 阻擋項 1、改進清單 P0-2）；brief §19「精靈審計後的八項」D8、§16.1；README〈自己 build image〉；`.github/workflows/release.yml`；CHANGELOG

## 為什麼

- GHCR 只有 `0.1.0-rc1`，`:latest` 是空的：`release.yml` 遇到預發佈 tag 不動 `:latest`。README 的第一個指令照做就走不通。
- **D8 拍板**：P0 修完才發，避免一般使用者第一次改 qBittorrent 設定就卡住（32）。

## 做什麼

1. CHANGELOG 的 `[Unreleased]` 收成 `0.1.0`，並把 32–40 的破壞性變更列清楚。
2. 打 `v0.1.0` tag，確認 `release.yml` 推出 `0.1.0` 與 `:latest`。打 tag 與 push 是使用者自己 repo 的發佈，直接做。
3. README 拿掉「`:latest` 是空的，自己 build」的提示框，保留「自己 build」作為進階段落。
4. 在乾淨的環境（沒有本機 image、隔離的專案名，照 34 的做法）從 README 第一步開始照做。

## 驗收

- [ ] `docker pull ghcr.io/1morr/berth:latest` 與 `:0.1.0` 拉得到，digest 相同（輸出貼在 Comments）
- [ ] 乾淨環境照 README 做 `docker compose up -d`，拉到 image，S1（三個服務都選套件內）走完；附截圖
- [ ] CHANGELOG、README 已改；progress.md 記一行
- [ ] 全部檢查（`pre-commit run --all-files`）、test 綠燈
