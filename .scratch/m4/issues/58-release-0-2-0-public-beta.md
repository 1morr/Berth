# 58 — 發 0.2.0：第一個公開 beta

**Status:** done

**Blocked by:** 55（Unraid 實跑的結論寫進 CHANGELOG 的「測過的平台」）、56（release 附件）、57（新 README）

**讀:** `docs/research/usability-audit-2026-10-07.md` §2 E5、§6.3；README（新的英文版）〈Versions & upgrading〉；票 41（上一次發版的流程與 Comments）

## 為什麼

- GHCR 的 `:latest` 還是 0.1.0，不含票 43–54；照 README 部署會看到舊精靈（審計 P1-1、E5）。
- 使用者要今天公開、寫進 CV：發版之後，「下載 zip → `up -d`」才是一般人實際拿得到的東西。

## 做什麼

1. CHANGELOG `[Unreleased]` 收成 `[0.2.0]`。
   - 開頭寫：「公開 beta」、測過的平台（Windows Docker Desktop、Unraid 7.1）、已知限制（連到 README）。
   - 從 0.1.0 升級要注意的破壞性變更，照票 41 的寫法。
2. **打 `v0.2.0` tag 並 push 之前，先問使用者**（對外動作）。
3. 發版之後驗證：
   - GHCR 的 `latest` 與 `0.2.0` 是同一個 digest；release 頁有 zip 附件。
   - 在一個乾淨目錄，用 README 上的「最新版」連結下載 zip，照英文 README 走到 S1 入庫一部公有領域電影。
4. 在 GitHub repo 設定 description、topics（self-hosted、jellyfin、qbittorrent、prowlarr、media-automation 之類）與網站連結。**改 repo 設定前先問使用者。**

## 驗收

- [x] 使用者同意後 push `v0.2.0`；Release run 綠燈；匿名 `tags/list` 與 digest 比對結果貼在 Comments
- [x] 乾淨環境照英文 README 從 zip 走到入庫一部，附截圖
- [x] progress.md 的 M4 列與 session 紀錄記一行

## Comments

**發佈**（2026-10-09）：使用者開工時經協調者授權推 tag、發 release、改 repo 設定、push main（不在場，這張不再問）。
`82c13f2`（CHANGELOG 收版、`pyproject.toml` 0.2.0、部署檔註解英文、code-review 修正）打 annotated tag `v0.2.0` 並 push；
Release run `37836996064` 綠燈（image 與 deploy bundle 兩個 job，約 3 分鐘）。

```text
# 匿名（ghcr.io/token 拿的 pull token，沒有登入）
GET /v2/1morr/berth/tags/list → {"name":"1morr/berth","tags":["0.1.0-rc1","0.1.0","0.1","latest","0.2.0","0.2"]}
HEAD manifests/latest → docker-content-digest: sha256:9ec2722c965d999a84e8b05a33e2576940ec076f84439bd63e21076d523112eb
HEAD manifests/0.2.0  → docker-content-digest: sha256:9ec2722c965d999a84e8b05a33e2576940ec076f84439bd63e21076d523112eb
HEAD manifests/0.2    → docker-content-digest: sha256:9ec2722c965d999a84e8b05a33e2576940ec076f84439bd63e21076d523112eb
HEAD manifests/0.1.0  → docker-content-digest: sha256:8b93295c50f143bbc5d9d8e1529d55f17f2dc4068f5cbeef9fc62caa8b2a6425
$ gh release view v0.2.0
isDraft: false, isPrerelease: false, assets: berth-deploy-0.2.0.zip (6163), berth-deploy.zip (6163)
```

**repo 設定**：description「Self-hosted media acquisition that ends in your Jellyfin library: Prowlarr or RSS to qBittorrent,
matched against TMDB, hardlinked into Jellyfin. Public beta.」；topics `self-hosted`、`selfhosted`、`jellyfin`、`qbittorrent`、
`prowlarr`、`media-automation`、`tmdb`、`docker-compose`、`hardlinks`、`homelab`；網站連結 `https://github.com/1morr/Berth/releases/latest`
（沒有文件站，連到使用者實際要下載的地方）。

**乾淨環境照英文 README 走到入庫**（2026-10-09 04:10–04:25 +08）：本機唯一的 `ghcr.io/1morr/berth:latest` 是 0.1.0、沒有容器用它，
先 `docker image rm` 掉模擬新機器。repo 外 `C:/Users/Roxy/berth-t58`，`curl -LO` README 上的
`releases/latest/download/berth-deploy.zip`、解壓（`berth/` 裡三個檔，註解是英文）、`cp .env.example .env`。

偏差：這台機器上審計的 `berth`、`berth-*` 容器與 `berth` 網路還在跑，compose 把名字與子網寫死，所以另加
`docker-compose.override.yml` 改容器名（`berth-t58*`）、網路名、子網（172.26.0.0/16）與 Berth 的固定 IP；下載的三個檔沒動。
`.env` 只改五個 port（61383 / 61096 / 61080 / 61881 / 61696）與 `COMPOSE_PROJECT_NAME=berth-t58`，其餘預設。

`up -d` 拉到 `9ec2722c…12eb`，約 30 秒四個容器 healthy，`/api/health` 回 `{"status":"ok","version":"0.2.0",...}`。
介面切 EN（預設跟瀏覽器是 ZH）。截圖在 `.playwright-mcp/t58/`（gitignore，不進版控）：

| 步驟 | 結果 | 截圖 |
| --- | --- | --- |
| 頁 1 | 套件內 Jellyfin 12.1.0，建管理員 t58admin（密碼由本機 helper 填，不出現在工具輸出） | `t58-01`、`t58-02` |
| 頁 2 | 選套件內就設好 WebUI 登入，v5.2.3 | `t58-03` |
| 頁 3 | 進頁自己建 Movies / TV / Anime，3 條 Route 各 6 / 6 | `t58-04` |
| 頁 4 | 「Test recommended sites and add the ones that pass」：加入 dmhy、Anime Tosho、ACG.RIP、Mikan、The Pirate Bay；Nyaa、YTS 連不上，1337x、EZTV 被 Cloudflare 擋 | `t58-05`、`t58-06` |
| 頁 5 | TMDB key 由 `keysrv.py` 在頁面裡 fetch 填入（key 不出現在任何工具輸出），測試通過 | `t58-07` |
| 頁 6 | Finish setup → Discover，已登入 | `t58-08`、`t58-09` |
| 搜尋 | 《Night of the Living Dead》(1968，TMDB 10331，公有領域)：34 筆，107 筆名字對不上已略過 | `t58-10` |
| 送單 | `Night Of The Living Dead 1968 720p BRRip x264-x0r`（1.6 GB，The Pirate Bay）→ Movies，04:20:05 | `t58-11`、`t58-12` |
| 入庫 | 04:22:28 硬鏈接進 `/data/library/movies/Night of the Living Dead (1968) [tmdbid-10331]/`，兩端 link count 2、同一個 inode `1407374886215951` | — |
| Jellyfin | 04:25 作品頁「Ledger Matches · In Jellyfin」；媒體庫 Movies 一部「IMPORTED」、有「Open in Jellyfin」；健康頁全綠 | `t58-13`、`t58-14`、`t58-15` |

用完 `docker compose down`（容器與 `berth-t58` 網路已移除）；`C:/Users/Roxy/berth-t58`（1.7 GB，含下載的片與 `CREDENTIALS.md`）
留著，不需要了可以整個刪掉。沒碰其他容器與 Unraid。

**實跑看到並修掉（`cbd9619`，不在 0.2.0 的 image 裡，進 `[Unreleased]`）**：頁 5 回頭看的說明（zh-Hant 與 en）說測不過的 key
照樣存下，票 45 之後不對。改成「只有測過的 key 才存下，測不過時原本那一把照樣在用」，`web/src/i18n/auditCopy.test.ts`
加 `FAILED_KEY_SAVED`（雙向：原本兩句與換句話說會紅，改後的說法不會紅），先紅再改綠。

**code-review（`ef1e582`，兩軸 opus，在打 tag 之前）已處理**

- Standards / Spec：破壞性清單漏了票 45 的「既有 Jellyfin 新位址不回答 409 `unverified` → 400」→ 補上；並照票 41 的寫法逐票點名沒有破壞性變更的票（43、44、46–57、59、60），提票 46 的 `ConnectionReason` 多三個值。
- Spec：「compose 檔只改了註解」不精確（`${X:?…}` 錯誤訊息也改了）→ 改寫。
- Spec：zip 裡的 `preseed/qbittorrent/10-berth.sh` 還是中文，而且「由精靈用 API 設定，看得到差異也可重按」在票 32 之後不對 → 一起翻成英文並改正。
- Standards：`.env.example` 的 port 段少了「（例如開發環境）」→ 補回。
- 自己對照時發現：CHANGELOG 完全沒寫票 48（「S01 + S02」讀成多季合集）→ 補進 0.2.0 的 Fixed。

**code-review 未處理**

- Standards：compose 註解拿掉了 plan / brief / 票號的出處，repo 裡的維護者少了追溯線索。留著：這份檔是給拿 zip 的使用者看的，他們沒有 repo；出處在 git 歷史與 brief 都查得到。
- Standards：qBittorrent「兩個 port 內外同號」的說明在 `.env.example` 與 compose 各寫一份。翻譯前就是這樣，兩處的讀者不同（改 `.env` 的人、讀 compose 的人），不動。
- `pyproject.toml` 版號不在票面，但不改的話 `/api/health` 會回 0.1.0，算必要。tag 與版號一致目前沒有 CI 守，記在 progress.md「偏差與決定」。
