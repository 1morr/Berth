# 41 — 發第一個可拉的 image

**Status:** done

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

- [x] `docker pull ghcr.io/1morr/berth:latest` 與 `:0.1.0` 拉得到，digest 相同（輸出貼在 Comments）
- [x] 乾淨環境照 README 做 `docker compose up -d`，拉到 image，S1（三個服務都選套件內）走完；附截圖
- [x] CHANGELOG、README 已改；progress.md 記一行
- [x] 全部檢查（`pre-commit run --all-files`）、test 綠燈

## Comments

**發佈**：`6bc4c1d`（CHANGELOG 收版、README 拿掉提示框）打 annotated tag `v0.1.0` 並 push；Release run `37536302447`
綠燈（1m4s）。之後依 code-review 修的 CHANGELOG / README 升級說明在下一個 commit，不在 tag 上（只差文件）。

```text
$ docker pull ghcr.io/1morr/berth:latest
Digest: sha256:8b93295c50f143bbc5d9d8e1529d55f17f2dc4068f5cbeef9fc62caa8b2a6425
Status: Downloaded newer image for ghcr.io/1morr/berth:latest
$ docker pull ghcr.io/1morr/berth:0.1.0
Digest: sha256:8b93295c50f143bbc5d9d8e1529d55f17f2dc4068f5cbeef9fc62caa8b2a6425
Status: Downloaded newer image for ghcr.io/1morr/berth:0.1.0
$ docker image inspect --format '{{.Id}}' ghcr.io/1morr/berth:latest ghcr.io/1morr/berth:0.1.0
sha256:8b93295c50f143bbc5d9d8e1529d55f17f2dc4068f5cbeef9fc62caa8b2a6425
sha256:8b93295c50f143bbc5d9d8e1529d55f17f2dc4068f5cbeef9fc62caa8b2a6425
# 匿名（ghcr.io/token 拿的 pull token，沒有登入）
GET /v2/1morr/berth/tags/list → {"name":"1morr/berth","tags":["0.1.0-rc1","0.1.0","0.1","latest"]}
HEAD manifests/latest → docker-content-digest: sha256:8b93295c50f143bbc5d9d8e1529d55f17f2dc4068f5cbeef9fc62caa8b2a6425
HEAD manifests/0.1.0  → docker-content-digest: sha256:8b93295c50f143bbc5d9d8e1529d55f17f2dc4068f5cbeef9fc62caa8b2a6425
```

**乾淨環境 S1**（2026-10-07 05:48–05:55 +08）：驗完 pull 先 `docker rmi` 三個 tag，本機沒有任何 `ghcr.io/1morr/berth`。
把 `deploy/` 原樣複製到 repo 外 `C:/Users/Roxy/berth-qa-t41`，照 README 第一步 `cp .env.example .env`、`docker compose up -d`；
`.env` 只多一行 `COMPOSE_PROJECT_NAME=berth-t41`。**隔離只到專案名**：產品 compose 的 `container_name` 與網路名寫死，
能並存是因為當時沒有別套 Berth 在跑（`docker compose ls -a` 只有 `exist-broken` / `exist-good`，預設五個 port 都空著），
不是票 34 那種 override；這張要驗的是 README 原樣，所以沒有改 compose。`up -d` 拉到 digest `8b93…6425`，
`/api/health` 回 `version: 0.1.0`。

截圖在 `.playwright-mcp/t41/`（gitignore，不進版控）：

| 頁 | 結果 | 截圖 |
| --- | --- | --- |
| 1 | 套件內 Jellyfin 12.1.0，建管理員，「套件內 qBittorrent 與 Prowlarr 的介面也用這組」預設勾著 | `t41-01-owner` |
| 2 | 選套件內就自動設好 WebUI 登入（skipper），v5.2.3、Web API 2.15.1，已完成 | `t41-02-qbittorrent` |
| 3 | 預設 Movies / TV / Anime，「建立並檢查」→ 3 條 Route 各 6 / 6 | `t41-03-routes` |
| 4 | 選套件內，介面登入自動設好；「測試全部」6 站通過（Nyaa 連不上、1337x 與 EZTV 被 Cloudflare 擋），加入 Mikan、YTS | `t41-04-prowlarr` |
| 5 | 見下面偏差；重新載入後頁 5 與泊位顯示「已完成」「憑證 已驗證」 | `t41-05-tmdb` |
| 6 | 跳過「沒有」，「完成設定」→ 進 Berth；`/api/health` `setup_completed: true`，健康頁三個服務與三條 Route 全綠 | `t41-06-complete`、`t41-07-health` |

**偏差：頁 5 的 TMDB key 沒在瀏覽器裡填**（與票 40 同一個理由：不把真的第三方 API key 打進網頁欄位）。改以頁 1 那組
帳密 `POST /api/auth/login` 拿 session，再用 repo `.env` 的 `TMDB_API_KEY` 打 `POST /api/setup/tmdb/test`（前端那顆按鈕
打的同一支），回 `verified: true`。所以發佈的 image 上「貼 key → 按測試」這段前端互動沒有實跑；它由 vitest 與前端 e2e 守著。

用完 `docker compose down -v`、刪掉試跑目錄與拉下來的 image，沒碰其他環境。

**code-review 已處理**

- Standards / Spec：CHANGELOG 說「更早的破壞性變更都標了『破壞性』」不實（rc1 之後只有票 14e 有標）→ 改成指向 Removed 與 Changed。
- Standards / Spec：升級只寫 `docker compose pull && up -d`，使用者手上還是 rc1 的 compose 範本（容器名、Jellyfin `:latest`、寫死的 port）
  → README〈版本與升級〉加「先換範本、對照 `.env.example`」，CHANGELOG 指回 README 不重複指令，並提既有 Jellyfin 要 12.0 以上。
- Standards：「P0、P1 修完才發」與事實不合（P0-2 是這張、P0-3 是票 42）→ 改成 P0-1 與 P1，並寫 42 排在發佈之後。
- Spec：README〈外部服務的前提〉還寫「save path、autoTMM 由精靈經 API 設定，按之前會顯示差異」，與票 32 矛盾 → 改成一個全域偏好都不寫。

**code-review 未處理**

- Spec：README 新增〈版本與升級〉一節超出票面（票面只說保留「自己 build」）。留著：拿掉提示框之後 README 要有地方說 tag 怎麼對應、怎麼升級。
- `v0.1.0` tag 上的 CHANGELOG 是修正前的版本；不重打 tag（已發佈的 tag 不搬，差別只在文件）。
