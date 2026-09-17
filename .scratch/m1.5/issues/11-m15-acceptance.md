# 11 — M1.5 驗收與里程碑收尾

**Status:** ready-for-agent

**Blocked by:** 06、09、10

**讀:** plan §10（e2e）、§11.2b（驗收）；brief §17（M1.5 那一列）；`.scratch/m1/issues/15-m1-acceptance.md`（M1 收尾的做法）

## 做什麼

把 M1.5 的驗收釘進 CI，然後收尾。

**e2e 加上權限與瀏覽**（拆票時使用者拍板放進 e2e，每晚對真的 Jellyfin 12.1 跑）：在 M1 那一套 compose 上，以
Jellyfin API 建一個只開放一個媒體庫的一般使用者，用它登入 Berth，驗證：

- 看不到沒權限的媒體庫，直接請求那個媒體庫被拒；
- 不是 Berth 入庫的作品在牆上瀏覽得到（e2e 要自己放一部不經 Berth 的作品進 Jellyfin）；
- 標為已看之後 Jellyfin 那一端該使用者的 `UserData` 真的變了，標回未看也是；
- 某一集的播放連結指向 Jellyfin 的那一集；
- 帳號在 Jellyfin 被停用之後，Berth 的 session 結束。

**真環境走一次 brief §17 的驗收**：以一般使用者（`user` 角色）登入，不開 Jellyfin Web 就從媒體庫找到要看的那一集、
看到自己的進度並標記已看，按播放落在 Jellyfin 的那一集。

收尾包含 M1.5 新頁面與改過的頁面的 `/impeccable critique`、`audit`、`polish`，以及票 01–10 的 Comments 逐條
過完——該延後的寫進 plan §11.3 以後的里程碑而不是另開票（M1 票 15 的先例）。

## 驗收

- [ ] e2e 以受限的一般使用者驗證上面五件事，GitHub Actions 的 `e2e.yml` 綠燈（附執行紀錄）
- [ ] brief §17 M1.5 的驗收在真環境以 `user` 角色實跑一次並附證據
- [ ] `/impeccable critique`、`audit`、`polish` 對 M1.5 的頁面跑完，發現逐條處理或明確記錄為延後
- [ ] `DESIGN.md` 依 M1.5 實際做出來的東西更新
- [ ] README、CHANGELOG、CONTEXT.md 更新；plan §10 的 e2e 範圍同步改
- [ ] 票 01–10 的 Comments 逐條過完；延後的寫進 plan 對應的里程碑，並在 `docs/progress.md` 記錄
- [ ] lint / type / test / benchmark 門檻 / 前端測試全綠並貼指令輸出
