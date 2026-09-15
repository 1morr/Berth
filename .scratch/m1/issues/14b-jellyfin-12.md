# 14b — Jellyfin 12：原生多版本、依版本裝 MergeVersions、釘 image

**Status:** ready-for-agent

**Blocked by:** 無硬相依（2026-09-15 插入，排在 14 之後、15 之前：票 15 的驗收在 12.x 上跑，這些不先修會踩到）

**讀:** brief §7.7、§7.8、§19（2026-09-15 那三列）、§20.9；plan §8.2（`run_task`）、§9.1、§9.3（第 3 步）、§9.4（第 8、9 步）、§9.5、§11.2（T1.10）；`docs/research/jellyfin-12.md` §5（升級阻力在 §4）

## 做什麼

開發途中 Jellyfin 出了 12.0（2026-09-08），套件內的 `latest` 已經是 12.1。查證（brief §20.9）找到四件事：

- 12.x 原生合併劇集的多個版本，MergeVersions 在上面是空跑。
- 「檔案與版本」的劇集版本名是照 10.x + 插件的樣子算的，在 12.x 是錯的。
- 精靈第 3 步的重試在 12.x 回 403，一直卡住，精靈不再冪等。
- 多集檔與同起始集的單集，在 12.x 會被併成一集。

使用者拍板（brief §19）：

- 兩條版本線都支援，**10.x 的支援在 Jellyfin 13.0 正式發佈時拿掉**。
- 套件內 image 釘在 12.1 這條線。
- 多集衝突送審核。

## 驗收

- [ ] 精靈的插件步驟、既有服務的「安裝 MergeVersions」按鈕、resolver 的合併觸發，都依 `public_info.version` 判斷：
  - 12 以上不裝、不觸發，也不寫 `jellyfin_request_failed(request=merge)`；UI 說明 12.x 原生合併。
  - 已經裝好的插件不動。
  - 10.x 行為不變。
  - fake 的兩種版本各有測試。
- [ ] 精靈第 3 步：`POST /Startup/User` 回 403（第一個使用者已有密碼）時，當成已經設過、繼續往下，由之後的登入驗證密碼對不對。fake 模擬這個行為，並補「第 4 步失敗後重試走得完」的測試。
- [ ] 「檔案與版本」的劇集版本名：
  - Jellyfin 已收錄時讀它回的 `MediaSources[].Name`。
  - 還沒收錄時照實說明，不自己重算。
  - 票 13 那個版本名測試的前提同步改掉。
- [ ] planner：新正片與同一季的帳本 Entry、或同一份 Plan 的其他正片，起始集相同而結束集不同時，送 review。
  - 理由要說得出「Jellyfin 12 會把它們併成一集、後面那一集會消失」。
  - 補 benchmark fixture 或單元測試，`berth bench` 的 `auto_wrong` 不升。
- [ ] `deploy/docker-compose.yml` 的 Jellyfin 釘 `lscr.io/linuxserver/jellyfin:version-12.1ubu2604`。README 寫明：
  - 支援的 Jellyfin 版本：12.x 已實測，10.10.7 / 10.11.11 的實測範圍。
  - 只有 10.x 需要 MergeVersions。
  - 升級步驟：先備份 Jellyfin 的 `/config`、升級後完整掃描一次、不能降級。
- [ ] 真環境（票 12 / 13 那一套）換成 12.1 後實跑一次，playwright 附結果：
  - 同一集兩個版本入庫後，在 Jellyfin 是一集兩個來源。
  - 「檔案與版本」顯示 Jellyfin 的版本名。
  - 精靈的 Jellyfin 步驟與健康檢查綠燈。
  - **換 image 前先備份 Jellyfin 與 Berth 的 `/config`**（升級不可逆）。
- [ ] 文件跟著程式改：plan §8.2、§9.3、§9.4、§9.5、§12，README，CHANGELOG；推翻的地方記進 progress.md 的偏差。
- [ ] lint / type / test 全綠並貼指令輸出
