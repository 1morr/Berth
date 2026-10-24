# 04 — 命令標記補齊（二）：服務、設定、搜尋與帳號；拆掉豁免表

**Status:** ready-for-agent

**Blocked by:** 03

**讀:** 同 03；brief §16.4（既有服務不被改動：精靈對外部服務的寫入多半不可逆）

## 為什麼

接續 03。這一半大多是精靈、設定與外部服務的命令，寫到別人服務上的通常回不去，要特別小心別標成可逆。標完之後豁免表整個刪掉，以後每個 service 命令一出生就被守。

## 做什麼

1. 標完其餘模組的公開命令：`auth`、`bench`、`clients`、`deeplink`、`discover`、`downloads`、`events`、`health`、`hints`、`jellyfin`（含 `save_bundled_libraries`）、`jellyfin_access`、`jellyfin_images`、`qbittorrent`、`routes`、`search`、`settings`、`setup`、`steps`、`tmdb`、`tracking`、`watch`、`watch_area`、`watching`（約 76 個；沒有公開命令的模組直接拿掉）。
2. 刪掉 `BEFORE_M3` 與用到它的分支，測試 docstring 改成「每個 service 模組都被守」。CLAUDE.md〈架構規則〉那一句同步改（不再有豁免表）。
3. 判不出等級的寫進 Comments，不要猜。

## 驗收

- [ ] `BEFORE_M3` 不存在，所有 service 模組的公開命令都有標記，`test_command_marks` 綠
- [ ] 寫到外部服務、回不去的命令標成 `irreversible`，有測試列出它們
- [ ] CLAUDE.md 架構規則那一句與測試對得上
- [ ] 全部檢查、pytest 綠；progress.md 已更新
