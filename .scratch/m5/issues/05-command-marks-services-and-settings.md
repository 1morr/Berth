# 05 — 命令標記補齊（二）：服務、設定、搜尋與帳號；拆掉豁免表

**Status:** done

**Blocked by:** 04

**讀:** 同 04；brief §16.4（既有服務不被改動：精靈對外部服務的寫入多半不可逆）

## 為什麼

接續 04。這一半大多是精靈、設定與外部服務的命令，寫到別人服務上的通常回不去，要特別小心別標成可逆。標完之後豁免表整個刪掉，以後每個 service 命令一出生就被守。

## 做什麼

1. 標完其餘模組的公開命令：`auth`、`bench`、`clients`、`deeplink`、`discover`、`downloads`、`events`、`health`、`hints`、`jellyfin`（含 `save_bundled_libraries`）、`jellyfin_access`、`jellyfin_images`、`qbittorrent`、`routes`、`search`、`settings`、`setup`、`steps`、`tmdb`、`tracking`、`watch`、`watch_area`、`watching`（約 76 個；沒有公開命令的模組直接拿掉）。
2. 刪掉 `BEFORE_M3` 與用到它的分支，測試 docstring 改成「每個 service 模組都被守」。CLAUDE.md〈架構規則〉那一句同步改（不再有豁免表）。
3. 判不出等級的寫進 Comments，不要猜。

## 驗收

- [x] `BEFORE_M3` 不存在，所有 service 模組的公開命令都有標記，`test_command_marks` 綠
- [x] 寫到外部服務、回不去的命令標成 `irreversible`，有測試列出它們
- [x] CLAUDE.md 架構規則那一句與測試對得上
- [x] 全部檢查、pytest 綠；progress.md 已更新

## Comments

- 等級全部判得出來，沒有留白。判法寫在 `berth/services/commands.py` docstring（改設定與 Route、重建分類、原語）。
- **改了票面模組之外的標記**：`indexer.apply_default_indexers`、`add_recommended_indexers`、`remove_indexer`（反向命令拿掉：加回去的是新的一站）、兩台的 `set_interface_login`、`notify.set_bot_token` / `set_berth_url`、`health_issues.set_min_free`。理由：plan §11.6「irreversible——含改設定、加索引站、Route」與 brief §16.4「只能再設一組蓋過」。
- code-review 兩軸都提的、已改：`jellyfin_access.jellyfin_access`（停用時結束 session）與 `jellyfin.resolve_interface_login`（同 `sign_in` 的登入）改 `irreversible`；`health.check_health` 因「重建分類不算」改 `reversible`，與送單的 `add_manual_download` 對齊。
- 沒處理（判斷題）：
  - `setup.retest_service`、`health.check_service` 標 `read`：重寫的是套件內 Prowlarr 掛載 key 的抄本與測試結論。若登錄表要把「重新測試」當工具，再看一次。
  - `settings.write_settings` / `update_settings` 照最重的標 `irreversible`，可逆的命令（`notify.set_mine`、`indexer.skip_indexers`）也呼叫它們：原語的等級不往上傳，已寫進 docstring。
  - `auth.open_session` 的反向命令 `sign_out` 是 `irreversible`；同票 04 `add_feed` → `delete_feed` 的情形，撤銷要不要確認卡由票 06 / 14 決定。
  - `rss.set_exclusions`（全域）與 `set_feed_interval` / `set_feed_routes` 留 `reversible`：前者是 brief §6.10 的修正回流，後者是單一 Feed 的設定。若使用者認為 Feed 的 Route 指派也算「改 Route」，改標即可。
  - 「改設定（brief §14 永遠要人，M5 票 05）」的註解在四處重複；docstring 已有全文，留著是為了讀那一支時不必跳檔。
  - 名單是封閉的：之後新增的外部寫入或設定命令要自己加進名單（測試檔註明）。
