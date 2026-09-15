# 14b — Jellyfin 12：只支援 12 以上、拿掉 MergeVersions、釘 image

**Status:** ready-for-agent

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

- [ ] **MergeVersions 整段移除**，檔案清單照研究 §5.2 第 1 點：
  - 精靈的插件步驟（plan §9.4 第 8、9 步）與重啟、既有服務的「安裝 MergeVersions」按鈕。
  - resolver 的合併觸發與 `NO_MERGE_TASK`、`JellyfinRequest` 裡 merge 的說明。
  - `settings.services.jellyfin` 的 `merge_movies_task_id` / `merge_episodes_task_id`、`setup.jellyfin.merge_versions_installed`。
  - 前端的步驟與 i18n、fake、fake 設定伺服器的情境、測試。
  - 既有 Jellyfin 上已經裝好的插件不動。
  - 資料庫裡已存的設定 JSON 還帶著那幾個鍵：確認讀得起來，讀不起來就用 Alembic 清掉，不在 model 留相容欄位。
- [ ] **版本下限**：精靈的 Jellyfin 步驟（套件內與既有）與健康檢查讀 `/System/Info/Public` 的 `Version`，低於 12.0 就紅燈、不往下做。
  - 訊息說出目前的版本、需要 12 以上，並附升級注意：先完整備份、移除第三方插件、升級後完整掃描、不能降級（brief §20.9）。
  - fake 回 `10.11.11` 時，精靈停在那一步、健康檢查紅燈，各有測試。
- [ ] 精靈第 3 步：`POST /Startup/User` 回 403（第一個使用者已有密碼）時，當成已經設過、繼續往下，由之後的登入驗證密碼對不對。fake 模擬這個行為，並補「第 4 步失敗後重試走得完」的測試。
- [ ] 「檔案與版本」的劇集版本名：
  - Jellyfin 已收錄時讀它回的 `MediaSources[].Name`。
  - 還沒收錄時照實說明，不自己重算。
  - 票 13 那個版本名測試的前提同步改掉。
- [ ] planner：新正片與同一季的帳本 Entry、或同一份 Plan 的其他正片，起始集相同而結束集不同時，送 review。
  - 理由要說得出「Jellyfin 12 會把它們併成一集、後面那一集會消失」。
  - 補 benchmark fixture 或單元測試，`berth bench` 的 `auto_wrong` 不升。
- [ ] `deploy/docker-compose.yml` 的 Jellyfin 釘 `lscr.io/linuxserver/jellyfin:version-12.1ubu2604`。README 寫明：
  - Jellyfin 版本下限 12.0。
  - 從 10.x 升級的注意事項（§20.9 的升級阻力）。
  - 套件內 Jellyfin 之後怎麼升級。
  - BTH 步驟表、外部服務前提、fake 情境列裡的 MergeVersions 一併拿掉。
- [ ] 實跑：
  - 真環境（票 12 / 13 那一套）換成 12.1：同一集兩個版本入庫後，在 Jellyfin 是一集兩個來源；「檔案與版本」顯示 Jellyfin 的版本名；精靈的 Jellyfin 步驟與健康檢查綠燈。
  - **換 image 前先備份 Jellyfin 與 Berth 的 `/config`**（升級不可逆）。
  - 以 fake 設定伺服器的 10.11 情境，用 playwright 看精靈的版本下限訊息。
- [ ] 文件跟著程式改：plan §2.1（`merge_*_task_id`、`setup.jellyfin`）、§3.1、§3.2、§8.2、§9.3、§9.4、§9.5、§11.2 T1.6、§12，README，CHANGELOG；推翻的地方記進 progress.md 的偏差。
- [ ] lint / type / test 全綠並貼指令輸出
