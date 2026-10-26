# 05 人工點與命令登錄表現況盤點

盤點日期 2026-10-27，commit `5fc0bbc8`（v0.3.0 之後）。唯讀盤點，沒有改程式碼。名詞照 `CONTEXT.md`。
標記欄寫法：`R`＝`Effect.READ`、`V`＝`REVERSIBLE`、`I`＝`IRREVERSIBLE`；「未標」＝函式在 `tests/unit/test_command_marks.py` 的 `BEFORE_M3` 豁免模組裡、沒有 `@command`。
「可逆？」是我的判斷，與標記無關（標記欄單獨列，兩者不一致處在最後的觀察裡）。

## A. 所有需要人的點

後端人工動作的實際進入點是 `berth/api/*.py` 的端點，函式欄寫的是端點呼叫的 `services` 函式。
`berth/api/gate.py` 把 `/settings /routes /jellyfin/libraries /issues /reconcile /review /files /rss /weekly` 整段列為 admin，
另有 `DELETE /jobs/*`、`GET /jobs/*/deletion`、`POST /jobs/*/reimport`、`PUT /plans/*/items`、`POST /plans/*/approve|reject` 為 admin。

### A.1 入庫要人決定（Review Queue，`/review`，admin）

觸發：`services.review.queue_keys` 列出的四種 `ReviewKind`（`plan`、`audit`、`unmatched`、`duplicate`）。

| # | 點 | 頁面 / 路由 | 觸發條件 | 人能做的動作 | 對應 service 函式 | 標記 | 可逆？ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 低信心 Plan | `/review`（`review/PlanRow.tsx`，`plans/PlanEditor.tsx`） | Job 在 `review`，Plan 因七種 `ReviewReason` 之一停下（`low_confidence`、`medium_not_allowed`、`nothing_to_import`、`target_exists`、`audit_undone`、`air_date_conflict`、`runtime_conflict`） | 逐列改（季、集、action）；核准；套用到 RSS Series | `plan_review.edit_items`；`correct_series_from_plan`（套用到 Series 時，在 `api/plans.py` 內） | 未標；`series_review.correct_series_from_plan` V（無 inverse） | 可逆：編輯只改 Plan；落地前沒動檔案 |
| 2 | 核准 Plan | 同上 | 同上 | 「核准」 | `plan_review.approve_plan(session, hub, plan_id, *, actor)`（之後 API 層叫 `imports.nudge()`） | 未標 | 可逆：寫的是硬鏈接，原檔在 complete，可 `review.undo_audit` 或 rematch；但 `undo_audit` 自己丟掉帳本列，「原樣再核准」不行 |
| 3 | 重新規劃（舊稱拒絕） | 同上 | 同上 | 「重新規劃」，端點仍叫 `reject` | `plan_review.reject_plan`（API 叫 `plans.nudge()`） | 未標 | 可逆：只是丟掉這份 Plan 重算，檔案不動；但丟掉人逐列改的內容 |
| 4 | 已入庫待確認（Audit） | `/review` audit 段（`review/AuditRow.tsx`、`AuditGroup.tsx`） | medium 自動入庫後 `ledger.audit` 掛旗標；RSS Series 第一批（`confirmed = false`）high 也掛 | 確認；撤銷；「修正」（rematch）；整組「全部確認」 | `review.confirm_audit`、`review.confirm_audits`（批次）、`review.undo_audit`、`series_review.confirm_series`（一組）、`rematch.rematch_file` | 前四個 V（`confirm_*` inverse＝`review.undo_audit`；`undo_audit`、`confirm_series` 無 inverse）；`rematch_file` 未標 | `confirm` 可逆（有 `undo_audit`）；`undo_audit` 實質不可逆（拆鏈接、刪帳本列、Job 回 review，不能原樣重來），標成 V 可疑 |
| 5 | Unmatched 檔案 | `/review` unmatched 段（`review/UnmatchedRow.tsx` → `components/RematchForm.tsx`） | Plan Item `action = unmatched`，檔案留在 complete | 指派到某一集 / 標為 Extra / 忽略 | `rematch.rematch_file(..., job_file_id=…, to: Assignment, actor)` | 未標 | 可逆：一律經 Plan，可再 rematch 回去（「忽略」也是 rematch action） |
| 6 | 重複版本（Duplicate） | `/review` duplicate 段（`review/DuplicateRow.tsx`） | 新 Plan Item 與帳本既有一份同集同 Tags 或同起始集 | 取代舊版 / 保留兩者 / 跳過 | `duplicates.decide_duplicate(session, factory, item_id, decision: DuplicateDecision, *, actor)` | 未標 | 「取代」不可逆（舊硬鏈接被換掉，來源仍在 complete，可 reimport 補回，但舊版的帳本與命名沒了）；「保留兩者」「跳過」可逆 |
| 7 | 第一批確認（RSS Series） | `/review` audit 段，以 Series 分組 | RSS Series `confirmed = false`，且 `first_batch.vouch` 說證據不夠強不能由系統確認 | 「全部確認」；在第一批改正一集並套用到 Series | `series_review.confirm_series`、`series_review.correct_series`；系統版是 `first_batch.confirm_by_batch` | V（無 inverse） | `confirmed` 旗標本身沒有「取消確認」命令，原始碼註解自己說 M5 再決定 |

### A.2 Issue（`/issues`，admin）

觸發：`issues` 表 `status = open`；十九種 `IssueType`。動作表在 `berth/domain/enums.py` 的 `ISSUE_ACTIONS`，一律經 `issues.resolve_issue(session, factory, issue_id, action: IssueAction, *, actor, plans, media="")`，另外「忽略」經 `issues.ignore_issue(session, issue_id, *, actor)`。
這兩個函式**都沒標**（`issues` 在豁免表，模組內只標了 `count_open`、`open_issues`、`still_ignored` 三個 R）。因此下表的「標記」欄對 resolve 類動作都是「未標」，可逆性是逐 `IssueAction` 判斷。

| # | Issue 型別 | 觸發條件 | 人能按的（`IssueAction`） | 可逆？（`ACTION_DELETES` 為準） |
| --- | --- | --- | --- | --- |
| 1 | `library_link_missing` | 帳本有、媒體庫目標檔不在 | `relink`；`forget`；`delete_complete` | relink 可逆；forget 刪帳本列（可由 `rebuild_ledger` 補回，算可逆）；`delete_complete` **不可逆**（走 `deletion.delete_job` 四旗標） |
| 2 | `source_missing` | 帳本有、complete 來源不在 | `mark_sourceless` | 可逆性偏低：帳本列改成 `source_missing`，不會再開 Issue；沒有反向動作 |
| 3 | `inode_mismatch` | 目標與來源不是同一 inode | `replace_with_link`（只在大小一致時給） | **不可逆**（複製品被換掉，`ACTION_DELETES=True`） |
| 4 | `orphan_complete` | complete 底下有目錄無人認領 | `delete_orphan`；`adopt`（要選作品） | `delete_orphan` **不可逆**；`adopt` 可逆（只加 Job、鏈接、帳本列） |
| 5 | `unknown_torrent` | qBittorrent 有 Berth category/tag 的 torrent 但無 Job | `claim_torrent`（要選作品） | 可逆（只加東西） |
| 6 | `unmanaged_library_file` | 媒體庫有非 Berth 建立的檔案 | `claim_file` | 可逆（只加帳本列）；「永不刪」由 `test_issue_types.py` 守 |
| 7 | `job_without_files` | Job 已 imported 但帳本一列都沒有 | `replan` | 可逆 |
| 8 | `missing_files` | 客戶端說檔案不見了 | `recheck`；`accept_loss` | recheck 可逆；`accept_loss` 讓 Job 進 `removed`（四旗標全不勾，磁碟不動），算可逆性低（沒有「取消承認」） |
| 9 | `client_error` | qBittorrent state `error` | `retry` | 可逆 |
| 10 | `client_removed` | torrent 從客戶端消失 | `resubmit`；`accept_removal` | resubmit 可逆（再送一次）；`accept_removal` 同 `accept_loss` |
| 11 | `jellyfin_item_unresolved` | 反查六次仍找不到 item | `relook`；`rescan` | 可逆 |
| 12 | `jellyfin_item_mismatch` | Jellyfin 回驗：季集或 TMDB id 與帳本不符 | `relook` | 可逆；修法在 Jellyfin 裡，Berth 只有「再比一次」 |
| 13 | `library_uses_tvdb`、`low_disk_space` | 健康檢查量到 | 無（動作表是空 tuple），條件解除由系統收 | 只能「忽略」 |
| 14 | `first_batch_stuck`（巡檢） | RSS Series 第一批的 Job 卡在 `submit_failed` / `client_error` 超過門檻 | 無；出路是去 Job 頁重試或刪，或去審核頁確認 Series | 動作在別的頁，見 A.3、A.1 #7 |
| 15 | `feed_poll_failing`、`feed_backfill_failing`（巡檢） | Feed 輪詢或每日補漏失敗超過一天 | 無；去 `/rss` 修 Feed 網址 | 設定類，見 A.5 |
| 16 | `series_episodes_missing`（巡檢） | RSS Series 已入庫的集數中間缺 | 無；去作品頁搜缺的集 | 見 A.6 |
| 17 | `series_episodes_collide`（巡檢） | 同一 Series 兩個發佈名寫不同集入庫成同一集 | 無；去作品頁 rematch | `rematch.rematch_file`（未標） |
| — | 任一型別的「忽略」 | open | `ignore` | 可逆，但會把問題藏起來；巡檢 5 種、健康 2 種、回驗 1 種與 `unknown_torrent` 的忽略在條件持續期間有效，其餘每天重開（`record_issue`） |
| — | 立即對帳 / 重建帳本 | `/issues` 頁頭 | 「立即對帳」（`POST /reconcile`）；「重建帳本」（`POST /issues/rebuild-ledger`） | `reconcile.reconcile_once` 未標；`ledger_rebuild.rebuild_ledger` V（無 inverse）、`read_ledger_gap` R |

`IssueAction` 共 17 個，其中 `delete_complete`、`replace_with_link`、`delete_orphan` 三顆 `ACTION_DELETES=True`。

### A.3 下載頁「需要人」（`/jobs`、`/jobs/$hash`）

篩選器 `JobFilter.ATTENTION`（`services/jobs.py` `_ATTENTION`，與前端 `web/src/jobs/jobState.ts` 對齊，`tests/unit/test_job_filters.py` 守）：`submit_failed`、`stalled`、`missing_files`、`client_error`、`review`、`import_failed`。動作只住在 Job 詳情頁（`jobs/JobActions.tsx`），顯示與否由後端旗標 `retryable` / `replannable` / `reimportable` 決定。

| # | 狀態 | 詳情頁上的動作 | 對應 service 函式 | 標記 | 可逆？ |
| --- | --- | --- | --- | --- | --- |
| 1 | `submit_failed` | 重試（`retryable`） | `jobs.retry_job(session, factory, job_hash)` | 未標 | 可逆：再送一次存下來的連結；成功後就是送出 torrent，之後只能刪 |
| 2 | `import_failed` | 重試（從沒鏈接的接著做） | `jobs.retry_job`（同一端點） | 未標 | 可逆（鏈接可拆） |
| 3 | `stalled` | **沒有 Job 頁動作**（`RETRYABLE` 只含 `submit_failed`、`import_failed`）；只剩刪除 | `deletion.delete_job` | 未標 | 見下 |
| 4 | `missing_files`、`client_error` | Job 頁沒有重試鍵；動作在對應的 Issue（A.2 #8、#9） | `issues.resolve_issue(RECHECK / RETRY)` | 未標 | 可逆 |
| 5 | `review` | 重新規劃（admin）；核准在 `/review` | `plan.replan_job(session, factory, hub, job_hash, *, role)` | 未標 | 可逆 |
| 6 | `completed` / `planning`（卡住時） | 重新規劃 | 同上 | 未標 | 可逆 |
| 7 | 可重新入庫的狀態（`REIMPORTABLE`，且 `completed_at` 非空） | 重新入庫（admin） | `reimport.reimport_job(session, job_hash, *, actor)` | 未標 | 可逆（走正常規劃入庫） |
| 8 | 任何狀態（admin） | 刪除，四旗標 `unlink`、`remove_torrent`、`delete_files`、`purge`，預設全不勾，有就地確認區（`jobs/JobDelete.tsx`，`components/ConfirmPanel.tsx`） | `deletion.estimate_deletion`（R 性質）、`deletion.delete_job(session, factory, job_hash, scope: DeleteScope, *, actor)` | 兩個都未標 | `delete_files`、`purge` **不可逆**；只勾 `unlink` 或只勾 `remove_torrent` 時可逆程度較高（`remove_torrent` 仍不可逆：torrent 與做種狀態沒了） |

### A.4 RSS（`/rss`，admin）

| # | 點 | 觸發條件 | 人能做的 | 對應 service 函式 | 標記 | 可逆？ |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 待綁定的 RSS Series | 自動綁定失敗（名字、開播日、唯一性不成立），帶「理由 + 候選」；Feed Item 留著不送 | 選作品與 Route 後綁定（`rss/SeriesBinder.tsx`），可一鍵選候選 | `rss.bind_series(session, factory, series_id, *, media_id, route_id, user_id, now)` | V，inverse＝`rss.unbind_series` | 綁定可逆，但會**補舊集並送單**（`unbind_series` 自己註明不收回已送出的 Job），所以實質有不可逆的副作用 |
| 2 | 解除綁定 | 綁錯 | 「解除綁定」 | `rss.unbind_series` | V，inverse＝`rss.bind_series` | 同上 |
| 3 | 被排除的 Feed Item | 命中排除條件（`excluded`） | 逐筆「照樣下載」 | `rss.release_item(session, factory, item_id, *, user_id)` | V（無 inverse） | 送出 torrent 後不可收回，標 V 可疑 |
| 4 | 第一輪預覽（priming） | 新搜尋 Feed（Nyaa、acg.rip）`primed_at` 為空 | 「全部下載」或「只追之後的」 | `rss.prime_feed(…, mode: PrimeMode)` | I | 不可逆（選的那一刻記在 Feed 上，`all` 會送出一批） |
| 5 | 排除條件、Feed 間隔、Feed Route、刪除 Feed | 設定 | 編輯 / 刪除 | `rss.set_exclusions`、`set_feed_exclusions`、`set_series_exclusions`、`set_feed_interval`、`set_feed_routes`、`delete_feed` | 皆 V；`delete_feed` inverse＝`add_feed` | 設定類；`delete_feed` 連同 Feed Item 紀錄，`add_feed` 不是真反向 |
| 6 | 一次性 RSS 連結 | 貼網址 | 讀出一批、勾選送出 | `oneshot.read_oneshot`（R）+ `downloading.add_manual_download`（V） | 如左 | 送出的 Job 同一般手動送單 |
| 7 | 訂閱 | 作品頁「訂閱」 | Mikan / 搜尋型 Feed | `rss.subscribe_mikan`、`rss.subscribe_search` | V；`subscribe_search` inverse＝`rss.delete_feed`，`subscribe_mikan` 無 | 同上 |

### A.5 設定、精靈、健康（admin）

這一類是人**自己決定要設什麼**，不是「等人處理」；brief §14 把「改設定與 Route」列為永遠要人。

| # | 點 | 頁面 / 路由 | 人能做的 | 對應 service 函式 | 標記 | 可逆？ |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 精靈（五個泊位：Jellyfin、qBittorrent、媒體庫路徑、Prowlarr、TMDB） | `/setup`（`pages/SetupPage.tsx`、`web/src/setup/*`） | 選 Service Origin（套件內 / 既有）、填位址與憑證、建 Route、選索引站、貼 TMDB key | `setup.*`、`jellyfin.*`、`qbittorrent.*`、`routes.create_route`、`indexer.*`、`tmdb.verify_tmdb` | 幾乎未標（`setup`、`jellyfin`、`qbittorrent`、`routes` 在豁免表；`indexer.*` 已標；`setup.resolve_bundled` R；`qbittorrent.set_interface_login` V） | 憑證與 Route 可改；Jellyfin 管理員建立、API key 建立等有外部副作用 |
| 2 | 設定分頁 | `/settings/{jellyfin,qbittorrent,routes,indexers,tmdb,notifications}`（`pages/*SettingsPage.tsx`） | 重測、換憑證、換 Route、換介面登入、不用 Prowlarr、Jellyfin 對外網址、最低剩餘磁碟 | `settings.*`（`deeplink.set_public_url`、`health_issues.set_min_free`、`health.check_service`）、`routes.update_route`／`delete_route`／`check_route(s)`、`indexer.skip_indexers`、`indexer.remove_indexer` | 見 B；多數未標 | Route 刪除、`indexer.remove_indexer` 可疑 |
| 3 | 通知設定 | `/settings/notifications` | 填 bot token、Berth 對外網址、個人 Discord ID 與訂閱種類、送測試 | `notify.set_bot_token`、`set_berth_url`、`set_mine`（V）、`send_test`（I）、`read_*`（R） | 已標 | 設定可逆；`send_test` 對外發訊息 |
| 4 | 殘留 qBittorrent 分類 | 精靈 / 設定的 leftover 清單（`setup/LeftoverList.tsx`） | 移除空的 `berth-*` 分類 | `leftovers.remove_empty_categories` | I | 不可逆（但只刪空分類） |
| 5 | 健康頁 | `/health` | 「立即重測」；Route 紅燈時去設定 | `health.check_service`、`routes.check_routes` | 未標 | 唯讀性質 |

### A.6 作品頁上的人工動作（使用者主動，不是「等人」，但同樣要列進命令面）

| 動作 | 位置 | service 函式 | 標記 |
| --- | --- | --- | --- |
| 搜尋 Search Result 並送單 | `media/SearchPanel.tsx`、`SubmitAction.tsx` | `search.search_torrents`（未標）、`downloading.add_manual_download`（V，無 inverse） | 混 |
| 開關 Search Name | `QueryChoices.tsx` | `search.remember_names`（V，inverse 指向自己） | V |
| 搜缺的集（Missing Episode Search，分批「問下一批」） | `media/missing.ts`、`SeasonsPanel.tsx` | `search.plan_queries` 等（未標） | — |
| 修正（rematch）已入庫檔案 | `media/FilesPanel.tsx` | `rematch.rematch_file` | 未標 |
| 重新反查 | `api/media.ts` `resolveEarly` | `resolver.resolve_early` | V |
| 標為已看 / 未看（會清掉觀看次數，先確認） | `media/WatchArea.tsx`、`api/jellyfin.ts` `markPlayed` | `watch.*`（`watch` 模組在豁免表，且沒有 `async def` 命令） | 未標；標為未看**不可逆**，對 Jellyfin 的使用者資料寫入 |
| 重新整理 TMDB | `api/media.ts` `refresh` | `media.refresh_media` | 未標 |

### A.7 「等你處理」通知與巡檢

| 點 | 觸發 | 動作 | 函式 | 標記 |
| --- | --- | --- | --- | --- |
| 「有 N 件等你處理」 | `notify_sender` 迴圈每 10 秒看三份清單（`review.queue_keys`、`issues.open_issues`、`rss.unbound_series`，合成 `waiting.waiting_now`）與上一輪比，新出現的寫進 `notifications` | 看訊息、點連結到 `/review#audit-12` 等錨點 | `notify.watch_waiting`（寫待送表）、`notify.send_due`（送）、`waiting.waiting_now`（R） | `watch_waiting`、`send_due` 都標 I，`waiting_now` R |
| 放太久提醒 | `sweeping` 每日 05:00，最舊一件等滿 3 天 | 同上 | `sweep.sweep_once`（I）→ `notify.queue_lingering`（I） | I |
| 巡檢開的 Issue | 同 A.2 的 14–17 | 見 A.2 | `sweep.sweep_once` | I |
| 週報 | 每週一巡檢後 | 看 `/weekly`、點連結 | `weekly.compose_weekly`（I）、`read_report`、`list_reports`、`has_reports`（R） | 已標 |

## B. 命令登錄表的現況

### B.1 裝飾器與儲存

檔案：`berth/services/commands.py`（約 70 行）。

- `Effect(StrEnum)`：`READ`、`REVERSIBLE`、`IRREVERSIBLE`。
- `@dataclass(frozen=True, slots=True) class CommandMark: effect: Effect; inverse: str | None = None`。
- `command(effect, *, inverse=None)`：只做 `setattr(function, "__berth_command__", CommandMark(...))`，**函式原樣回傳，不包一層**。反向命令寫成字串 `"<模組>.<函式>"`（相對 `berth.services`）。
- `mark_of(function) -> CommandMark | None`：唯一的讀取方式。
- 檔頭自己說：「這裡只有標記——不收集、不查詢，登錄表本身在 M5 做。」

結論：**沒有可列舉的登錄表**。要列舉得自己 `pkgutil.iter_modules(berth.services.__path__)`＋`inspect` 掃全部模組（`tests/unit/test_command_marks.py` 的 `service_modules()` / `commands_of()` 就是這樣做），而且 `commands_of` 只認「模組自己定義的公開 `async def`」。每一筆只存 `effect` 與 `inverse` 兩個欄位。沒有存：名稱（靠模組名＋函式名推）、輸入 schema、輸出型別、拒絕理由（各模組的例外類別）、說明文字（只有 docstring）、誰能呼叫（admin 與否在 `api/gate.py`）。

### B.2 豁免表

`BEFORE_M3` 共 **41 個模組**：`auth`、`bench`、`claims`、`clients`、`complete`、`deeplink`、`deletion`、`discover`、`downloads`、`duplicates`、`events`、`health`、`health_issues`、`hints`、`importer`、`inventory`、`issues`、`jellyfin`、`jellyfin_access`、`jellyfin_images`、`jobs`、`media`、`plan`、`plan_review`、`plan_view`、`qbittorrent`、`reconcile`、`reimport`、`rematch`、`resolve_schedule`、`resolver`、`routes`、`search`、`settings`、`setup`、`steps`、`tmdb`、`tracking`、`watch`、`watch_area`、`watching`。

`berth/services` 共 60 個模組（含 `commands` 本身），公開 `async def` 共 **219** 個，其中 **80 個已標、139 個未標**；139 個全在豁免模組內。
豁免模組內部分已標：`issues` 3/8、`qbittorrent` 1/8、`resolver` 1/4、`search` 1/3、`setup` 1/9，其餘 0。
最大缺口：`jobs` 14、`routes` 13、`jellyfin` 9、`setup` 8、`issues` 5、`health` 7、`claims` 6、`plan` 6、`rematch` 6、`qbittorrent` 7、`auth` 5、`media` 5。

**豁免表裡的模組，剛好是所有「人工動作」的主體**（`plan_review`、`issues`、`rematch`、`duplicates`、`deletion`、`jobs`、`reimport`、`plan`、`routes`、`claims`）。M3 之後新增的模組（`review`、`rss`、`series_review`、`first_batch`、`notify`、`sweep`、`weekly`、`indexer` 等）才有標。

### B.3 已標命令統計

`@command(` 出現 81 次；其中 `downloading.download_round` 是 `@asynccontextmanager`，不是 coroutine function，`commands_of` 掃不到它，所以掃得到的是 80。

| Effect | 數量（含 `download_round`） |
| --- | --- |
| `READ` | 36 |
| `REVERSIBLE` | 34 |
| `IRREVERSIBLE` | 11 |
| 合計 | 81 |

有 `inverse=` 的 V 命令共 9 個：`indexer.skip_indexers`→自己、`indexer.remove_indexer`→`indexer.apply_default_indexers`、`review.confirm_audit`／`confirm_audits`→`review.undo_audit`、`rss.add_feed`→`rss.delete_feed`、`rss.delete_feed`→`rss.add_feed`、`rss.bind_series`↔`rss.unbind_series`、`rss.subscribe_search`→`rss.delete_feed`、`search.remember_names`→自己。其餘 25 個 V 沒有 inverse。

**所有標成 `irreversible` 的**（11 個）：

| 命令 | 實際是什麼 |
| --- | --- |
| `downloading.download_round` | 一輪「正在下載」通知的 context manager |
| `downloading.queue_downloading` | 寫「正在下載」待送列 |
| `leftovers.remove_empty_categories` | 刪 qBittorrent 空的 `berth-*` 分類 |
| `notify.send_test` | 對 Discord 送測試訊息 |
| `notify.queue_ready` | 寫「可以看了」待送列 |
| `notify.watch_waiting` | 寫「等你處理」待送列 |
| `notify.queue_lingering` | 寫「放太久」待送列 |
| `notify.send_due` | 送出迴圈一輪 |
| `rss.prime_feed` | 第一輪預覽的選擇 |
| `sweep.sweep_once` | 每日巡檢一輪 |
| `weekly.compose_weekly` | 產生週報 |

其中 10 個是**系統背景迴圈或對外發訊息**，不是 AI 要呼叫的命令；真正會刪資料的（`deletion.delete_job`、`issues.resolve_issue(delete_complete / delete_orphan / replace_with_link)`、`routes.delete_route`）一個都沒標。

### B.4 簽名形狀

共通形狀（`services` 層沒有 pydantic，輸入是散參數、`Enum`、dataclass；pydantic 只在 `berth/api/*.py` 的 `…In` 模型）：

- 第一個參數永遠是 `session: AsyncSession`，**呼叫端提供**；命令內部自己 `commit()`（例如 `resolve_issue`、`approve_plan`），不是 unit-of-work 由外層管理。
- 需要外部服務的多一個 `factory: ServiceClientFactory`（`services/clients.py` 的 Protocol：`jellyfin() / qbittorrent() / prowlarr() / tmdb() / torrent()`）。
- 要寫事件的帶 keyword-only 的 `actor: str`（`jobs.actor_of(user_id)` 產生，值是 user id 字串或 `"system"`，docstring 預告 `ai` 在 M5）；RSS 那一批用 `user_id: int | None`，另一批用 `role: Role`。**沒有統一的 caller / actor 型別**。
- 要叫醒迴圈的，**喚醒在 API 層做**（`imports.nudge()`、`plans.nudge()` 來自 `ImportHintsDep` / `PlanHintsDep`），service 函式只讓狀態落地；有的把 `hub: EventHub` 當參數。
- 拒絕＝**每個模組自己一個例外類別**，形狀都是 `(reason: <封閉集合 StrEnum>, detail: str)`，**沒有共同基類**：`PlanRejectedError`、`IssueRejectedError`、`ReviewRejectedError`、`RematchRejectedError`、`RssRejectedError`、`JobRejectedError`、`ClaimRejectedError`、`NotifyRefusedError`、`OwnerRejectedError`、`PublicUrlRejectedError`（`ValueError` 子類，只有原文）。API 層的 `*_refusal()` 函式把它轉成 `HTTPException`。
- 回傳是 service 層自己的 dataclass（`PlanView`、`IssueView`、`JobView`、`SeriesView`、`AuditUndone`、`RematchOutcome`…），沒有統一的結果包裝。

三個代表：

```python
# berth/services/review.py:347 —— 最簡單的一種
@command(Effect.REVERSIBLE, inverse="review.undo_audit")
async def confirm_audit(session: AsyncSession, ledger_id: int, *, actor: str) -> None:

# berth/services/rss.py:2042 —— 帶外部服務與 user_id，內部起「正在下載」一輪
@command(Effect.REVERSIBLE, inverse="rss.unbind_series")
async def bind_series(
    session: AsyncSession, factory: ServiceClientFactory, series_id: int,
    *, media_id: str, route_id: int, user_id: int | None, now: datetime | None = None,
) -> SeriesView:

# berth/services/issues.py:319 —— 一個函式吞十七種動作（未標）
async def resolve_issue(
    session: AsyncSession, factory: ServiceClientFactory, issue_id: int,
    action: IssueAction, *, actor: str, plans: JobHints | None = None, media: str = "",
) -> IssueView:
```

另兩個對照：`plan_review.approve_plan(session, hub: EventHub, plan_id, *, actor)`（未標，要 hub）、`rematch.rematch_file(session, factory, *, ledger_id=None, job_file_id=None, to: Assignment, actor)`（未標，二選一參數＋dataclass）。

要包成 AI 工具 / MCP 工具要補的：(1) 從簽名產生 JSON schema（沒有 pydantic 輸入模型，`Enum` 與 dataclass 可轉，`AsyncSession` / `factory` / `hub` / `JobHints` 要由執行器注入而不暴露）；(2) 統一 `actor`／`user_id`／`role` 三種身分參數；(3) 一個把各模組例外轉成統一「拒絕理由」的層；(4) 把 API 層做的 `nudge()` 與 `hub.publish` 移進命令或讓執行器補；(5) 每個命令的名稱、說明、admin 與否的登錄資料（目前散在 docstring 與 `api/gate.py`）。

### B.5 現有 LLM / AI 程式碼

grep `anthropic|openai|llm|settings.ai|ai_` 於 `berth/`、`tests/`、`web/src`、`pyproject.toml`：**沒有任何 provider SDK、設定鍵或依賴**。僅有的是：

| 檔案 | 內容 |
| --- | --- |
| `berth/adapters/ai.py`（50 行） | `AiPlanner` Protocol（`propose(context, files, rules_plan) -> Plan \| None`）與 `NullAiPlanner`（永遠回 `None`）。M1 定的介面，「實作在 M4」的承諾沒做；**`services` 沒有任何地方用它**（只有 `tests/unit/test_ai.py` import） |
| `berth/services/jobs.py` 的 `actor_of` docstring | 預告 `ai` 這個 actor 值在 M5 |
| `docs/design-brief.md` §6.10、§14 | 設計 |

其他 grep 命中（`parser/cjk.py`、`services/notify.py`、`host_mount.py`、測試 fixture）是字串巧合（「llm」出現在別的單字裡、`ai` 出現在日文假名或 Discord 文字中），不是 AI 程式碼。

`AiPlanner.propose` 的形狀（收 Plan、回同型 Plan，單一任務型別）與 brief §6.10 / §14 後來的「AI 任務＝資料包＋工具＋預算」不一致，M5 多半要重做，不是填實作。

## C. 通知與頻道

### C.1 現況

- **通道**：Discord bot **私訊**，`berth/adapters/notify/discord.py` 的 `HttpDiscordBot`。純 REST（`POST /users/@me/channels` 開 DM channel、`POST /channels/{id}/messages` 送 embed），**不連 gateway、不需要 intent**。沒有 webhook、沒有頻道訊息（2026-10-21 決定不做）。
- **能不能收訊息**：不能。Protocol 只有 `NotifyChannel.send(recipient, Message) -> Delivery` 與 `DiscordBot.identify() -> BotIdentity`（`GET /applications/@me`）。沒有 gateway 連線、沒有 interactions endpoint、沒有 message component（按鈕）支援；`Message` 只有 `title / description / fields / links`。`adapters/notify/__init__.py` 與 `fake.py`（`FakeDiscordBot`）同形。
- 失敗處理：`Delivery(failure: DeliveryFailure, detail, retry_after, whole_channel)`，不丟例外；403/50278、50007 分類為「到不了」。
- **服務層**：`berth/services/notify.py`（1169 行）。`Notification Outbox`＝`berth/models/notification.py` 的 `notifications` 表，與觸發的狀態變更同交易；送出迴圈 `pipeline/notifying.py`（`notify_sender`，每 10 秒）。四種 `NotificationKind`：`ready`、`downloading`、`waiting`（admin）、`weekly`（admin）。合併窗：寫入後最早 5 分鐘送，同收件人 × 作品 × Route 合併；「等你處理」10 分鐘；24 小時送不到放棄。訊息文案在 `notify.py` 內以 `zh-Hant` / `en` 兩個字典，送出時照收件人語言組。

### C.2 每人訂閱資料形狀

`berth/models/auth.py` 的 `users` 表直接帶欄位，沒有另開訂閱表：

| 欄位 | 型別 | 意義 |
| --- | --- | --- |
| `discord_user_id` | `Text`，預設 `""` | snowflake（17–20 位數字），空字串＝不收 |
| `notify_language` | `Language` enum | 存 Discord ID 那一刻的介面語言 |
| `notify_kinds_json` | `JsonText`（`list[str]`），預設 `["ready"]` | 訂閱的 `NotificationKind` 值 |
| `notify_unreachable_at` / `notify_unreachable_detail` | `UtcDateTime?` / `Text` | 上次 Discord 說到不了 |

非 admin 的 `set_mine` 會把 `ADMIN_ONLY_KINDS`（`waiting`、`weekly`）濾掉。bot token 與 Berth 對外網址存在 `settings` 表（`notify.set_bot_token`、`notify.set_berth_url`）。收件人解析：`recipients.subscribers(session, kind)`，加上送出時用 Jellyfin `UserViews` 檢查看不看得到那個媒體庫。

### C.3 個人 API token（brief §16.2）

**沒有實作。** brief §16.2「所有 API 需登入；未來 AI / MCP 用個人 API token」只是一句話。現況：

- 認證只有 cookie `berth_session`（`api/gate.py`；`models/auth.py` 的 `UserSession.token_hash` 是 session，不是 API token），搭配 `X-Requested-With` 標頭防跨站。
- 身分來源是 Jellyfin，`users` 是鏡射，沒有 token 表、沒有 `Authorization: Bearer` 處理（grep `Bearer|api_token|ApiToken` 於 `berth/` 僅命中 `adapters/tmdb`，是 TMDB 的）。
- 門禁 `access_of(method, path)` 只看方法與路徑，不看 token 範圍；沒有 scope 概念。

## D. 前端殼

| 項目 | 現況 | 檔案 |
| --- | --- | --- |
| 殼元件 | `AppShell({children})`：skip link、頁首（產品名、`NavLink` 九項、`Identity`＋`LanguageToggle`＋登出）、`<main id="main" tabIndex={-1}>`。只包 setup 完成後的頁面；`setup`、`login` 不套殼。**每個路由自己 `<AppShell><Page/></AppShell>` 包**，不是 layout route | `web/src/AppShell.tsx`、`web/src/routes.tsx` |
| 路由 | TanStack Router（code-based，`createRoute`）。根路由是 `Outlet`；門禁在各路由 `beforeLoad`（`requireSignedInPage`、`requireSession`、`wizardGate`）。設定頁用 `settingsRoute()` 工廠 | `web/src/routes.tsx`、`web/src/router.ts` |
| 路由表 | `/setup /login / /media/$mediaId /library /library/$libraryId /jobs /jobs/$hash /issues /review /rss /weekly /weekly/$reportId /health /settings /settings/{jellyfin,qbittorrent,routes,indexers,tmdb,notifications}` | `web/src/routes.tsx` |
| 頁面 | 每頁一個檔 | `web/src/pages/*Page.tsx` |
| UI 庫 | **沒有元件庫**：React 19、Tailwind v4（`@tailwindcss/vite`）、自刻元件（`controls.tsx` 的 `PrimaryButton`/`GhostButton`/`NAV_LINK`、`ConfirmPanel`、`Tile`、`QueueRow`…）；設計語彙在 `DESIGN.md` / `PRODUCT.md` | `web/src/components/`、`web/src/index.css` |
| 狀態管理 | `@tanstack/react-query` 5 管伺服器狀態＋元件本地 `useState`；沒有全域 store。登入者是 `meQueryOptions`；SSE 推播 `EventSource('/api/events/stream')` 用來 invalidate 查詢 | `web/src/api/auth.ts`、`web/src/api/events.ts` |
| i18n | `i18next` + `react-i18next`，**單一 TS 檔**：`zhHant` 與 `en` 兩個物件在同一檔，`Translations<T>` 型別強迫兩邊 key 樹相同；語言存 `localStorage['berth.language']`，同步初始化；`<html lang>` 驅動 CSS `:lang()`。後端不知道 UI 語言，TMDB 兩輪資料由 `i18n/displayRound.ts` 挑 | `web/src/i18n/resources.ts`、`web/src/i18n/index.ts`、`web/src/i18n/displayRound.ts`、`web/src/components/LanguageToggle.tsx` |
| API client | 手寫薄 fetch 封裝，前綴 `/api`，錯誤是 `ApiError(status, message, detail)`；`signedOut(error)`＝401。型別**全部由 OpenAPI 產生**：`pnpm gen:api` ＝ `berth openapi --output openapi.json && openapi-typescript openapi.json -o src/api/schema.d.ts`；`api/schemas.ts` 是唯一 import `schema.d.ts` 的檔案（`Schemas['…']`）。各領域一個 `api/<領域>.ts` | `web/src/api/client.ts`、`web/src/api/schema.d.ts`、`web/src/api/schemas.ts`、`web/package.json` |
| 開發 / 打包 | Vite 8，`/api` 代理到 `127.0.0.1:8383`；vitest（jsdom）、playwright e2e | `web/vite.config.ts`、`web/e2e/` |
| 側面板可掛的位置 | `AppShell` 的 `<main>` 外面（頁首以下）是自然的位置，因為所有已登入頁都經過它；`setup` 與 `login` 不經過，符合「精靈不開助理」。要換成 layout route 才不必每個路由重複包 | `web/src/AppShell.tsx` |

## 對 M5 的觀察

1. **沒有登錄表，只有標記。** `commands.py` 自己說「不收集、不查詢」。M5 要做的不是「補個裝飾器」，而是從零決定登錄資料長什麼樣（名稱、輸入 schema、結果型別、拒絕理由集合、誰能呼叫），並決定是用現有 `__berth_command__` 屬性掃描，還是裝飾器時註冊。標記只有 `effect` 與 `inverse` 兩格，不夠 AI 用。

2. **人工動作的主體全在豁免表裡。** 139 個未標命令包含 `plan_review.approve_plan`、`edit_items`、`reject_plan`、`issues.resolve_issue`／`ignore_issue`、`rematch.rematch_file`、`duplicates.decide_duplicate`、`jobs.retry_job`、`plan.replan_job`、`reimport.reimport_job`、`deletion.delete_job`、`routes.*`。「所有需要人工的地方都能交給 AI」這個目標，第一步就是把這十來個模組從 `BEFORE_M3` 拿掉並標完。這是機械工作量最大的一塊，但也是最先決定 AI 邊界的一塊（每個都要判斷 R/V/I）。

3. **`issues.resolve_issue` 是一個函式、十七種動作，可逆性差很大。** 同一個函式裡 `relook` 是 R 級、`delete_complete` / `replace_with_link` / `delete_orphan` 是不可逆（`ACTION_DELETES` 已經逐顆回答這件事）。登錄表若只能標「函式」層級，這個函式只能標最嚴的 I，AI 就永遠用不了 `relink`、`recheck`、`retry` 這些該自動做的。需要決定：拆成每個 `IssueAction` 一個命令，或讓標記可以依參數值取（例如 `effect_of(action)`）。`ISSUE_ACTIONS`（型別→動作）與 `ACTION_DELETES`（動作→是否刪）已是現成資料，可直接當登錄表來源。

4. **幾個已標的標記可疑**，M5 前要重審：
   - `review.undo_audit` 標 V 但拆鏈接＋刪帳本列＋Job 回 review，且註解明說「原樣再核准不行」；`confirm_audit` 的 inverse 指向它，但反方向（撤銷的反向）不存在。
   - `rss.release_item`、`rss.bind_series`、`rss.poll_feed`、`downloading.add_manual_download` 標 V，但都會**送出 torrent**，`unbind_series` 自己註明不收回已送的 Job。brief §14 的「在預算與磁碟門檻內補下載」才算可逆，這幾個沒有預算或磁碟閘。
   - `indexer.skip_indexers`、`search.remember_names` 的 inverse 指向自己（用同一個命令再按一次別的選項），`indexer.remove_indexer` 的 inverse 是 `apply_default_indexers`（不是對稱的反向）。
   - `notify.set_bot_token`、`indexer.apply_default_indexers`、`indexer.set_interface_login`、`qbittorrent.set_interface_login` 標 V，但 brief §14 寫「改設定與 Route 永遠要人」。標記與 brief 規則不一致，需要決定「設定類」要不要另立一級（例如工具表裡直接排除）。
   - `series_review.confirm_series`、`correct_series`、`rebuild_ledger` 標 V 但無 inverse；`confirm_series` 的 docstring 自己留了「M5 再決定要不要另立取消確認」。

5. **10 個標成 I 的命令都不是 AI 該呼叫的。** 它們是通知與巡檢的背景工作；`download_round` 甚至是 context manager，連 `commands_of` 都掃不到它。標記的 I 現在混了「對外發訊息」與「破壞性」兩種意思；登錄表需要把「系統內部、不暴露為工具」分出來（可能是第四個維度，不是第四個 Effect）。

6. **沒有單一 service 命令對應的人工點**（M5 要先補 service 或決定不碰）：
   - `stalled` 的 Job：Job 頁沒有重試鍵，`RETRYABLE` 只含 `submit_failed`、`import_failed`；只剩刪除。AI 對 `stalled` 無事可做。
   - `first_batch_stuck`、`feed_poll_failing`、`feed_backfill_failing`、`series_episodes_missing`、`series_episodes_collide`、`library_uses_tvdb`、`low_disk_space`：Issue 的動作表是空的，出路都在別頁或別的命令（`retry_job`、`correct_series`、搜缺的集、改 Feed 網址、`rematch_file`）。AI 任務要處理它們，得從 Issue 的 `subject` 導到另一個命令，而不是 `resolve_issue`。
   - 套用到 RSS Series 不是獨立命令：它在 `api/plans.py` 的 `put_items` 內分支呼叫 `series_review.correct_series_from_plan`；這個分支（edit＋correct）的組合邏輯在 API 層，要包進 service。
   - 「全部確認」第一批：系統版（`first_batch.confirm_by_batch`）與人工版（`series_review.confirm_series`）是兩個命令，帶不同參數。

7. **API 層做了命令語意的一部分。** `nudge()` 喚醒 importer / planner、`hub.publish`、`current_actor()`、`role`、將例外轉成 `HTTPException`、admin 判斷（`gate.py` 只看方法與路徑，連 `replannable` 的「review 狀態只有 admin」都得放進 service 內）都在 API 或門禁。AI 工具直接叫 service 會漏掉喚醒（只能等 60 秒的掃描補上）與權限檢查。需要一個統一的「命令執行器」承接 actor（含 `ai` 這個值）、角色、喚醒、錯誤轉換。

8. **拒絕理由有，但是每模組一套、沒共同基類。** 十個例外類別都是 `(reason: StrEnum, detail: str)`，這個形狀對 AI 很友善（封閉集合＋原文），可以不改語意，只加共同基類或協議；翻成 AI 工具的錯誤結果幾乎免費。`JobRejectedError`、`PublicUrlRejectedError` 兩個形狀略不同。

9. **沒有任何 AI 基礎建設**：沒有 SDK 依賴、沒有 `settings.ai`、沒有預算或記帳表、沒有 `ai` 這個 actor 的處理。`AiPlanner`／`NullAiPlanner` 是孤兒，M5 的「AI 任務」模型（資料包、允許的工具、預算、結果＝已處理或交給人）和它的單一 `propose` 簽名對不上，應直接重設計，不要沿用。

10. **對話與外部管道的缺口比 M5 大。** Discord adapter 只能發、不能收，沒有按鈕，沒有 gateway，沒有個人 API token、沒有 scope。M7 的「同一個 bot 收訊息、Proposal 帶按鈕、用個人 token 身分」是從零開始；M5/M6 做側面板時，認證仍是 session cookie，不要被 M7 的 token 設計綁住。AI 動作的 `actor` 在被代表使用者執行時要記「誰授權的」，現在 `events.actor` 只存一個字串。

11. **前端：側面板的自然落點是 `AppShell`，但它不是 layout route。** 每個路由自己包 `<AppShell>`，側面板跨頁保持開著的狀態（對話、串流）要放在 shell 之上，換頁不會重掛的位置，否則每換一頁對話就重置。要順便決定 `setup`、`login` 不顯示。i18n 是單一 TS 檔、型別強迫雙語，AI 的新文案走同一條；後端文字（AI 理由）要不要翻譯，沿用「事實存、句子在畫面上翻」（`ReasonCode`、`ItemReason`）還是例外，需要決定。API 型別由 OpenAPI 產生，新的 AI／Proposal 端點進 `schema.d.ts` 不需手寫型別。

12. **規模估計**：80 個已標命令裡 R 36 個可直接當 AI 讀取工具；真正需要判斷的是未標的 139 個，其中跟「人工點」直接有關的約 30 個（`jobs` 14、`issues` 5、`plan_review` 3、`rematch` 6、`duplicates` 1、`deletion` 3、`reimport` 1、`plan` 6、`claims` 6、`routes` 13 的一部分）。
