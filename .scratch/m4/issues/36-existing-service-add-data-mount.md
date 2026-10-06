# 36 — 既有服務的接入說明：只多掛一條 `/data`，並停掉套件內那一台

**Status:** ready-for-agent

**Blocked by:** 34（實跑要用 34 的隔離做法，不能動 berth-trial / berth-audit）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S2 第一點、S3「qBittorrent 沒掛 `/data`」那列、§C1、§C2 全部、「文件與實作不符」的 README:33、`choice.existing.*`、`routes.fix.existing.qbittorrentMount`、plan §9.5 四列；改進清單 P1-6、P1-7）；brief §16.4、§20.14；plan §9.5；README〈選「既有」的條件〉

## 為什麼（2026-10-06 審計）

- 卡片寫「同一個容器路徑（例如都是 /data）」。「例如」暗示可以是別的路徑，實際上**只能是 `/data`**：Berth 的三層路徑是固定的。
- 掛錯時的補法要求使用者「下載目錄也移到它底下…不要分開掛 /downloads」，比 Berth 需要的多。照做的話，使用者的舊 torrent 可能找不到檔案。
  Berth 只在自己的目錄讀寫，最小改法是**多加一條 `/data` 掛載、原本的全部留著**（報告 §C2 的 compose 與 `docker run` 範例）。
- 實測：README 的混用指示「把它從 `COMPOSE_PROFILES` 拿掉再 `docker compose up -d`」不會停掉已經在跑的套件內容器。Compose 對不在啟用 profile 裡的服務，不會動既有容器。
- plan §9.5 的 NAS 範例（三個容器都掛 `/volume1/media:/volume1/media`、在 qBittorrent 頁設根目錄）與實作不符。

## 做什麼

1. 精靈「既有」卡片與 README 的條件寫明：容器路徑必須是 `/data`，`DATA_ROOT` 要是能硬鏈接的檔案系統，既有 Jellyfin 要先有對應類型的媒體庫。
2. 掛載補法（頁 3 與設定頁）改成「在原本的 compose 或 `docker run` 上多加一條 `${DATA_ROOT}:/data`」，原本的掛載不用動。附報告 §C2 那種片段。
3. README 混用指示補上停掉套件內那一台的指令（`docker compose stop <服務>`，或 `up -d --remove-orphans` 之類，以實跑結果為準）。
   `.env.example` 的 `COMPOSE_PROFILES` 註解與精靈「選了既有」那一段同步改。
4. plan §9.5 的 NAS 範例照 §C2 改寫。

## 驗收

- [ ] vitest：卡片不再出現「例如」；補法片段只有加 `/data` 那一條，沒有「移到它底下」（zh-Hant 與 en 並列）
- [ ] 實跑（隔離環境，指令與結果貼在 Comments）：既有 qBittorrent 保留 `/downloads`、既有 Jellyfin 保留 `/tv`，各只多掛一條 `/data`，頁 3 6/6
- [ ] 實跑：照 README 的混用指示做完，`docker ps` 裡套件內那一台確實停掉
- [ ] README、`.env.example`、plan §9.5 已改；brief §20.14 補上 Compose 不停既有容器的實測（附來源或腳本）
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
