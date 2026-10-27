# 03b — 補完命令標記：服務連線、設定與讀取這一批模組

**Status:** done

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

- [x] 這一批模組都不在豁免表，`test_command_marks` 守住
- [x] 每支命令的 inverse 指到存在、而且有標記的命令（閘門已守）
- [x] 豁免表整張刪掉，閘門守全部 services
- [x] 全部檢查與 pytest 綠；progress.md 已更新

## Comments

- 2026-10-27（票 02 留）：閘門現在也認 `@asynccontextmanager` 包過的公開函式。這一批模組裡的 `jellyfin_access.jellyfin_access` 會被掃到：只有內部用的改成私有；跨模組要用的鎖或入口標 `INTERNAL`。
- 2026-10-27（票 02 留）：brief §14 說改 Route 永遠要人；`routes.*` 改 Route 的命令要帶 `Flag.SETTINGS`，`needs_person` 才擋得到。
- 2026-10-27（票 03b 做完）：19 個模組的 73 支公開 `async def` 全標上，沒有改私有的（每支都有跨模組或 API 的呼叫端）；`bench`、`clients`、`watch` 沒有公開的 `async def`。`BEFORE_M3` 整張刪掉，閘門守全部 services。判斷過的 24 支釘進 `NAMED`。有疑問的標法：
  - **`auth.sign_in`、`auth.sign_out` 被 API 叫，卻標 `INTERNAL`**：偏離票 03「被 API 叫的不標」。理由是登入、登出是人自己的身分，AI 不該代人做；`Flag.INTERNAL` 的定義沒寫到這一類。`auth.read_session`（API 門禁，不是端點）、`jellyfin_access.jellyfin_access`（API 與 service 共用的入口）同樣標 `INTERNAL`。票 06 做登錄表時定：`INTERNAL` 要不要明寫「身分與門禁」這一類。
  - **`health.check_health`、`health.check_service` 是迴圈的入口，也是 API 的按鈕**（「立即重測」「測試連線」）：照票 03 的 `rss.poll_feed` 先例不標 `INTERNAL`，與做什麼第 2 條「背景迴圈的入口標 `INTERNAL`」字面不合。
  - **在使用者的 Jellyfin 上建東西**：`bootstrap_jellyfin`、`create_libraries`、`add_berth_paths` 標 `IRREVERSIBLE`（Berth 沒有命令收回，brief §16.4 不刪 Jellyfin 的）；`connect_jellyfin` 也會在 Jellyfin 留一把舊 key，但那把 key 使用者看不到、不影響什麼，標 `REVERSIBLE`。兩者都帶 `settings`，`needs_person` 一樣。
  - **`routes.delete_route` 標 `IRREVERSIBLE`**（code-review 兩軸都指出）：只刪得了沒人引用的，category 與子目錄留著，但重建的是新的一條，同 `rss.delete_feed`。`create_route` 的反向因此指到一個不可逆的命令，同 `rss.add_feed`。
  - **`setup.choose_service` 標 `IRREVERSIBLE`，可逆性看參數**：換 qBittorrent 時勾了 `remove_empty_categories` 才移除空分類（同 `leftovers.remove_empty_categories`），照最嚴的標。`setup.complete_setup`、`claim_owner`、`sign_in_existing_owner` 沒有命令回去，標 `IRREVERSIBLE`。
  - **`CONNECTS_OUT` 只給收任意位址的**：`setup.choose_service`、`sign_in_existing_owner`。`claim_owner` 的 `target` 要等於存下、測過的那一台（`_aimed_at`），不帶（code-review 抓到原本標錯）。
  - **沒帶 `settings` 但會寫設定分組的**：`routes.reread_libraries`、`jellyfin.remember_libraries` 照 Jellyfin 現況換掉精靈的媒體庫快照；`setup.retest_service` 對套件內 Prowlarr 重讀掛載的 key。都是同步外部的現況，不是使用者定的規則，所以不帶；登錄表若要更嚴再回來加。
  - **`settings.write_settings`、`update_settings`** 是底層，能寫任何一組，標 `REVERSIBLE` + `internal` + `settings`（照最嚴）。`auth.read_session` 會刪過期的列、`discover.*` 會寫 TMDB 快取，照 `media.read_media` 的先例標 `READ`。
  - **觀察（不在本票範圍）**：作品頁的「標為已看／未看」由 `api/jellyfin.py` 直接呼叫 `JellyfinAccess.mark_played`，不經 services，所以沒有命令、不會進登錄表。研究 05 說標為未看會清掉觀看次數、不可逆；票 06 若要它當工具，要先搬進 services。
