# 15 — M1 e2e 與里程碑收尾

**Status:** ready-for-agent

**Blocked by:** 13、14、14b、14c

**讀:** plan §10、§11.2（T1.8）；brief §17（M1 那一列）

## 做什麼

把 M1 的整條路徑釘進 CI，然後收尾。

e2e 在 compose 環境跑：用本地產生的 `.torrent` 與檔案，以 `seedMode` 讓 torrent 立即完成，走通
送單 → 完成 → planning → importing → ledger → Jellyfin 反查，並驗證硬鏈接 inode 與 Jellyfin 真的
查得到 item。nightly 與 release 跑。

收尾包含 M1 六個新頁面的 `/impeccable critique`、`audit`、`polish`，以及票 01–14 的 Comments 逐條
過完——該延後的寫進 plan §11.3 而不是另開票（M0 票 11 的先例）。

## 驗收

- [ ] compose 環境的 e2e 走通完整流程，用真的 qBittorrent 與真的 Jellyfin
- [ ] e2e 驗證硬鏈接 inode 相同，且 Jellyfin 反查得到 item id
- [ ] e2e 在 GitHub Actions 的 nightly 綠燈（附一次真的執行紀錄）
- [ ] brief §17 的三部作品（美劇一季、動漫一季、電影）在真環境實跑一次並附證據
- [ ] `/impeccable critique`、`audit`、`polish` 對 M1 的新頁面跑完，發現逐條處理或明確記錄為延後
- [ ] `DESIGN.md` 依 M1 實際做出來的東西更新
- [ ] README、CHANGELOG、CONTEXT.md 更新：`berth bench`、型別產生指令、新頁面與新名詞
- [ ] 票 01–14 的 Comments 逐條過完；延後的寫進 plan §11.3，並在 `docs/progress.md` 記錄
- [ ] lint / type / test / benchmark 門檻 / 前端測試全綠並貼指令輸出
