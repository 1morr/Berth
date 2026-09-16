# 14b — Jellyfin 12：只支援 12 以上、拿掉 MergeVersions、釘 image

**Status:** done

**Blocked by:** 無硬相依（2026-09-15 插入，排在 14 之後、15 之前：票 15 的驗收在 12.x 上跑，這些不先修會踩到）

**讀:** brief §7.7、§7.8、§16.4、§19（2026-09-15 那幾列）、§20.9；plan §8.2（`run_task`）、§9.1、§9.3（第 3 步）、§9.4（第 8、9 步）、§9.5、§11.2（T1.10）、§12；`docs/research/jellyfin-12.md` §4（升級阻力）、§5（對 Berth 的影響，檔案清單在 §5.2 第 1 點）

## 做什麼

開發途中 Jellyfin 出了 12.0（2026-09-08），套件內的 `latest` 已經是 12.1。查證（brief §20.9）找到：

- 12.x 原生合併劇集的多個版本，MergeVersions 在上面是空跑。
- 「檔案與版本」的劇集版本名是照 10.x + 插件的樣子算的，在 12.x 是錯的。
- 精靈第 3 步的重試在 12.x 回 403，一直卡住，精靈不再冪等。
- 多集檔與同起始集的單集，在 12.x 會被併成一集。

使用者拍板（brief §19）：

- **只支援 Jellyfin 12 以上**，MergeVersions 整段移除，不留給 10.x 的分支。
- 套件內 image 釘在 12.1 這條線。
- 多集衝突送審核。

## 驗收

- [x] **MergeVersions 整段移除**，檔案清單照研究 §5.2 第 1 點：
  - 精靈的插件步驟（plan §9.4 第 8、9 步）與重啟、既有服務的「安裝 MergeVersions」按鈕。`JellyfinStep` 九步變七步，`POST /api/setup/jellyfin/plugin` 刪除。
  - resolver 的合併觸發與 `NO_MERGE_TASK`、`JellyfinRequest` 裡 merge 的說明（`JellyfinRequest` 只剩 `scan`，`EventType.MERGE_VERSIONS_REQUESTED` 刪除）。
  - `settings.services.jellyfin` 的 `merge_movies_task_id` / `merge_episodes_task_id`、`setup.jellyfin.merge_versions_installed`。
  - 前端的步驟與 i18n、fake、fake 設定伺服器的情境、測試。**adapter 的介面上也不再有插件那幾支**（`/Repositories`、`/Packages`、`/Plugins`、`/System/Restart`），所以「重啟別人的 Jellyfin」在那一層就做不到。
  - 既有 Jellyfin 上已經裝好的插件不動。
  - 資料庫裡已存的設定 JSON 還帶著那幾個鍵：`SettingsGroup` 的 `extra="ignore"` 讀得起來，不需要 Alembic，model 上也沒有相容欄位。**code-review 抓到這條當初沒有閘門**（我一度以為既有測試守著，其實那條只驗 `PathSettings`），補了 `tests/unit/test_models.py::test_rows_written_before_mergeversions_was_removed_still_read`：餵一份帶 `merge_movies_task_id` / `merge_episodes_task_id` / `merge_versions_installed` 的舊 JSON 進去。
- [x] **版本下限**：精靈的 Jellyfin 步驟（套件內與既有）與健康檢查讀 `/System/Info/Public` 的 `Version`，低於 12.0 就紅燈、不往下做（`adapters/jellyfin.MIN_VERSION`，一處定義，兩處共用同一句原文）。
  - 訊息說出目前的版本、需要 12 以上，並附升級注意：先完整備份、移除第三方插件、升級後完整掃描、不能降級（brief §20.9）。原文（英文）由後端帶，升級注意走 i18n。
  - fake 回 `10.11.11` 時，精靈停在那一步、健康檢查紅燈，各有測試（`test_setup_jellyfin.py` 套件內與既有各一條、`test_setup_api.py` 一條、`test_health_service.py` 一條）。
- [x] 精靈第 3 步：`POST /Startup/User` 回 403（第一個使用者已有密碼）時，當成已經設過，繼續往下（那一步是 `skipped`），由之後的登入驗證密碼對不對。fake 模擬這個行為，並補「第 4 步失敗後重試走得完」的測試。
- [x] 「檔案與版本」的劇集版本名：
  - Jellyfin 已收錄時讀它回的 `MediaSources[].Name`（反查那一刻抄進帳本的 `jellyfin_version_name`，migration `3f6c0a7d94e2`）。
  - 還沒收錄時照實說明（顯示檔名的 tags 並說那不是版本名），不自己重算。
  - 票 13 那個版本名測試的前提同步改掉（票 13 的驗收行也標了註）。
- [x] planner：新正片與同一季的帳本 Entry、或同一份 Plan 的其他正片，起始集相同而結束集不同時，送 review。
  - 理由說得出「Jellyfin 12 只用季號與集號分組，會把它們併成一集、後面那一集從集列表上消失」。
  - 純函式那一半在 `parser/planner.py`（benchmark 量得到），比帳本那一半在 `services/plan.py`；兩邊各有單元 / 整合測試，`berth bench` 的 `auto_wrong` 仍是 0。
- [x] `deploy/docker-compose.yml` 的 Jellyfin 釘 `lscr.io/linuxserver/jellyfin:version-12.1ubu2604`。README 寫明：
  - Jellyfin 版本下限 12.0。
  - 從 10.x 升級的注意事項（§20.9 的升級阻力）。
  - 套件內 Jellyfin 之後怎麼升級。
  - BTH 步驟表、外部服務前提、fake 情境列裡的 MergeVersions 一併拿掉（`installed` 與 `failing` 兩個情境換成 `old-jellyfin`）。
- [x] 實跑：
  - 真環境（票 12 / 13 那一套）換成 12.1：**先備份 Jellyfin 與 Berth 的 `/config`**（`m1-acceptance/backup-before-12.1/`，75 MB + 712 KB），再以釘住的 tag 重建 jellyfin 與 berth（berth image 由這一份工作目錄 build）。`/System/Info/Public` 回 `12.1.0`，健康檢查四項全綠（`jellyfin ok · 12.1.0 · 3 libraries · unsupported=False`）、Route 全綠。
  - 50 筆帳本重排反查之後**全部寫下 Jellyfin 算的版本名**（單一版本時是整個檔名主幹）。
  - 同一集兩個版本：再送一份 The Bear S03E01 的另一個發佈組（`…-Sakurato`），自己走完送單 → 下載 → 規劃 → 入庫；**Jellyfin 12.1 把兩個檔案併成一集兩個來源**（`翌日`，`IndexNumber=1`，`sources: 2`），名字是它算的 `Tomorrow [WEB][1080p][Sakurato]` 與 `Tomorrow [WEB][1080p][SuccessfulCrab]`，`GET /api/media/tv:136315` 的 versions 就是這兩個。
  - 以 fake 設定伺服器的 `old-jellyfin` 情境，用 playwright 看精靈的版本下限訊息：泊位 1 紅燈「版本太舊 · 這台 Jellyfin 是 10.11.11，Berth 需要 12.0 以上」，底下是為什麼要 12 與升級前後要做的事；剖面只剩版本 / API key / 媒體庫三列（MergeVersions 那一列沒了），API key 維持「尚未取得」——閘門擋在第一步。
- [x] 文件跟著程式改：plan §2.1（`merge_*_task_id`、`setup.jellyfin`）、§2.3（`jellyfin_version_name`）、§3.1、§3.2、§8.2、§9.1、§9.3、§9.4、§9.5、§11.2 T1.6、§12，README，CHANGELOG；推翻的地方記進 progress.md 的偏差。
- [x] lint / type / test 全綠並貼指令輸出（見下方 Comments）。

## Comments

**指令輸出**（2026-09-16）：

```
uv run ruff check .        → All checks passed!
uv run ruff format --check → 264 files already formatted
uv run mypy .              → Success: no issues found in 199 source files
uv run pytest -q           → 1319 passed in 268.10s
pnpm -C web lint           → (eslint, 無輸出)
pnpm -C web typecheck      → (tsc -b --noEmit, 無輸出)
pnpm -C web test           → Test Files 20 passed (20) / Tests 296 passed (296)
uv run berth bench         → auto_correct 140 · auto_wrong 0 · missed 0（23 fixtures, 333 files）
```

**實跑抓到的一件事（留給 M2）**：同一集第二個版本入庫之後，Jellyfin 會把**兩個**來源的名字一起改成「去掉共同前綴」的樣子（`The Bear (2022) - S03E01 - Tomorrow [WEB][1080p][X]` → `Tomorrow [WEB][1080p][X]`）。帳本上先前那一筆已經反查完、不再排程，名字因此停在單一版本時的舊樣子，同一組裡兩個版本名的長短會不一致。畫面仍然是「Jellyfin 說的」，只是其中一筆是舊的。要讓它自己追上，歸屬是 M2 的 Reconciler（重新反查既有帳本），不在本票範圍。

**版本閘門的截圖**：`.playwright-mcp/14b-version-gate-10.11.png`（不進版控）。

**演練情境**：`installed`（既有 Jellyfin + 已裝插件）與 `failing`（插件下載失敗）兩個情境沒有意義了，換成 `old-jellyfin`（既有 Jellyfin 停在 10.11）。它底下的其餘兩個服務照 `bundled` 而不是 `mixed`——後者的 qBittorrent 永遠回 403，第 2 步過不去，而這個情境要看的是泊位 1。

## code-review（兩軸）

**Standards 軸**——修掉的：

- 「九步」與「兩顆要二次確認的按鈕」的過期字散在八個地方（`api/setup.py` 的 docstring 更是 OpenAPI description，已經被產進 `web/src/api/schema.d.ts`）。逐處改成七步 / 一顆，重產型別檔。
- 同一段邏輯與同一句理由在 `parser/planner.py` 與 `services/plan.py` 各寫一次（Duplicated Code）：把判準 `episode_span()` 與後果那一句 `SPAN_CLASH_CONSEQUENCE` 抽到 `parser`，比帳本那一半接同一份。
- 「介面上沒有插件那幾支」原本寫在 `scheduled_tasks()` 的 docstring 上，是整個 Protocol 的事實，移到 class docstring。
- `VersionView` / `VersionOut` 的欄位從 `label` 改名 `name`：帳本欄位叫 `jellyfin_version_name`，同一個概念本來有三個詞。
- `FilesPanel` 的 React key 用 `label || tags`，兩個都空時會撞；改用位置。

留著的一條：`JellyfinPublicInfo.supported` 與 `version_supported()` 看起來像 Middle Man，實際是兩個入口——一個手上有回應物件（精靈、健康檢查），一個手上只有存下來的版本字串（`read_jellyfin_status`）。兩邊都要，留著。

**Spec 軸**——修掉的：

- plan §6 的端點清單還列著已經刪掉的 `POST /setup/jellyfin/plugin`、`.impeccable/surfaces/web-src-pages-setuppage-tsx.md` 還記著 MergeVersions 那一列與第二顆確認按鈕：兩處補上。
- 「舊設定 JSON 讀得起來」**沒有閘門**（我原本誤以為既有測試守著）：補了 `test_rows_written_before_mergeversions_was_removed_still_read`。
- pre-plan 沒有比帳本，下載中的預覽看不到涵蓋範圍衝突：`_preplan` 改成與正式那一輪走同一支 `_against_ledger`。
- **比帳本沒有分資料夾**（真缺陷）：同一部作品有兩條 Route 時，A 媒體庫的 `S01E01-E02` 會誤擋 B 媒體庫的 `S01E01`。判定改成以**目標資料夾**為界——那正是 Jellyfin 12 的分組範圍，也與 `inventory._versions` 的版本分組同一條規則。測試的帳本路徑跟著改用產品自己的命名模板算（手寫的那一條少了 `[tmdbid-…]`，根本落在別的資料夾）。
- **版本名只抄一次、之後永遠不更新**（我自己實跑時發現、原本推給 M2）：第二個版本入庫會改掉同一集其他版本的名字，所以 importer 寫下新帳本時，把同一個資料夾裡其他正片重新排一次反查（`_restate_versions`）。畫面上那一組因此會一起更新，而不是一長一短。

留著的一條：adapter 介面連 `/Repositories`、`/Packages`、`/Plugins`、`/System/Restart` 與 fake 的重啟旗標一起刪，嚴格說超出「移除 MergeVersions」的字面範圍。留著是因為那幾支只為插件而存在，留下去就是沒人呼叫的死路徑（全域 CLAUDE.md：內部程式碼改動直接刪舊路徑）。
