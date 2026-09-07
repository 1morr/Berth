# 05 — 精靈骨架、建立管理員與服務偵測（第 1–2 步）

**Status:** done

**Blocked by:** 03

**讀:** plan §9.3（第 1–2 步）、§6（setup 群組）、§7、§11.1（T0.6）；brief §16.3

## 做什麼

這是第一張 UI 票：開頭先跑 `/impeccable hooks on` 與 `/impeccable init`，新頁面先 `shape` 再實作。

乾淨環境開瀏覽器落在 `/setup`，走完精靈前兩步：建立 Berth 管理員（帳號、密碼，勾選「同一組帳密也套用到 qBittorrent 與 Prowlarr 介面」，預設勾），然後 Berth 逐一探測三個 compose 主機名，在畫面上逐服務顯示判定結果是「套件內」還是「既有」。setup 未完成時 `setup/*` 匿名開放、其他頁一律導向精靈。

**與 plan 的偏差**：plan §11.1 把 adapters（T0.4）與精靈（T0.6）分成兩個任務，本里程碑改成按精靈步驟垂直切票，每張票帶進自己需要的 adapter 能力、Fake 與契約測試。開工時確認這條已在 `docs/progress.md` 的「偏差與決定」。

## 驗收

- [x] `GET /api/setup/status` 回目前步驟與各服務判定；setup 完成後 `setup/*` 需登入（登入本身在票 07，在它落地之前完成後一律 401）
- [x] `POST /api/setup/admin` 存下管理員帳號與**明文**密碼，以及「套用到其他服務」的勾選（改用明文的理由見 progress.md 偏差；密碼只進不出，回應裡沒有它）
- [x] `POST /api/setup/detect` 逐一探測 `jellyfin:8096` 的 `/System/Info/Public`、`qbittorrent:8080` 的 `/api/v2/app/version`（免密）、`prowlarr:9696` 的 `/ping`，並從唯讀掛載的 `/ext/prowlarr/config.xml` 讀 API key
- [x] 判定規則正確：Jellyfin `StartupWizardCompleted=false`、qBittorrent 免密可進、Prowlarr 讀得到 key 且無索引站 → 套件內；否則既有並顯示連線表單
- [x] 服務未就緒時輪詢至多 2 分鐘，UI 顯示等待狀態，逾時後可重試
- [x] 三個服務可任意組合：把 Jellyfin 從 `COMPOSE_PROFILES` 拿掉後該服務顯示為既有並出現表單，其餘兩個仍判為套件內
- [x] Prowlarr 讀不到 API key 時退回手動貼上，也支援 `PROWLARR__AUTH__APIKEY` 的部署方式
- [x] 探測用到的三個 adapter 各有 `Protocol` 介面與 `Fake`，契約測試對 `tests/fixtures/http/` 的錄製回應綠燈
- [x] 前兩步各自可重跑且不產生重複資料
- [x] 未完成 setup 時直接開 `/` 會被導向 `/setup`
- [x] playwright 對 Fake 後端跑通前兩步並附結果

## Comments

### 實跑結果（2026-09-07）

`scripts/fake_setup_server.py` 起真的 Berth（真 API、真 DB、真前端 build），只把三個外部服務換成 Fake。

- **`bundled`**：`/` 導向 `/setup` → 建立管理員 `skipper`（剖面四列即時跟著帳號與勾選變）→ 探測 →
  三格泊位點亮為「套件內」，帶實測值 `10.11.11`、`v5.2.3 · Web API 2.15.1`；重新整理後仍在第 2 步（續行成立）。
- **`mixed`**：Jellyfin `not_deployed`、qBittorrent `auth_required`、Prowlarr `has_indexers` →
  三格轉「既有」並就地展開連線表單（Jellyfin 只有位址、qBittorrent 加帳密、Prowlarr 加 API key），
  `not_deployed` 那條另附可複製的 `COMPOSE_PROFILES=…`。
- **`starting`**：qBittorrent `pending`，倒數貼在那一條纜繩上；8 秒內實測 3 次 `POST /setup/detect`
  （首次 + 兩次 3 秒輪詢），超過 120 秒後自動轉「逾時」並換成「重試」按鈕與 `docker compose ps/logs` 指令。
- **對真服務的 smoke**：用 `deploy/docker-compose.yml` 起乾淨的三個容器錄 fixture，並在 compose 網路內
  跑過分類器——`jellyfin:8096` → 200、`sonarr-not-here:8096` → `NOT_DEPLOYED`、`jellyfin:9999` → `UNAVAILABLE`。

**無障礙**（WCAG 2.2 AA，PRODUCT.md）：深淺兩主題所有文字配對實測 ≥ 4.5:1
（深色 `ink/hull` 14.18、`ink-dim/deck` 6.53、`on-signal` 對四個塗裝色 6.53–12.35、`blocked-ink/well` 5.96；
亮色對應值 15.02 / 7.25 / 6.53–12.35 / 6.00），分隔線與按鈕邊框 ≥ 3:1。
Tab 序與視覺序一致、無 positive tabindex，焦點環是內底色外字色的雙環（單色會在黃色塗裝上消失）。
390px 寬無橫向溢出（`documentElement.scrollWidth === clientWidth`），泊位板自己水平捲動。

### code-review 的發現（都已處理）

Spec 軸抓到兩個真的 bug，兩個都在同一個 commit 修掉並補了迴歸測試：
重探會清掉使用者剛填好的連線、以及「測試連線」把套件內的 Prowlarr 永久判成既有。
Standards 軸抓到的死鍵、硬編文案、CONTEXT.md 未更新、共用元件放錯資料夾也一併處理。
細節記在 `docs/progress.md` 的「偏差與決定」。沒有留下未處理的發現。

### 留給後面的票

- **`DESIGN.md` 尚未產生**：新世界剛落地，依 impeccable 的規則由 documenter 在 M0 UI 收尾（票 11）
  依實際做出來的東西寫，不在本票先寫一份規則書。
- **shadcn/ui 未引入**（見 progress.md 偏差）。票 06 起若出現需要行為原語的元件（dialog、popover、
  combobox），在那一票引入並回頭統一。
- **`POST /setup/services/{kind}` 只做到「存下來並測一次」**：Jellyfin 的管理員登入與 API key 在票 06，
  qBittorrent 的偏好差異在票 08，兩者都會擴充同一個 client `Protocol`。
- **CSRF 的伺服器端檢查在票 07**。前端的 API client 已經對所有非 GET 帶 `X-Requested-With`，
  票 07 只需要加伺服器端那一半。
