# 01 — 以受限使用者實測 Jellyfin 的權限表（研究）

**Status:** ready-for-agent

**Blocked by:** 無 —— 可立即開工

**讀:** plan §11.2b（前置那一段）；brief §20.8、§20.9；`docs/research/library-browsing.md` §2、§3、§5、§9

## 做什麼

M1.5 的安全邊界建立在研究文件第 2 節那張表上：伺服器 API key 代讀時，哪些 Jellyfin 端點會套用使用者的
媒體庫權限、哪些不會。那張表**全部是讀原始碼得來的**（當時伺服器上沒有受限使用者），研究文件與 brief
§20.8 都要求逐列實測過才動工。本票就是那一輪實測，外加 M1.5 後面幾張票要用、但還沒人查過的事實。

在**一次性的** Jellyfin 上做（compose 釘的 `version-12.1ubu2604`，scratchpad 裡全新的 `/config` 與
dummy 媒體樹，跑完即刪）：兩個媒體庫、一個管理員、一個只開放其中一個媒體庫的一般使用者。不碰正式
部署與 e2e 那一套的任何容器。

要回答的：

1. 研究第 2 節的表逐列實測（API key + 受限使用者的 `userId`），每一列記下實際的狀態碼與筆數。
2. M1.5 要用的每個 `/Items` 過濾與排序參數，伺服器是不是**真的有過濾**（`/Items` 靜默忽略不存在的參數，
   研究 §2 末）：`parentId`、`includeItemTypes`、`genres`、`years`、`sortBy`、`startIndex` / `limit`。
3. **從 TMDB id 找到這位使用者看得到的 Jellyfin 作品**（Media 詳情的觀看區要用，票 08）：哪一種查法會套
   權限、伺服器真的有過濾。查不到會套權限的，就寫出「先找到、再用 `/Items/{id}?userId=` 驗可見性」的兩段法。
4. 對 Series 與 Season 標已看 / 未看，會不會遞迴到底下的集（研究 §5 只是原始碼推論）。
5. 帳號被 Jellyfin 停用之後，API key 代讀這位使用者的 `UserViews`、`/Items`、Resume 是否照樣回資料；
   `GET /Users/{id}` 讀得到 `Policy.IsDisabled` 與 `EnabledFolders`。
6. 12.1 與研究當時的 12.0.0 有沒有不一樣的地方（研究只測過 12.0.0）。

## 驗收

- [ ] 實驗腳本留在 `scripts/experiments/`（plan §10 的實驗層），可重跑，起停一次性容器
- [ ] 研究第 2 節的表逐列有實測結果（狀態碼、筆數），推論錯的列標出來並改正
- [ ] 上面第 2–6 點各有結論與實測證據
- [ ] 結論寫回 `docs/research/library-browsing.md` 與 brief §20.8，拿掉【只讀原始碼】的註記或改成實測標記
- [ ] 錄下後面契約測試要用的 HTTP fixture（`UserViews`、`/Users/{id}`、帶 `UserData` 的 `/Items`、
      `/Items/Filters`、Resume、NextUp、Seasons、Episodes、`UserPlayedItems`、圖片回應的標頭），
      受限使用者那一組要看得出「沒權限時回什麼」
- [ ] 實測結果若推翻 plan §11.2b 或 brief §12 的做法，同一個 commit 改文件並在 progress.md 記一行
- [ ] 一次性容器與 volume 已刪除（貼 `docker ps -a` 與 `docker volume ls` 的過濾結果）
