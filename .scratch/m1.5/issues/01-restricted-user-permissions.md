# 01 — 以受限使用者實測 Jellyfin 的權限表（研究）

**Status:** done

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

- [x] 實驗腳本留在 `scripts/experiments/`（plan §10 的實驗層），可重跑，起停一次性容器
- [x] 研究第 2 節的表逐列有實測結果（狀態碼、筆數），推論錯的列標出來並改正
- [x] 上面第 2–6 點各有結論與實測證據
- [x] 結論寫回 `docs/research/library-browsing.md` 與 brief §20.8，拿掉【只讀原始碼】的註記或改成實測標記
- [x] 錄下後面契約測試要用的 HTTP fixture（`UserViews`、`/Users/{id}`、帶 `UserData` 的 `/Items`、
      `/Items/Filters`、Resume、NextUp、Seasons、Episodes、`UserPlayedItems`、圖片回應的標頭），
      受限使用者那一組要看得出「沒權限時回什麼」
- [x] 實測結果若推翻 plan §11.2b 或 brief §12 的做法，同一個 commit 改文件並在 progress.md 記一行
- [x] 一次性容器與 volume 已刪除（貼 `docker ps -a` 與 `docker volume ls` 的過濾結果）

## Comments

- 2026-09-17 收尾：一次性容器與 volume 已刪。`docker ps -a --filter name=berth-exp-jellyfin` 只剩表頭
  （`CONTAINER ID   IMAGE ... NAMES`），`docker volume ls --filter name=berth-exp` 只剩表頭（`DRIVER    VOLUME NAME`）；
  另外 `docker volume ls -q | sort` 與開工前的快照逐字相同（18 個，都不是本票建的）。腳本自己的 ffmpeg 容器是
  `--rm`，Jellyfin 容器以 `rm -f -v` 刪，所以 image 宣告的 `VOLUME /config` 沒有留下匿名 volume。
- 2026-09-17 範圍：票面寫兩個媒體庫，實際建三個（TV、Movies 允許，Anime 無權），理由見 progress.md 偏差與決定。
  沒有推翻 plan §11.2b 或 brief §12 的做法；plan §11.2b 補了兩條約束（`parentId` 只放驗證過的媒體庫 id、`userId`
  在 adapter 是必要參數）。
- 2026-09-17 code-review（Spec）處理了的：無權的**季**當 `parentId` 原本沒測卻寫成實測（補一列，實測同樣洩漏）；
  「`UserPlayedItems` 沒有寫入」的讀回原本在 DELETE 之後，證明不了（改成每次 POST 後立刻讀回）；brief §20.8 說
  「使用者 token 只有 `parentId=<無權的媒體庫>` 回 401」寫成適用所有端點（改成只對 `/Items`，其餘帶 `parentId` 的
  端點使用者 token 也照回）；表上補 200 與 `/Genres`、`/Years` 的筆數；brief §20.9 的 `includeItemTypes` 遞迴改標實測；
  排序「每個鍵都有作用」寫得比證據強（改列出證明不了的三個）；`PG < PG-13 < R` 也是字串順序、撐不起「照分級高低」
  （只留劇集那組）；CORS 標頭在 12.0.0 沒記請求有沒有帶 `Origin`，「兩版沒差異」改成判定不了；「四條洩漏」改成
  「六列【新】，其中兩列洩漏」。
- 2026-09-17 code-review（Standards）處理了的：`--record` 換版本會覆寫 fixture，違反 fixture README「新版本開新檔案」
  （拿掉用不到的 `--image`，`--record` 在伺服器不是 12.1.0 時停下）；研究 §11 對 12.0.0 沒量過的兩件事（provider id 過濾、
  不帶 `recursive` 的遞迴）寫成「兩版相同 / 仍然」；fixture README 的「item id 由路徑決定」補上來源（brief §20.9）與兩輪
  實測；研究 §0 寫 scratchpad 但預設是系統暫存目錄；`Title.age_days` 的註解與劇的 `DateCreated` 實測矛盾；
  `AuthenticateByName` 寫了兩次（收成 `Server.login`）；`Catalog.id` 改名 `title_id`；實驗 README 的新段落插在
  `jellyfin_naming.py` 的說明前面。另外自查到兩句沒實測的說法（共用 DeviceId 會作廢 token）改成「預防，沒有實測」。
- 2026-09-17 code-review（Standards）**沒處理**（判斷題，一次性實驗腳本不值得）：`Credential.header` / `Server.json` /
  `create_library` 與 `jellyfin_naming.py` 的同名方法形狀重複；`(srv, api, c, user_id, report, fixtures)` 一路傳進每個
  `run_*`；`Row.expected` / `Outcome.verdict` 用字串混放判定與狀態碼；`run_regression` 一次做好幾件事；圖片與舊式驗證
  因為要自訂標頭而繞過 `Server`；`c` / `catalog` 兩種寫法、`FORBIDDEN`（媒體庫名）與 `forbidden`（id 集合）。
