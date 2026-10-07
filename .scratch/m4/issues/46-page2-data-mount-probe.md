# 46 — 頁 2 測連線時就驗 qBittorrent 看得到 `/data`

**Status:** done

**Blocked by:** 36（補法沿用「只加一條 `/data`」）、38（頁 2 的前進條件先收好）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S3「qBittorrent 沒掛 `/data`」那列、§B1「能不能接被拆在兩頁」、§C3 第 1 條、改進清單 P2-4）；M4 票 19 與它在 progress.md 的偏差（探針會觸發「完成時執行外部程式」）；brief §16.4；plan §9.3

## 為什麼（2026-10-06 審計，實測）

- 掛 `/downloads`、沒掛 `/data` 的 qBittorrent，在頁 2 測試**通過**，要到頁 3 的第三條纜繩才失敗。截圖 s3-11、s3-12。
- Berth 已經有探針（票 19），頁 2 就可以先問一次。

## 做什麼

1. 頁 2 的連線測試通過之後，接著問一次 qBittorrent 看不看得到 `/data`。用票 19 的探針或更輕的方式都可以，以「不觸發完成時執行外部程式」為準；做法記在偏差。
2. 看不到時頁 2 轉紅，補法與 36 相同。
3. 那一台的「完成時執行外部程式」提示沿用票 19 的說法。

## 驗收

- [x] 整合測試（雙向）：看不到 `/data` 的 qBittorrent 在頁 2 轉紅並附補法；看得到的照常通過
- [x] 探針 torrent 跑完不留在 qBittorrent 裡（測試斷言）
- [x] 實跑掛 `/downloads` 的那台（照 34 的隔離），附截圖
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e、真服務 e2e 綠燈

## Comments

**2026-10-07 實作紀錄**

- 做法（偏差已記）：**校驗不完的探針**。`probe_torrent(unfinished=True)` 兩片、最後一片雜湊算在反相的內容上；
  `scripts/experiments/qbittorrent_unfinished_probe.py` 對 4.4.5 與 5.2.3 實測（brief §20.2）：看得到停在 0.5、看不到 0、
  `chmod 000` 是 `error`；「完成時執行外部程式」只被單片的對照組觸發，5.2.3 的「加入時執行」四包都觸發。
- 後端：`setup._data_sight` 在連上、版本夠之後於共用根目錄（`routes.shared_root_of`）放兩片的探測檔問一次；
  `ConnectionReason` 多 `data_unseen` / `data_unreadable` / `data_unsettled`，`detail` 是那條路徑，原文是 adapter 的
  `sight_error`（頁 3 共用）。`probe_sight` 判看得到改成進度 > 0。Berth 自己沒有那個目錄、寫不進、或共用根目錄是 `/`
  時不問。套件內也跑。
- 前端：`fixOf` 的三個新理由，`data_unseen` 的片段來自 `remedyFor('download_visible', …)`（既有：compose＋
  `docker run -v`；套件內：compose 一段）；既有表單測不過不屬於哪一格時，`Notice` 裡也畫片段。既有 qBittorrent 表單多一句
  `connect.probe`（不觸發完成時、加入時會觸發一次），套件內不提。
- 測試：`tests/integration/test_setup_qbittorrent_data.py`（既有紅 → 掛上綠、兩次 `open_probes == {}` 與無探測檔、
  表單測不過不存、套件內也紅、Berth 沒有 `/data` 或共用根目錄是 `/` 時不問）；`test_qbittorrent_probe.py`、
  `test_torrent_source.py`；`test_setup_owned_writes.py` 白名單放行頁 2 的探針（共用根目錄＋校驗不完，雙向變異）且
  兩輪都斷言它真的跑了；`ServiceChoice.test.tsx` 五條。`tests/integration/conftest.py` 讓沒寫路徑設定的測試不碰這台
  機器的 `/data`（本機 `C:\data` 真的存在，跑第一輪全量時探測檔寫了進去）。
- **檢查**：`uv run pre-commit run --all-files` 全過；pytest 3538 passed（23 deselected）；vitest 86 檔 1347；
  `pnpm -C web e2e` 35 passed；`uv run --env-file .env python -m tests.e2e.stack` 23 passed。
- 真服務 e2e：`_prowlarr_as_existing` 還在等票 45 之前的 200，改成 400 `connection_failed`＋`attempt`（獨立 commit）。

**實跑（隔離：工作樹 build 的 `berth:qa-t46`；repo 外 `C:/Users/Roxy/berth-qa-t46`，project / 容器 / 網路 `t46*`、子網
`10.234.0.0/16`、port 3xxxx；「使用者原本的」`t46-mine-qbittorrent` 5.2.3 只掛 `/config`、`/downloads`；跑完 `down -v`、
刪目錄與 image，`docker ps -a` / `volume ls` / `network ls --filter name=t46` 都空；沒碰 berth-trial / berth-audit）**

- 頁 1 套件內 Jellyfin 成為擁有者；頁 2 選既有，表單有探針那一句（`.playwright-mcp/t46-01-p2-form-hint.png`）。
- 填 `http://host.docker.internal:38081`、帳密留空、測試連線：`POST /api/setup/services/qbittorrent` 400；表單紅「你的
  qBittorrent 看不到 /data：…（例如只掛了 /downloads）…」，片段 `qbittorrent: volumes: - ${DATA_ROOT}:/data` 與
  `-v ${DATA_ROOT}:/data`，「這一組沒有存下」（`t46-02-p2-no-data-red.png`）。`torrents/info` 是 `[]`，`data/` 無
  `.berth-probe-*`。
- mine 多掛 `./data:/data`、`up -d` 重建（掛載 `/config /downloads /data`），再按測試連線：「qBittorrent 連上了」，泊位
  「已完成 · 既有 · v5.2.3」（`t46-03-p2-mounted-green.png`）；`torrents/info` `[]`，容器裡 `/data` 是空的。

**code-review 未處理的發現**

- Standards：autouse fixture 改寫私有 `setup._data_root`（偏差已記理由）。
- Standards：`_test_connection` 多一個只有 qBittorrent 用得到的 `data_root` 參數，Jellyfin / Prowlarr 也先讀一次路徑設定。
  留著：`_test_connection` 沒有 session，拆開要改兩個呼叫端的形狀。
- Standards：`_data_sight` 先 `os.access` 再寫，中間狀況可能改變；寫檔丟 `OSError` 時 `_classified` 不攔。沒有 repro，不修。
- Standards：`ProbeSight` 有三份平行對照（`sight_error`、routes 的 `_SIGHT_FAILURE`、setup 的 `_SIGHT_REASON`）；
  `unfinished` 旗標穿過五個簽章、`UNFINISHED_PROBE_PAYLOAD` 要與它成對傳。留著：各自對到不同層的封閉集合。
- Standards：頁 2 借用頁 3 `download_visible` 的 `remedyFor` 產生片段——刻意的，片段要與頁 3 一字不差（票面「補法與 36 相同」）。
