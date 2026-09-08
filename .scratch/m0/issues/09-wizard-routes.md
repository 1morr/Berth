# 09 — 精靈第 7–8 步：媒體庫 → Route、硬鏈接檢查、完成

**Status:** done

**Blocked by:** 06、08

**讀:** plan §9.3（第 7–8 步）、§9.5（檢查與訊息）、§8.6、§2.2（routes）、§11.1（T0.6）；brief §4、§16.4

## 做什麼

從 Jellyfin 媒體庫建立 Library Route，每個 Route 立刻在 qBittorrent 建 category 並跑三項檢查，全綠後寫 `settings.setup.completed` 結束精靈。這張票也帶進 fs adapter —— 它是唯一會動 library 的模組。

套件內 Jellyfin 自動由三個媒體庫建三個 Route（movies / tv / anime，anime 用 `anime` profile）；既有 Jellyfin 由使用者勾選媒體庫，每個媒體庫可選「加入 Berth 路徑」產生的新路徑或既有路徑之一作為寫入目標。

## 驗收

- [x] 套件內：自動建立三個 Route，各有 slug、名稱、Jellyfin 媒體庫 id、目標路徑、category、profile
- [x] 既有：勾選媒體庫並選定寫入目標後建立 Route，兩種選法都跑同樣的檢查
- [x] 每個 Route 在 qBittorrent 建立 `berth-*` category；category 已存在但 save path 不同時回報衝突且不覆寫
- [x] 檢查一：qBittorrent 的全域 save path 與各 category 路徑在 Berth 內 `stat` 得到
- [x] 檢查二：Jellyfin 回報的媒體庫路徑在 Berth 內 `stat` 得到
- [x] 檢查三：在 Route 目標寫探測檔 → `POST /Environment/ValidatePath` 確認 Jellyfin 看得到同一路徑 → 從 complete 根目錄對探測檔 `link()`，確認同 device、同 inode，之後清乾淨
- [x] 任一檢查失敗時指出「哪個容器少了哪個掛載」並附該容器的 compose `volumes:` 修正片段；`EXDEV` 另附「兩個目錄在 Berth 內是不同掛載」的說明
- [x] fs adapter 的 `link`、`stat`、`same_inode`、`link_test`、`free_space`、`is_within` 有單元測試
- [x] 寫入路徑不在任一 Route 的 `target_path` 底下時 fs adapter 拒絕（防路徑逃逸）
- [x] `POST /api/setup/complete` 寫 `settings.setup.completed`，之後 `setup/*` 需登入、`/` 不再導向精靈
- [x] 精靈全程可重跑，Route 重建不產生重複列

## Comments

### 完成時的狀態（2026-09-08）

- 358 個後端測試 + 86 個前端測試綠燈；ruff / ruff-format / mypy --strict / import-linter / eslint /
  prettier / tsc 全過。
- playwright 對 `scripts/fake_setup_server.py --scenario bundled` 走完八步：三條 Route 全綠，
  **Windows NTFS 上真的建了硬鏈接**（`dev=11550084160259632778 · inode=17451448556763814 · free=621.7 GB`）；
  新增的 `--scenario unmounted` 則看得到檢查三失敗、泊位 4 變紅、jellyfin 的 compose `volumes:` 片段。
  深淺兩主題與 zh-Hant / en 都跑過，手機寬度（390px）四格泊位板水平捲動、工作面單欄。

### code-review 的發現與處置

兩軸都跑過（Standards / Spec）。已修：檢查一原本 `stat` 自己剛建的目錄等於沒檢查（改成 stat
qBittorrent 回報的路徑）、`app/preferences` 讀不到被吞掉、檢查二吃第 3 步的快照而不是向 Jellyfin
現查、完成頁寫死綠色、profile 的 radio 群組共用 `name`、`berth_path` 兩處各算一次、前端兩個撞名
的型別、plan §8.6 對 `roots` 的說法與程式碼不符。逐條記在 `docs/progress.md` 的「偏差與決定」。

**沒有處理、留給後續的**：

- `read_route_status` 以「媒體庫名 → Route」建索引，所以 brief §4.3 允許的「同一個媒體庫多條
  Route」在畫面上會被收斂成一條。M0 的精靈一個媒體庫只建一條，這個限制要在 M1 的 Route 設定頁
  解掉（那裡才會有「再加一條」的入口）。
- 重跑第 7 步會刪掉沒被勾到的 Route。M0 沒有東西引用 `route_id`，M1 有 Job 之後要改成不刪、
  或改成明確的「刪除 Route」動作。
- 硬鏈接的方向照 brief §4.4（complete → library）而不是票面文字的（library → complete），
  而且 `probe_visible` 與 `hardlink` 用各自的探測檔。brief 的【決定】優先於 plan 的敘述順序，
  而且這個方向與 M1 入庫時真正要做的操作一致。
