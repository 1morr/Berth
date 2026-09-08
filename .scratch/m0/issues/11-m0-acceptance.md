# 11 — M0 收尾：雙平台驗收、既有服務組合、README 與 UI 定稿

**Status:** done

**Blocked by:** 10

**讀:** brief §17（M0 驗收）、§16.1、§16.3；plan §11.1；票 01–10 的 `## Comments`

## 做什麼

把 M0 當成一個產品驗收一次：在乾淨環境從 `docker compose up` 走到四項綠燈，全程不開任何外部服務的介面；再走一次 NAS 使用者最常見的「既有 Jellyfin + 套件內 qBittorrent 與 Prowlarr」組合。然後補齊 README，收尾 M0 的 UI，把前面各票留下的 code-review 發現清一遍。

## 驗收

- [x] 乾淨 Linux 宿主：`docker compose up` → 只操作 Berth → 四項綠燈，全程沒開過 qBittorrent / Jellyfin / Prowlarr 的介面（**是 Docker Desktop Linux VM 的 ext4，不是實體 Linux 或 NAS**——真 Linux kernel、真 bind mount、真 `link()`，但同一台 Windows 的同一個 Docker 引擎。brief §20.6 的兩條仍未做）
- [x] 乾淨 Windows Docker Desktop（NTFS bind mount）：同上
- [x] 「既有 Jellyfin + 套件內 qBittorrent 與 Prowlarr」的組合走通，既有媒體庫是加路徑而非搬路徑，觀看紀錄未受影響
- [x] README 定稿：硬鏈接前提（單一掛載根、不可 exFAT、不可跨 btrfs 子卷 / ZFS dataset / mergerfs branch）、支援平台、qBittorrent 版本下限與必要設定、Jellyfin 需 MergeVersions（套件模式自動安裝）、TMDB 歸屬聲明與 logo、全部指令
- [x] `/impeccable critique`、`audit`、`polish` 跑過 M0 的所有頁面，發現的問題修掉或記進對應票的 Comments
- [x] CHANGELOG 記下 M0
- [x] 票 01–10 的 Comments 裡未處理的 code-review 發現重新過一遍，該修的修、該延後的**寫進 plan §11.2 T1.9 與 §11.3 而不是另開票**（plan §11 本來就是 `/to-tickets` 的輸入，M1 開頭拆票會拆到；此時另開票會與那一輪的編號打架）
- [x] lint / type / test / 前端 build 全綠，貼出指令輸出

## Comments

### 三輪驗收（2026-09-08）

全部用 `deploy/docker-compose.yml` 與本機 build 的 image，**只操作 `http://localhost:8383`**，
沒有開過 qBittorrent / Jellyfin / Prowlarr 的介面。（排查時用過各服務的 REST API 與
`docker logs`，那是 debug 不是使用者流程。）

| 環境 | 結果 |
| --- | --- |
| 乾淨 Linux 宿主（ext4） | 八步走完、四項綠燈。硬鏈接 `dev=2112 · inode=33555095 · free=1015.4 GB` |
| 乾淨 Windows Docker Desktop（NTFS，9p bind mount） | 同上。三條 Route 的 NTFS inode 各不相同 |
| 既有 Jellyfin + 套件內 qBittorrent 與 Prowlarr | 同上。第 3 步只跑了 `public_info` / `libraries` / `api_key` 三個唯讀步驟 |

「Linux 宿主」是 Docker Desktop Linux VM 上的 ext4 持久磁碟（`/mnt/docker-desktop-disk`），
**不是另一台實體 Linux，也不是 NAS**——與票 04 同一個限制，brief §20.6 的兩條仍然保留。
WSL 的 Ubuntu 沒開 Docker Desktop 整合，開它要動使用者的 Docker Desktop 設定，沒有為此去改。

既有媒體庫「加路徑而非搬路徑」的前後對照：`Films` 的 Locations 由 `['/data/nas-films']` 變成
`['/data/library/films', '/data/nas-films']`；項目 ID `599a049dbd96080eec0c1b968a0d2dbe`、
Path、`Played`、`PlayCount`、`LastPlayedDate` **五項全部未變**。

### 驗收抓到並修掉的三個缺陷

1. **入口腳本從來沒有接手過 `/data`**：`take_ownership berth:berth /data` 展開成
   `chown /data berth:berth berth:berth`，一律失敗。Windows 上看不出來，乾淨的 Linux 宿主上
   Berth 連 `/data/library` 都建不出來。回歸測試 `tests/unit/test_entrypoint.py`。
2. **qBittorrent 5.x 的登入被判成失敗**：成功時 4.4.5 回 `200 Ok.`、5.2.3 回 `204` 空 body。
   原本「不是 `Ok.` 就是失敗」讓**每一套用預設 image 的部署**健康檢查永遠紅著。兩個版本的
   回應都錄成 fixture。
3. **Prowlarr 冷啟動時 `indexer/schema` 超過 5 秒探測逾時**：第一次呼叫要讀 627 份定義組出
   5.6 MB 回應，9p 上實測 9.42 秒（第二次 0.34 秒）。這一支改用自己的逾時。

### `/impeccable critique` / `audit` / `polish`

報告：`.impeccable/critique/2026-09-08-m0-ui.md`。機械檢測器 31 個元件 **0 findings**；
Nielsen 十項 **22/40**。修掉的：泊位板標籤對比 3.56:1 → **9.63:1**、英文把 API 端點大寫掉、
索引站「之後再說」零回饋、`<summary>` 的焦點環、「顯示」按鈕的觸控目標、窄版 carousel → 2×2、
`aria-current`、精靈的出口與 `?berth=N` 深連結。逐條記在 `docs/progress.md`。

### 沒有在 M0 修、已記錄的

- 每一步的左欄剖面與右欄纜繩列是同一份清單（重構範圍大）。
- 一格密碼無二次確認欄、十個索引站預設全勾——**這兩條是產品立場，要使用者決定**，不是我該替他選的。
- 綠色與紅色等重；全綠健康頁約 1000px、同一顆綠章重複 8 次。
- **亮色主題的 surface 文件與程式碼互相矛盾**：文件說「降明度提彩度以達 AA」，程式碼是兩主題
  共用信號色（`index.css` 有寫理由）。兩份留著遲早出事，要挑一份改。
- `assigned` 黃有三個意思（語言鍵、checkbox accent、所有主要按鈕），違反「每個顏色只有一個意思」。
- 三頁缺 `<h1>`、無 `<nav>` landmark、無 skip link；精靈裡 `h3` 出現在 `h2` 之前。
- 非 admin 開 `/settings/services` 靜默彈回，沒有訊息。
- `<summary>` 在無障礙樹上是 `generic` 而不是 `button[expanded]`。
- 窄版 Route 列把路徑尾巴截掉，三條 Route 看起來一樣。

### 票 01–10 的 Comments 掃過一遍

已處理：票 01 的「型別感知 eslint」（只開 `no-floating-promises` 與 `no-misused-promises`，
抓到兩個真的漏 await）、票 07 的 `routes.tsx` 重複兩行（收成 `requireSignedInPage`）、
票 05 的 `DESIGN.md`（本票產生）。

延後的寫進 **plan §11**（它本來就是 `/to-tickets` 的輸入，M1 / M2 開頭拆票時自然會被拆到），
不另開票：新增 **T1.9**（`openapi-typescript` 型別產生器與 CI 過期檢查、帶 job id 的結構化
日誌、Route 設定頁的「一個媒體庫多條 Route」與明確刪除動作）；§11.3 補兩條（媒體庫掛 TVDB
插件的警告成為 Issue、磁碟空間門檻）。

### 未做

- `v0.1.0` 沒有 tag。GHCR 上只有 `0.1.0-rc1`，compose 範本 pin 的 `:latest` 仍是空的
  （README 已寫明要自己 build）。發版會把 image 推成公開的 `:latest`，那是使用者的決定。

### 指令輸出（2026-09-08 收尾）

```
=== uv run ruff check . ===
All checks passed!

=== uv run ruff format --check . ===
131 files already formatted

=== uv run mypy ===
Success: no issues found in 99 source files

=== uv run lint-imports ===

Dependencies point downwards (plan 1.3) KEPT
api and pipeline call services only KEPT
parser and naming depend on domain only KEPT
adapters depend on domain only KEPT

Contracts: 4 kept, 0 broken.

=== uv run pytest ===
..................................................................       [100%]
426 passed in 38.24s

=== pnpm -C web lint ===
$ eslint .

=== pnpm -C web format:check ===
Checking formatting...
All matched files use Prettier code style!

=== pnpm -C web typecheck ===
$ tsc -b --noEmit

=== pnpm -C web test ===
 Test Files  8 passed (8)
      Tests  104 passed (104)

=== pnpm -C web build ===
dist/assets/index-B53F9yAS.css   17.09 kB │ gzip:   4.50 kB
dist/assets/index-BOP3d8T5.js   473.05 kB │ gzip: 143.64 kB

[32m✓ built in 158ms[39m
```
