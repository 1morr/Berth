# 34 — 真服務 e2e 恢復，能與試跑環境並存

**Status:** done

**Blocked by:** 32（e2e 對頁 2 的斷言要照不寫全域鍵之後的行為寫）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（§A3「真服務 e2e 從票 16 之後沒跑過」、「還原與清理」、改進清單 P1-8）；票 15、26、31 的 `## Comments`（撞名與 `CONFIG_ROOT` / `DATA_ROOT` 外洩）；plan §10；README 的 e2e 段落

## 為什麼

- 真服務 e2e 從票 16 之後沒在本機跑過。票 26、31 都記了同一個原因：撞名，不准動使用者的試跑環境。所以票 26 之後的行為（密碼規則、完成時照頁序再驗）只有單元測試與 Fake 後端在守。
- 撞名的來源：`deploy/docker-compose.yml` 寫死了專案名 `berth`、四個 `container_name`（`berth`、`berth-*`）、網路名 `berth`，host port 則讀 `.env`。
  `C:\Users\Roxy\berth-trial` 與 `C:\Users\Roxy\berth-audit` 用的也是這一份，兩者彼此都會撞。
- 票 15 記過另一個陷阱：e2e 匯出的 `CONFIG_ROOT` / `DATA_ROOT` 被之後的 `docker compose up` 繼承，試跑環境的 Berth 因此掛到 e2e 的資料庫。

## 做什麼

1. 讓 e2e 的整套服務有自己的專案名、容器名、網路名與 host port，只在 e2e 這邊覆寫。產品 compose 的容器名不改（票 16 的決定：使用者看到的是 `berth-*`）。
   如果有一個名字非得改產品 compose 才能覆寫，停下來回報。
2. e2e 的環境變數不外洩到呼叫它的 shell：只在 e2e 的程序或 compose 呼叫裡生效。
3. 補上票 26 之後的行為：qBittorrent 介面密碼規則、完成時照頁序再驗，以及 32 的「全域偏好不影響 Route」。
4. README 的 e2e 段落寫明：試跑環境開著也能跑，跑完不留容器。

## 驗收

- [x] berth-trial 或 berth-audit 其中一套開著時，本機跑 `tests/e2e` 全綠；跑之前與之後 `docker ps` 比對，那一套的容器 ID 與狀態不變（指令與輸出貼在 Comments）
- [x] CI 的 nightly e2e 綠燈（手動觸發一次，貼連結）
- [x] 新增的 e2e 涵蓋票 26 的密碼規則、完成時照頁序再驗、32 的全域 `save_path` 改掉後送單仍成功
- [x] 跑完之後呼叫端 shell 的 `CONFIG_ROOT` / `DATA_ROOT` 沒有被改（e2e 自己的測試或腳本守著）
- [x] README 已改；全部檢查（`pre-commit run --all-files`）、test 綠燈

## Comments

**實作（2026-10-06）**：

- `tests/e2e/stack.py`：`uv run --env-file .env python -m tests.e2e.stack [pytest 參數]`，本機與 nightly 同一條。拆殘留 → build →
  `up --detach`（不 `--wait`）→ `pytest -m e2e tests/e2e -rA` → 失敗（含 build / `up` 失敗）印 `ps --all` 與 log → `finally`
  `down --volumes --remove-orphans`。`-p berth-e2e` 與兩個 `-f` 寫在命令列（蓋過呼叫端的 `COMPOSE_PROJECT_NAME` / `COMPOSE_FILE`），
  `e2e.env` 的值放進子程序環境、蓋過呼叫端 shell 的同名變數（compose 讓 shell 優先於 `--env-file`，所以反方向也會外洩）。
- `tests/e2e/compose.yml`：專案名、`container_name`（`berth-e2e`、`berth-e2e-{qbittorrent,jellyfin,prowlarr}`）、網路名、子網
  `10.231.0.0/16`（`!override`；Docker 自動配發的 172.17–31 / 192.168 以外，code-review 指出 172.30 會被別的專案自動拿走）、
  Berth 的固定 IP 與 qBittorrent 的 `BERTH_IP`、四份 `/config` 改 named volume（以掛載點蓋掉產品那一條）。`e2e.env`：五個 port 28xxx、
  `CONFIG_ROOT` 是佔位值（產品 compose 的 `:?` 要它有值）。**產品 compose 一個字都沒改**，沒有非改不可的名字。
- 閘門 `tests/unit/test_e2e_stack.py`：對展開後的兩份 compose 比專案名、容器名、網路名、子網重疊、白名單 IP、宿主 port、掛宿主路徑的每一條；
  檔內變異 11 種違規都紅、4 種無關改寫（重新序列化、改 volume 名、port 各 +1、加無關環境變數）都綠。對 HEAD 的舊設定跑一次列出 18 條。
  runner：以 `os.environ`（先 `setenv` 一組試跑環境的變數）跑一輪 `main`，呼叫端不變、compose 拿 e2e 的值、pytest 失敗與 `up` 失敗都還是 `down`；
  手動突變 `os.environ.update(E2E_ENV)` 會紅。harness 的容器名對 compose 的 `container_name`。
- 新 e2e（`conftest.configured` 的精靈那一段）：頁 2 先送 5 字元密碼 → 那一列 `failed` / `login_rejected`、`current_step == 2`，再送合規的；
  qBittorrent WebUI 把全域 `save_path` 改成 `/data/not-berth` 之後才建 Route、送單（`test_the_global_save_path_steers_nothing`：沒被改回來、
  三筆 `content_path` 都不在它底下；三筆都 `imported` 由第一條守）；完成前 `docker stop` qBittorrent、重新測試紅、收回頁 4 的跳過 → 422 指頁 2 →
  start、重測綠 → 422 指頁 4 → 跳過 → 完成。
- 順手：qBittorrent WebUI 登入收成 `harness.qbittorrent_webui()`（四處重複）；check-yaml 排除 `tests/e2e/compose.yml`（不認得 `!override`）。

**實跑（本機 Docker Desktop，berth-audit 開著）**：berth-audit 是審計留下的拋棄式環境，用的正是套件預設的 port 8383 / 8080 / 8096 / 9696
與 `berth`、`berth-*` 容器名、`172.28.0.0/16`。開工時它沒有容器，`docker compose up -d` 起來當對照、跑完 `docker compose down` 回到原狀。
berth-trial 沒動。呼叫端 shell 先放一組試跑環境會留下的變數：

```
$ export CONFIG_ROOT=C:/nonexistent/caller-config DATA_ROOT=C:/nonexistent/caller-data COMPOSE_PROJECT_NAME=berth
$ docker ps -a --no-trunc --format '{{.ID}} {{.Names}} {{.State}} {{.Image}}' | sort -k2 > ps-before2.txt
$ uv run --env-file .env python -m tests.e2e.stack
...
tests\e2e\test_1_m1_pipeline.py .....                                    [ 21%]
tests\e2e\test_2_m15_library.py ......                                   [ 47%]
tests\e2e\test_3_m2_repair.py .....                                      [ 69%]
tests\e2e\test_4_m3_rss.py .......                                       [100%]
======================= 23 passed in 1108.67s (0:18:28) =======================
 Volume berth-e2e_berth-e2e-data Removed
 Network berth-e2e Removed
exit=0 elapsed=1133s
after: CONFIG_ROOT=C:/nonexistent/caller-config DATA_ROOT=C:/nonexistent/caller-data COMPOSE_PROJECT_NAME=berth
$ docker ps -a --no-trunc ... | sort -k2 | diff ps-before2.txt - && echo "docker ps: IDENTICAL"
docker ps: IDENTICAL
$ docker image inspect -f '{{.Id}}' lscr.io/linuxserver/{qbittorrent:latest,jellyfin:version-12.1ubu2604,prowlarr:latest} python:3.13-alpine | diff images-before2.txt -
image tags: IDENTICAL
e2e leftovers: containers=[] volumes=[] networks=[]
(berth-audit) 16e1249a7fdb berth running / ad21a1d50bd9 berth-jellyfin running / d434941c7a33 berth-prowlarr running / 655352926cbe berth-qbittorrent running
```

- 第一輪（code-review 之前的版本，子網 172.30、還有 `pull`）也是 23 passed（18:35），容器 ID 與狀態不變，但 `docker ps` 的 Image 欄從
  `lscr.io/linuxserver/qbittorrent:latest`、`jellyfin:version-12.1ubu2604` 變成裸 sha：`pull` 把試跑環境共用的 tag 移到新 image，
  試跑環境下一次 `up -d` 就會換 image。拿掉 `pull`（`up` 會先拉完缺的 image 才啟動任何容器，冷啟動閘門不受影響；CI 的 runner 是空的）；
  兩個 tag 以 `docker tag <原 sha>` 指回原 image，第二輪之前的快照與開工前逐字相同。

**CI**：手動觸發 nightly e2e（`c0aedf1`）綠燈，`23 passed in 1093.05s (0:18:13)`，跑完 `Network berth-e2e Removed`：
<https://github.com/1morr/Berth/actions/runs/37478670388>。同一個 commit 的 CI 也綠。

**收尾**：`pre-commit run --all-files` 全綠；`uv run pytest` 3517 passed、23 deselected（e2e）。

**code-review（`/code-review c67a16d`，兩軸 opus）**：

- 已處理：`e2e.env` 檔頭不實（「.env.example 建議的 18xxx」、宣稱閘門也比 18xxx）；`_host_port` docstring；harness「第 4 步」改頁 2；
  WebUI 登入四處重複 → `qbittorrent_webui()`；容器名 harness 與 compose 各一份沒人守 → 單元測試；`--env-file` 與 `compose_env` 兩條路 → 留一條；
  `!reset` 沒用到；`qbittorrent_is("down")` → `green: bool`；build / `up` 失敗只印 `ps` → 也印 log；子網落在 Docker 自動配發範圍 → 10.231；
  runner 的測試傳拷貝不是 `os.environ` → 改 `os.environ`；空轉的 `web_ui_username == ""` 斷言拿掉；`pull` 移動共用 tag → 拿掉；
  progress.md 偏差記推翻票 15。
- 未處理：密碼規則只驗「密碼 < 6」，帳號 < 3 與含冒號沒進 e2e（票面寫「密碼規則」；帳號規則前端先擋，票 26 的整合測試與實測都有）；
  不 `pull` 之後本機 e2e 用的是已有的 image，要對新版跑得先自己 pull（README 寫了）。
