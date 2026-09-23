# 大媒體庫量測（M2 票 11，plan §11.3 決定 2）

2026-09-23。回答兩件事：1,000 部的媒體庫上 Berth 有沒有超過拆票時寫死的門檻，以及票上列的五件各花多少。

> **門檻**：1,000 部的媒體庫上 `GET /inventory/{id}` p95 > 1 s，或 reconciler 走完一輪 > 10 分鐘，就做分段取；
> 否則不做快取。

**判定**：

| 門檻 | 修正前 | 修正後 | 判定 |
| --- | --- | --- | --- |
| `GET /inventory/{id}` p95 ≤ 1 s | **3.4 s**（超了；同一程序內 `read_wall` 的 p95，經過 serve 的 p95 沒量成，§2） | **0.66–0.68 s** | 超了 → 修了。**修的不是分段取**（使用者 2026-09-23 認可）：時間在 Berth 自己的分組（§2），Jellyfin 的兩支 p95 相加 0.31 s |
| 對帳一輪 ≤ 10 分鐘 | 26.5–30.8 s | （沒改） | 沒超，約門檻的 1/20 → 不做分段取（§3） |

被刪掉的 Jellyfin 帳號（§4）：Jellyfin 回 404，Berth 原本當成「問不到 Jellyfin」回 503、session 活到 30 天期滿——
**這一票修成與停用同一種處置**（刪掉他的每一張 session、401 `account_disabled`，使用者拍板）。

## 0. 環境、資料量與怎麼造的

- 腳本：`scripts/experiments/large_library.py`（宿主，起停整個環境）+ `large_library_berth.py`（在 Berth 的 image 裡跑），
  指令在根 README〈實驗腳本〉。
- **沒有一輪 1,000 部的量測從頭跑到尾**（下面「這台機器不穩」那一條）：數字來自同一個環境上分段補量的幾輪
  （`--keep` / `--reuse` / `--stages`）。原始資料都在 `.local/experiments/`（不進版控）：直打 Jellyfin 的三輪（§1）
  與反查在 `reuse.log`、`after.log`、`final.log`，`final` 那一輪另有 `results/large-library-jellyfin-reconcile.json`；
  修正前的 `read_wall` 拆開量在 `reuse.log`；修正後的 `GET /inventory` 在 `after.log` 與
  `results/large-library-inventory-reconcile.json`（含刪除帳號）；對帳三輪只在 `rec.log`（JSON 在寫下之前程序就倒了，
  腳本之後改成對帳量完先寫報告）；掃描秒數在 `full.log`。
- **Jellyfin 12.1.0**（`lscr.io/linuxserver/jellyfin:version-12.1ubu2604`，`deploy/` 釘的那一個）、**qBittorrent 5.2.3**、
  Berth 是這個 commit 的 `deploy/Dockerfile` `backend` 那一層（Python 3.13）。三者在同一個 docker network，
  同一個 `/data` volume 掛在同一個容器路徑——**帳本路徑要與 Jellyfin 回報的 `Path` 一字不差**（brief §20.1），
  所以 Berth 不能跑在 Windows 宿主上。
- 宿主：Windows 11、Docker Desktop 29.6.2（VM 32 執行緒、15.5 GiB）、Intel i9-13900HX。數字是量級，不是 NAS 上的值。
- **1,000 部怎麼造的**：一個 TV 媒體庫、1,000 部劇、每部 1 季 12 集＝**12,000 個集檔**。每一集在
  `/data/complete/tv/<release>/` 是一支 1 秒的 64×64 MKV（各自一個 inode），硬鏈接進
  `/data/library/tv/<作品> (<年>) [tmdbid-N]/Season 01/`——Berth 入庫的形狀。網路 fetcher 全關、不寫 NFO，
  TMDB id 只從資料夾名來。掃描 12,000 集花 **341 秒**。
  電影庫不另外造：每部一個 item，比劇集輕（劇集的 `UnplayedItemCount` 要數底下的集，`MediaSources` 是 12 倍的列）。
- **Berth 這一端是最壞的情況：1,000 部全是 Berth 經手的**——1,000 部 Media（快照 1 季 12 集都已播出）、1,000 筆
  `imported` 的 Job、12,000 列帳本（先跑一輪真的反查把 Jellyfin id 填上）、qBittorrent 上 1,000 個停著的 torrent
  （跳過校驗，hash 與 Job 相同）。牆的 `tracked` 因此是 1,000 格。
- 觀看紀錄照真實比例撒在 `viewer`（非管理員、全部媒體庫）上：250 部看過前三集、100 部整部看完、50 部看到一半。
- 延遲一律是容器對容器，依序打（不並行），先熱一次不計；p95 是 nearest-rank（n=20 時是第 19 小）。
- **這台機器在長時間滿載下不穩**：量測期間 VM 核心 log 有 segfault，Python（`libpython`、`ip 0`）與 Jellyfin 的
  .NET（`libc`）都有，沒有 OOM（原文在 `results/large-library-dmesg-segfaults.txt`；VM 的 ring buffer 之後被清掉，
  那一份是當時看到的輸出）。Jellyfin 被 s6 無聲拉起來 2 次（`jellyfin_startups` 是 3），`berth serve`（-11）與
  量測程序也各倒過。`faulthandler` 兩次都停在 `resolver.locate` 呼叫 `JellyfinItem.source_paths` 的純 Python
  生成式裡——那是程序九成 CPU 時間所在，純 Python 程式碼本身觸發不了 segfault。**推測**是這顆 13 代 i9 的硬體
  不穩（沒有換機器驗證）。表上的數字只取完成的請求；在別台機器上重量時先確認報告的 `jellyfin_startups` 是 1、
  `dropped_connections` 是空的。

## 1. 票上的五件之一到四：直打 Jellyfin

參數照 Berth 的 adapter 抄（`berth/adapters/jellyfin/client.py`），API key 代讀 `viewer`。三輪（`reuse`、`after`、`final`）的範圍：

| # | 呼叫（誰在用） | 筆數 | 位元組 | p50 | p95 |
| --- | --- | --- | --- | --- | --- |
| 1 | `library_index`：牆的整份清單，`enableUserData=false`（每一次 `GET /inventory` 都問） | 1,000 | 318 KB | 30–31 ms | 32–35 ms |
| 2 | `tmdb_index`：不帶 `parentId` 的 `/Items?hasTmdbId=true&fields=ProviderIds`（Media 詳情的觀看區） | 1,000 | 303 KB | 31–33 ms | 34–39 ms |
| 3a | `items(Series)` 帶整份 `MediaSources`（反查、對帳） | 1,000 | 409 KB | 38–39 ms | 40–41 ms |
| 3b | `items(Episode)` 帶整份 `MediaSources`（反查、對帳） | 12,000 | **25.9 MB** | **4.2–4.5 s** | **4.4–5.0 s** |
| 3c | 對照：同上不帶 `MediaSources` | 12,000 | 8.3 MB | 0.48–0.50 s | 0.50–0.53 s |
| 4a | 牆的一頁：100 部，帶觀看紀錄（現況） | 100 | 63 KB | 244–249 ms | 253–267 ms |
| 4b | `library_index` **帶**觀看紀錄（整份 1,000 部） | 1,000 | 538 KB | **1.94–1.96 s** | 1.98–2.00 s |
| 4c | 只取篩出來的 50 部（`ids=`，帶觀看紀錄） | 50 | 27 KB | 135–159 ms | 139–182 ms |
| 4c | 只取篩出來的 200 部（同上） | 200 | 108 KB | 426–446 ms | 439–848 ms |

- **整份 `MediaSources` 是 9 倍**（3b 對 3c）：每一集多一整份串流資訊。12,000 集 4.5 s，而 Jellyfin client 的逾時是
  30 s（`JELLYFIN_TIMEOUT_SECONDS`）——線性外推約 **8 萬集**會撞上，那時反查與對帳的 Jellyfin 那一方會每一輪都「問不到」。
- **分段取的代價**（3b 改成 `startIndex` + `limit`，`sortBy=SortName`）：`limit=500` 25 頁共 6.1–8.8 s（最慢一頁 284–1,185 ms），
  `limit=2000` 7 頁共 4.8–5.0 s（最慢一頁 779–821 ms）。**總時間不會變少**，只是每一個請求變短——它解的是逾時，不是慢。
  兩個長尾（4c 200 部的 848 ms、`limit=500` 的 8.8 s）都在 `reuse` 那一輪，同一段時間 Jellyfin 被重啟過，當作環境噪音看。
- **觀看紀錄的代價在 Series 的 `UnplayedItemCount`**：同一份整份清單，關掉是 31 ms，打開是 1.95 s（4b 對 1）。
  牆的一頁 100 部帶觀看紀錄是 250 ms（4a），所以現在每一次 `GET /inventory` 都付了這 250 ms 裡的大部分。
- **`ids=` 有長度上限**：200 個 id（約 6.6 KB 的 query）回 200；500 個回 **414 URI Too Long**（宿主直打重現）。

## 2. 門檻一：`GET /inventory/{id}`

`viewer` 登入 `berth serve`（另一個程序，同 `jellyfin_images.py`），第 1 頁與第 5 頁各依序打 30 次；另外在同一程序內
把 `read_wall` 拆開量 10 次。

| | 修正前 | 修正後 |
| --- | --- | --- |
| 經過 `berth serve`，第 1 頁 p50 / p95 | 沒量成：冷的那一次 3.43 s，之後 serve 程序 segfault（-11），其餘連線被拒 | 626–635 / **666–670 ms** |
| 經過 `berth serve`，第 5 頁 p50 / p95 | — | 637–653 / **663–683 ms** |
| 冷的第一次（權限快取與 Jellyfin 都還沒熱） | 3.43 s | 675–709 ms |
| 同一程序：`_survey`（Berth 經手的 1,000 部）p95 | **3.32 s** | 386–390 ms |
| 同一程序：Jellyfin 的那一頁 p95 | 269 ms | 268–273 ms |
| 同一程序：整份清單 p95 | 45 ms | 44 ms |
| 同一程序：整支 `read_wall` p95 | **3.41 s** | 650–685 ms |

回應 397 KB（`tracked` 1,000 格 + 牆 100 格）。

**3 秒在 `services/inventory._survey`**：它對每一部作品各把整份帳本與 Job 篩一次
（`entry.media_id == media.id` 的生成式），1,000 部 × 13,000 列＝**2,600 萬次 ORM 屬性讀取**。這一條是在 Berth 的 image 裡以同樣的資料量單獨重現
`_survey`、開 cProfile 看到的（`attributes.__get__` 26,193,021 次、4.3 s，`_survey` 3.0–3.4 s；一次性的 bench，
沒有留下來）。**同一支 bench 在 Windows 宿主上只有 0.3 s**——那裡的路徑正規化讓帳本那一份被篩空了，只剩 Job 的
1,000 × 1,000，所以大媒體庫只能在容器裡量。改成先按 `media_id` 分組、一次走完之後是 0.39 s，剩下的是載入 12,000 列帳本
與 1,000 份快照。

**為什麼不是分段取**（使用者 2026-09-23 認可）：票上的補救預設的是「Jellyfin 回太多」，而 Jellyfin 的兩支 p95 相加 0.31 s——牆本來就是一頁 100 部，
整份清單 1,000 部只要 31 ms。把整份清單分段只會多幾次往返。原因不在那裡，修法就不在那裡；也沒有加快取
（決定 2 的另一半照舊成立）。

**剩下的 0.67 s 裡最大的一塊是 Jellyfin 算那一頁的觀看紀錄（~250 ms）與 Berth 載帳本（~390 ms）**。離門檻還有 0.3 s；
帳本再大（例如 2,000 部的最壞情況）會先吃掉這一段，那時要改的是 `_survey` 只載牆需要的欄位，不是分段。

## 3. 門檻二：對帳一輪

`reconcile_once` 在同一個容器裡直接跑（與背景那一輪同一支），五方齊全：帳本 12,000 列、qBittorrent 1,000 筆、
complete 1,000 項、媒體庫 12,000 個檔、Jellyfin 12,000 列反查過的正片。三輪都沒有開出或更新任何 Issue（環境是一致的）。

| 輪 | 總計 | 帳本 | qBittorrent | complete | 媒體庫 | **Jellyfin** | 寫 Issue 的檢查 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 29.54 s | 0.10 | 0.11 | 0.01 | 0.34 | **27.95** | 1.04 |
| 2 | 30.79 s | 0.17 | 0.12 | 0.01 | 0.38 | **29.11** | 1.00 |
| 3 | 26.46 s | 0.14 | 0.10 | 0.01 | 0.34 | **24.93** | 0.94 |

一輪反查（12,000 列同時到期，第一次入庫的放大版）：27.4–30.7 s（五輪）。

**沒超，不做分段取**，也不順手做：

- 分段取解的是單一請求太長（§1：總時間反而多），而 Jellyfin 那一方 25–29 s 裡，Jellyfin 的回應只占 4.5 s——
  其餘是 `resolver.locate` 逐條帳本線性掃全部 item（12,000 × 12,000，崩潰時的 `faulthandler` 堆疊兩次都停在這個迴圈）。
  分段取不會讓它變快。
- 門檻的用意是「超了才動」（決定 2），而 30 秒離 10 分鐘有 20 倍。

**下一次該重量的時候**（兩條都與集數有關，不是作品數）：

1. `locate` 是帳本列數 × item 數：線性放大 5 倍（約 6 萬集）時是 25 倍，約 10 分鐘——那時改成以路徑建索引一次比完。
2. 整份 `MediaSources` 的那一個請求約 8 萬集會撞上 30 s 的逾時（§1）——那時才是分段取。

## 4. 票上第五件：被刪掉的 Jellyfin 帳號

M1.5 票 01 量過停用（研究 library-browsing.md §2）。這次在同一個環境建一個 `gone`、讓他登入 Berth、用 API key
`DELETE /Users/{id}`（204），再代讀他：

| API key 代讀已刪除的帳號 | 回應 |
| --- | --- |
| `GET /Users/{id}` | **404**，body 是 JSON 字串 `"User not found"` |
| `GET /UserViews?userId=` | 404，`Error processing request.` |
| `GET /Items?userId=&recursive=true` | 404，`Error processing request.` |
| `GET /UserItems/Resume?userId=`、`GET /Shows/NextUp?userId=`、`GET /Items/{集}?userId=` | 404，problem details |
| `POST /UserPlayedItems/{集}?userId=` | 404，problem details（沒有寫入） |
| 重新 `POST /api/auth/login`（Berth） | 401 `invalid username or password`（Jellyfin 認不得這個帳號） |

與停用並列：**停用的帳號 API key 照常代讀代寫，只有 `Policy.IsDisabled` 說得出來；刪除的帳號每一支都是 404**。

Berth 原本的行為（修正前，20 部的小規模量測）：`user_policy` 的 404 被 `HttpSession` 翻成 `ProtocolMismatchError`，
閘門再翻成 `jellyfin_unreachable`——**`GET /inventory` 一直回 503「問不到 Jellyfin」，session 活到 30 天期滿**。
修正後（1,000 部的量測）：權限快取過期的下一個請求回 **401 `account_disabled`**（`this Jellyfin account is disabled or gone`），
再下一個是 401 `sign in to use this API`——session 已經刪掉（量測時 `detail` 是 `disabled or gone`，之後分成
`disabled` 與 `gone` 兩句）。**只有 `GET /Users/{id}` 的 404 算刪除**：`user_policy` 改成 404 → `NotFoundError`，
`services/jellyfin_access._grant` 把它當成停用；`UserViews` 的 404 仍是「問不到 Jellyfin」——那一支的 404 也可能是
位址設錯（反向代理的路徑），不該拿它把所有人登出（code-review 的 Spec 軸指出）。

## 5. 對 Berth 設計的影響

- **不做快取**（決定 2 照舊）；**inventory 修掉 `_survey` 的二次方分組**，p95 從 3.4 s 回到 0.66–0.68 s。
- **對帳不動**；下一次重量的兩個條件寫在 §3。
- **票 14 要在「待審 / 對不到」篩出來的卡片畫觀看狀態時**：不要打開 `library_index` 的 `enableUserData`——那會讓每一次
  `GET /inventory` 多 1.9 s、直接超過門檻。改成只在篩選打開時、只替篩出來的那幾部以 `ids=` 另外問（50 部約 150 ms），
  一次最多 200 個 id（500 個是 414）。`ids=` 不套媒體庫權限（研究 library-browsing.md §2），id 只能來自這一次
  `library_index` 回的、已驗過媒體庫的那一份。
- **被刪掉的帳號與停用同一種處置**，前端不必改（`account_disabled` 本來就照「登入失效」處理）。
