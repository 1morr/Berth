# 03b — 補完命令標記：服務連線、設定與讀取這一批模組

**Status:** ready-for-agent

**Blocked by:** 02

**讀:** plan §11.6〈分段〉第 1 段；brief §14；`docs/research/m5-ai-direction-2026-10-27.md` A3 的 R1；票 02 定下的旗標與「要不要人」的規則；`tests/unit/test_command_marks.py` 的 `BEFORE_M3` 豁免表

## 為什麼

`services` 有 219 支公開的 `async def`，其中 139 支沒有標記，全在 `BEFORE_M3` 豁免表的模組裡。登錄表只收有標記的命令。豁免表分兩批清，這是 第二批；另一批是票 03。

## 做什麼

1. 這一批模組：auth、bench、clients、deeplink、discover、health、health_issues、jellyfin、jellyfin_access、jellyfin_images、qbittorrent、routes、search、settings、setup、tmdb、watch、watch_area、watching。
2. 每支公開的 `async def` 都標上 Effect、inverse 與旗標。背景迴圈的入口標 `INTERNAL`。標的依據寫在 docstring，或留下一行說明為什麼。
3. 標的時候發現不該是公開命令的（只有內部用），改成私有，不要硬標。
4. 從豁免表移掉這一批模組。最後一批清完的那張票刪掉整張豁免表，`test_command_marks` 改成守全部 services。
5. 有疑問的標法（可逆性看參數、要不要人有爭議的）列在 Comments，不自己發明新規則。

## 驗收

- [ ] 這一批模組都不在豁免表，`test_command_marks` 守住
- [ ] 每支命令的 inverse 指到存在、而且有標記的命令（閘門已守）
- [ ] 豁免表整張刪掉，閘門守全部 services
- [ ] 全部檢查與 pytest 綠；progress.md 已更新

## Comments

- 2026-10-27（票 02 留）：閘門現在也認 `@asynccontextmanager` 包過的公開函式。這一批模組裡的 `jellyfin_access.jellyfin_access` 會被掃到：只有內部用的改成私有；跨模組要用的鎖或入口標 `INTERNAL`。
- 2026-10-27（票 02 留）：brief §14 說改 Route 永遠要人；`routes.*` 改 Route 的命令要帶 `Flag.SETTINGS`，`needs_person` 才擋得到。
