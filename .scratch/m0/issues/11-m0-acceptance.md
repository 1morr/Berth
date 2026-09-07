# 11 — M0 收尾：雙平台驗收、既有服務組合、README 與 UI 定稿

**Status:** ready-for-agent

**Blocked by:** 10

**讀:** brief §17（M0 驗收）、§16.1、§16.3；plan §11.1；票 01–10 的 `## Comments`

## 做什麼

把 M0 當成一個產品驗收一次：在乾淨環境從 `docker compose up` 走到四項綠燈，全程不開任何外部服務的介面；再走一次 NAS 使用者最常見的「既有 Jellyfin + 套件內 qBittorrent 與 Prowlarr」組合。然後補齊 README，收尾 M0 的 UI，把前面各票留下的 code-review 發現清一遍。

## 驗收

- [ ] 乾淨 Linux 宿主：`docker compose up` → 只操作 Berth → 四項綠燈，全程沒開過 qBittorrent / Jellyfin / Prowlarr 的介面
- [ ] 乾淨 Windows Docker Desktop（NTFS bind mount）：同上
- [ ] 「既有 Jellyfin + 套件內 qBittorrent 與 Prowlarr」的組合走通，既有媒體庫是加路徑而非搬路徑，觀看紀錄未受影響
- [ ] README 定稿：硬鏈接前提（單一掛載根、不可 exFAT、不可跨 btrfs 子卷 / ZFS dataset / mergerfs branch）、支援平台、qBittorrent 版本下限與必要設定、Jellyfin 需 MergeVersions（套件模式自動安裝）、TMDB 歸屬聲明與 logo、全部指令
- [ ] `/impeccable critique`、`audit`、`polish` 跑過 M0 的所有頁面，發現的問題修掉或記進對應票的 Comments
- [ ] CHANGELOG 記下 M0
- [ ] 票 01–10 的 Comments 裡未處理的 code-review 發現重新過一遍，該修的修、該延後的寫成 M1 的票
- [ ] lint / type / test / 前端 build 全綠，貼出指令輸出

## Comments
