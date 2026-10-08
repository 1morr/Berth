# 71 — 只用 compose 檔加 `.env` 就能部署，發 0.2.1

**Status:** ready-for-agent（第 1–7 步的本機部分已在分支 `1morr/m4-71-compose-only` 做完；剩 VM 實跑與第 8 步，見 Comments）

**Blocked by:** 70（內嵌 preseed 的寫法與結論）；排在 42 之後做（同一批 guide 與 brief §20.14，避免兩個 session 同時改）

**讀:** 票 70 的結論與 brief 裡它新增的那一節；brief §19 E4、§20.17；票 56、57、58 的 Comments；README、README.zh-Hant、`docs/guide/` 的安裝、Unraid、升級三段；`docs/development.md` 的發版段

## 為什麼

- 使用者拍板（2026-10-09）：**部署只要 compose 檔加 `.env`**，貼進 Unraid Compose Manager 或任何資料夾就能 `up`。不下載 zip、不 clone、不放額外檔案。
- 這推翻 E4（票 56 的 release 附件 zip）。
- Release 頁**保留，只放那一版的說明**（CHANGELOG 段落），**不附任何檔案**。版本化的 image 照舊在推 `v*` tag 時發到 GHCR。

## 做什麼

1. **部署檔**：
   - compose 照票 70 定案的寫法內嵌 qBittorrent preseed；
   - 刪掉 preseed 目錄與它的掛載；
   - `.env.example` 的註解寫明：`DATA_ROOT`、`CONFIG_ROOT` 在 Unraid / Compose Manager 一定要用絕對路徑，否則會寫到隨身碟。
2. **拿掉 zip**（照全域規則直接刪舊路徑，不留相容層）：
   - 打包腳本、它的測試、pytest 為它加的 import 路徑；
   - release workflow 建 zip 與上傳附件的步驟；Release 頁照常建、內容是說明；
   - 實驗腳本裡引用 preseed 路徑的地方。
3. **閘門**：
   - 新測試：部署用 compose 的每個 host 掛載來源都是 `${變數}` 開頭或絕對路徑，不准相對路徑；
   - 雙向變異：加一條 `./x:/y` 會紅，改無關的註解或服務名不紅；
   - 現有的 preseed 腳本測試改成從 compose 檔抽出內嵌的腳本（還原 `$$`）再跑，原本守的行為一條不少。
4. **介面文案**：zh-Hant 與 en 提到 preseed 目錄或 zip 的補救說明改寫，例如套件內 qBittorrent 進不去時，請使用者確認 compose 是完整複製的。
5. **文件**（README 與 README.zh-Hant 同輪改，`test_readme_docs` 守兩份一致）：
   - 安裝改成：取得 compose 與 `.env.example` → 改幾個值 → `up -d`。
     - 連結指向**這次發版的 tag** 底下的原始檔（例如 `raw.githubusercontent.com/1morr/Berth/v0.2.1/deploy/...`），不指 `main`，免得 compose 比 image 新。
     - 下一次發版要更新這個連結：寫進 `docs/development.md` 的發版步驟。
   - Compose 最低版本寫 2.23.1。
   - `docs/guide/requirements.md`〈Unraid〉改寫成 Compose Manager 的做法：Add New Stack → 貼 compose → 貼 `.env` 改值 → Compose Up。不再提 Indirect Path 與 berth-deploy 目錄。
   - `upgrading.md`：從 0.2.0 升上來，之前下載過 zip 的人怎麼換（換 compose 檔即可，preseed 目錄可刪）。
6. **紀錄**：
   - brief §19 E4 那列記「2026-10-09 使用者推翻：只用 compose＋.env」；
   - §20.17 標成被取代，指到 70 的那一節；
   - plan §9.1、CHANGELOG `[Unreleased]` → `[0.2.1]`，從 0.2.0 升級要注意的寫清楚；
   - progress.md 偏差與決定。
7. **實跑**：在 repo 外的乾淨目錄，只放 compose 與 `.env` 兩個檔，照新 README 走到頁 2 套件內 qBittorrent 綠。
   - 本機一次；42 那台 VM（rootless）一次。
   - 本機用 `berth-t71` 專案名與另一組 port。
8. **發 0.2.1**（使用者已授權推 tag、建 Release、push main）：
   - pyproject 版號；
   - 推 `v0.2.1`，Release run 綠；
   - Release 頁沒有附件、有說明；
   - 匿名查 GHCR：`latest` 與 `0.2.1` 是同一個 digest。
   - 發版後照 README 上的連結，在乾淨環境從頭走到入庫一部公有領域電影：TMDB key 照審計做法，不出現在任何輸出。
9. **不碰 Unraid**：使用者要自己在 Unraid 上照新 README 部署。

## 驗收

- [x] 部署檔裡沒有相對路徑掛載、沒有 preseed 目錄；新閘門雙向驗證寫在測試檔內
- [x] preseed 行為測試改成讀 compose 內嵌的腳本，原有斷言都在且綠
- [x] zip 打包、它的測試與 release workflow 的附件步驟都刪掉；Release 頁照常建、無附件
- [x] README、README.zh-Hant、guide、development.md（發版步驟含更新 compose 連結）、`.env.example` 已改；全 repo 掃斷鏈 0
- [ ] 乾淨目錄只放 compose＋`.env`：本機與 VM 各一次到頁 2 綠，附指令輸出（本機完成；VM 待協調者確認空出來）
- [ ] `v0.2.1` 已發（合進 main 之後做；版號、CHANGELOG、連結已在分支上改好）：Release run 綠、無附件、GHCR `latest` = `0.2.1` digest；照 README 從乾淨環境入庫一部，附截圖
- [x] brief E4 推翻紀錄、§20.17 標取代、plan §9.1、CHANGELOG `[0.2.1]`、progress.md 已更新
- [x] 全部檢查、pytest、vitest、前端 e2e 綠燈

## Comments

### 協調者的範圍（2026-10-09）

- 只在分支 `1morr/m4-71-compose-only`（建在票 70 的 `b9d6d0d` 上）commit，不 push、不合併。
- **做到第 7 步就停**。第 8 步（推 `v0.2.1`、Release run、GHCR digest、照 README 入庫一部）等 70、71 合進 `main` 之後在 `main` 上做；版號、CHANGELOG `[0.2.1]`、README 指向 `v0.2.1` 的連結先在分支上改好。
- VM 那一次放在最後：票 42 正在 VM 上用 `~/berth-trial-42` 入庫，開始前先問協調者 VM 空出來沒有。

### 自己拍板的地方（使用者希望少打擾）

- **README 的連結指 `raw.githubusercontent.com/1morr/Berth/v0.2.1/deploy/...`，compose 裡的 image 仍是 `:latest`**：票只要求連結指 tag。compose 不比 image 新就夠了；pin `:0.2.1` 會讓「換 compose 才升級」變成唯一的升級路徑，與 upgrading.md 現有的 tag 說明衝突。
- **新閘門 `test_readme_docs.py` 的連結 tag 檢查**：票只說「下一次發版要更新這個連結，寫進 development.md」。規則要有閘門，所以加了測試：使用者文件裡每條部署檔連結的 ref 都要等於 `v<pyproject 版號>`，README 兩份都要連到兩個檔。改版號沒換連結就紅。
- **release workflow 的說明取 CHANGELOG 那一段**（`awk` 抽 `## [<版本>]`、相對連結換成 tag 底下的 blob），找不到那一段就讓 job 失敗。沒有另寫腳本：只有 workflow 用它。本機用 GNU sed 跑 `v0.2.0` 那一段，輸出正確。
- **掛載閘門也管頂層 `configs` / `secrets` 的 `file:`**：把 `content` 換成 `file: ./10-berth.sh` 是最可能的回退，它也是一個要放在 compose 旁邊的檔。named volume 不是宿主路徑，不算。
- **介面文案只改說明，沒加指令按鈕**：補救是「重新完整複製 compose，再 `up -d --force-recreate qbittorrent`」，附 Unraid 的做法。沒有新增 `CopyLines`，因為需要先換檔，複製一行指令並不能解決問題。
- **`inline_preseed.py` 改成從部署檔抽腳本**（只用標準庫、逐行取 `content: |` 那一塊）。下次換版本重量時，量的就是使用者拿到的那一份。

### 實跑：本機（2026-10-09 06:46–06:50 +08）

乾淨目錄在 repo 外（session scratchpad 的 `t71-local/berth/`），只放 `docker-compose.yml` 與 `.env` 兩個檔。兩個檔從工作樹的 `deploy/` 複製：README 連到的 `v0.2.1` tag 還不存在，內容相同。`.env` 只改了 `DATA_ROOT`、`CONFIG_ROOT`（兩個 repo 外的絕對路徑）與五個 port（58383 / 58096 / 58080 / 56881 / 59696）；`diff` 對 `deploy/` 只有這幾行，compose 逐字相同。

**override**：本機的審計環境 `berth`（容器名 `berth`、子網 172.28.0.0/16）正在跑。為了並存，照票 58 的做法加 override，只改專案名、網路名、子網（172.27.0.0/16，本機沒人用）、四個容器名（`berth-t71*`）與 `BERTH_IP` / `ipv4_address`（172.27.0.2）。**override 放在乾淨目錄之外**，用第二個 `-f` 疊上，所以目錄裡始終只有兩個檔：

```
$ ls -A
.env
docker-compose.yml
$ COMPOSE_PROJECT_NAME=berth-t71 docker compose -f docker-compose.yml -f ../side/coexist.override.yml up -d
 Container berth-t71-qbittorrent Started
 Container berth-t71 Started
（四個約 40 秒 healthy）
$ docker compose … logs qbittorrent | grep -E 'custom-init|berth-preseed'
[custom-init] Files found, executing
[custom-init] 10-berth.sh: executing...
[berth-preseed] added to /config/qBittorrent/qBittorrent.conf: WebUI\AuthSubnetWhitelistEnabled=true WebUI\AuthSubnetWhitelist=172.27.0.2/32
[custom-init] 10-berth.sh: exited 0
$ docker exec berth-t71-qbittorrent stat -c '%U:%G %a %F' /custom-cont-init.d/10-berth.sh
root:root 555 regular file
$ curl -s -o /dev/null -w '%{http_code}' http://localhost:58080/api/v2/app/version   # 宿主，不在白名單
403
$ curl -s http://localhost:58383/api/health
{"status":"ok","version":"0.2.0","setup_completed":false,"owner_established":false}
```

image 是本機已有的 `ghcr.io/1morr/berth:latest`（= 0.2.0，`9ec2722c`），沒有 pull。compose 的改動只動到 qbittorrent，0.2.0 的 image 照常能用。

精靈以 Playwright 走：頁 1 選套件內，建管理員 `t71admin`。密碼是隨機產生的，由本機一個只回那份 JSON 的 helper 在頁面內 fetch 後填入，不出現在任何工具輸出。頁 2 選套件內：**連上了、連線測試通過、v5.2.3 · Web API 2.15.1，WebUI 登入「已完成」**。截圖在 `.playwright-mcp/t71/t71-01-page1.png`、`t71-02-page2.png`（gitignore）。

清理：`down --volumes`，刪掉 `t71-local/`；`docker ps -a`、`docker network ls` 過濾 `t71` 都是空的。審計環境的 `berth` 從頭到尾 `Up 4 hours (healthy)`，沒有被動到。

### 實跑：VM（rootless）

尚未做，等協調者確認 VM 空出來。

### 檢查與測試（2026-10-09，本機）

```
$ uv run pre-commit run --all-files      # 全部 Passed（code-review 修完之後再跑一次）
$ uv run pytest -q
3693 passed, 24 deselected in 718.83s (0:11:58)
$ pnpm -C web exec vitest run
 Test Files  90 passed (90)
      Tests  1425 passed (1425)
$ pnpm -C web build && pnpm -C web e2e   # port 8484–8520 先確認沒被占
  35 passed (2.4m)
```

### 全 repo 斷鏈

`git ls-files -co --exclude-standard '*.md'` 共 261 份，以 `test_readme_docs.broken_links` 逐份掃：**0**。這只掃相對連結；`v0.2.1` 的 raw 連結在 tag 推上去之前是 404，要在第 8 步驗。

### code-review（b9d6d0d 對工作樹，Standards 與 Spec 兩軸 opus）已處理

- `test_both_readmes_link_the_deploy_files` 沒有雙向變異 → 拆出 `missing_deploy_links`，補上紅、綠兩向（Standards）。
- `_edited(change: Any)` → `Callable[[dict[str, Any]], None]`；URL 模板 `DEPLOY_LINK` 與 regex `_DEPLOY_LINK` 撞名 → 模板改叫 `DEPLOY_URL`（Standards）。
- Compose Manager 的按鈕是 **ENV File** 不是 Env File（對照 dcflachs/compose_plugin 的 `compose_manager_main.php`）→ 改（Spec）。
- 「Compose Manager Plus 有同樣步驟」沒有來源 → 刪（Spec）。
- 「stack 在隨身碟上無妨」寫成了肯定句，brief §20.18 標的是推論 → guide 加上「未在 Unraid 實測」（Spec）。
- `-rc` tag 沒有對應的 CHANGELOG 段，Release job 會在 image 推完後才失敗；合進 main 到推 tag 之間 README 連結是 404 → development.md〈發版〉寫明（Spec）。
- README 的「match the image docker compose pulls」在下一版之後就不成立 → 改成「compose 不比 image 新」（Spec）。
- 介面文案的補救只有 CLI → 加上 Unraid 的做法（Spec）。
- 「全 repo 掃斷鏈」沒有證據 → 上面那一段（Spec）。

### 未處理（判斷後留著）

- `inline_preseed.deployed_script()` 與測試的 `embedded_script()` 用兩種方法抽同一段，前者寫死 `    content: |` 與 6 格縮排（Standards，Duplicated Code）。實驗腳本只能用標準庫；compose 一旦重排，它在 `lines.index` 會直接丟 `ValueError`，不會量錯。為了把兩份綁在一起，要讓測試 import `scripts/experiments/`，而這張剛拿掉 `pythonpath = ["scripts"]`。
- 每次發版要改四處 `v0.2.1`（Standards，Shotgun Surgery）：測試守著，development.md 寫了 `git grep` 的做法。
